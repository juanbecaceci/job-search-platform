"""
sheets_manager.py — CRUD para el Job Tracker en Google Sheets.
Uso: python core/sheets_manager.py --action add_position --data '{"company": "Acme", ...}'
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build

# Imported as `core.sheets_manager` (repo root on sys.path) and also run
# directly (`python core/sheets_manager.py`, whose sys.path[0] is core/). Put
# the repo root on the path so the `core.*` imports resolve either way — the
# `core.google_auth` import in `get_sheets_service` needs it too.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.env_config import load_env  # noqa: E402

# Env comes from data/credentials/.env then a root .env, both resolved from the
# repo root rather than the CWD (see core/env_config.py). This used to be a
# CWD-relative `load_dotenv("data/credentials/.env")`, which silently loaded
# nothing whenever the process started anywhere but the repo root.
load_env()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
# Spreadsheet id: accept either variable name (.env.example uses SPREADSHEET_ID).
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_JOB_TRACKER_ID") or os.getenv("SPREADSHEET_ID")
# Credential/token paths are NOT duplicated here: auth is delegated to
# core/google_auth.py (one token, both scopes), which owns them.

# Hoja 1: Positions
POSITIONS_SHEET = "Positions"
POSITIONS_HEADERS = [
    "id", "search_name", "source", "sources", "tipo",
    "company", "role", "url", "location", "remote",
    "salary", "date_discovered", "score", "rank", "status",
    "evaluation_notes", "notes", "description", "tags"
]

# Hoja 2: Applications
APPLICATIONS_SHEET = "Applications"
APPLICATIONS_HEADERS = [
    "position_id", "cv_version", "cv_drive_url", "cover_letter_drive_url",
    "date_applied", "contact", "response_date", "interview_date",
    "outcome", "notes"
]

# Hoja 3: Search Configs
SEARCHES_SHEET = "Search Configs"
SEARCHES_HEADERS = [
    "search_id", "name", "keywords", "markets", "sources",
    "date_created", "active"
]

# Hoja 4: Companies
COMPANIES_SHEET = "Companies"
COMPANIES_HEADERS = [
    "company", "industry", "size", "website", "research_drive_url",
    "notes", "date_researched"
]

VALID_STATUSES = [
    "Discovered", "Evaluating", "Shortlisted", "CV Draft",
    "Ready to Apply", "Applied", "Acknowledged",
    "Interview Scheduled", "Interviewing", "Offer Received",
    "Negotiating", "Accepted", "Rejected", "Withdrawn", "Ghosted"
]


def _force_utf8():
    """Emite UTF-8 aunque la consola de Windows esté en cp1252, para que los
    prints con flechas/acentos (p. ej. 'Estado actualizado: … → Shortlisted')
    no rompan con UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def get_sheets_service(interactive: bool = True):
    """Build the Sheets client.

    `interactive=False` is what the API's job handlers pass: it never opens a
    browser, it raises `GoogleAuthError` telling the user to run
    `scripts/authorize_google.py`. The CLI entry points below keep the old
    interactive behaviour.
    """
    from core.google_auth import get_credentials

    creds = get_credentials(interactive=interactive)
    return build("sheets", "v4", credentials=creds)


def _fmt_tags(tags) -> str:
    """Los tags llegan como lista desde los fetchers; a Sheets van como texto."""
    if isinstance(tags, list):
        return ", ".join(str(t) for t in tags)
    return str(tags or "")


def make_position_id(company: str, role: str) -> str:
    raw = f"{company.lower().strip()}-{role.lower().strip()}"
    raw = re.sub(r"[^a-z0-9\-]", "", raw.replace(" ", "-"))
    hash_suffix = hashlib.md5(raw.encode()).hexdigest()[:6]
    return f"{raw[:30]}-{hash_suffix}"


def get_all_values(service, sheet_name: str) -> list:
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A:Z"
    ).execute()
    return result.get("values", [])


def ensure_headers(service, sheet_name: str, headers: list):
    values = get_all_values(service, sheet_name)
    if not values or values[0] != headers:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]}
        ).execute()
        print(f"Headers inicializados en hoja '{sheet_name}'")


def append_row(service, sheet_name: str, row: list):
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()


def find_row_by_id(values: list, id_value: str, id_col: int = 0) -> Optional[int]:
    for i, row in enumerate(values):
        if len(row) > id_col and row[id_col] == id_value:
            return i
    return None


