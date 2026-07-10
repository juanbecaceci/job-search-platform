"""
load_positions_bulk.py - Bulk-load already-normalized positions into the Job Tracker.

Bridges discovery sources that don't return structured JSON (e.g. the agent
reading markdown from the Indeed MCP connector's search_jobs, or the user pasting
job posts in chat) into the same dedup + bulk-insert path the API/scraper
tools use, instead of writing rows to Sheets one at a time.

Input: a JSON file with a list of position dicts (at least company/role/url).
Missing fields get the same defaults as the other fetch tools
(tipo=full-time, remote=True).

Usage:
  py core/load_positions_bulk.py --file .tmp/indeed_jobs.json --search-name my_search
  py core/load_positions_bulk.py --file .tmp/indeed_jobs.json --search-name my_search --region worldwide
"""

import argparse
import json
import sys
from pathlib import Path

from env_config import target_region  # importing this loads data/credentials/.env
from location_filters import REGION_CHOICES, filter_by_region, normalize_region

REQUIRED_FIELDS = ["company", "role", "url"]


def normalize(pos: dict) -> dict:
    return {
        "source": pos.get("source", "indeed"),
        "tipo": pos.get("tipo", "full-time"),
        "company": str(pos.get("company", "")).strip(),
        "role": str(pos.get("role", "")).strip(),
        "url": str(pos.get("url", "")).strip(),
        "location": str(pos.get("location", "")).strip() or "Remote",
        "remote": pos.get("remote", True),
        "salary": str(pos.get("salary", "")).strip(),
        "description": str(pos.get("description", ""))[:3000],
        "tags": pos.get("tags", []),
        "date_posted": str(pos.get("date_posted", "")).strip(),
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


def _force_utf8():
    """Emite UTF-8 aunque la consola de Windows esté en cp1252, para que las
    descripciones/emojis no rompan el print del resumen con UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main():
    _force_utf8()
    parser = argparse.ArgumentParser(description="Bulk-load normalized positions (JSON) into the Job Tracker")
    parser.add_argument("--file", required=True, help="Ruta a un JSON con una lista de posiciones")
    parser.add_argument("--search-name", default="default", help="Nombre de búsqueda para el tracker")
    parser.add_argument(
        "--region", "--market",
        dest="region",
        default=None,
        choices=REGION_CHOICES,
        help="Filtro de elegibilidad geográfica. Default: TARGET_REGION del .env "
             "(y 'worldwide' si no está seteada). `--market` es un alias histórico."
    )
    args = parser.parse_args()

    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("Error: el archivo debe contener una lista JSON de posiciones.")
        sys.exit(1)

    positions = [normalize(p) for p in raw]
    positions = [p for p in positions if all(p.get(f) for f in REQUIRED_FIELDS)]

    region = normalize_region(args.region if args.region is not None else target_region())
    if region not in ("worldwide", ""):
        before_geo = len(positions)
        positions = filter_by_region(positions, region)
        print(f"[Geo] {len(positions)}/{before_geo} compatibles con {region} remoto")

    positions = dedup(positions)
    for pos in positions:
        pos["search_name"] = args.search_name

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.sheets_manager import add_positions_bulk

    result = add_positions_bulk(positions)
    print(f"{result['added']} agregadas, {result.get('updated', 0)} actualizadas, {result.get('skipped', 0)} sin cambios.")


if __name__ == "__main__":
    main()
