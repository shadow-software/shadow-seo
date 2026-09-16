---
name: seo-triple-audit
description: >
  Run a full local SEO + GEO/AEO audit with three parallel crawlers (SiteOne
  Crawler, xseo, crawlie). Use when the user asks for a site crawl, technical
  SEO audit, Screaming Frog replacement, pre-deploy SEO gate, LLM-readiness,
  GEO score, or AEO checks on a local or staging site.
user-invokable: true
argument-hint: "[app-id|url]"
---

# SEO triple-audit (SiteOne + xseo + crawlie)

Screaming Frog is **retired** on this estate (no free licence). Use the
**triple-audit stack** instead — three CLI crawlers run in parallel for maximum
coverage:

| Tool | Strength |
| --- | --- |
| **SiteOne Crawler** | Full technical audit: status codes, redirects, titles, canonicals, robots, sitemaps, security headers, assets, JS/browser errors, CSP/CORS/mixed content, quality scores, CI gate |
| **xseo** | Clean on-page SEO + duplication checks; JSON/CSV/HTML/SARIF; `xseo diff` for regressions |
| **crawlie** | Technical SEO **plus GEO/LLM-readiness** (AEO): llms.txt, structured data for AI, thin-for-AI, answer-engine signals |

## One command (preferred)

```bash
# Install once (idempotent, no sudo)
~/Source/shadow-founder-toolset/install/laptop/install-seo-crawlers.sh

# WDK (WordPress staging) — unified audit with profile merge
ss-seo-audit-wdk --profile wdk
# same as: ss-seo-audit --start wdk --profile wdk

# Lightweight (n8n / quick check)
ss-seo-audit --quick --profile shadowsoftware --url=https://shadowsoftware.com/

# Audit a local estate app (starts server, waits, runs all three)
ss-seo-audit --start shadowsoftware

# Audit URL directly (site already running)
ss-seo-audit http://127.0.0.1:4321/

# Production hostname against local instance
ss-seo-audit --url=https://www.example.com \
  --resolve='www.example.com:443:127.0.0.1'

# Relaxed gates (still writes full reports)
ss-seo-audit --start dabdash --relaxed
```

**Output:** `/tmp/<slug>-seo-audit-<timestamp>/` with `SUMMARY.md`, per-tool
HTML/JSON, and logs. Open `siteone/report.html` and `crawlie/report.html` in a
browser for the richest view.

**Exit codes:** `0` all gates passed; `2` one or more strict gates failed (expected
when fixing issues — read `SUMMARY.md`).

## Strict defaults (do not loosen unless asked)

The wrapper runs aggressive settings:

- **SiteOne:** `--browser`, CI min overall **8.0**, SEO/security/a11y/best-practices **8.0**, performance **7.0**, zero 404/5xx/criticals/warnings
- **xseo:** `--fail-on medium`
- **crawlie:** `--render`, `--fail-on warning` (includes GEO/AEO checks)

Static sites: add `--no-browser` for faster runs.

**Browser binary:** On the founder laptop, `ss-seo-audit` auto-uses Brave Origin
(`/opt/brave-origin-bin/brave`) — not Google Chrome. crawlie uses `$CHROME`;
SiteOne uses `--browser-path`. Override: `SHADOW_SEO_BROWSER=/path/to/chromium`
or `ss-seo-audit --browser-path …`. If no browser is found, the command exits
with a clear error (use `--no-browser` to skip JS rendering).

## Individual tools

```bash
ss-siteone-crawl --url=http://127.0.0.1:8999/ --browser --ci --ci-min-score=8
ss-xseo-crawl http://127.0.0.1:8999/ --out report.json --fail-on medium
ss-crawlie-crawl crawl http://127.0.0.1:8999/ --render --format json --fail-on warning
```

## Workflow

1. **Start or confirm** the target is HTTP-ready (`ss-estate status <app>` or `--start`).
2. **Run** `ss-seo-audit --start <app>` (or pass a URL).
3. **Read** `SUMMARY.md` first, then HTML reports for details.
4. **Fix** issues in the repo; re-run until gates pass.
5. **Optional:** keep `siteone/report.json` as `--ci-baseline` for regression checks on the next run.

## Local estate app IDs

See `shadow-founder-toolset/docs/local-estate.md` — common targets:

| Alias | App id | URL |
| --- | --- | --- |
| **wdk** | `weeddeliverykelowna` | `http://staging.weeddeliverykelowna.localhost:8092` |
| — | `agt` | `http://127.0.0.1:8082` |
| — | `dabdash` | `http://127.0.0.1:8000` |
| — | `shadowsoftware` | `http://127.0.0.1:8999` |
| — | `raywinkelman` | `http://127.0.0.1:4321` |

WDK is Docker Compose WordPress — use default `--browser` / crawlie `--render`
(Elementor/JS). Ensure `*.localhost` resolves to loopback in your browser; the
crawler uses the staging hostname from `estate.json`.

## Pair with Lighthouse

SiteOne/xseo/crawlie cover crawl/indexation/on-page/GEO. Run Lighthouse separately
for Core Web Vitals when performance is in scope (`npm run lh:baseline` on PWAs).

## Do not use

- Screaming Frog (licence required; removed from estate tooling)
- Ad-hoc Python `sf-audit-url.py` except legacy blog one-offs — prefer SiteOne single-page mode instead