def update_cell(service, sheet_name: str, row_index: int, col_index: int, value: str):
    col_letter = chr(ord("A") + col_index)
    range_notation = f"{sheet_name}!{col_letter}{row_index + 1}"
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_notation,
        valueInputOption="RAW",
        body={"values": [[value]]}
    ).execute()


def batch_update_values(service, updates: list):
    """Escribe muchos rangos en UN solo request (values.batchUpdate).

    `updates`: lista de {"range": "Hoja!A1:D1", "values": [[...]]}. Google Sheets
    limita a 60 write requests por minuto y por usuario; una escritura celda-por-
    celda (p. ej. evaluar 58 vacantes × 4 celdas) revienta ese cupo con 429. Un
    batchUpdate cuenta como UN request sin importar cuántos rangos lleve, así que
    toda la evaluación/ranking cabe en 1-2 requests. Best-effort ante rangos vacíos."""
    if not updates:
        return
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": updates},
    ).execute()


# ─── Public API ──────────────────────────────────────────────

def add_position(data: dict) -> str:
    """Agrega una posición con estado Discovered. Retorna el position_id."""
    if not SPREADSHEET_ID:
        print("Error: GOOGLE_SHEETS_JOB_TRACKER_ID no configurado en .env")
        sys.exit(1)

    service = get_sheets_service()
    ensure_headers(service, POSITIONS_SHEET, POSITIONS_HEADERS)

    position_id = make_position_id(data.get("company", ""), data.get("role", ""))

    # Dedup check
    values = get_all_values(service, POSITIONS_SHEET)
    existing = find_row_by_id(values, position_id)
    if existing is not None:
        print(f"Posición ya existe (id: {position_id}). Actualizando sources.")
        existing_row = values[existing]
        existing_sources = existing_row[3] if len(existing_row) > 3 else ""
        new_source = data.get("source", "")
        if new_source and new_source not in existing_sources:
            updated_sources = f"{existing_sources},{new_source}" if existing_sources else new_source
            update_cell(service, POSITIONS_SHEET, existing, 3, updated_sources)
        return position_id

    row = [
        position_id,
        data.get("search_name", ""),
        data.get("source", ""),
        data.get("source", ""),
        data.get("tipo", "full-time"),
        data.get("company", ""),
        data.get("role", ""),
        data.get("url", ""),
        data.get("location", ""),
        "Sí" if data.get("remote", True) else "No",
        data.get("salary", ""),
        date.today().isoformat(),
        "",
        "",
        "Discovered",
        "",
        data.get("notes", ""),
        data.get("description", ""),
        _fmt_tags(data.get("tags", ""))
    ]
    append_row(service, POSITIONS_SHEET, row)
    print(f"Posición agregada: {position_id} | {data.get('company')} — {data.get('role')}")
    return position_id


def add_positions_bulk(positions: list[dict]) -> dict:
    """Agrega posiciones en lote evitando una lectura por fila."""
    if not SPREADSHEET_ID:
        print("Error: GOOGLE_SHEETS_JOB_TRACKER_ID no configurado en .env")
        sys.exit(1)

    if not positions:
        return {"added": 0, "updated": 0, "skipped": 0}

    service = get_sheets_service()
    ensure_headers(service, POSITIONS_SHEET, POSITIONS_HEADERS)
    values = get_all_values(service, POSITIONS_SHEET)

    existing_by_id = {}
    for idx, row in enumerate(values):
        if idx == 0 or not row:
            continue
        existing_by_id[row[0]] = (idx, row)

    rows_to_append = []
    source_updates = []
    added = updated = skipped = 0

    for data in positions:
        position_id = make_position_id(data.get("company", ""), data.get("role", ""))
        new_source = data.get("source", "")

        if position_id in existing_by_id:
            row_idx, existing_row = existing_by_id[position_id]
            existing_sources = existing_row[3] if len(existing_row) > 3 else ""
            if new_source and new_source not in existing_sources:
                updated_sources = f"{existing_sources},{new_source}" if existing_sources else new_source
                source_updates.append({
                    "range": f"{POSITIONS_SHEET}!D{row_idx + 1}",
                    "values": [[updated_sources]]
                })
                updated += 1
            else:
                skipped += 1
            continue

        row = [
            position_id,
            data.get("search_name", ""),
            new_source,
            new_source,
            data.get("tipo", "full-time"),
            data.get("company", ""),
            data.get("role", ""),
            data.get("url", ""),
            data.get("location", ""),
            "Sí" if data.get("remote", True) else "No",
            data.get("salary", ""),
            date.today().isoformat(),
            "",
            "",
            "Discovered",
            "",
            data.get("notes", ""),
            data.get("description", ""),
            _fmt_tags(data.get("tags", ""))
        ]
        rows_to_append.append(row)
        existing_by_id[position_id] = (len(values) + len(rows_to_append) - 1, row)
        added += 1

    if source_updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "RAW", "data": source_updates}
        ).execute()

    if rows_to_append:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{POSITIONS_SHEET}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows_to_append}
        ).execute()

    print(f"Bulk Sheets: {added} agregadas, {updated} sources actualizadas, {skipped} ya existentes.")
    return {"added": added, "updated": updated, "skipped": skipped}


