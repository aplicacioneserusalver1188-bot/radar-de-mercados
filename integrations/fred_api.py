"""Cliente FRED API opcional; el radar existente sigue usando sus CSV públicos."""
import json
import os
import urllib.parse
import urllib.error
import urllib.request

API_URL = "https://api.stlouisfed.org/fred/series/observations"

def observations(series_id, limit=100, *, observation_start=None, observation_end=None):
    if not series_id or not all(c.isalnum() or c in "_-" for c in series_id):
        raise ValueError("Serie FRED inválida")
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY no configurada; las series actuales siguen funcionando vía CSV.")
    params = {"series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": max(1, min(int(limit), 1000))}
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    try:
        with urllib.request.urlopen(API_URL + "?" + urllib.parse.urlencode(params), timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"FRED API devolvió HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError("No se pudo conectar con FRED API.") from error
