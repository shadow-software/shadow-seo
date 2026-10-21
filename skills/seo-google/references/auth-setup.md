# Google API Authentication Setup

## Overview

Three credential types serve different APIs:

| Type | Used By | Cost |
|------|---------|------|
| **API Key** | PageSpeed Insights, CrUX, CrUX History, Knowledge Graph | Free |
| **Service Account** | Search Console, Indexing API | Free |
| **Both** | Full seo-google skill | Free |

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Name it (e.g., "Codex SEO") and note the project ID
4. Select the project after creation

## Step 2: Enable APIs

Navigate to **APIs & Services > Library** and enable:

| API | Required For |
|-----|-------------|
| Google Search Console API | GSC Search Analytics, URL Inspection, Sitemaps |
| PageSpeed Insights API | PSI Lighthouse lab data |
| Chrome UX Report API | CrUX field data + History |
| Web Search Indexing API | Indexing API v3 |
| Knowledge Graph Search API | Entity verification (optional) |

## Step 3: Create an API Key

1. **APIs & Services > Credentials > Create Credentials > API key**
2. Click **Restrict key**:
   - Under **API restrictions**, select: PageSpeed Insights API, Chrome UX Report API, Knowledge Graph Search API
3. Copy the key (starts with `AIzaSy...`)

## Step 4: Create a Service Account

1. **IAM & Admin > Service Accounts > Create Service Account**
2. Name: `codex-seo` (or similar)
3. Skip optional permissions steps
4. Click on the created service account > **Keys > Add Key > Create new key > JSON**
5. Download the JSON file and store it securely (e.g., `~/.config/codex-seo/service_account.json`)

The JSON file looks like:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "[redacted service-account private key]",
  "client_email": "codex-seo@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

The `client_email` field is what you add to Search Console.

## Step 5: Grant Search Console Access

1. Go to [Google Search Console](https://search.google.com/search-console)
2. Select your property
3. **Settings > Users and permissions > Add user**
4. Paste the service account `client_email`
5. Set permission level:
   - **Full** for read-only (Search Analytics, URL Inspection, Sitemaps)
   - **Owner** if you also need the Indexing API

## Step 6: Create Config File

```bash
mkdir -p ~/.config/codex-seo
```

Save to `~/.config/codex-seo/google-api.json`:

```json
{
  "service_account_path": "~/.config/codex-seo/service_account.json",
  "api_key": "AIzaSy...",
  "default_property": "sc-domain:example.com"
}
```

### Property URL Formats

| Format | Example | When to Use |
|--------|---------|-------------|
| Domain property | `sc-domain:example.com` | Covers all URLs on the domain (recommended) |
| URL-prefix property | `https://example.com/` | Covers only that specific prefix |

## Step 7: Verify Setup

```bash
python scripts/google_auth.py --check
```

Expected output at Tier 1 (authenticated):
```
Credential Tier: 1 -- Authenticated (API key + OAuth/Service Account)

  [OK] PageSpeed Insights v5
  [OK] Chrome UX Report (CrUX) API
  [OK] CrUX History API
  [OK] Google Search Console API
       Service account: codex-seo@your-project.iam.gserviceaccount.com
  [OK] Google Indexing API v3
```

## Environment Variable Alternatives

Instead of (or in addition to) the config file:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | API key for PSI/CrUX |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| `GSC_PROPERTY` | Default GSC property (e.g., `sc-domain:example.com`) |

## OAuth Scopes Used

| Scope | APIs |
|-------|------|
| `https://www.googleapis.com/auth/webmasters.readonly` | GSC (read) |
| `https://www.googleapis.com/auth/webmasters` | GSC (read/write, needed for sitemap submission) |
| `https://www.googleapis.com/auth/indexing` | Indexing API |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `403 Forbidden` on GSC | Service account email not added to GSC property, or wrong permission level |
| `404 Not Found` on GSC | Wrong property URL format. Use `sc-domain:` or include trailing slash for URL-prefix |
| `404 Not Found` on CrUX | Site has insufficient Chrome traffic. Not a credentials issue. |
| `429 Rate Limit` | Wait and retry. See rate-limits-quotas.md for per-API limits |
| `API not enabled` | Enable the specific API in GCP Console > APIs & Services > Library |
