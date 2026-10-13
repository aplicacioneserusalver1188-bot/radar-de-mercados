import os
import unittest
from unittest.mock import patch
from integrations import fred_api, sec_edgar, wolfram, yahoo_finance

class IntegrationBoundariesTest(unittest.TestCase):
    def test_sec_rejects_bad_cik_before_network(self):
        with self.assertRaises(ValueError): sec_edgar.company_facts("AAPL")
    def test_sec_requires_identifying_agent(self):
        with patch.dict(os.environ, {"SEC_USER_AGENT": ""}, clear=False):
            with self.assertRaises(RuntimeError): sec_edgar.submissions("320193")
    def test_fred_requires_key(self):
        with patch.dict(os.environ, {"FRED_API_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError): fred_api.observations("VIXCLS")
    def test_fred_rejects_unsafe_series_name(self):
        with self.assertRaises(ValueError): fred_api.observations("VIXCLS&x=1")
    def test_yahoo_rejects_unsafe_symbol(self):
        with self.assertRaises(ValueError): yahoo_finance.latest_quote("AAPL;DROP")
    def test_wolfram_requires_app_id(self):
        with patch.dict(os.environ, {"WOLFRAM_APP_ID": ""}, clear=False):
            with self.assertRaises(RuntimeError): wolfram.query("inflation rate")
    def test_wolfram_rejects_empty_query(self):
        with self.assertRaises(ValueError): wolfram.query(" ")

if __name__ == "__main__": unittest.main()
