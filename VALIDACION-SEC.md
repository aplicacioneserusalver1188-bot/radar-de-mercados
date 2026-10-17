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
- La prueba SEC en vivo se ejecutó y se detuvo antes de acceder a la red: falta `SEC_USER_AGENT` con nombre de aplicación y correo real de contacto. No se inventó una identidad.

## Contraste documental

Se consultó el [10-K oficial NVIDIA FY2026](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm): ingresos 215.938 millones USD, beneficio neto 120.067 millones USD y EPS diluido 4,90 USD/acción. La prueba en vivo ahora contrasta estas tres cifras con companyfacts, además de comprobar Business, Risk Factors y MD&A en el HTML.

La consulta del documento mediante navegador no acredita que el extractor haya procesado su HTML real. Esa validación sigue pendiente hasta disponer del identificador SEC. Configurarlo en el entorno local y ejecutar `node tests/sec_live_smoke.cjs`; también existe el flujo manual SEC extractor validation con el secreto `SEC_USER_AGENT`.

No se usaron Gemini, APIs de pago ni cálculos externos de Wolfram. Las pruebas existentes de secciones usan documentos sintéticos; no deben confundirse con una descarga real de la SEC.
