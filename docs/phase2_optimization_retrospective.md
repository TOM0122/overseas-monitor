# Phase 2 Optimization Retrospective

## Codex Mistakes To Avoid Repeating

1. Reported tasks as verified when the sandbox could not actually exercise the real path. Codex's environment cannot reach Keepa or DeepSeek (SSL/network blocked), so "compiles + fake-data passes" is not full verification for anything that hits Keepa or the LLM. Those steps must be confirmed with a real `--dry-run` on a machine with network access before a task is considered done.

2. Assumed `--dry-run` output reflects new code end-to-end. The analyzer reads from Supabase, so after adding the bestseller `brand`/`title` columns the dry-run still showed nulls — the stored rows predated the enrichment. New columns only surface after a real write populates them; verify enrichment against fresh data, not the last snapshot.

3. Left a blocking third-party call without a timeout. Keepa's `query` / `best_sellers_query` with `wait=True` can wait indefinitely (the library exposes no timeout argument). Any blocking call with internal wait/retry needs an external wall-clock guard so one stuck call cannot hang the whole pipeline.

4. Matched brand on the title only. Brands that appear in the URL slug but not the title (e.g. `diveblues-fan`) were dropped. Identity matching must consider every available signal — title and de-slugified URL — not just the most obvious field.

5. Trusted scraped free-text over computable values. hip2save took the page's textual "X% off" even when price and original price implied a different discount, producing wrong numbers. When a value can be computed from authoritative fields, prefer the computed value and treat scraped text as fallback only.

6. Shipped defensive helpers without covering degenerate inputs. The DingTalk truncation appends a fixed-size notice; when the configured byte limit was smaller than the notice itself the budget math broke. A helper that appends a marker must stay correct when the limit is smaller than the marker.

7. Replaced a code path without removing the old one. An obsolete Slickdeals parser (`find_result_nodes` / `parse_deal_node` and their private helpers) lingered long after `find_deal_links` / `parse_deal_link` superseded it. When you replace a path, delete the old one in the same change and grep for helpers it orphaned.

8. Risked tests depending on ignored files. `debug/` is gitignored, so any fixture a committed test relies on must be copied into a committed location (`tests/fixtures/`) — never read straight from `debug/`, or the test breaks on a clean checkout.
