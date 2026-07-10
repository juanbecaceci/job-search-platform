"""
evaluate_position.py - Motor deterministico de evaluacion de vacantes.

El razonamiento (evaluar salario y asignar 1-5 a cada criterio leyendo el JD)
lo hace el agente en la conversacion. Este tool solo calcula, persiste y rankea.

Flujo:
1. `--list-pending` -> exporta posiciones a evaluar.
2. El agente evalua el salary gate y los 4 criterios ponderados.
3. `--write-scores --data-file <json>` -> calcula score/categoria, descarta si
   corresponde y escribe todo en Google Sheets.

Uso:
  python core/evaluate_position.py --list-pending --status Discovered
  python core/evaluate_position.py --write-scores --data-file .tmp/scores.json
  python core/evaluate_position.py --show-ranking --min-score 45
  python core/evaluate_position.py --rerank
"""

import argparse
import json
import sys
from pathlib import Path

CRITERIA_PATH = Path("config/scoring_criteria.json")


def _force_utf8():
    """Emite UTF-8 aunque la consola de Windows esté en cp1252, para que las
    descripciones/emojis (p. ej. 🚀 en un JD) no rompan el print/redirect con
    UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

# Estados que NO participan del ranking
NON_RANKED_STATUSES = {"Rejected", "Withdrawn", "Ghosted"}

SALARY_FAIL = "FAIL"
SALARY_PASS = "PASS"
SALARY_UNKNOWN = "UNKNOWN"


def load_criteria() -> dict:
    if not CRITERIA_PATH.exists():
        print(f"Error: {CRITERIA_PATH} no encontrado.")
        sys.exit(1)
    return json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))


def _score_value(raw) -> float:
    """Acepta un numero o un objeto {'score': n, 'note': '...'}."""
    if isinstance(raw, dict):
        return float(raw.get("score", 0))
    return float(raw)


def compute_weighted_score(scores: dict, criteria: dict) -> float:
    """scores: {criterion_id: number|{'score': n}}. Devuelve 0-100."""
    scale_max = float(criteria.get("scale_max", 5))
    total = 0.0
    for criterion in criteria["criteria"]:
        cid = criterion["id"]
        weight = float(criterion["weight"])
        val = _score_value(scores.get(cid, 0))
        total += val * weight
    return round((total / scale_max) * 100, 1)


def category_for_score(score: float, criteria: dict) -> dict:
    categories = sorted(
        criteria.get("categories", []),
        key=lambda item: item.get("min_score", 0),
        reverse=True,
    )
    for category in categories:
        if score >= category["min_score"]:
            return category
    return {
        "id": "DESCARTAR",
        "recommended_action": "No invertir tiempo en aplicar.",
    }


def normalize_salary_gate(entry: dict, criteria: dict) -> dict:
    """
    Normaliza el salary gate enviado por el agente.

    Formatos aceptados:
    - {"status": "PASS|FAIL|UNKNOWN", "evaluated_usd_month": 3500, "note": "..."}
    - {"passes_floor": true|false|null, ...}
    - "PASS" / "FAIL" / "UNKNOWN"
    """
    gate = entry.get("salary_gate", {})
    floor = criteria.get("salary_gate", {}).get("floor_usd_month", 3500)

    if isinstance(gate, str):
        gate = {"status": gate}
    elif not isinstance(gate, dict):
        gate = {}

    status_raw = str(gate.get("status", "")).strip().upper()
    passes_floor = gate.get("passes_floor")

    if passes_floor is True:
        status = SALARY_PASS
    elif passes_floor is False:
        status = SALARY_FAIL
    elif status_raw in {"PASS", "PASA", "OK", "CUMPLE", "VALIDATED"}:
        status = SALARY_PASS
    elif status_raw in {"FAIL", "NO_PASA", "BELOW_FLOOR", "DESCARTADA", "DESCARTAR"}:
        status = SALARY_FAIL
    elif status_raw in {"UNKNOWN", "UNPUBLISHED", "NO_PUBLICADO", "A_VALIDAR", "A VALIDAR"}:
        status = SALARY_UNKNOWN
    else:
        status = SALARY_UNKNOWN

    return {
        "status": status,
        "floor_usd_month": gate.get("floor_usd_month", floor),
        "evaluated_usd_month": gate.get("evaluated_usd_month", ""),
        "salary_text": gate.get("salary_text", ""),
        "note": gate.get("note", ""),
    }


def format_evaluation_notes(
    scores: dict,
    summary: str,
    action: str,
    salary_gate: dict,
    category: str,
    recommended_action: str,
    score_category: str = "",
) -> str:
    scale_suffix = "/5"
    lines = [
        f"Salary gate: {category if category in {'A VALIDAR', 'DESCARTADA POR SALARIO'} else salary_gate['status']}",
        f"Salary floor: USD {salary_gate['floor_usd_month']}/mes",
    ]
    if salary_gate.get("evaluated_usd_month") != "":
        lines.append(f"Salary evaluated: USD {salary_gate['evaluated_usd_month']}/mes")
    if salary_gate.get("salary_text"):
        lines.append(f"Salary source: {salary_gate['salary_text']}")
    if salary_gate.get("note"):
        lines.append(f"Salary note: {salary_gate['note']}")

    lines.append(f"Category: {category}")
    if score_category and score_category != category:
        lines.append(f"Score category: {score_category}")
    lines.append(f"Recommended action: {action or recommended_action}")
    lines.append("")

    for cid, raw in scores.items():
        if isinstance(raw, dict):
            note = raw.get("note", "")
            lines.append(f"[{cid}: {raw.get('score', '')}{scale_suffix}] {note}".rstrip())
        else:
            lines.append(f"[{cid}: {raw}{scale_suffix}]")
    if summary:
        lines.append(f"\nSummary: {summary}")
    return "\n".join(lines)


# Sheets helpers

def _sheets():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools import sheets_manager as sm
    return sm


def update_evaluation_fields(
    position_id: str,
    score: str | float = "",
    rank: str | int = "",
    status: str = "",
    evaluation_notes: str = "",
):
    sm = _sheets()
    service = sm.get_sheets_service()
    values = sm.get_all_values(service, sm.POSITIONS_SHEET)
    row_idx = sm.find_row_by_id(values, position_id)

    if row_idx is None:
        print(f"Posicion no encontrada: {position_id}")
        sys.exit(1)

    if score != "":
        score = str(round(float(score), 1))

    sm.update_cell(service, sm.POSITIONS_SHEET, row_idx, sm.POSITIONS_HEADERS.index("score"), str(score))
    sm.update_cell(service, sm.POSITIONS_SHEET, row_idx, sm.POSITIONS_HEADERS.index("rank"), str(rank))
    sm.update_cell(
        service,
        sm.POSITIONS_SHEET,
        row_idx,
        sm.POSITIONS_HEADERS.index("evaluation_notes"),
        evaluation_notes,
    )
    if status:
        sm.update_cell(service, sm.POSITIONS_SHEET, row_idx, sm.POSITIONS_HEADERS.index("status"), status)


# Mode: list-pending

def list_pending(status: str, limit: int = 0):
    """Exporta las posiciones con el estado dado, para que el agente las evalue."""
    sm = _sheets()
    service = sm.get_sheets_service()
    values = sm.get_all_values(service, sm.POSITIONS_SHEET)

    if not values or len(values) < 2:
        print(json.dumps([], ensure_ascii=False))
        return

    headers = values[0]
    status_col = headers.index("status") if "status" in headers else 14

    pending = []
    for row in values[1:]:
        if len(row) > status_col and row[status_col] == status:
            record = dict(zip(headers, row))
            pending.append({
                "position_id": record.get("id", ""),
                "company": record.get("company", ""),
                "role": record.get("role", ""),
                "location": record.get("location", ""),
                "salary": record.get("salary", ""),
                "tipo": record.get("tipo", "full-time"),
                "url": record.get("url", ""),
                "description": record.get("description", "") or record.get("notes", ""),
            })

    if limit:
        pending = pending[:limit]

    print(json.dumps(pending, ensure_ascii=False, indent=2))
    print(f"\n# {len(pending)} posiciones con estado '{status}' listas para evaluar.", file=sys.stderr)


# Mode: write-scores

def write_scores(entries: list):
    """
    entries: lista de dicts con:
      {
        "position_id": str,
        "salary_gate": {
          "status": "PASS|FAIL|UNKNOWN",
          "evaluated_usd_month": number,
          "salary_text": str,
          "note": str
        },
        "scores": {criterion_id: number | {"score": n, "note": str}},
        "summary": str (opcional),
        "action": str (opcional)
      }
    """
    criteria = load_criteria()
    threshold = criteria.get("score_threshold_auto_discard", 45)

    sm = _sheets()
    service = sm.get_sheets_service()
    values = sm.get_all_values(service, sm.POSITIONS_SHEET)
    row_by_id = {row[0]: idx for idx, row in enumerate(values) if idx > 0 and row}

    # Columnas contiguas score(M)/rank(N)/status(O)/evaluation_notes(P): se
    # escriben en un solo rango por posicion y todo junto en un batch (evita 429).
    updates = []
    kept, validation, discarded_salary, discarded_score = 0, 0, 0, 0
    for entry in entries:
        pid = entry.get("position_id", "")
        if not pid:
            print("Entrada sin position_id, se ignora.")
            continue
        row_idx = row_by_id.get(pid)
        if row_idx is None:
            print(f"  [{pid}] no encontrada en Sheets, se ignora.")
            continue

        scores = entry.get("scores", {})
        summary = entry.get("summary", "")
        action = entry.get("action", "")
        salary_gate = normalize_salary_gate(entry, criteria)

        if salary_gate["status"] == SALARY_FAIL:
            notes = format_evaluation_notes(
                scores=scores,
                summary=summary,
                action=action,
                salary_gate=salary_gate,
                category="DESCARTADA POR SALARIO",
                recommended_action="Descartar automaticamente: no cumple el piso salarial.",
            )
            updates.append({
                "range": f"{sm.POSITIONS_SHEET}!M{row_idx + 1}:P{row_idx + 1}",
                "values": [["", "", "Rejected", notes]],
            })
            discarded_salary += 1
            print(f"  [{pid}] salario < USD {salary_gate['floor_usd_month']}/mes -> Rejected")
            continue

        final_score = compute_weighted_score(scores, criteria)
        score_category = category_for_score(final_score, criteria)

        if final_score < threshold:
            category = score_category["id"]
            recommended_action = score_category["recommended_action"]
        elif salary_gate["status"] == SALARY_UNKNOWN:
            category = "A VALIDAR"
            recommended_action = (
                "Validar salario antes de avanzar; si confirma el piso, seguir la categoria "
                f"{score_category['id']}."
            )
        else:
            category = score_category["id"]
            recommended_action = score_category["recommended_action"]

        notes = format_evaluation_notes(
            scores=scores,
            summary=summary,
            action=action,
            salary_gate=salary_gate,
            category=category,
            recommended_action=recommended_action,
            score_category=score_category["id"],
        )

        status = "Rejected" if final_score < threshold else "Evaluating"
        updates.append({
            "range": f"{sm.POSITIONS_SHEET}!M{row_idx + 1}:P{row_idx + 1}",
            "values": [[str(round(final_score, 1)), "0", status, notes]],
        })

        if final_score < threshold:
            discarded_score += 1
            print(f"  [{pid}] {final_score}/100 < {threshold} -> Rejected")
        elif salary_gate["status"] == SALARY_UNKNOWN:
            validation += 1
            print(f"  [{pid}] {final_score}/100 -> A VALIDAR salario")
        else:
            kept += 1
            print(f"  [{pid}] {final_score}/100 -> {category}")

    sm.batch_update_values(service, updates)

    print(
        "\n"
        f"{kept} evaluadas, {validation} a validar, "
        f"{discarded_salary} descartadas por salario, {discarded_score} descartadas por score. "
        "Re-rankeando..."
    )
    rerank_all()


# Mode: rerank

def rerank_all():
    """Recalcula el ranking global por tipo segun el score y lo escribe en Sheets."""
    sm = _sheets()
    service = sm.get_sheets_service()
    values = sm.get_all_values(service, sm.POSITIONS_SHEET)
    if not values or len(values) < 2:
        return

    headers = values[0]
    idx = {h: i for i, h in enumerate(headers)}
    score_i = idx.get("score", 12)
    rank_i = idx.get("rank", 13)
    status_i = idx.get("status", 14)
    tipo_i = idx.get("tipo", 4)

    tracks = {}
    for row_num, row in enumerate(values[1:], start=1):
        if len(row) <= score_i:
            continue
        status = row[status_i] if len(row) > status_i else ""
        if status in NON_RANKED_STATUSES:
            continue
        try:
            score = float(row[score_i] or 0)
        except ValueError:
            continue
        if score <= 0:
            continue
        tipo = row[tipo_i] if len(row) > tipo_i else "full-time"
        track = "gig" if tipo in ("gig", "freelance") else "full-time"
        tracks.setdefault(track, []).append((row_num, score))

    rank_col = chr(ord("A") + rank_i)
    updates = []
    for track, items in tracks.items():
        items.sort(key=lambda x: x[1], reverse=True)
        for rank, (row_num, score) in enumerate(items, 1):
            updates.append({
                "range": f"{sm.POSITIONS_SHEET}!{rank_col}{row_num + 1}",
                "values": [[str(rank)]],
            })

    # Un solo batch para todos los ranks (evita el limite de 60 writes/min).
    sm.batch_update_values(service, updates)
    print(f"Ranking actualizado: {len(updates)} posiciones re-rankeadas.")


# Mode: show-ranking

def print_ranking(min_score: float = 45, tipo: str = "full-time"):
    sm = _sheets()
    ranking = sm.get_ranking(min_score=min_score, tipo=tipo)
    if not ranking:
        print(f"No hay posiciones rankeadas con score >= {min_score} (tipo={tipo}).")
        return

    print(f"\n{'#':<4} {'Score':<7} {'Company':<25} {'Role':<35} {'Status':<20}")
    print("-" * 95)
    for i, pos in enumerate(ranking, 1):
        print(
            f"{i:<4} "
            f"{pos.get('score', ''):<7} "
            f"{str(pos.get('company', ''))[:24]:<25} "
            f"{str(pos.get('role', ''))[:34]:<35} "
            f"{pos.get('status', ''):<20}"
        )


# CLI

def main():
    _force_utf8()
    parser = argparse.ArgumentParser(
        description="Motor deterministico de evaluacion (el agente hace el razonamiento)."
    )
    parser.add_argument("--list-pending", action="store_true",
                        help="Exporta posiciones a evaluar")
    parser.add_argument("--status", default="Discovered",
                        help="Estado a listar (default: Discovered)")
    parser.add_argument("--limit", type=int, default=0, help="Maximo de posiciones a listar")

    parser.add_argument("--write-scores", action="store_true",
                        help="Escribe evaluaciones en Sheets")
    parser.add_argument("--data-file", help="Ruta a JSON con la lista de evaluaciones")
    parser.add_argument("--data", help="JSON inline con la lista de evaluaciones")

    parser.add_argument("--rerank", action="store_true", help="Recalcula el ranking global")
    parser.add_argument("--show-ranking", action="store_true", help="Muestra el ranking actual")
    parser.add_argument("--min-score", type=float, default=45, help="Score minimo para el ranking")
    parser.add_argument("--tipo", default="full-time", help="Track de ranking (full-time|gig)")
    args = parser.parse_args()

    if args.list_pending:
        list_pending(args.status, args.limit)
    elif args.write_scores:
        if args.data_file:
            entries = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
        elif args.data:
            entries = json.loads(args.data)
        else:
            print("Error: --write-scores requiere --data-file o --data")
            sys.exit(1)
        if isinstance(entries, dict):
            entries = [entries]
        write_scores(entries)
    elif args.rerank:
        rerank_all()
    elif args.show_ranking:
        print_ranking(min_score=args.min_score, tipo=args.tipo)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
