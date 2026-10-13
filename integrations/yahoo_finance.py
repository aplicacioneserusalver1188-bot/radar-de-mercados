"""Adaptador local y efímero de Yahoo Finance.

No se ejecuta en GitHub Actions ni persiste resultados: Yahoo no se usa aquí
como fuente redistribuida. La persona usuaria debe revisar sus términos e
instalar voluntariamente ``yfinance`` en su entorno local.
"""
import re

_SYMBOL = re.compile(r"^[A-Z0-9.^=-]{1,15}$")

def _symbol(symbol):
    value = str(symbol).strip().upper()
    if not _SYMBOL.fullmatch(value):
        raise ValueError("Símbolo de Yahoo Finance inválido")
    return value

def latest_quote(symbol):
    """Devuelve la última vela disponible, sin recomendaciones ni almacenamiento."""
    ticker = _symbol(symbol)
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError("Instale yfinance localmente para habilitar esta consulta opcional.") from error
    history = yf.Ticker(ticker).history(period="5d", auto_adjust=False, actions=False)
    if history.empty:
        raise RuntimeError(f"Yahoo Finance no devolvió cotizaciones para {ticker}.")
    row = history.iloc[-1]
    return {"symbol": ticker, "date": history.index[-1].date().isoformat(), "close": float(row["Close"]), "currency": None}
