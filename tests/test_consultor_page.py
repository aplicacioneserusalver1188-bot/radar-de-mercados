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

    def test_worker_keeps_wolfram_secret_server_side(self):
        worker = (ROOT / "worker" / "template.mjs").read_text(encoding="utf-8")
        self.assertIn("env.WOLFRAM_APP_ID", worker)
        self.assertIn('path !== "/api/wolfram"', worker)
        self.assertIn("WOLFRAM_MONTHLY_CAP", worker)
        self.assertIn("wolfram_usage_monthly", worker)
        self.assertNotIn("WOLFRAM_APP_ID=", worker)

    def test_worker_exposes_only_server_side_sec_and_binance_routes(self):
        worker = (ROOT / "worker" / "template.mjs").read_text(encoding="utf-8")
        page = (ROOT / "consultor.html").read_text(encoding="utf-8")
        self.assertIn('path === "/api/sec"', worker)
        self.assertIn('env.SEC_USER_AGENT', worker)
        self.assertIn('data-api.binance.vision', worker)
        self.assertNotIn('SEC_USER_AGENT', page)
        self.assertIn('/api/binance', page)

if __name__ == "__main__": unittest.main()
