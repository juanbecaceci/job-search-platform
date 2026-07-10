"""`evaluate_batch` job: score one or more positions against the active
scoring config, via a one-shot agent call per position (no chat thread, no
`proposed_changes` HITL gate — this writes the evaluation straight onto the
`Position` row, matching how PLATFORM_SPEC.md §5 describes it: a `202` job
whose result is the evaluation itself).

The agent supplies the per-criterion scores + salary gate (reading the JD is
reasoning, not arithmetic); `core/evaluate_position.py`'s pure functions turn
that into the final weighted score/category (core/CLAUDE.md: reuse them
rather than reimplementing). Deliberately does NOT change `Position.status` —
pipeline transitions stay solely on `POST /positions/{id}/status`.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.agent.one_shot import run_agent_text
from api.agent.output_parser import extract_fenced_block
from api.agent.task_prompts import build_evaluation_prompt
from api.config import ROOT_DIR
from api.models import Position, PositionEvent, ScoringConfig
from api.models.enums import Actor, PositionEventType

_CORE_DIR = str(ROOT_DIR / "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core.evaluate_position import (  # noqa: E402
    category_for_score,
    compute_weighted_score,
    format_evaluation_notes,
    normalize_salary_gate,
)


def _config_dict(cfg: ScoringConfig) -> dict[str, Any]:
    return {
        "scale_max": cfg.scale_max,
        "criteria": cfg.criteria,
        "categories": cfg.categories,
        "salary_gate": cfg.salary_gate,
        "score_threshold_auto_discard": cfg.score_threshold_auto_discard,
    }


def _evaluate_one(position: Position, config: ScoringConfig) -> dict[str, Any]:
    criteria_dict = _config_dict(config)
    company_name = position.company.name if position.company else None
    system, user_prompt = build_evaluation_prompt(
        {
            "role": position.role,
            "description": position.description,
            "salary_raw": position.salary_raw,
            "location": position.location,
            "remote": position.remote,
            "tipo": position.tipo,
            "url": position.url,
        },
        company_name,
        criteria_dict,
    )
    text = run_agent_text(system, user_prompt)
    block = extract_fenced_block(text, "json")
    if not block:
        raise ValueError(f"agent returned no parsable output for {position.id!r}")
    parsed = json.loads(block)

    scores = {k: v for k, v in parsed.items() if k not in ("salary_gate", "summary")}
    final_score = compute_weighted_score(scores, criteria_dict)
    salary_gate = normalize_salary_gate(parsed, criteria_dict)
    score_category = category_for_score(final_score, criteria_dict)
    threshold = criteria_dict.get("score_threshold_auto_discard", 45)

    if salary_gate["status"] == "FAIL":
        category = "DESCARTADA POR SALARIO"
        recommended_action = "Descartar automáticamente: no cumple el piso salarial."
    elif final_score < threshold:
        category = score_category["id"]
        recommended_action = score_category["recommended_action"]
    elif salary_gate["status"] == "UNKNOWN":
        category = "A VALIDAR"
        recommended_action = (
            "Validar salario antes de avanzar; si confirma el piso, seguir la "
            f"categoría {score_category['id']}."
        )
    else:
        category = score_category["id"]
        recommended_action = score_category["recommended_action"]

    notes = format_evaluation_notes(
        scores=scores,
        summary=parsed.get("summary", ""),
        action=recommended_action,
        salary_gate=salary_gate,
        category=category,
        recommended_action=recommended_action,
        score_category=score_category["id"],
    )

    weight_by_id = {c["id"]: c["weight"] for c in criteria_dict["criteria"]}
    evaluation = {
        cid: {
            "score": (raw.get("score") if isinstance(raw, dict) else raw),
            "weight": weight_by_id.get(cid, 0),
            "rationale": raw.get("rationale", "") if isinstance(raw, dict) else "",
        }
        for cid, raw in scores.items()
        if cid in weight_by_id
    }

    return {
        "score": final_score,
        "score_category": category,
        "evaluation": evaluation,
        "summary": notes,
        "recommended_action": recommended_action,
        "scoring_config_version": config.version,
    }


def handle(session: Session, job, params: dict[str, Any], progress) -> dict[str, Any]:
    position_ids: list[str] = params["position_ids"]
    config = session.scalar(select(ScoringConfig).where(ScoringConfig.is_active.is_(True)))
    if config is None:
        raise ValueError("No active scoring config")

    total = max(len(position_ids), 1)
    evaluated: list[str] = []
    failed: dict[str, str] = {}

    for idx, pid in enumerate(position_ids):
        progress(idx / total, f"evaluating {pid}")
        position = session.get(Position, pid, options=[selectinload(Position.company)])
        if position is None:
            failed[pid] = "position not found"
            continue
        try:
            result = _evaluate_one(position, config)
        except Exception as exc:  # noqa: BLE001 — one bad eval shouldn't fail the batch
            failed[pid] = str(exc)
            continue

        old_score = position.score
        position.score = result["score"]
        position.score_category = result["score_category"]
        position.evaluation = result["evaluation"]
        position.summary = result["summary"]
        position.recommended_action = result["recommended_action"]
        position.scoring_config_version = result["scoring_config_version"]
        session.add(
            PositionEvent(
                position_id=pid,
                event_type=PositionEventType.SCORE_CHANGE.value,
                from_value=str(old_score) if old_score is not None else None,
                to_value=str(result["score"]),
                payload={"score_category": result["score_category"]},
                actor=Actor.AGENT.value,
            )
        )
        session.commit()
        evaluated.append(pid)
        progress((idx + 1) / total, f"evaluated {pid}")

    return {"evaluated": evaluated, "failed": failed, "count": len(evaluated)}
