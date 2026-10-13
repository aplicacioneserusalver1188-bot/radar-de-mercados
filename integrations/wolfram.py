"""Cliente optativo para cálculos de Wolfram|Alpha mediante AppID de entorno."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.wolframalpha.com/v2/query"

def query(input_text):
    if not isinstance(input_text, str) or not input_text.strip() or len(input_text) > 500:
        raise ValueError("Consulta de Wolfram inválida")
    app_id = os.environ.get("WOLFRAM_APP_ID", "").strip()
    if not app_id:
        raise RuntimeError("WOLFRAM_APP_ID no configurado; la fuente es opcional.")
    params = urllib.parse.urlencode({"appid": app_id, "input": input_text.strip(), "output": "JSON", "format": "plaintext"})
    try:
        with urllib.request.urlopen(API_URL + "?" + params, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Wolfram|Alpha devolvió HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError("No se pudo conectar con Wolfram|Alpha.") from error
