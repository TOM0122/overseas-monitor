# Parser Accuracy Report - 2026-05-29

## Scope

This is a one-time parser accuracy check for:

- `scrapers/slickdeals_scraper.py`
- `scrapers/hip2save_scraper.py`

Commands attempted:

```bash
python -m scrapers.slickdeals_scraper --limit 5 --dry-run --debug-html
python -m scrapers.hip2save_scraper --limit 5 --dry-run --debug-html
```

Result: the Codex runtime could not resolve `slickdeals.net` or `hip2save.com` (`NameResolutionError: nodename nor servname provided`). Escalated network execution was requested twice and timed out. Therefore, no fresh online sample could be captured in this runtime.

Fallback used for this report:

- Slickdeals: existing same-day fixture `debug/slickdeals/20260529T033056Z-handheld-fan-search.html`
- hip2save: existing same-day fixtures under `debug/hip2save/20260529T0254*`

No database writes were performed.

## Slickdeals Field Accuracy

Validated sample: first 5 parsed deals from `debug/slickdeals/20260529T033056Z-handheld-fan-search.html`.

Representative parsed row:

- Deal ID: `19560666`
- Title: `Diveblues 100-Speed Rechargeable Foldable Handheld Turbo Fan`
- Price: `$9.95`
- Original price: `$20`
- Thumbs up: `107`
- Comments: `21`
- Posted at: `May 25, 2026 10:48 PM`

Representative DOM snippets:

```html
<a class="dealCardListView__title dealCardListView__title--underline" title="Diveblues 100-Speed Rechargeable Foldable Handheld Turbo Fan">...</a>
<span class="dealCardListView__finalPrice" title="from $9.95">from $9.95</span>
<span class="dealCardListView__listPrice" title="$20">$20</span>
<span class="dealCardListView__voteCount">+107</span>
<span class="dealCardListView__commentsCount">21</span>
<span class="slickdealsTimestamp" title="May 25, 2026 10:48 PM">May 25, 2026 10:48 PM</span>
```

| Field | Status | Notes |
|---|---:|---|
| `title` | ✅ | Matches `.dealCardListView__title`; no username/comment noise in the checked rows. |
| `url` | ✅ | Points to the corresponding `/f/{deal_id}-...` detail URL. |
| `price` | ✅ | Matches `.dealCardListView__finalPrice`; no year/mAh/comment-number pollution in checked rows. |
| `original_price` | ✅ | Matches `.dealCardListView__listPrice`; null when no list price is shown. |
| `discount_pct` | ✅ | Uses `.dealCardListView__savings` when present, otherwise correctly computes from price and original price. |
| `thumbs_up` | ✅ | Matches `.dealCardListView__voteCount`; `+107` parsed as `107`. |
| `comments_count` | ✅ | Matches `.dealCardListView__commentsCount`. |
| `posted_at` | ✅ | Uses `.slickdealsTimestamp[title]`; parsed as UTC. |
| `brand` | ✅ | Monitored brands use config spelling; unknown brands are reasonably inferred from title start. |
| `category` | ✅ | Fan deals are retained; sampled products are actual fan products. |

Conclusion: Slickdeals parser is usable for the 3-7 day test period.

## hip2save Field Accuracy

Fresh online validation could not be completed because the runtime could not resolve `hip2save.com`.

Existing fixture result before the category fix:

- All checked hip2save detail fixtures pointed to the same non-fan article:
  `Chick-fil-A’s Summer Menu Drops on June 8th (w/ Fan-Favorite Peach Milkshake!)`
- The old category filter treated `Fan-Favorite` as a fan product because it matched `\bfans?\b`.
- Parsed output incorrectly produced a `fan` deal with `price=1.0` from unrelated page text.

Problem DOM snippet:

```html
<h1 class="entry-title">Chick-fil-A’s Summer Menu Drops on June 8th (w/ Fan-Favorite Peach Milkshake!)</h1>
<meta property="og:title" content="Chick-fil-A's Summer Menu Drops on June 8th (w/ Fan-Favorite Peach Milkshake!)">
```

Fix applied:

- `scrapers/slickdeals_scraper.py::is_relevant_to_category`
- Changed fan category matching from `\bfans?\b` to `\bfans?\b(?![-\s]?favorites?)`.
- This shared helper is used by both Slickdeals and hip2save.

Post-fix offline verification:

- `Fan-Favorite Peach Milkshake` is no longer treated as category `fan`.
- Real product phrase `Diveblues Handheld Turbo Fan` still matches category `fan`.
- Existing hip2save false-positive fixtures now return `None` instead of invalid deals.

| Field | Status | Notes |
|---|---:|---|
| `title` | ⚠️ | Extraction works on the non-fan fixture, but no valid hip2save fan deal was available for field-level validation. |
| `url` | ⚠️ | Search/detail link extraction could not be validated on a valid fan deal in this runtime. |
| `price` | ⚠️ | The previous invalid `price=1.0` was caused by category misclassification, not a valid fan deal price. Needs validation on a real hip2save fan deal. |
| `original_price` | ⚠️ | Regex escaping bug was fixed earlier; no valid fan fixture available to confirm live behavior. |
| `discount_pct` | ⚠️ | No valid fan fixture available to confirm live behavior. |
| `thumbs_up` | ✅ | hip2save has no Slickdeals-style thumbs; parser returns `null`. |
| `comments_count` | ⚠️ | Regex escaping bug was fixed earlier; no valid fan fixture available to confirm live behavior. |
| `posted_at` | ⚠️ | Existing non-fan fixture parsed date, but valid fan deal behavior remains unverified. |
| `brand` | ⚠️ | Works mechanically, but not validated on a real hip2save fan deal. |
| `category` | ✅ | False positive `Fan-Favorite` case is fixed and now rejected. |

Conclusion: hip2save should remain optional during the 3-7 day test period. It is safe from the observed `fan-favorite` false positive, but its detailed fields still need a fresh live fan-deal sample before using hip2save data as a core reporting source.

## Overall Conclusion

- Slickdeals: usable for test-period reporting.
- hip2save: optional only; category false positive fixed, but full field accuracy could not be proven due network/DNS limits and lack of a valid fan fixture.
- No Supabase data was written.

Recommended local follow-up on a machine with normal network access:

```bash
python -m scrapers.hip2save_scraper --limit 5 --dry-run --debug-html
```

If this produces valid fan deals, repeat the field table above against the new `debug/hip2save/*` files.
