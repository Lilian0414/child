from pathlib import Path


def test_browser_renders_all_core_allowed_grounding_actions() -> None:
    app = (Path(__file__).parents[4] / "apps" / "web" / "app.js").read_text()

    assert "for (const action of prompt.allowed_actions)" in app
    # "skip" is intentionally not a button the child clicks — Core already
    # treats an unanswered candidate as skipped (`resolve_revision` defaults
    # any prompt with no supplied decision to "skip"), so the UI only needs
    # explicit actions for the choices a child actually makes.
    for action in ("confirm", "correct", "reject"):
        assert f"{action}:" in app
    assert "case 'character':\n      return { visible_description: text }" in app
