"""Test Suite for Camera Privacy Person Detection & Frame Sanitization."""
import unittest
from core.security import PrivacyPersonFilter
from core.gemini_inventory_vision import GeminiInventoryVisionAnalyzer


class TestCameraPrivacy(unittest.TestCase):
    """Test person detection rejection and privacy guarantees for camera scanning."""

    def setUp(self):
        self.vision_analyzer = GeminiInventoryVisionAnalyzer()

    def test_clean_shelf_frame_passes_privacy_filter(self):
        # Empty mock image bytes without person markers
        mock_shelf_frame = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        has_person, msg = PrivacyPersonFilter.inspect_image_for_persons(mock_shelf_frame)
        self.assertFalse(has_person)

    def test_image_with_person_detected_generates_privacy_warning(self):
        # Image with person detection marker string
        person_frame = b"\xFF\xD8\xFFperson_detected_in_camera_frame_mock\x00"
        has_person, msg = PrivacyPersonFilter.inspect_image_for_persons(person_frame)
        self.assertTrue(has_person)
        self.assertIn("person", msg.lower())

        # Analyzer must return privacy warning and empty items
        result = self.vision_analyzer.analyze_image(person_frame)
        self.assertEqual(len(result.items), 0)
        self.assertTrue(any("PRIVACY_FILTER" in w for w in result.warnings))


if __name__ == "__main__":
    unittest.main()
