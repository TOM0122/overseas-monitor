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
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

from scrapers.slickdeals_scraper import (
    CONFIG_DIR,
    PROJECT_ROOT,
    USER_AGENTS,
    KeywordConfig,
    is_relevant_to_category,
    load_brand_list,
    load_keyword_configs,
    normalize_spaces,
    parse_discount_pct,
    parse_money,
    request_with_retry,
)
from utils.db import get_repository

logger = logging.getLogger(__name__)

HIP2SAVE_BASE_URL = "https://hip2save.com"
SOURCE = "hip2save"
DISCOUNT_DISCREPANCY_PP = 10.0  # 文字折扣与计算折扣差异超过该百分点时记日志


@dataclass(frozen=True)
class Hip2SaveLink:
    url: str
    title: str | None = None


def run(*, limit: int = 20, dry_run: bool = False, debug_html: bool = False) -> list[dict]:
    load_dotenv()
    keyword_configs = load_keyword_configs(CONFIG_DIR / "keywords.txt")
    monitored_brands = load_brand_list(CONFIG_DIR / "brand_list.txt")
    session = requests.Session()

    all_deals: list[dict] = []
    for index, keyword_config in enumerate(keyword_configs, start=1):
        try:
            logger.info(
                "Scraping hip2save keyword=%r category=%s",
                keyword_config.keyword,
                keyword_config.category,
            )
            html = fetch_search_page(session, keyword_config.keyword)
            if debug_html:
                save_debug_html(keyword_config.keyword, html, "search")

            links = find_deal_links(html, keyword_config)
            keyword_deals: list[dict] = []
            for link in links:
                if len(keyword_deals) >= limit:
                    break
                try:
                    detail_html = fetch_url(session, link.url)
                    if debug_html and len(keyword_deals) == 0:
                        save_debug_html(keyword_config.keyword, detail_html, "detail")
                    deal = parse_detail_page(
                        detail_html,
                        link,
                        keyword_config,
                        monitored_brands,
                    )
                    if deal:
                        keyword_deals.append(deal)
                    time.sleep(random.uniform(2, 3))
                except Exception:
                    logger.exception("Failed to parse hip2save detail url=%s", link.url)

            all_deals.extend(keyword_deals)
            logger.info("Parsed %s hip2save deals for keyword=%r", len(keyword_deals), keyword_config.keyword)
        except Exception:
            logger.exception("Failed to scrape hip2save keyword=%r", keyword_config.keyword)

        if index < len(keyword_configs):
            time.sleep(random.uniform(2, 3))

    unique_deals = dedupe_deals(all_deals)
    logger.info("Collected %s unique hip2save deals", len(unique_deals))

    if dry_run:
        print(json.dumps(unique_deals, ensure_ascii=False, indent=2, default=str))
        return unique_deals

    get_repository().upsert_slickdeals_deals(unique_deals)
    return unique_deals


def fetch_search_page(session: requests.Session, keyword: str) -> str:
    return fetch_url(session, f"{HIP2SAVE_BASE_URL}/?s={quote_plus(keyword)}")


def fetch_url(session: requests.Session, url: str) -> str:
    response = request_with_retry(session, url, headers_factory=build_headers)
    return response.text


def build_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": HIP2SAVE_BASE_URL,
    }


def find_deal_links(html: str, keyword_config: KeywordConfig) -> list[Hip2SaveLink]:
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[Hip2SaveLink] = []
    for link in soup.select("article a[href], h2 a[href], h3 a[href], a[href*='hip2save.com/deals/'], a[href^='/deals/']"):
        href = str(link.get("href", "")).strip()
        url = urljoin(HIP2SAVE_BASE_URL, href)
        parsed = urlparse(url)
        if parsed.netloc and "hip2save.com" not in parsed.netloc:
            continue
        if "/deals/" not in parsed.path:
            continue
        # 跳过社交分享变体（?share=facebook/sms/custom-...），它们会重定向到站外。
        if "share" in parse_qs(parsed.query):
            continue
        # 规范化为 scheme://host/path，让 ?share= / #respond 等同一 deal 的变体合并为一次请求。
        canonical_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        title = normalize_spaces(link.get_text(" ", strip=True))
        if title and not is_relevant_to_category(title, canonical_url, keyword_config.category):
            continue
        if canonical_url in seen:
            continue
        seen.add(canonical_url)
        links.append(Hip2SaveLink(url=canonical_url, title=title or None))
    return links


def parse_detail_page(
    html: str,
    link: Hip2SaveLink,
    keyword_config: KeywordConfig,
    monitored_brands: list[str],
) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup) or link.title
    if not title:
        return None
    if not is_relevant_to_category(title, link.url, keyword_config.category):
        return None

    body_text = normalize_spaces(soup.get_text(" ", strip=True))
    price = extract_price(soup, body_text, title)
    original_price = extract_original_price(soup, body_text, price)
    discount_pct = extract_discount_pct(soup, body_text, price, original_price)
    posted_at = extract_posted_at(soup, body_text)
    scraped_at = datetime.now(timezone.utc)

    return {
        "deal_id": f"{SOURCE}:{stable_slug(link.url)}",
        "source": SOURCE,
        "title": title,
        "brand": match_monitored_brand(title, monitored_brands, url=link.url),
        "category": keyword_config.category,
        "price": price,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "url": link.url,
        "thumbs_up": None,
        "comments_count": extract_comments_count(soup, body_text),
        "posted_at": posted_at,
        "scraped_at": scraped_at.isoformat(),
    }


