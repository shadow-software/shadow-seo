# Plan: Product / Merchant schema validator (shadow-seo)

**Why:** `analyze_schema.py` only checks type presence + JSON parse. GSC Product/Merchant/Review warnings (e.g. nested `itemReviewed`, missing Offer fields) slip through. All Shadow storefronts emit Product schema — this must live here, not in dabdash.com.

**Trigger incident:** Maritime Smoke GSC 2026-10-10 — nested Review `itemReviewed` under Product. DabDash fix: `d983bcbbf` (local master; deploy separately).

---

## Do not rely on Google Rich Results Test API

- No public RRT API for raw JSON-LD / staging.
- Closest official API: **GSC URL Inspection** (`scripts/gsc_inspect.py`) — indexed URLs only, quota-limited, verified property required. Use as **optional post-deploy spot-check**, not CI gate.
- schema.org validator is human-oriented; not a build dependency.

**Approach:** local deterministic ruleset mirroring Google’s documented Product snippet + Merchant listings + Review nesting rules, plus optional GSC inspect for live properties.

---

## Implementation (phased)

### P0 — Local Product/Merchant contract (must ship)

1. **`scripts/validate_product_schema.py`** (pure, no network)
   - Input: JSON-LD object / `@graph` / HTML string / URL (fetch via existing `fetch_page` / session helpers).
   - Walk Product (and AggregateOffer / Offer / nested Review / AggregateRating).
   - Emit structured findings: `{severity, code, path, message}` with severities `error` | `warning`.

2. **Rules to encode first** (from real GSC mails + Google docs)

   | Code | Severity | Rule |
   |---|---|---|
   | `product.missing_offers_or_rating` | error | Product needs `offers` OR `aggregateRating` OR `review` |
   | `product.missing_image` | error | `image` present, absolute URL(s) |
   | `product.missing_name` | error | |
   | `offer.missing_price` | error | Offer/AggregateOffer price fields |
   | `offer.missing_currency` | error | |
   | `offer.missing_availability` | warning→error if snippet-critical | |
   | `offer.missing_shippingDetails` | warning | Merchant listings |
   | `offer.missing_return_policy` | warning | `hasMerchantReturnPolicy` |
   | `offer.missing_validFrom` | warning | |
   | `offer.missing_priceValidUntil` | warning | |
   | `product.missing_brand_or_gtin` | warning | brand and/or gtin/mpn/sku |
   | `review.nested_itemReviewed` | error | Review nested under Product/SoftwareApplication must **omit** `itemReviewed` |
   | `review.standalone_needs_itemReviewed` | warning | Top-level Review (not nested) should have `itemReviewed` |

3. **Wire into `analyze_schema.py`**
   - After type detection, if Product present → run validator; fold findings into `issues` / `validation` / score.
   - Keep homepage-type checks unchanged.

4. **Product URL sampling in site audits**
   - From sitemap or `/products` links, sample N product URLs (default 5–10) when `page_type`/audit is site-wide ecommerce.
   - Fail audit if any sampled product has `error` severity.
   - Hook: `seo-ecommerce` + `seo-schema` + `seo-triple-audit` / `ss-seo-audit` path.

5. **Tests** (`tests/test_validate_product_schema.py`)
   - Fixtures: good Product+Offer; nested `itemReviewed` (expect error); missing shippingDetails (warning); Product with neither offers nor rating (error); AggregateOffer shape.
   - Golden HTML snippets from Maritime-like JSON-LD (anonymized).

6. **Docs**
   - Update `skills/seo-schema/SKILL.md` Validation section: “run `validate_product_schema` for Product pages; do not claim RRT API.”
   - One line in `docs/COMMANDS.md`.

### P1 — Optional Google spot-check

7. **`gsc_inspect` rich-results slice**
   - After local pass is green, optional `--gsc-inspect` on 1–3 monitored product URLs per verified property.
   - Cache results; never block CI on quota/auth failure (degrade to `setup_required`).
   - Only for domains with existing GSC OAuth in `~/.config/codex-seo/`.

### P2 — Expand types (later)

8. Same pattern for Article/LocalBusiness required fields (out of scope for this ticket unless free).

---

## Non-goals

- Third-party paid schema APIs.
- Scraping Rich Results Test UI.
- DabDash PHP Pest “full ontology” suite (keep generator tests in dabdash; estate contract in shadow-seo).
- Auto-rewriting live sites (report + fix tickets only).

---

## Acceptance

- `python scripts/analyze_schema.py https://…/products/… --json` reports `review.nested_itemReviewed` on pre-fix HTML and clean on post-fix.
- `pytest tests/test_validate_product_schema.py` green.
- Full site audit that samples products fails closed on nested `itemReviewed`.
- Skill/docs no longer imply Google RRT API exists.

---

## Suggested first commit (shadow-seo)

`feat(schema): local Product/Merchant validator + nested itemReviewed rule`

Then wire sampling into ecommerce/triple-audit in a follow-up commit.
