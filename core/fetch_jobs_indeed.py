"""
fetch_jobs_indeed.py - Indeed discovery through a structured API provider.

FALLBACK. The primary Indeed source is the official MCP connector
(`mcp__claude_ai_Indeed__search_jobs`), wired into `search_run` via
`api/agent/mcp_sources.py` — see Workflow 03 Step 2.

Use this script when the MCP connector isn't available in the environment, or
when you want a deterministic, agent-free Indeed fetch (this module makes plain
HTTP calls; the MCP path spends an agent turn).

History: an earlier note here claimed Indeed's MCP was "Claude Connector only"
because fresh non-Claude sessions got HTTP 403 "invalid_client". Re-verified
2026-07-30 and that is no longer true — the endpoint advertises RFC 7591
dynamic client registration (`https://secure.indeed.com/oauth/v2/register`
returns 201 to an anonymous request) and answers unauthenticated calls with a
standard 401 + `WWW-Authenticate` challenge. Any MCP client can self-register,
so the connector is not the only route.

Default provider: Scrappa Indeed Jobs API
Docs: https://scrappa.co/apis/indeed-jobs-api

Required env:
  SCRAPPA_API_KEY=...

Usage:
  py core/fetch_jobs_indeed.py --keywords "automation engineer,workflow automation" --save
  py core/fetch_jobs_indeed.py --keywords "automation engineer" --add-to-sheets --search-name my_search
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
# Importing env_config loads data/credentials/.env (then a root .env).
from env_config import job_search_country, job_search_location, target_region
from location_filters import REGION_CHOICES, filter_by_region, normalize_region

SCRAPPA_ENDPOINT = os.getenv("SCRAPPA_INDEED_ENDPOINT", "https://scrappa.co/api/indeed/jobs")
HEADERS = {"Accept": "application/json"}


def _first_present(data: dict, keys: list[str], default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return default


def normalize_position(raw: dict) -> dict:
    url = _first_present(raw, ["url", "job_url", "apply_url", "application_url", "link"])
    company = _first_present(raw, ["company", "company_name", "employer", "employer_name"])
    role = _first_present(raw, ["title", "job_title", "position"])
    location = _first_present(raw, ["location", "job_location", "formatted_location"], "Remote")
    salary = _first_present(raw, ["salary", "salary_snippet", "salary_text"])
    description = _first_present(raw, ["description", "summary", "snippet"])
    date_posted = _first_present(raw, ["posted", "date_posted", "posted_at", "publication_date"])

    return {
        "source": "indeed",
        "tipo": "full-time",
        "company": str(company).strip(),
        "role": str(role).strip(),
        "url": str(url).strip(),
        "location": str(location).strip() or "Remote",
        "remote": True,
        "salary": str(salary).strip(),
        "description": str(description or "")[:3000],
        "tags": raw.get("tags") or raw.get("attributes") or [],
        "date_posted": str(date_posted).strip(),
    }


def dedup(positions: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for pos in positions:
        key = "|".join([
            pos.get("company", "").lower().strip(),
            pos.get("role", "").lower().strip(),
            pos.get("url", "").lower().strip(),
        ])
        if key in seen:
            continue
        seen.add(key)
        unique.append(pos)
    return unique


def fetch_scrappa(keyword: str, api_key: str, location: str,
                  country: str, limit: int, job_type: str = "fulltime") -> list[dict]:
    params = {
        "query": keyword,
        "location": location,
        "country": country,
        "limit": limit,
        "job_type": job_type,
    }
    headers = {**HEADERS, "X-API-KEY": api_key}
    resp = requests.get(SCRAPPA_ENDPOINT, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, list):
        return payload
    return payload.get("results") or payload.get("jobs") or payload.get("data") or []


def fetch_all(keywords: list[str], location: str, country: str,
              limit: int, region: str = None) -> list[dict]:
    api_key = os.getenv("SCRAPPA_API_KEY")
    if not api_key:
        print("Error: SCRAPPA_API_KEY no configurado en .env.")
        print("Creá una key en Scrappa y agregala como SCRAPPA_API_KEY antes de usar Indeed.")
        sys.exit(1)

    positions = []
    for keyword in keywords:
        print(f"[Indeed/Scrappa] {keyword} | location={location} | country={country}")
        try:
            raw_jobs = fetch_scrappa(keyword, api_key, location, country, limit)
            normalized = [normalize_position(job) for job in raw_jobs]
            positions.extend([p for p in normalized if p["company"] and p["role"] and p["url"]])
            print(f"[Indeed/Scrappa] {len(raw_jobs)} recibidas")
        except requests.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            print(f"[Indeed/Scrappa] HTTP error con '{keyword}': {e} {body}")
        except Exception as e:
            print(f"[Indeed/Scrappa] Error con '{keyword}': {e}")
        time.sleep(0.5)

    region = normalize_region(region if region is not None else target_region())
    if region not in ("worldwide", ""):
        before_geo = len(positions)
        positions = filter_by_region(positions, region)
        print(f"[Geo] {len(positions)}/{before_geo} compatibles con {region} remoto")

    unique = dedup(positions)
    print(f"\nTotal Indeed único: {len(unique)} posiciones ({len(positions)} antes de dedup)")
    return unique


def _force_utf8():
    """Emite UTF-8 aunque la consola de Windows esté en cp1252, para que las
    descripciones/emojis no rompan el print del sample con UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main():
    _force_utf8()
    parser = argparse.ArgumentParser(description="Fetch jobs from Indeed via Scrappa")
    parser.add_argument("--keywords", required=True, help="Keywords separadas por coma")
    parser.add_argument(
        "--location",
        default=job_search_location(),
        help="Ubicación para Indeed. Default: JOB_SEARCH_LOCATION del .env ('remote')."
    )
    parser.add_argument(
        "--country",
        default=job_search_country(),
        help="País (ISO 3166 de 2 letras) para Indeed/Scrappa. "
             "Default: JOB_SEARCH_COUNTRY del .env ('US')."
    )
    parser.add_argument("--limit", type=int, default=25, help="Resultados por keyword. Default: 25")
    parser.add_argument(
        "--region", "--market",
        dest="region",
        default=None,
        choices=REGION_CHOICES,
        help="Filtro de elegibilidad geográfica. Default: TARGET_REGION del .env "
             "(y 'worldwide' si no está seteada). `--market` es un alias histórico."
    )
    parser.add_argument("--save", action="store_true", help="Guarda resultados en .tmp/indeed_jobs.json")
    parser.add_argument("--add-to-sheets", action="store_true", help="Agrega resultados a Google Sheets")
    parser.add_argument("--search-name", default="default", help="Nombre de búsqueda para el tracker")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    positions = fetch_all(
        keywords=keywords,
        location=args.location,
        country=args.country,
        limit=args.limit,
        region=args.region,
    )

    if args.save:
        output_path = Path(".tmp/indeed_jobs.json")
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(json.dumps(positions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Guardado en {output_path}")

    if args.add_to_sheets:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from tools.sheets_manager import add_positions_bulk

        for pos in positions:
            pos["search_name"] = args.search_name
        result = add_positions_bulk(positions)
        print(f"\n{result['added']} posiciones agregadas a Google Sheets.")

    if not args.save and not args.add_to_sheets:
        print(json.dumps(positions[:5], ensure_ascii=False, indent=2))
        print(f"... ({len(positions)} total). Usá --save o --add-to-sheets para persistir.")


if __name__ == "__main__":
    main()