def get_position_ids_with_description() -> set:
    """IDs de posiciones que ya tienen descripción no vacía en Sheets.

    Sirve para que el discovery no vuelva a traer descripciones ya guardadas
    (p. ej. la 2ª pasada de LinkedIn): re-correr un search no gasta requests de
    detalle en vacantes ya enriquecidas. Best-effort: ante cualquier problema
    devuelve un set vacío (el llamador simplemente no deduplica contra Sheets)."""
    if not SPREADSHEET_ID:
        return set()
    try:
        service = get_sheets_service()
        values = get_all_values(service, POSITIONS_SHEET)
    except Exception as e:
        print(f"[dedup] No se pudo leer Sheets: {e}")
        return set()
    if not values:
        return set()
    headers = values[0]
    if "id" not in headers or "description" not in headers:
        return set()
    id_col = headers.index("id")
    desc_col = headers.index("description")
    ids = set()
    for row in values[1:]:
        if len(row) > desc_col and row[id_col] and str(row[desc_col]).strip():
            ids.add(row[id_col])
    return ids


def update_status(position_id: str, new_status: str, notes: str = ""):
    """Actualiza el estado de una posición."""
    if new_status not in VALID_STATUSES:
        print(f"Estado inválido: {new_status}. Válidos: {VALID_STATUSES}")
        sys.exit(1)

    service = get_sheets_service()
    values = get_all_values(service, POSITIONS_SHEET)
    row_idx = find_row_by_id(values, position_id)

    if row_idx is None:
        print(f"Posición no encontrada: {position_id}")
        sys.exit(1)

    status_col = POSITIONS_HEADERS.index("status")
    notes_col = POSITIONS_HEADERS.index("notes")

    update_cell(service, POSITIONS_SHEET, row_idx, status_col, new_status)
    if notes:
        existing_notes = values[row_idx][notes_col] if len(values[row_idx]) > notes_col else ""
        combined = f"{existing_notes}\n[{date.today().isoformat()}] {notes}".strip()
        update_cell(service, POSITIONS_SHEET, row_idx, notes_col, combined)

    print(f"Estado actualizado: {position_id} → {new_status}")


def update_score(position_id: str, score: float, rank: int = 0, evaluation_notes: str = ""):
    """Actualiza score y notas de evaluación. El rank pasado se ignora: siempre se
    recalcula con un re-rank global inmediatamente después (ver rerank_all en
    evaluate_position.py), para que el ranking nunca quede desincronizado entre
    posiciones evaluadas por caminos distintos (batch vs. individual/manual)."""
    service = get_sheets_service()
    values = get_all_values(service, POSITIONS_SHEET)
    row_idx = find_row_by_id(values, position_id)

    if row_idx is None:
        print(f"Posición no encontrada: {position_id}")
        sys.exit(1)

    update_cell(service, POSITIONS_SHEET, row_idx, POSITIONS_HEADERS.index("score"), str(round(score, 1)))
    update_cell(service, POSITIONS_SHEET, row_idx, POSITIONS_HEADERS.index("evaluation_notes"), evaluation_notes)
    update_cell(service, POSITIONS_SHEET, row_idx, POSITIONS_HEADERS.index("status"), "Evaluating")
    print(f"Score actualizado: {position_id} → {score}/100")

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.evaluate_position import rerank_all
    rerank_all()


def get_by_status(status: str) -> list:
    """Retorna lista de posiciones con el estado dado."""
    service = get_sheets_service()
    values = get_all_values(service, POSITIONS_SHEET)
    if not values or len(values) < 2:
        return []

    headers = values[0]
    status_col = headers.index("status") if "status" in headers else 14
    return [
        dict(zip(headers, row))
        for row in values[1:]
        if len(row) > status_col and row[status_col] == status
    ]


