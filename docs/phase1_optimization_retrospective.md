# Phase 1 Optimization Retrospective

## Codex Mistakes To Avoid Repeating

1. Treated early Slickdeals parser output as acceptable before proving every key field against raw HTML. The correct workflow is to save HTML, locate the exact DOM for title, price, thumbs, comments, and posted time, then update selectors.

2. Let stale Supabase rows confuse report validation. `--dry-run` only proves parser output; it does not refresh stored data. Any report validation that depends on Supabase must be preceded by a real write after parser fixes.

3. Initially mixed Amazon BSR meanings. Keepa generic `SALES` rank is not necessarily the `Best Sellers in Personal Fans` category rank. BSR reporting must always carry `bsr_category_id` and compare only records with the same category id.

4. Allowed old product categories and abnormal prices to leak into the report payload. Analyzer inputs must filter to the intended category and sanitize values before the LLM sees them.

5. Added new data sources before fully documenting schema migration impact. Any new table or column must ship with SQL, README instructions, and a local verification command in the same change.
