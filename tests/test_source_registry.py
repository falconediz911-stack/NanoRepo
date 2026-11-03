from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "validate_source_event.py"
)
SPEC = importlib.util.spec_from_file_location("validate_source_event", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
source_events = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source_events)


class SourceEventValidationTests(unittest.TestCase):
    def test_registered_iso_event_is_metadata_only(self) -> None:
        result = source_events.validate_event(
            "nanoos.iso.published",
            "falconediz911-stack/NanoOS-Beta21-ISO",
        )
        self.assertIn("metadata-only", result)

    def test_registered_website_event_is_metadata_only(self) -> None:
        result = source_events.validate_event(
            "nanoos.website.feed.updated",
            "falconediz911-stack/nanoos-website",
        )
        self.assertIn("metadata-only", result)

    def test_registered_tool_package_is_allowed(self) -> None:
        result = source_events.validate_event(
            "nanoos.tool.source.updated",
            "falconediz911-stack/NanoRepo",
            "nanoos-cpu-info",
        )
        self.assertIn("nanoos-cpu-info", result)

    def test_unknown_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            source_events.validate_event(
                "nanoos.iso.published",
                "someone/else",
            )

    def test_wrong_event_for_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            source_events.validate_event(
                "nanoos.tool.source.updated",
                "falconediz911-stack/NanoOS-Beta21-ISO",
                "nanoos-cpu-info",
            )

    def test_unregistered_package_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            source_events.validate_event(
                "nanoos.tool.source.updated",
                "falconediz911-stack/NanoRepo",
                "some-unregistered-package",
            )


if __name__ == "__main__":
    unittest.main()
