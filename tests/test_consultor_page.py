import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ConsultorPageTest(unittest.TestCase):
    def test_page_has_real_series_and_no_embedded_credentials(self):
        page = (ROOT / "consultor.html").read_text(encoding="utf-8")
        self.assertIn("VIXCLS", page)
        self.assertIn("Wolfram", page)
        self.assertNotIn("FRED_API_KEY", page)
        self.assertNotIn("WOLFRAM_APP_ID", page)
    def test_review_build_copies_consultor(self):
        build = (ROOT / "scripts" / "build_review.py").read_text(encoding="utf-8")
        self.assertIn('"consultor.html"', build)

if __name__ == "__main__": unittest.main()
