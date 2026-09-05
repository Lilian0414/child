from pathlib import Path


def test_browser_renders_all_core_allowed_grounding_actions() -> None:
    app = (Path(__file__).parents[4] / "apps" / "web" / "app.js").read_text()

    assert "for (const action of prompt.allowed_actions)" in app
    for action in ("confirm", "correct", "reject", "skip"):
        assert f"{action}:" in app
    assert "case 'character':\n      return { visible_description: text }" in app
