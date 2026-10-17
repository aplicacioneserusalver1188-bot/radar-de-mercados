# Validación SEC — 17 de octubre de 2026

Trabajo limitado a `dev/observatorio-rm-fuentes-20261013`; sin despliegue ni cambios en main.

## Correcciones verificadas

- La serie anual de EPS diluido selecciona `USD/shares`, en lugar de buscar USD.
- Cada observación anual conserva unidad, concepto XBRL y enlace al informe.
- Nuevas pruebas cubren unidades, procedencia, rechazo de trimestres y accesiones ajenas, valores no finitos y hechos instantáneos del balance.
- El comando de pruebas y su flujo de validación incluyen la nueva suite.
- Se reconstruyó el archivo del servidor en dist; no se publicó la aplicación.

## Resultado local

- 12 pruebas Node aprobadas.
- 11 pruebas Python aprobadas.
- Construcción y comprobación de sintaxis del servidor aprobadas.
- La prueba SEC en vivo aprobó el 17 de octubre de 2026. El secreto `SEC_USER_AGENT` se configuró en GitHub Actions por autorización del propietario; su valor no está en el código, este documento ni los registros públicos.

## Contraste documental

Se consultó el [10-K oficial NVIDIA FY2026](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm): ingresos 215.938 millones USD, beneficio neto 120.067 millones USD y EPS diluido 4,90 USD/acción. La prueba en vivo ahora contrasta estas tres cifras con companyfacts, además de comprobar Business, Risk Factors y MD&A en el HTML.

## Validación real y repetición manual

La [ejecución 39071718143](https://github.com/aplicacioneserusalver1188-bot/radar-de-mercados/actions/runs/39071718143) aprobó tanto `test` como `live-sec-smoke`. Se repitieron manualmente todos los trabajos desde Actions (intento 2), con el mismo resultado satisfactorio. Los registros muestran `SEC_USER_AGENT: ***` y `PASS: NVIDIA FY2026 live 10-K, sections present and plausible`.

La prueba descargó el HTML original del 10-K, verificó un tamaño superior a 100.000 caracteres y extrajo Business, Risk Factors y MD&A, cada uno con más de 1.200 caracteres. Comprobó vocabulario financiero y de riesgos en los apartados, descargó companyfacts de la SEC y contrastó los ingresos, beneficio neto y EPS indicados arriba con la misma accesión y fecha de cierre.

El flujo no está en main, por lo que GitHub no ofrece el botón Run workflow. Se habilitó una alternativa explícita: un commit cuyo mensaje incluya `[sec-live]`, que modifique una ruta observada por el flujo, ejecuta la consulta real únicamente en `dev/observatorio-rm-fuentes-20261013`. Las ejecuciones existentes pueden repetirse manualmente con Re-run all jobs. No se modificó main para habilitar el botón.

No quedan pendientes para esta validación del 10-K FY2026. No se ha desplegado ni comprobado la configuración de un servidor de producción; eso está fuera del alcance solicitado. Las advertencias del runner sobre la versión interna de Node de las acciones y la próxima migración de Ubuntu no impidieron las pruebas.

No se usaron Gemini, APIs de pago ni cálculos externos de Wolfram. Las pruebas existentes de secciones usan documentos sintéticos; no deben confundirse con una descarga real de la SEC.
