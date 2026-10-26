"""FlowtTix Windows Desktop Agent — pywinauto-based automation."""

from .agent import WindowsAgent
from .locators import locate_element
from .recorder import WindowsRecorder
from .replay import WindowsReplayEngine
from .transformer import transform_windows_events

__all__ = [
    "WindowsAgent",
    "WindowsRecorder",
    "WindowsReplayEngine",
    "locate_element",
    "transform_windows_events",
]
