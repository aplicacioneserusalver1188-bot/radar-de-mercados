# Informe diario Wall Street — módulo en desarrollo

## Estado y alcance
Este módulo reutiliza las 13 series FRED ya disponibles en el Radar de Mercados y produce un informe HTML con fecha de cada observación, interpretación prudente y seguimiento de nueve empresas. **No** cuenta aún con cotizaciones de índices, resultados financieros actualizados, noticias individuales verificadas ni motor de IA; no se simula que existan.

## Ejecución
`python scripts/update_data.py && python scripts/daily_wall_street.py`

Sin secretos, se crea `reports/wall-street-latest.html` y se omite el envío. En GitHub Actions, el workflow `daily-wall-street.yml` está previsto para las **11:00 UTC = 07:00 Venezuela**, con posible retraso propio de GitHub Actions. Los eventos `schedule` de GitHub solo se ejecutan desde la rama predeterminada; **no funcionará automáticamente mientras el workflow permanezca en esta rama de desarrollo**.

## Configuración segura antes de activar
Crear en GitHub Settings → Secrets and variables → Actions los secretos:
- `GMAIL_USER`: dirección de la cuenta emisora.
- `GMAIL_APP_PASSWORD`: contraseña de aplicación de Google, nunca la contraseña principal; requiere configuración compatible de Google.
- `REPORT_TO`: correo destinatario.

No guardar secretos en archivos ni en el historial Git. Alternativa futura: Gmail API/OAuth con autorización y renovación adecuadas.

## Limitaciones y validación pendiente
- Revisar cobertura, frescura y fallos de FRED.
- Agregar datos bursátiles y empresariales con fuente, fecha y condiciones de uso.
- Agregar noticias verificadas con enlaces directos y análisis (sin inventar titulares).
- Probar ejecución real del workflow, correo y horarios antes de aprobar la publicación.
- Evitar duplicar envíos; no activar la automatización hasta verificar secretos y confirmar que el informe tiene la profundidad requerida.
- El envío depende de GitHub Actions y Google, no de ChatGPT Plus.
- La rama principal, la portada y el tablero existente no se modifican en esta propuesta.
