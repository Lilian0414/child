"""Reproducible synthetic observer benchmark CLI."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from child_agent_api.observer import (
    FakeObserverProvider,
    ImageInput,
    ObservationPipeline,
    ObserverFailure,
)
from child_agent_api.providers.openai_compatible import OpenAICompatibleObserver


@dataclass
class CaseResult:
    case_id: str
    provider: str
    model: str
    parse_schema_success: bool
    repair_used: bool
    latency_ms: int
    error_category: str | None
    policy_violations: list[str]
    expected_facts_matched: list[str]
    expected_facts_missed: list[str]
    ambiguous_stayed_tentative: bool


def _facts(items: list[Any]) -> set[str]:
    return {
        f"{item.kind.value}:{json.dumps(item.candidate, sort_keys=True, separators=(',', ':'))}"
        for item in items
    }


def run_fixture(case: dict[str, Any]) -> CaseResult:
    error = TimeoutError("synthetic timeout") if case.get("provider_error") == "timeout" else None
    provider = FakeObserverProvider(
        json.dumps(case.get("response"))
        if not isinstance(case.get("response"), str)
        else case["response"],
        repair_response=(
            json.dumps(case["repair_response"])
            if isinstance(case.get("repair_response"), dict)
            else case.get("repair_response")
        ),
        error=error,
    )
    expected = set(case.get("expected_facts", []))
    try:
        result = ObservationPipeline(provider).run(
            ImageInput(case["media_id"], f"synthetic:{case['case_id']}".encode(), "image/svg+xml"),
            batch_id=f"obsb_{case['case_id'].lower().replace('-', '_')}",
            timeout_seconds=1,
        )
        actual = _facts(result.batch.items)
        ambiguous = all(
            item.needs_confirmation and item.status.value == "proposed"
            for item in result.batch.items
        )
        return CaseResult(
            case["case_id"],
            result.provider,
            result.model,
            True,
            result.repair_used,
            result.latency_ms,
            None,
            [],
            sorted(expected & actual),
            sorted(expected - actual),
            ambiguous,
        )
    except ObserverFailure as failure:
        return CaseResult(
            case["case_id"],
            provider.provider_id,
            provider.model_id,
            False,
            failure.repair_used,
            0,
            failure.category.value,
            [str(failure)] if failure.category.value == "policy_violation" else [],
            [],
            sorted(expected),
            True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("fake", "live"), default="fake")
    parser.add_argument("--json", type=Path, default=Path("build/observer-benchmark.json"))
    parser.add_argument("--markdown", type=Path, default=Path("build/observer-benchmark.md"))
    args = parser.parse_args()
    fixture_path = Path(__file__).parents[2] / "benchmarks" / "observer_cases.json"
    cases = json.loads(fixture_path.read_text())
    if args.provider == "live":
        required = ("CHILD_OBSERVER_API_KEY", "CHILD_OBSERVER_MODEL", "CHILD_OBSERVER_BASE_URL")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            parser.error(f"live benchmark not run; missing: {', '.join(missing)}")
        # Constructing the isolated adapter validates configuration. Live fixture execution is
        # intentionally explicit and cannot silently fall back to deterministic evidence.
        OpenAICompatibleObserver(
            api_key=os.environ[required[0]],
            model=os.environ[required[1]],
            base_url=os.environ[required[2]],
        )
        parser.error("live benchmark requires an operator-supplied media runner; not run")
    results = [run_fixture(case) for case in cases]
    payload = {
        "benchmark_version": "observer-benchmark.v1",
        "fixture_count": len(cases),
        "results": [asdict(item) for item in results],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n")
    passed = sum(
        (item.error_category == case.get("expected_error") and not item.expected_facts_missed)
        for item, case in zip(results, cases, strict=True)
    )
    args.markdown.write_text(
        "# Observer benchmark\n\n"
        f"Provider: `fake/deterministic-v1`  \nCases: {len(cases)}  \n"
        f"Expected outcomes: {passed}/{len(cases)}\n\n"
        + "| Case | Schema | Repair | Error | Tentative |\n|---|---:|---:|---|---:|\n"
        + "".join(
            f"| {r.case_id} | {r.parse_schema_success} | {r.repair_used} | "
            f"{r.error_category or '-'} | {r.ambiguous_stayed_tentative} |\n"
            for r in results
        )
    )
    print(
        f"observer benchmark: {passed}/{len(cases)} expected outcomes; "
        f"json={args.json}; markdown={args.markdown}"
    )


if __name__ == "__main__":
    main()
