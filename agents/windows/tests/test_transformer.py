"""Tests for Windows event transformer."""

from agents.windows.src.recorder import WindowsEvent
from agents.windows.src.transformer import transform_windows_events


def test_click_event():
    events = [WindowsEvent(
        timestamp=0.5, event_type="click",
        automation_id="btnOK", name="OK", control_type="Button",
        coordinates={"x": 100, "y": 200},
    )]
    doc = transform_windows_events(events)
    steps = doc["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["type"] == "win.click"
    assert steps[0]["target"]["selector"] == "#btnOK"


def test_type_event():
    events = [WindowsEvent(
        timestamp=1.0, event_type="type",
        name="Username", control_type="Edit",
        value="alice",
    )]
    doc = transform_windows_events(events)
    steps = doc["process"]["steps"]
    assert steps[0]["type"] == "win.fill"
    assert steps[0]["value"] == "alice"


def test_key_press():
    events = [WindowsEvent(timestamp=2.0, event_type="key_press", key="ctrl+s")]
    doc = transform_windows_events(events)
    assert doc["process"]["steps"][0]["type"] == "win.key_press"
    assert doc["process"]["steps"][0]["params"]["key"] == "ctrl+s"


def test_window_action():
    events = [WindowsEvent(
        timestamp=3.0, event_type="window.maximize",
        window_title="Notepad",
    )]
    doc = transform_windows_events(events)
    assert doc["process"]["steps"][0]["type"] == "win.window_maximize"


def test_merge_consecutive_types():
    events = [
        WindowsEvent(timestamp=1.0, event_type="type", name="Field", control_type="Edit", value="abc"),
        WindowsEvent(timestamp=1.5, event_type="type", name="Field", control_type="Edit", value="def"),
    ]
    doc = transform_windows_events(events)
    steps = doc["process"]["steps"]
    assert len(steps) == 1
    assert steps[0]["value"] == "def"


def test_right_click():
    events = [WindowsEvent(
        timestamp=0.5, event_type="right_click",
        name="File", control_type="MenuItem",
        coordinates={"x": 50, "y": 50},
    )]
    doc = transform_windows_events(events)
    assert doc["process"]["steps"][0]["type"] == "win.right_click"


def test_target_accessibility_fallback():
    events = [WindowsEvent(
        timestamp=0.5, event_type="click",
        name="Submit", control_type="Button",
        coordinates={"x": 100, "y": 200},
    )]
    doc = transform_windows_events(events)
    target = doc["process"]["steps"][0]["target"]
    assert target["strategy"] == "accessibility"
    assert target["role"] == "Button"


def test_coordinates_only():
    events = [WindowsEvent(
        timestamp=0.5, event_type="click",
        coordinates={"x": 300, "y": 400},
    )]
    doc = transform_windows_events(events)
    target = doc["process"]["steps"][0]["target"]
    assert target["strategy"] == "coordinates"
