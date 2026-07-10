# Workflow 02 - Configure a Job Search Session

## Objective
Define a search session with clear parameters before running discovery. Each session has a name, keywords, target markets, and source selection. Gmail monitoring for application responses is also configured here.

## When to Use
- Starting a new round of job search
- Targeting a specific niche or geography
- Running a freelance/contract search separately from full-time

---

## Inputs

Ask the user to confirm:

| Parameter | Options | Default |
|---|---|---|
| Search name | Any descriptive name | e.g., `automation_remote_jul26` |
| Keywords | Comma-separated list | See `config/job_sites.json` -> `search_keywords_by_role` |
| Markets | Argentina-LATAM remote / Remote global / USA-Canada / Latam-Spain / All | Argentina-LATAM remote |
| Sources | Which active sources to activate (APIs / MCP / scraper / manual) | All automated sources enabled |
| Type | full-time / freelance / contract / all | full-time |
| Min score threshold | 0-100 | 45 (configured in `config/scoring_criteria.json`; salary gate USD 3.500/month) |

---

## Steps

### 1. Confirm keywords

Use `config/job_sites.json` -> `search_keywords_by_role` as starting point:
- `automation_engineer`: automation engineer, automation consultant, process automation, workflow automation
- `product_ops`: product operations, product ops, product engineer, technical product manager
- `ai_ops`: AI operations, AI ops, conversational AI, chatbot operations, LLM operations
- `operations`: operations automation, digital operations, business automation, operations specialist
- `freelance_automation`: automation specialist, workflow automation, process automation consultant

Ask the user if he wants to customize or add keywords.

### 2. Confirm sources

Current active sources in the system:
- `Remotive API`
- `Remote OK API`
- `Himalayas API`
- `Arbeitnow API`
- `Jobicy API`
- `Indeed API provider` (Scrappa; requires `SCRAPPA_API_KEY`)
- `LinkedIn` scraper (`jobs-guest`)
- `Upwork MCP` (freelance / contract)
- `manual` (jobs the user shares in chat)

Important notes:
- The 5 public APIs + `Indeed API provider` + `LinkedIn` are the main full-time discovery track.
- `Upwork MCP` is the dedicated freelance / contract track.
- `manual` is not queried automatically. It is used for startup roles or individual jobs the user finds outside the system.
- `Wellfound` and `Fiverr` are no longer active sources. Do not configure them for discovery.

### 3. Log search config to Sheets

```
python core/sheets_manager.py --action setup
```

Then add a row to the "Search Configs" sheet with:
- search_id, name, keywords (semicolon-separated), markets, sources, date_created, active=TRUE

### 4. Configure Gmail monitoring

Set up periodic checks using:
```
mcp__claude_ai_Gmail__search_threads
```

Query pattern per company after applying:
```
from:{company_domain} after:{date_applied} (entrevista OR interview OR application OR aplicacion)
```

This should be run every 3-7 days after an application is sent. Results trigger status updates: `Applied` -> `Acknowledged` or `Interview Scheduled`.

---

## Source Decision Guide

| Source | Best for | Notes |
|---|---|---|
| Indeed API provider | High volume, global coverage | Use `core/fetch_jobs_indeed.py` with Scrappa and `SCRAPPA_API_KEY`. Official Indeed MCP is Claude Connector-only in practice and fails in Codex with `HTTP 403 invalid_client`. |
| Remotive API | Remote-first SaaS roles | Free, no auth, call via `fetch_jobs_api.py` |
| Remote OK API | Remote tech roles | Free, no auth, call via `fetch_jobs_api.py` |
| Himalayas API | Remote-first tech roles | Paged feed; local keyword filtering |
| Arbeitnow API | Remote roles with EU/DACH bias | Filter remote + keyword locally |
| Jobicy API | Highest current yield | Only API with real server-side filtering |
| LinkedIn scraper | Volume + quality | Public `jobs-guest` endpoint; can hit HTTP 429 |
| Upwork MCP | Freelance/contract | Separate ranking track |
| Manual | Startups / one-off jobs | Added manually to the tracker, same scoring flow |

---

## Recommended Presets

- **Argentina/LATAM remote full-time search:** Remotive, Remote OK, Himalayas, Arbeitnow, Jobicy, Indeed, LinkedIn
- **Freelance / contract search:** Upwork MCP
- **Startup or external finds:** manual

If the user does not specify otherwise, use:
- `type = full-time`
- `markets = Argentina-LATAM remote`
- `sources = Remotive, Remote OK, Himalayas, Arbeitnow, Jobicy, Indeed, LinkedIn`

---

## Output

- Search config logged in Google Sheets -> "Search Configs" sheet
- Search name confirmed and ready to pass to Workflow 03

---

## Next Step

-> Run **Workflow 03 - Discover Jobs**
