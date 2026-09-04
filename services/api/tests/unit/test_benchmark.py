import json
from pathlib import Path
from xml.etree import ElementTree

from child_agent_api.benchmark import run_live
from child_agent_api.observer import FakeObserverProvider

FIXTURE_ROOT = Path(__file__).parents[2] / "benchmarks"


def test_all_benchmark_media_are_valid_repository_owned_svg() -> None:
    cases = json.loads((FIXTURE_ROOT / "observer_cases.json").read_text())
    assert len(cases) == 12
    for case in cases:
        media = FIXTURE_ROOT / case["media_file"]
        assert media.is_relative_to(FIXTURE_ROOT)
        assert ElementTree.fromstring(media.read_bytes()).tag == "{http://www.w3.org/2000/svg}svg"


def test_live_runner_sends_fixture_to_configured_provider() -> None:
    case = {
        "case_id": "LIVE-01",
        "media_id": "med_live01",
        "media_file": "media/g_01.svg",
        "expected_facts": ['object:{"label":"sun"}'],
    }
    provider = FakeObserverProvider(
        '{"items":[{"observation_id":"obs_live01","kind":"object",'
        '"candidate":{"label":"sun"},"confidence":0.8}]}'
    )
    result = run_live(case, provider, FIXTURE_ROOT)  # type: ignore[arg-type]
    assert provider.observe_calls == 1
    assert result.parse_schema_success is True
    assert result.expected_facts_missed == []
