from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

from utils.db import get_repository

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
SLICKDEALS_BASE_URL = "https://slickdeals.net"
SEARCH_URL = f"{SLICKDEALS_BASE_URL}/newsearch.php"
VALID_CATEGORIES = {"fan", "hand_warmer"}
SOURCE = "slickdeals"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


@dataclass(frozen=True)
class KeywordConfig:
    keyword: str
    category: str


def run(*, limit: int = 20, dry_run: bool = False, debug_html: bool = False) -> list[dict]:
    """Scrape Slickdeals search results and optionally upsert them to Supabase."""
    load_dotenv()
    keyword_configs = load_keyword_configs(CONFIG_DIR / "keywords.txt")
    monitored_brands = load_brand_list(CONFIG_DIR / "brand_list.txt")
    max_post_age_days = int(os.getenv("SLICKDEALS_MAX_POST_AGE_DAYS", "30"))
    session = requests.Session()

    all_deals: list[dict] = []
    for index, keyword_config in enumerate(keyword_configs, start=1):
        try:
            logger.info(
                "Scraping Slickdeals keyword=%r category=%s",
                keyword_config.keyword,
                keyword_config.category,
            )
            html = fetch_search_page(session, keyword_config.keyword)
            if debug_html:
                save_debug_html(keyword_config.keyword, html, "search")
            deals = parse_search_results(
                html=html,
                keyword_config=keyword_config,
                monitored_brands=monitored_brands,
                limit=limit,
                max_post_age_days=max_post_age_days,
            )

            if not deals:
                logger.warning(
                    "No deals parsed for keyword=%r. TODO: fallback to Playwright when static parsing fails.",
                    keyword_config.keyword,
                )
                if debug_html:
                    save_debug_html(keyword_config.keyword, html, "no-deals")

            all_deals.extend(deals)
            logger.info("Parsed %s deals for keyword=%r", len(deals), keyword_config.keyword)
        except requests.HTTPError as exc:
            logger.exception("Failed to scrape keyword=%r", keyword_config.keyword)
            if debug_html and exc.response is not None:
                save_debug_html(keyword_config.keyword, exc.response.text, f"http-{exc.response.status_code}")
        except Exception:
            logger.exception("Failed to scrape keyword=%r", keyword_config.keyword)

        if index < len(keyword_configs):
            sleep_seconds = random.uniform(2, 3)
            logger.info("Sleeping %.1f seconds before next request", sleep_seconds)
            time.sleep(sleep_seconds)

    unique_deals = dedupe_deals(all_deals)
    logger.info("Collected %s unique Slickdeals deals", len(unique_deals))

    if dry_run:
        print(json.dumps(unique_deals, ensure_ascii=False, indent=2, default=str))
        return unique_deals

    repository = get_repository()
    repository.upsert_slickdeals_deals(unique_deals)
    return unique_deals


def load_keyword_configs(path: Path) -> list[KeywordConfig]:
    configs: list[KeywordConfig] = []
    for line_number, line in read_non_comment_lines(path):
        if "|" not in line:
            raise ValueError(f"{path}:{line_number} must use format: keyword | category")

        keyword, category = [part.strip() for part in line.split("|", maxsplit=1)]
        if not keyword:
            raise ValueError(f"{path}:{line_number} keyword is empty")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"{path}:{line_number} category must be one of {sorted(VALID_CATEGORIES)}"
            )
        configs.append(KeywordConfig(keyword=keyword, category=category))

    if not configs:
        raise ValueError(f"No keywords found in {path}")
    return configs


def load_brand_list(path: Path) -> list[str]:
    return [line for _, line in read_non_comment_lines(path)]


