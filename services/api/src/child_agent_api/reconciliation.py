"""Deterministic semantic comparison and bounded grounding selection."""

from child_agent_api.domain.models import (
    GroundingPrompt,
    ObservationBatch,
    ObservationKind,
    ReconciliationCandidate,
    SemanticChange,
    WorldState,
)

MAX_GROUNDING_PROMPTS = 5
UNCERTAIN_CONFIDENCE = 0.5


def _canonical(world: WorldState) -> list[tuple[str, ObservationKind, dict[str, object]]]:
    values: list[tuple[str, ObservationKind, dict[str, object]]] = []
    values.extend(
        (item.character_id, ObservationKind.CHARACTER, {"name": item.name, **item.attributes})
        for item in world.characters
    )
    values.extend(
        (
            item.object_id,
            ObservationKind.OBJECT_COUNT if item.count != 1 else ObservationKind.OBJECT,
            {"label": item.type, "count": item.count},
        )
        for item in world.objects
    )
    values.extend(
        (
            item.relationship_id,
            ObservationKind.RELATIONSHIP,
            {"from_ref": item.from_ref, "to_ref": item.to_ref, "kind": item.kind},
        )
        for item in world.relationships
    )
    values.extend(
        (
            item.fact_id,
            ObservationKind.FACT,
            {
                "fact_id": item.fact_id,
                "subject_ref": item.subject_ref,
                "predicate": item.predicate,
                "value": item.value,
                "depends_on": item.depends_on,
            },
        )
        for item in world.facts
        if item.fact_id not in world.stale_fact_ids
    )
    return values


def _normalized(kind: ObservationKind, value: dict[str, object]) -> dict[str, object]:
    if kind in {ObservationKind.OBJECT, ObservationKind.OBJECT_COUNT}:
        return {"label": value.get("label", value.get("type")), "count": value.get("count", 1)}
    return value


def reconcile(
    revision_id: str, batch: ObservationBatch, world: WorldState
) -> list[ReconciliationCandidate]:
    """Compare meanings, preferring exact matches before one-to-one changes/removals."""
    current = _canonical(world)
    remaining = set(range(len(current)))
    results: list[ReconciliationCandidate] = []
    unmatched = []
    for item in batch.items:
        value = _normalized(item.kind, dict(item.candidate))
        exact = next(
            (
                index
                for index in sorted(remaining)
                if current[index][1] == item.kind
                or {current[index][1], item.kind}
                <= {ObservationKind.OBJECT, ObservationKind.OBJECT_COUNT}
                if _normalized(current[index][1], current[index][2]) == value
            ),
            None,
        )
        if exact is None:
            unmatched.append(item)
            continue
        remaining.remove(exact)
        ref, kind, old = current[exact]
        change = (
            SemanticChange.UNCERTAIN
            if item.confidence < UNCERTAIN_CONFIDENCE
            else SemanticChange.UNCHANGED
        )
        results.append(_candidate(revision_id, item.observation_id, change, kind, ref, old, value))

    for item in unmatched:
        compatible = [
            index
            for index in remaining
            if current[index][1] == item.kind
            or {current[index][1], item.kind}
            <= {ObservationKind.OBJECT, ObservationKind.OBJECT_COUNT}
        ]
        if compatible:
            index = compatible[0]
            remaining.remove(index)
            ref, kind, old = current[index]
            change = (
                SemanticChange.UNCERTAIN
                if item.confidence < UNCERTAIN_CONFIDENCE
                else SemanticChange.CHANGED
            )
            results.append(
                _candidate(
                    revision_id, item.observation_id, change, kind, ref, old, dict(item.candidate)
                )
            )
        else:
            change = (
                SemanticChange.UNCERTAIN
                if item.confidence < UNCERTAIN_CONFIDENCE
                else SemanticChange.ADDED
            )
            results.append(
                _candidate(
                    revision_id,
                    item.observation_id,
                    change,
                    item.kind,
                    None,
                    None,
                    dict(item.candidate),
                )
            )
    for index in sorted(remaining):
        ref, kind, old = current[index]
        results.append(_candidate(revision_id, None, SemanticChange.REMOVED, kind, ref, old, None))
    return results


def _candidate(
    revision_id: str,
    observation_id: str | None,
    change: SemanticChange,
    kind: ObservationKind,
    current_ref: str | None,
    current_value: dict[str, object] | None,
    proposed_value: dict[str, object] | None,
) -> ReconciliationCandidate:
    suffix = observation_id or current_ref or "unknown"
    return ReconciliationCandidate.model_validate(
        {
            "candidate_id": f"cand_{revision_id.removeprefix('rev_')}_{suffix}",
            "revision_id": revision_id,
            "change": change,
            "kind": kind,
            "current_ref": current_ref,
            "current_value": current_value,
            "observation_id": observation_id,
            "proposed_value": proposed_value,
            "requires_grounding": change != SemanticChange.UNCHANGED,
        }
    )


def select_prompts(candidates: list[ReconciliationCandidate]) -> list[GroundingPrompt]:
    priorities = {
        SemanticChange.CHANGED: 0,
        SemanticChange.REMOVED: 1,
        SemanticChange.ADDED: 2,
        SemanticChange.UNCERTAIN: 3,
        SemanticChange.UNCHANGED: 4,
    }
    selected = sorted(
        (item for item in candidates if item.requires_grounding),
        key=lambda item: (priorities[item.change], item.candidate_id),
    )[:MAX_GROUNDING_PROMPTS]
    return [
        GroundingPrompt(
            candidate_id=item.candidate_id,
            change=item.change,
            kind=item.kind,
            allowed_actions=(
                ["confirm", "correct", "reject", "skip"]
                if item.change == SemanticChange.REMOVED
                or item.kind in {ObservationKind.OBJECT, ObservationKind.OBJECT_COUNT}
                else ["correct", "reject", "skip"]
            ),
        )
        for item in selected
    ]
