"""Cliente FRED API opcional; el radar existente sigue usando sus CSV públicos."""
import json
import os
import urllib.parse
import urllib.request

def observations(series_id, limit=100):
    if not series_id or not all(c.isalnum() or c in "_-" for c in series_id):
        raise ValueError("Serie FRED inválida")
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY no configurada; las series actuales siguen funcionando vía CSV.")
    params = urllib.parse.urlencode({"series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": max(1, min(int(limit), 1000))})
    with urllib.request.urlopen("https://api.stlouisfed.org/fred/series/observations?" + params, timeout=20) as response:
        return json.load(response)