def read_non_comment_lines(path: Path) -> Iterable[tuple[int, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            yield line_number, line


def fetch_search_page(session: requests.Session, keyword: str) -> str:
    warm_up_session(session)
    params = {
        "q": keyword,
        "src": "SearchBarV2",
        "isUserSearch": "1",
        "hideexpired": "1",
        "sort": "rating",
    }
    response = request_with_retry(session, SEARCH_URL, headers_factory=build_headers, params=params)
    return response.text


def warm_up_session(session: requests.Session) -> None:
    if session.cookies:
        return

    try:
        session.get(SLICKDEALS_BASE_URL, headers=build_headers(), timeout=20)
    except requests.RequestException as exc:
        logger.warning("Slickdeals homepage warm-up failed: %s", exc)


def build_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": f"{SLICKDEALS_BASE_URL}/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }


def _backoff_sleep(base_backoff: float, attempt: int) -> None:
    delay = base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
    logger.info("Backing off %.1fs before retry", delay)
    time.sleep(delay)


def request_with_retry(
    session: requests.Session,
    url: str,
    *,
    headers_factory,
    params: dict | None = None,
    max_retries: int | None = None,
    base_backoff: float | None = None,
    timeout: int = 20,
) -> requests.Response:
    """GET with exponential backoff and jitter for retryable HTTP/network errors."""
    max_retries = max_retries if max_retries is not None else int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
    base_backoff = base_backoff if base_backoff is not None else float(os.getenv("SCRAPER_BACKOFF_SECONDS", "3"))
    last_response: requests.Response | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, headers=headers_factory(), timeout=timeout)
            last_response = response
            if response.status_code in (403, 429) or response.status_code >= 500:
                logger.warning(
                    "Retryable HTTP %s url=%s attempt=%s/%s",
                    response.status_code,
                    url,
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    _backoff_sleep(base_backoff, attempt)
                    continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Request error url=%s attempt=%s/%s: %s", url, attempt, max_retries, exc)
            if attempt >= max_retries:
                raise
            _backoff_sleep(base_backoff, attempt)
    assert last_response is not None
    last_response.raise_for_status()
    return last_response


def parse_search_results(
    *,
    html: str,
    keyword_config: KeywordConfig,
    monitored_brands: list[str],
    limit: int,
    max_post_age_days: int = 30,
) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    deal_links = find_deal_links(soup)

    deals: list[dict] = []
    for link in deal_links:
        deal = parse_deal_link(
            link,
            keyword_config,
            monitored_brands,
            max_post_age_days=max_post_age_days,
        )
        if not deal:
            continue
        deals.append(deal)
        if len(deals) >= limit:
            break

    return deals


def find_deal_links(soup: BeautifulSoup) -> list[Tag]:
    seen_thread_ids: set[str] = set()
    links: list[Tag] = []

    for link in soup.select("a[href*='/f/']"):
        href = str(link.get("href", "")).strip()
        thread_id = extract_thread_id_from_url(href)
        if not thread_id or thread_id in seen_thread_ids:
            continue
        if is_comment_or_post_url(href):
            continue

        title = normalize_spaces(link.get_text(" ", strip=True))
        if not looks_like_deal_title(title, href):
            continue

        seen_thread_ids.add(thread_id)
        links.append(link)

    return links


def parse_deal_link(
    link: Tag,
    keyword_config: KeywordConfig,
    monitored_brands: list[str],
    max_post_age_days: int = 30,
) -> dict | None:
    href = str(link.get("href", "")).strip()
    deal_id = extract_thread_id_from_url(href)
    if not deal_id:
        return None

    url = urljoin(SLICKDEALS_BASE_URL, href)
    title = normalize_spaces(link.get_text(" ", strip=True)) or title_from_deal_url(url)
    if not title:
        return None
    if not is_relevant_to_category(title, url, keyword_config.category):
        return None

    container = nearest_deal_container(link)
    if is_expired_deal(container, url):
        logger.info("Skipping expired Slickdeals deal_id=%s title=%r", deal_id, title)
        return None

    price = extract_price(container) if container else None
    if price is None:
        price = parse_money(title) or parse_price_from_deal_url(url)

    original_price = extract_original_price(container, price) if container else None
    discount_pct = extract_discount_pct(container, price, original_price) if container else None

    scraped_at = datetime.now(timezone.utc)
    posted_at = extract_posted_at(container, scraped_at) if container else None
    if is_too_old(posted_at, scraped_at, max_post_age_days):
        logger.info(
            "Skipping stale Slickdeals deal_id=%s posted_at=%s title=%r",
            deal_id,
            posted_at,
            title,
        )
        return None

    return {
        "deal_id": deal_id,
        "source": SOURCE,
        "title": title,
        "brand": extract_brand(title, monitored_brands),
        "category": keyword_config.category,
        "price": price,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "url": url,
        "thumbs_up": extract_thumbs_up(container) if container else 0,
        "comments_count": extract_comments_count(container) if container else 0,
        "posted_at": posted_at,
        "scraped_at": scraped_at.isoformat(),
    }


def extract_price(node: Tag) -> float | None:
    selectors = [
        ".dealCardListView__finalPrice",
        ".price",
        ".dealPrice",
        ".itemPrice",
        "[class*='price']",
    ]
    return extract_first_money_value(node, selectors)


def extract_original_price(node: Tag, current_price: float | None) -> float | None:
    selectors = [
        ".dealCardListView__listPrice",
        ".originalPrice",
        ".oldListPrice",
        ".listPrice",
        ".wasPrice",
        "s",
        "strike",
    ]
    original_price = extract_first_money_value(node, selectors)
    if original_price is not None and original_price != current_price:
        return original_price
    return None


def extract_discount_pct(
    node: Tag,
    price: float | None,
    original_price: float | None,
) -> float | None:
    for selector in (".dealCardListView__savings", ".savings", "[class*='savings']"):
        selected = node.select_one(selector)
        if not selected:
            continue
        value = parse_discount_pct(selected.get_text(" ", strip=True))
        if value is not None:
            return value

    text = node.get_text(" ", strip=True)
    value = parse_discount_pct(text)
    if value is not None:
        return value

    if price is not None and original_price and original_price > price:
        return round((original_price - price) / original_price * 100, 2)
    return None


def parse_discount_pct(text: str) -> float | None:
    match = re.search(r"(\d{1,3})\s*%\s*(?:off|discount)?", text, flags=re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return value if 0 <= value <= 100 else None


def extract_first_money_value(node: Tag, selectors: list[str]) -> float | None:
    for selector in selectors:
        for selected in node.select(selector):
            price = parse_money(selected.get_text(" ", strip=True))
            if price is not None:
                return price
    return parse_money(node.get_text(" ", strip=True))


def parse_money(text: str) -> float | None:
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def parse_price_from_deal_url(url: str) -> float | None:
    path = urlparse(url).path
    slug_match = re.search(r"/f/\d+[-/](.+)$", path)
    if not slug_match:
        return None

    slug = slug_match.group(1).lower()
    # Common Slickdeals slugs encode prices as "-15-99-free-shipping" or "-10-free-shipping".
    price_match = re.search(
        r"(?:^|-)(\d{1,4})(?:-(\d{2}))?(?:-(?:free|walmart|amazon|shipping|store|digital|after|via|for|at)|$)",
        slug,
    )
    if not price_match:
        return None

    dollars = price_match.group(1)
    cents = price_match.group(2)
    return float(f"{dollars}.{cents or '00'}")


def extract_thumbs_up(node: Tag) -> int | None:
    selectors = [
        ".dealCardListView__voteCount",
        ".ratingNum",
        ".thumbsup",
        ".voteCount",
        "[class*='rating']",
        "[class*='vote']",
    ]
    value = extract_first_int(node, selectors)
    return value if value is not None else 0


def extract_comments_count(node: Tag) -> int | None:
    selectors = [
        ".dealCardListView__commentsCount",
        ".commentCount",
        ".comments",
        "[class*='comment']",
    ]
    value = extract_first_int(node, selectors)
    return value if value is not None else 0


def extract_first_int(node: Tag, selectors: list[str]) -> int | None:
    for selector in selectors:
        for selected in node.select(selector):
            value = parse_int(selected.get_text(" ", strip=True))
            if value is not None:
                return value
    return None


def parse_int(text: str) -> int | None:
    match = re.search(r"[+-]?\d[\d,]*", text)
    if not match:
        return None
    return int(match.group(0).replace(",", "").replace("+", ""))


def extract_posted_at(node: Tag, now_utc: datetime) -> str | None:
    selectors = [
        "time",
        ".slickdealsTimestamp",
        ".date",
        ".posted",
        ".timeAgo",
        "[class*='time']",
        "[class*='date']",
    ]
    for selector in selectors:
        for selected in node.select(selector):
            datetime_value = selected.get("datetime") or selected.get("title")
            parsed = parse_posted_at(str(datetime_value), now_utc) if datetime_value else None
            if parsed:
                return parsed.isoformat()

            parsed = parse_posted_at(selected.get_text(" ", strip=True), now_utc)
            if parsed:
                return parsed.isoformat()
    return None


def parse_posted_at(text: str, now_utc: datetime) -> datetime | None:
    normalized = normalize_spaces(text).lower()
    if not normalized:
        return None

    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%m/%d/%Y %I:%M %p",
        "%b %d, %Y %I:%M %p",
    ):
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    relative_match = re.search(r"(\d+)\s*(minute|minutes|min|hour|hours|day|days)\s*ago", normalized)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        if unit.startswith("min"):
            return now_utc - timedelta(minutes=amount)
        if unit.startswith("hour"):
            return now_utc - timedelta(hours=amount)
        if unit.startswith("day"):
            return now_utc - timedelta(days=amount)

    if "yesterday" in normalized:
        return now_utc - timedelta(days=1)
    if "today" in normalized or "just now" in normalized:
        return now_utc
    return None


def extract_brand(title: str, monitored_brands: list[str]) -> str | None:
    for brand in monitored_brands:
        pattern = rf"\b{re.escape(brand)}\b"
        if re.search(pattern, title, flags=re.IGNORECASE):
            return brand
    return infer_brand_from_title(title)


def dedupe_deals(deals: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for deal in deals:
        deal_id = deal.get("deal_id")
        if not deal_id:
            continue
        deduped[str(deal_id)] = deal
    return list(deduped.values())


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_thread_id_from_url(url: str) -> str | None:
    parsed_url = urlparse(url)
    path_match = re.search(r"/f/(\d+)", parsed_url.path)
    return path_match.group(1) if path_match else None


def is_comment_or_post_url(url: str) -> bool:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return bool(query_params.get("p") or parsed_url.fragment.startswith("post"))


def looks_like_deal_title(title: str, href: str) -> bool:
    if len(title) < 12:
        return False
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,30}", title):
        return False
    return bool(extract_thread_id_from_url(href))


def title_from_deal_url(url: str) -> str | None:
    slug_match = re.search(r"/f/\d+[-/](.+)$", urlparse(url).path)
    if not slug_match:
        return None
    slug = re.sub(r"-\d+(?:-\d{2})?-free-shipping.*$", "", slug_match.group(1))
    return normalize_spaces(slug.replace("-", " ")).title()


def nearest_deal_container(link: Tag) -> Tag:
    card = link.find_parent(class_=re.compile(r"\bdealCardListView\b"))
    if isinstance(card, Tag):
        return card

    feed_item = link.find_parent(class_=re.compile(r"\bsearchPageGrid__feedItem\b"))
    if isinstance(feed_item, Tag):
        return feed_item

    current = link
    for _ in range(6):
        parent = current.parent
        if not isinstance(parent, Tag):
            break
        if parent.name in {"article", "li"}:
            return parent
        class_text = " ".join(str(value) for value in parent.get("class", []))
        if re.search(r"(deal|result|thread)", class_text, flags=re.IGNORECASE):
            return parent
        current = parent
    return link.parent if isinstance(link.parent, Tag) else link


def is_expired_deal(container: Tag | None, url: str) -> bool:
    if container is None:
        return False
    class_text = " ".join(str(value) for value in container.get("class", []))
    if re.search(r"\b(expired|dead)\b", class_text, flags=re.IGNORECASE):
        return True

    text = normalize_spaces(container.get_text(" ", strip=True)).lower()
    if re.search(r"\b(expired|dead deal)\b", text):
        return True

    query = parse_qs(urlparse(url).query)
    attrsrc = " ".join(query.get("attrsrc", []))
    return "Thread:Expired:True" in attrsrc


def is_too_old(posted_at: str | None, now_utc: datetime, max_post_age_days: int) -> bool:
    if max_post_age_days <= 0:
        return False
    if not posted_at:
        logger.warning("Slickdeals deal missing posted_at; keeping because age cannot be verified")
        return False

    parsed = parse_datetime(posted_at)
    if not parsed:
        logger.warning("Slickdeals deal has unparsable posted_at=%r; keeping", posted_at)
        return False
    return parsed < now_utc - timedelta(days=max_post_age_days)


def parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# "fan"/"fans" 作为粉丝/受众/活动名出现，而非产品时的已知短语。
_FAN_NON_PRODUCT_PATTERNS = (
    r"fans?[-\s]?favorites?",   # Fan-Favorite / Fan Favorites
    r"fans?[-\s]?fest",         # Fan Fest
    r"fans?[-\s]?club",         # Fan Club
    r"fans?[-\s]?cave",         # Fan Cave
    r"fans?[-\s]?gear",         # Fan Gear
    r"fans?[-\s]?mail",         # Fan Mail
    r"fan[-\s]?fiction",        # Fan Fiction
    r"fans\s*:",                # "Dunkin' Fans:"（复数+冒号，典型的「面向受众」表达）
    # 「为某受众群体」的表达，如 "...for Soccer Fans"、"for true sports fans"
    r"for[-\s]+(?:[a-z'’\-]+[-\s]+){0,3}fans?\b",
    # 常见受众限定词 + fans（球迷/乐迷/影迷等）
    r"(?:soccer|football|sports?|baseball|basketball|hockey|nfl|nba|mlb|music|movie|concert|anime|k-?pop)[-\s]+fans?",
)


# 玩具 / 一元区合集等明显非「个人手持风扇」的语境，命中即判定不相关。
_FAN_HARD_EXCLUDE_PATTERNS = (
    r"\bbullseye\b",
    r"\bplayground\b",
    r"\bblasters?\b",
    r"bubble[-\s]?fans?",
    r"bubble[-\s]?machine",
    r"dollar[-\s]?spot",
)


def is_relevant_to_category(title: str, url: str, category: str) -> bool:
    text = f"{title} {urlparse(url).path}".lower()
    if category == "fan":
        # 先硬排除玩具/一元区合集等非产品语境。
        if any(re.search(pattern, text) for pattern in _FAN_HARD_EXCLUDE_PATTERNS):
            return False
        # 再剔除非产品用法，要求仍存在真正的 fan 词。
        stripped = text
        for pattern in _FAN_NON_PRODUCT_PATTERNS:
            stripped = re.sub(pattern, " ", stripped)
        return bool(re.search(r"\bfans?\b", stripped))
    if category == "hand_warmer":
        return bool(re.search(r"\bhand[-\s]?warmers?\b", text))
    return True


def infer_brand_from_title(title: str) -> str | None:
    candidate = title
    candidate = re.sub(r"^(prime members?|select [^:]+ locations?|amazon|walmart|costco):\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^\d+\s*[- ]?\s*(pack|pk)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^[0-9]+(?:\.[0-9]+)?[\"”]?\s+", "", candidate)
    candidate = re.sub(r"^(new|hot|deal|sale|various|assorted)\s+", "", candidate, flags=re.IGNORECASE)
    match = re.match(r"([A-Z][A-Za-z0-9&'+.-]{1,})", candidate.strip())
    if not match:
        return None
    return match.group(1)


def save_debug_html(keyword: str, html: str, suffix: str) -> Path:
    debug_dir = PROJECT_ROOT / "debug" / "slickdeals"
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_keyword = re.sub(r"[^A-Za-z0-9_-]+", "-", keyword).strip("-").lower()
    path = debug_dir / f"{timestamp}-{safe_keyword}-{suffix}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Saved debug HTML to %s", path)
    return path


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Slickdeals search results")
    parser.add_argument("--limit", type=int, default=20, help="Max deals per keyword")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing DB")
    parser.add_argument(
        "--debug-html",
        action="store_true",
        help="Save returned HTML pages under debug/slickdeals for parser troubleshooting",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    if args.limit <= 0:
        raise ValueError("--limit must be greater than 0")
    run(limit=args.limit, dry_run=args.dry_run, debug_html=args.debug_html)


if __name__ == "__main__":
    main()
