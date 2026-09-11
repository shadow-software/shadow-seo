# Upstream: codex-seo

Forked from [AgriciDaniel/codex-seo](https://github.com/AgriciDaniel/codex-seo) at
**`97c59bcdac3c9538bf0e3ae456c1e73aa387f85a`** (evaluated 2026-09-12 for
shadow-agent-markdown#34). MIT license — see `LICENSE`.

**Shadow Software does not run upstream `install.sh` via curl.** Clone this repo
(or sync per `shadow-agent-markdown/services/seo-suite/02-upstream-sync-policy.md`)
and invoke runners through the Shadow adaptation orchestrator.

## Remotes

```bash
git remote -v
# origin    https://github.com/shadow-software/shadow-seo.git
# upstream  https://github.com/AgriciDaniel/codex-seo.git
```

## Lineage

- Canonical OSS: [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo)
- Codex port (this upstream): [AgriciDaniel/codex-seo](https://github.com/AgriciDaniel/codex-seo)
- Shadow fork: [shadow-software/shadow-seo](https://github.com/shadow-software/shadow-seo)

Base-selection ADR: `shadow-agent-markdown/ops/adr/0003-seo-suite-base-selection.md`

## Shadow-specific wiring

Estate defaults, credentials, and read-only gates live in
`shadow-agent-markdown/services/seo-suite/` — not in this fork until a sync
merges an upstream security fix. Do not edit vendored skill text here for
one-off client work; change the adaptation layer or site profile instead.
