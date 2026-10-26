"""Integration test: record events -> transform -> produce valid scenario.

This test does NOT launch a real browser. It simulates the full pipeline
from raw events to a validated process definition.
"""

from packages.process_schema.src.models import ProcessDocument
from agents.browser.src.recorder import EventType, RecordedEvent
from agents.browser.src.transformer import transform_events


def _evt(event_type: str, **kwargs) -> RecordedEvent:
    return RecordedEvent(timestamp=1.0, event_type=event_type, **kwargs)


def test_end_to_end_pipeline():
    """Simulates: navigate -> fill form -> click submit -> validate schema."""

    # 1. Simulated recorded events
    events = [
        _evt(EventType.NAVIGATE, url="https://crm.example.com/new-case"),
        _evt(
            EventType.INPUT,
            target={"tag": "input", "selector": "#ref", "text": "", "name": "ref", "role": "textbox", "ariaLabel": "Reference", "rect": {"x": 100, "y": 200, "w": 300, "h": 30}},
            value="CASE-2024-001",
        ),
        _evt(
            EventType.CHANGE,
            target={"tag": "select", "selector": "#priority", "text": "", "name": "priority", "role": "", "ariaLabel": "", "rect": None},
            value="high",
        ),
        _evt(
            EventType.CLICK,
            target={"tag": "button", "selector": "#save", "text": "Save", "name": "", "role": "button", "ariaLabel": "Save case", "rect": {"x": 400, "y": 500, "w": 80, "h": 36}},
        ),
    ]

    # 2. Transform to scenario
    scenario = transform_events(events, process_name="Create CRM Case")

    # 3. Validate against schema
    doc = ProcessDocument(**scenario)
    assert doc.schema_version == "1.0"
    assert doc.process.name == "Create CRM Case"
    assert len(doc.process.steps) == 4

    steps = doc.process.steps
    assert steps[0].type == "browser.navigate"
    assert steps[1].type == "ui.fill"
    assert steps[1].value == "CASE-2024-001"
    assert steps[2].type == "ui.select"
    assert steps[2].value == "high"
    assert steps[3].type == "ui.click"
    assert steps[3].target is not None
    assert steps[3].target.selector == "#save"


def test_scenario_with_keyboard_shortcuts():
    events = [
        _evt(EventType.NAVIGATE, url="https://app.test"),
        _evt(EventType.KEYDOWN, metadata={"key": "s", "ctrl": True, "alt": False, "shift": False}),
    ]
    scenario = transform_events(events)
    doc = ProcessDocument(**scenario)
    assert len(doc.process.steps) == 2
    assert doc.process.steps[1].type == "keyboard.press"
    assert doc.process.steps[1].params["key"] == "Control+s"
