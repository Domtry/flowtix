"""Tests for the event-to-scenario transformer."""

from agents.browser.src.recorder import EventType, RecordedEvent
from agents.browser.src.transformer import transform_events


def _evt(event_type: str, **kwargs) -> RecordedEvent:
    return RecordedEvent(timestamp=1.0, event_type=event_type, **kwargs)


def test_navigate_produces_browser_navigate_step():
    events = [_evt(EventType.NAVIGATE, url="https://example.com")]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "browser.navigate"
    assert steps[0]["params"]["url"] == "https://example.com"


def test_click_produces_ui_click_step():
    events = [
        _evt(EventType.CLICK, target={"tag": "button", "selector": "#submit", "text": "Submit", "name": "", "role": "", "ariaLabel": "", "rect": None}),
    ]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "ui.click"
    assert steps[0]["target"]["selector"] == "#submit"


def test_input_events_are_merged():
    target = {"tag": "input", "selector": "#name", "text": "", "name": "name", "role": "", "ariaLabel": "", "rect": None}
    events = [
        _evt(EventType.INPUT, target=target, value="J"),
        _evt(EventType.INPUT, target=target, value="Jo"),
        _evt(EventType.INPUT, target=target, value="John"),
    ]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "ui.fill"
    assert steps[0]["value"] == "John"


def test_select_change_produces_ui_select():
    target = {"tag": "select", "selector": "#country", "text": "", "name": "country", "role": "", "ariaLabel": "", "rect": None}
    events = [_evt(EventType.CHANGE, target=target, value="FR")]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "ui.select"
    assert steps[0]["value"] == "FR"


def test_keydown_produces_keyboard_press():
    events = [_evt(EventType.KEYDOWN, metadata={"key": "Enter", "ctrl": False, "alt": False, "shift": False})]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "keyboard.press"
    assert steps[0]["params"]["key"] == "Enter"


def test_ctrl_combo_keydown():
    events = [_evt(EventType.KEYDOWN, metadata={"key": "s", "ctrl": True, "alt": False, "shift": False})]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert steps[0]["params"]["key"] == "Control+s"


def test_duplicate_navigate_filtered():
    events = [
        _evt(EventType.NAVIGATE, url="https://example.com"),
        _evt(EventType.NAVIGATE, url="https://example.com"),
    ]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert len(steps) == 1


def test_scroll_produces_ui_scroll():
    events = [_evt(EventType.SCROLL, metadata={"scrollX": 0, "scrollY": 500})]
    result = transform_events(events)
    steps = result["process"]["steps"]
    assert steps[0]["type"] == "ui.scroll"
    assert steps[0]["params"]["y"] == 500


def test_full_form_scenario():
    """Simulates: navigate, fill two fields, click submit."""
    events = [
        _evt(EventType.NAVIGATE, url="https://app.test/form"),
        _evt(EventType.INPUT, target={"tag": "input", "selector": "#email", "text": "", "name": "email", "role": "", "ariaLabel": "", "rect": None}, value="test@test.com"),
        _evt(EventType.CLICK, target={"tag": "input", "selector": "#password", "text": "", "name": "password", "role": "", "ariaLabel": "", "rect": None}),
        _evt(EventType.INPUT, target={"tag": "input", "selector": "#password", "text": "", "name": "password", "role": "", "ariaLabel": "", "rect": None}, value="secret"),
        _evt(EventType.CLICK, target={"tag": "button", "selector": "#login", "text": "Login", "name": "", "role": "button", "ariaLabel": "Login", "rect": None}),
    ]
    result = transform_events(events, process_name="Login")
    process = result["process"]
    assert process["name"] == "Login"
    steps = process["steps"]
    assert steps[0]["type"] == "browser.navigate"
    assert steps[1]["type"] == "ui.fill"
    assert steps[1]["value"] == "test@test.com"
    assert steps[2]["type"] == "ui.click"
    assert steps[3]["type"] == "ui.fill"
    assert steps[3]["value"] == "secret"
    assert steps[4]["type"] == "ui.click"
    assert steps[4]["target"]["selector"] == "#login"
