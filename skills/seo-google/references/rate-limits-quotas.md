# Google API Rate Limits & Quotas

## Consolidated Quota Table

| API | Per-Minute | Per-Day | Cost | Auth Type | Scope |
|-----|-----------|---------|------|-----------|-------|
| GSC Search Analytics | 1,200 QPM/user, 1,200 QPM/site | 30M QPD/project | Free | Service Account | Per user + per site |
| GSC URL Inspection | 600 QPM/site | 2,000 QPD/site | Free | Service Account | Per site |
| GSC Sitemaps | Standard | Standard | Free | Service Account | Per site |
| PageSpeed Insights v5 | 240 QPM | 25,000 QPD | Free | API Key | Per project |
| CrUX API | 150 QPM (shared) | Unlimited | Free | API Key | Per project |
| CrUX History API | 150 QPM (shared with CrUX) | Unlimited | Free | API Key | Per project |
| Indexing API | 380 RPM total, 180 read/min | 200 publish/day | Free | Service Account | Per project |
| Knowledge Graph | -- | 100,000 QPD | Free | API Key | Per project |
| Custom Search | -- | 10,000 QPD max | 100 free, $5/1K | API Key | Per project |
| Web Risk | 6,000 QPM | 100K/month | Free tier | API Key | Per project |

**Key distinction:** "Per site" quotas are scoped to a specific GSC property. "Per project" quotas are shared across all properties in a GCP project. "Per user" quotas are per authenticated user (service account).

## Exponential Backoff Strategy

When receiving 429 or 5xx errors:

```
Attempt 1: wait 1 second
Attempt 2: wait 2 seconds
Attempt 3: wait 4 seconds
Attempt 4: wait 8 seconds
Attempt 5: wait 16 seconds
Max: give up after 5 retries
```

Add random jitter (0-500ms) to each wait to avoid thundering herd.

## Common Error Codes

| Code | Meaning | Applies To | Action |
|------|---------|------------|--------|
| 400 | Bad request | All | Check URL format, request body |
| 401 | Unauthorized | Service Account APIs | Refresh credentials |
| 403 | Forbidden | GSC, Indexing | Check permissions (service account access) |
| 404 | Not found | CrUX, GSC | Insufficient traffic (CrUX) or invalid property (GSC) |
| 429 | Rate limited | All | Backoff and retry. Check Retry-After header. |
| 500 | Server error | All | Retry with backoff |
| 503 | Service unavailable | All | Retry with backoff |

## Retry-After Header

Some Google APIs return a `Retry-After` header with 429 responses. When present, use this value (in seconds) instead of exponential backoff.

## CrUX Shared Quota

The CrUX API and CrUX History API share the same 150 QPM quota per project. Plan accordingly if querying both APIs in the same workflow.

## Cost Summary

**All APIs used by seo-google are free** at normal usage levels. No billing is required for:
- PSI, CrUX, CrUX History (API key, unlimited free)
- GSC (service account, 30M QPD)
- Indexing API (service account, 200 publish/day)
- Knowledge Graph (API key, 100K QPD)

Only Custom Search and Web Risk have paid tiers at high volumes.
