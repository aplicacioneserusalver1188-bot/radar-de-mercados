"""Cliente de solo lectura para las API públicas de SEC EDGAR.

No se usa desde GitHub Actions. SEC solicita una identificación de contacto
real; por eso el agente se configura en el entorno y nunca se incluye aquí.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://data.sec.gov"
CACHE_SECONDS = 3600
MIN_REQUEST_INTERVAL = 0.12
_cache = {}
_last_request = 0.0

def _cik(cik):
    value = str(cik).strip()
    if not value.isdecimal() or not 1 <= len(value) <= 10:
        raise ValueError("CIK inválido")
    return f"{int(value):010d}"

def _user_agent():
    agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in agent:
        raise RuntimeError("Configure SEC_USER_AGENT con nombre y correo de contacto real.")
    return agent

def _get(path):
    global _last_request
    now = time.monotonic()
    entry = _cache.get(path)
    if entry and now - entry[0] < CACHE_SECONDS:
        return entry[1]
    pause = MIN_REQUEST_INTERVAL - (now - _last_request)
    if pause > 0:
        time.sleep(pause)
    request = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": _user_agent(), "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise RuntimeError("SEC EDGAR limitó la consulta; espere y vuelva a intentarlo.") from error
        raise RuntimeError(f"SEC EDGAR devolvió HTTP {error.code} para {path}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError("No se pudo conectar con SEC EDGAR.") from error
    _last_request = time.monotonic()
    _cache[path] = (_last_request, data)
    return data

def company_facts(cik):
    """Devuelve hechos XBRL reales de SEC para un CIK numérico."""
    return _get(f"/api/xbrl/companyfacts/CIK{_cik(cik)}.json")

def submissions(cik):
    """Devuelve el historial de presentaciones de una empresa."""
    return _get(f"/submissions/CIK{_cik(cik)}.json")
