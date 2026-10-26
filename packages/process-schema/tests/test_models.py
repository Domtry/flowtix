from src.models import ProcessDocument, Step, Target, TargetStrategy


def test_minimal_process() -> None:
    doc = ProcessDocument(
        process={
            "id": "test-1",
            "name": "Test process",
            "steps": [
                {
                    "id": "step-1",
                    "type": "browser.navigate",
                    "params": {"url": "https://example.com"},
                }
            ],
        }
    )
    assert doc.schema_version == "1.0"
    assert len(doc.process.steps) == 1


def test_step_with_target() -> None:
    step = Step(
        id="fill-name",
        type="ui.fill",
        target=Target(strategy=TargetStrategy.DOM, selector="#name"),
        value="John",
    )
    assert step.target is not None
    assert step.target.strategy == TargetStrategy.DOM
