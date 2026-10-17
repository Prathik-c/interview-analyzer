"""
tests/test_pdf_layout.py — Unit tests for PDF layout, text extraction, formatting, and contrast.
"""

import os
import json
import re
import unittest
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from backend.app.schemas.interview import AssessmentSession
from backend.app.services.report_service import (
    report_service,
    clean_text,
    DARK_BG,
    SURFACE,
    ACCENT,
    GREEN,
    AMBER,
    RED,
    TEXT_MAIN,
    TEXT_MUTED,
    WHITE,
)


def relative_luminance(rgb):
    """Compute relative luminance according to WCAG 2.1."""
    srgb = [c / 255.0 for c in rgb]
    lum = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2]


def contrast_ratio(c1, c2):
    """Compute contrast ratio between two RGB colors (1:1 to 21:1)."""
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestPDFLayout(unittest.TestCase):
    """Test PDF generation, layout constraints, contrast, and formatting."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.scratch_dir = cls.repo_root / "scratch"
        cls.scratch_dir.mkdir(parents=True, exist_ok=True)
        cls.session_path = cls.repo_root / "data" / "sessions" / "e91a376c-77d8-4143-abd1-90af5c4c8494.json"

        with open(cls.session_path, "r", encoding="utf-8") as f:
            cls.session_data = json.load(f)

        cls.session = AssessmentSession(**cls.session_data)
        cls.pdf_bytes = report_service.generate_pdf_report(cls.session)

        cls.output_pdf_path = cls.scratch_dir / "test_report.pdf"
        with open(cls.output_pdf_path, "wb") as f:
            f.write(cls.pdf_bytes)

    def test_pdf_layout_and_content_assertions(self):
        """
        Asserts:
        - no line ends with 'Frames S'
        - every 'Duration:' is followed by a number or 'not available'
        - page count is at most 6
        - no page has fewer than 5 lines of text
        - '????' does not appear
        """
        with pdfplumber.open(self.output_pdf_path) as pdf:
            page_count = len(pdf.pages)
            self.assertLessEqual(page_count, 6, f"Expected at most 6 pages, got {page_count}")

            for idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                lines = [line.strip() for line in text.splitlines() if line.strip()]

                # No page has fewer than 5 lines of text
                self.assertGreaterEqual(
                    len(lines),
                    5,
                    f"Page {idx + 1} has only {len(lines)} lines, expected at least 5 lines",
                )

                # '????' does not appear
                self.assertNotIn("????", text, f"Found '????' on page {idx + 1}")

                for line in lines:
                    # No line ends with 'Frames S'
                    self.assertFalse(
                        line.endswith("Frames S"),
                        f"Line truncated with 'Frames S' on page {idx + 1}: {line}",
                    )

                    # Every 'Duration:' is followed by a number or 'not available'
                    if "Duration:" in line:
                        after_dur = line.split("Duration:", 1)[1].strip()
                        matches = (
                            after_dur.startswith("not available")
                            or bool(re.match(r"^\d+(\.\d+)?\s*s", after_dur))
                        )
                        self.assertTrue(
                            matches,
                            f"Duration: not followed by number or 'not available' on page {idx + 1}: '{line}'",
                        )

    def test_non_latin_transcript_replaced_without_question_marks(self):
        """Non-Latin characters must be cleanly replaced with [non-English text] and never '????'."""
        data_copy = json.loads(json.dumps(self.session_data))
        data_copy["submissions"]["1"]["transcript"] = "नमस्ते दुनिया and 你好世界 and Telugu తెలుగు"
        test_session = AssessmentSession(**data_copy)
        pdf_bytes = report_service.generate_pdf_report(test_session)

        test_pdf = self.scratch_dir / "temp_non_latin.pdf"
        with open(test_pdf, "wb") as f:
            f.write(pdf_bytes)

        try:
            with pdfplumber.open(test_pdf) as pdf:
                full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                self.assertNotIn("????", full_text)
                self.assertIn("[non-English text]", full_text)
        finally:
            if test_pdf.exists():
                test_pdf.unlink()

    def test_text_colors_and_contrast_ratio(self):
        """
        Verify all text colors have WCAG contrast >= 4.5:
        - Body, labels, values are dark (contrast >= 4.5 on white)
        - Secondary text no lighter than RGB (90, 90, 90)
        - Header band text is white on dark band
        - Page 1 and page 2 render to PNG without errors
        """
        white = (255, 255, 255)

        # Body text colors against white page background
        page_colors = {
            "TEXT_MAIN": TEXT_MAIN,
            "TEXT_MUTED": TEXT_MUTED,
            "ACCENT": ACCENT,
            "GREEN": GREEN,
            "AMBER": AMBER,
            "RED": RED,
        }

        for name, color in page_colors.items():
            cr = contrast_ratio(color, white)
            self.assertGreaterEqual(
                cr,
                4.5,
                f"Color {name} {color} contrast ratio against white is {cr:.2f}, expected >= 4.5",
            )

        # Secondary text no lighter than (90, 90, 90)
        self.assertLessEqual(TEXT_MUTED[0], 90)
        self.assertLessEqual(TEXT_MUTED[1], 90)
        self.assertLessEqual(TEXT_MUTED[2], 90)

        # White on dark header bands
        header_cr = contrast_ratio(WHITE, DARK_BG)
        self.assertGreaterEqual(
            header_cr,
            4.5,
            f"WHITE on DARK_BG contrast ratio is {header_cr:.2f}, expected >= 4.5",
        )

        surface_cr = contrast_ratio(WHITE, SURFACE)
        self.assertGreaterEqual(
            surface_cr,
            4.5,
            f"WHITE on SURFACE contrast ratio is {surface_cr:.2f}, expected >= 4.5",
        )

        # Render page 1 and page 2 to PNG using pypdfium2 and save test_report_page1.png
        doc = pdfium.PdfDocument(self.output_pdf_path)
        img_page1 = doc[0].render(scale=2).to_pil()
        page1_png_path = self.scratch_dir / "test_report_page1.png"
        img_page1.save(page1_png_path)
        self.assertTrue(page1_png_path.exists())

        img_page2 = doc[1].render(scale=2).to_pil()
        self.assertIsNotNone(img_page2)


if __name__ == "__main__":
    unittest.main()