def extract_title(soup: BeautifulSoup) -> str | None:
    for selector in ("h1", ".entry-title", "article h1", "article h2"):
        node = soup.select_one(selector)
        if node:
            title = normalize_spaces(node.get_text(" ", strip=True))
            if title:
                return title
    meta = soup.select_one("meta[property='og:title']")
    if meta and meta.get("content"):
        return normalize_spaces(str(meta["content"]))
    return None


def extract_price(soup: BeautifulSoup, body_text: str, title: str | None = None) -> float | None:
    if title:
        price = price_from_title(title)
        if price is not None:
            return price
    for selector in ("[class*='price']", ".entry-content strong", "strong"):
        for node in soup.select(selector):
            value = parse_money(node.get_text(" ", strip=True))
            if value is not None:
                return value
    return parse_money(body_text)


def price_from_title(title: str) -> float | None:
    # 先去掉原价短语（如 "(Reg. $16)"），避免把原价当成售价读出来。
    cleaned = re.sub(
        r"\(?\s*(?:regularly|reg\.?|was|retail|orig(?:inally)?\.?)\s*\$\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?\s*\)?",
        " ",
        title,
        flags=re.IGNORECASE,
    )
    return parse_money(cleaned)


def extract_original_price(
    soup: BeautifulSoup,
    body_text: str,
    price: float | None,
) -> float | None:
    candidates: list[float] = []
    for selector in ("s", "strike", "del", "[class*='regular']", "[class*='retail']", "[class*='was']"):
        for node in soup.select(selector):
            value = parse_money(node.get_text(" ", strip=True))
            if value is not None:
                candidates.append(value)
    for match in re.finditer(r"(?:regularly|reg\.?|was|retail)\s*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", body_text, flags=re.IGNORECASE):
        candidates.append(float(match.group(1).replace(",", "")))
    for value in candidates:
        if price is None or value > price:
            return value
    return None


def _scan_textual_discount(soup: BeautifulSoup, body_text: str) -> float | None:
    for selector in ("[class*='discount']", "[class*='save']", "[class*='off']"):
        for node in soup.select(selector):
            value = parse_discount_pct(node.get_text(" ", strip=True))
            if value is not None:
                return value
    return parse_discount_pct(body_text)


def extract_discount_pct(
    soup: BeautifulSoup,
    body_text: str,
    price: float | None,
    original_price: float | None,
) -> float | None:
    computed = None
    if price is not None and original_price and original_price > price:
        computed = round((original_price - price) / original_price * 100, 2)
    if computed is not None:
        textual = _scan_textual_discount(soup, body_text)
        if textual is not None and abs(textual - computed) > DISCOUNT_DISCREPANCY_PP:
            logger.info(
                "hip2save discount mismatch: textual=%.1f computed=%.1f (price=%s original=%s); using computed",
                textual,
                computed,
                price,
                original_price,
            )
        return computed
    return _scan_textual_discount(soup, body_text)


def extract_comments_count(soup: BeautifulSoup, body_text: str) -> int | None:
    for selector in ("[class*='comment-count']", "[class*='comments-count']", "a[href*='#comments']"):
        node = soup.select_one(selector)
        if node:
            value = parse_count(node.get_text(" ", strip=True))
            if value is not None:
                return value
    match = re.search(r"([0-9][0-9,]*)\s+comments?", body_text, flags=re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def extract_posted_at(soup: BeautifulSoup, body_text: str) -> str | None:
    for selector in ("time", "[datetime]", "[class*='date']", "[class*='posted']"):
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("datetime") or node.get("title") or node.get_text(" ", strip=True)
        parsed = parse_posted_at(str(value))
        if parsed:
            return parsed.isoformat()
    parsed = parse_posted_at(body_text)
    return parsed.isoformat() if parsed else None


def parse_posted_at(text: str) -> datetime | None:
    cleaned = normalize_spaces(text)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(cleaned[:30], fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    match = re.search(r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})", cleaned)
    if match:
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(match.group(1), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def parse_count(text: str) -> int | None:
    match = re.search(r"[0-9][0-9,]*", text)
    return int(match.group(0).replace(",", "")) if match else None


def stable_slug(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.split("/")[-1] if path else re.sub(r"\W+", "-", url)
    return slug[:160]


def match_monitored_brand(title: str, monitored_brands: list[str], url: str | None = None) -> str | None:
    haystacks = [title]
    if url:
        # slug 形如 /deals/diveblues-fan/ -> "deals diveblues fan"，让品牌词可被 \b 命中。
        slug_text = urlparse(url).path.replace("/", " ").replace("-", " ")
        haystacks.append(slug_text)
    for brand in monitored_brands:
        for haystack in haystacks:
            if re.search(rf"\b{re.escape(brand)}\b", haystack, flags=re.IGNORECASE):
                return brand
    return None


def dedupe_deals(deals: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for deal in deals:
        deal_id = deal.get("deal_id")
        if deal_id:
            deduped[str(deal_id)] = deal
    return list(deduped.values())


def save_debug_html(keyword: str, html: str, suffix: str) -> Path:
    debug_dir = PROJECT_ROOT / "debug" / "hip2save"
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_keyword = re.sub(r"[^A-Za-z0-9_-]+", "-", keyword).strip("-").lower()
    path = debug_dir / f"{timestamp}-{safe_keyword}-{suffix}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Saved hip2save debug HTML to %s", path)
    return path


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape hip2save search results")
    parser.add_argument("--limit", type=int, default=20, help="Max deals per keyword")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing DB")
    parser.add_argument("--debug-html", action="store_true", help="Save returned HTML under debug/hip2save")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    if args.limit <= 0:
        raise ValueError("--limit must be greater than 0")
    run(limit=args.limit, dry_run=args.dry_run, debug_html=args.debug_html)


if __name__ == "__main__":
    main()