def get_ranking(min_score: float = 0, tipo: str = "full-time") -> list:
    """Retorna posiciones ordenadas por score descendente."""
    service = get_sheets_service()
    values = get_all_values(service, POSITIONS_SHEET)
    if not values or len(values) < 2:
        return []

    headers = values[0]
    rows = [dict(zip(headers, row)) for row in values[1:] if len(row) >= len(headers) - 2]
    filtered = [
        r for r in rows
        if r.get("tipo", "full-time") == tipo
        and float(r.get("score", 0) or 0) >= min_score
    ]
    return sorted(filtered, key=lambda x: float(x.get("score", 0) or 0), reverse=True)


def log_application(position_id: str, cv_url: str = "", cl_url: str = "", contact: str = ""):
    """Registra una postulación enviada."""
    service = get_sheets_service()
    ensure_headers(service, APPLICATIONS_SHEET, APPLICATIONS_HEADERS)

    row = [
        position_id, "v1", cv_url, cl_url,
        date.today().isoformat(), contact, "", "", "", ""
    ]
    append_row(service, APPLICATIONS_SHEET, row)
    update_status(position_id, "Applied")
    print(f"Postulación registrada: {position_id}")


def add_company_research(company: str, industry: str = "", size: str = "",
                          website: str = "", drive_url: str = "", notes: str = ""):
    """Agrega o actualiza research de empresa."""
    service = get_sheets_service()
    ensure_headers(service, COMPANIES_SHEET, COMPANIES_HEADERS)

    row = [company, industry, size, website, drive_url, notes, date.today().isoformat()]
    append_row(service, COMPANIES_SHEET, row)
    print(f"Research de empresa guardado: {company}")


def replace_sheet(service, sheet_name: str, headers: list, rows: list) -> int:
    """Truncate a tab and rewrite it with `headers` + `rows`.

    The SQLite->Sheets direction (DECISIONS #2: Sheets is a one-way export
    mirror, never read back). Clearing first is what makes the export a mirror
    rather than an append — rows deleted in SQLite must disappear here too.

    Returns the number of data rows written.
    """
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_name,
        body={},
    ).execute()

    values = [headers] + [list(r) for r in rows]
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    return len(rows)


def get_existing_sheet_titles(service) -> list:
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def ensure_sheets_exist(service, required: list):
    """Crea las pestañas que falten en el spreadsheet."""
    existing = get_existing_sheet_titles(service)
    to_add = [title for title in required if title not in existing]
    if to_add:
        requests = [{"addSheet": {"properties": {"title": t}}} for t in to_add]
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": requests}
        ).execute()
        print(f"Pestañas creadas: {', '.join(to_add)}")


def setup_spreadsheet():
    """Inicializa todas las hojas con sus headers."""
    service = get_sheets_service()
    sheets = [
        (POSITIONS_SHEET, POSITIONS_HEADERS),
        (APPLICATIONS_SHEET, APPLICATIONS_HEADERS),
        (SEARCHES_SHEET, SEARCHES_HEADERS),
        (COMPANIES_SHEET, COMPANIES_HEADERS),
    ]
    ensure_sheets_exist(service, [name for name, _ in sheets])
    for sheet_name, headers in sheets:
        ensure_headers(service, sheet_name, headers)
    print("Google Sheets configurado correctamente.")


# ─── CLI ─────────────────────────────────────────────────────

def main():
    _force_utf8()
    parser = argparse.ArgumentParser(description="Job Tracker — Google Sheets Manager")
    parser.add_argument("--action", required=True, choices=[
        "setup", "add_position", "update_status", "get_by_status", "get_ranking", "log_application"
    ])
    parser.add_argument("--data", help="JSON con los datos de la acción")
    parser.add_argument("--id", help="position_id para acciones de actualización")
    parser.add_argument("--status", help="Estado para filtros o actualizaciones")
    parser.add_argument("--score", type=float, help="Score (0-100)")
    parser.add_argument("--rank", type=int, help="Posición en ranking")
    args = parser.parse_args()

    data = json.loads(args.data) if args.data else {}

    if args.action == "setup":
        setup_spreadsheet()
    elif args.action == "add_position":
        add_position(data)
    elif args.action == "update_status":
        update_status(args.id, args.status, data.get("notes", ""))
    elif args.action == "get_by_status":
        positions = get_by_status(args.status)
        print(json.dumps(positions, ensure_ascii=False, indent=2))
    elif args.action == "get_ranking":
        ranking = get_ranking(min_score=float(data.get("min_score", 0)))
        print(json.dumps(ranking, ensure_ascii=False, indent=2))
    elif args.action == "log_application":
        log_application(args.id, data.get("cv_url", ""), data.get("cl_url", ""), data.get("contact", ""))


if __name__ == "__main__":
    main()
