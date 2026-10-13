# Consultor Inteligente de Activos: límites y arquitectura

La aplicación web se divide en tres capas:

1. **Datos:** las series macro públicas que el Radar ya publica en `data/market.json`; SEC EDGAR, FRED API y Yahoo Finance quedan fuera del navegador hasta que exista una credencial o licencia apta para una aplicación pública.
2. **Análisis:** cálculos deterministas reproducibles en el navegador (cambio entre observaciones, variación porcentual y comparación contra la observación anterior). Wolfram|Alpha se reserva para cálculos que aporten valor y se habilitará únicamente con un AppID del propietario guardado como secreto de servidor.
3. **Presentación:** `consultor.html` explica la procedencia de cada dato, separa hechos observados de cálculos y muestra las limitaciones antes de presentar una interpretación.

## Por qué no hay un proxy público de Yahoo, SEC o Wolfram aún

- La API de FRED exige una clave por usuario/aplicación y condiciones de atribución; no se expone una clave en el navegador.
- SEC solicita una identidad de usuario y un contacto real para el acceso automatizado. No se inventa una dirección de contacto ni se realiza scraping desde el navegador.
- Yahoo Finance no ofrece en este proyecto una licencia o clave de servidor para redistribuir cotizaciones a visitantes. Su conector local es deliberadamente efímero.
- Wolfram|Alpha exige un AppID. Sin uno, la página usa únicamente operaciones deterministas visibles y marca a Wolfram como no ejecutado.

Para habilitar la consulta pública de acciones/ETF hará falta que el propietario aporte una fuente de mercado con licencia pública compatible y, para EDGAR/Wolfram, los secretos correspondientes. No se activa ningún plan ni servicio de pago por defecto.
