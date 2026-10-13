# Integraciones de consulta

Estos módulos son de solo lectura, no se ejecutan en el flujo diario y no guardan credenciales ni resultados. El tablero original continúa alimentándose exclusivamente con series públicas de FRED.

| Fuente | Uso en este repositorio |
| --- | --- |
| SEC EDGAR | Hechos XBRL y presentaciones públicas; requiere `SEC_USER_AGENT` con contacto real y limita solicitudes. |
| FRED API | Consulta opcional con `FRED_API_KEY`; el CSV público actual se conserva. |
| Yahoo Finance | Consulta local y efímera mediante `yfinance`; no se incorpora al sitio ni al histórico distribuido. Revise sus términos para otro uso. |
| Wolfram\|Alpha | Cálculo o consulta opcional con `WOLFRAM_APP_ID`; no produce señales ni recomendaciones. |

Ninguna integración interpreta resultados como recomendación financiera.
