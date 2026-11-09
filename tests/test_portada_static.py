#!/usr/bin/env python3
"""Validaciones estáticas de la nueva portada; no necesitan dependencias externas."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
home = (ROOT / "portada-preview.html").read_text(encoding="utf-8")
dashboard = (ROOT / "index.html").read_text(encoding="utf-8")
consultor = (ROOT / "consultor.html").read_text(encoding="utf-8")
oportunidades = (ROOT / "oportunidades.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "data/market.json").read_text(encoding="utf-8"))
assert '<html lang="es"' in home
assert 'name="viewport"' in home
assert all('radar-theme' in page for page in (home, dashboard, consultor, oportunidades))
assert 'consultor.html' in home and 'oportunidades.html' in home
assert 'portada-preview.html' in consultor and 'portada-preview.html' in oportunidades
assert "$('query').value='SPY'" in consultor
assert "||'dark'" in dashboard
assert 'data-symbol="vix"' not in home  # los identificadores se generan desde las series
assert "['VIX','vix']" in home
assert "['Tesoro 10 años','treasury10y']" in home
assert "['Bitcoin','btc']" in home
assert home.index("['Petróleo (WTI)','wti']") < home.index("['Bitcoin','btc']")
assert 'index.html#academia' in home
assert "location.hash==='#academia'" in dashboard
assert 'portada-preview.html' in dashboard
assert 'https://www.bls.gov/schedule/news_release/' in home
assert 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm' in home
assert set(['vix','treasury10y']).issubset(data['series'])
for key in ('vix','treasury10y'):
    points = data['series'][key]['points']
    assert points and all('date' in x and 'value' in x for x in points)
assert 'Sin datos conectados' in home
assert 'localStorage' in home
print('OK: estructura, navegación, persistencia, fuentes y datos de respaldo.')
