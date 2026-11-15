# Informe diario Wall Street — módulo en desarrollo

## Avances implementados
- Fuentes FRED: 13 indicadores originales más PIB, PCE, PCE subyacente, PPI de materias primas, desempleo, ventas minoristas, Fed, Tesoro a dos años e índices estadounidenses (según disponibilidad de cada serie).
- Fuente SEC: `scripts/update_sec.py` intenta obtener datos XBRL oficiales de nueve empresas: NVIDIA, Microsoft, Apple, Amazon, Alphabet, Meta, Broadcom, JPMorgan y Tesla. Solo se incluyen cifras anuales de ejercicios completos de formularios 10-K, con fecha fiscal y variación frente al año anterior, cuando están disponibles.
- Correo HTML con explicaciones, fuente, fecha de observación, resúmenes contables y comunicaciones Fed recientes verificadas.
- Pruebas unitarias para inflación, empleo, registros fiscales SEC y cálculo de margen neto.
- Controles que evitan el envío si los indicadores macroeconómicos esenciales son insuficientes o si faltan credenciales de correo.

## Ejecución local de desarrollo
```bash
python -m unittest discover -s tests -v
python scripts/update_wall_street_data.py
python scripts/update_sec.py
python scripts/daily_wall_street.py
```
Sin credenciales Gmail, el informe HTML se genera y el último comando sale con error para **evitar falsos positivos de entrega**. Los errores de consulta SEC se reflejan como falta de métricas, nunca como datos inventados.

## Configuración antes de producción
GitHub → Settings → Secrets and variables → Actions:
- `GMAIL_USER`: Gmail que envía.
- `GMAIL_APP_PASSWORD`: contraseña de aplicación Google, distinta de la contraseña principal.
- `REPORT_TO`: dirección destinataria.
- `SEC_USER_AGENT`: identificación de aplicación SEC y contacto válido, por ejemplo nombre de aplicación y correo de soporte.

**No se incluyen contraseñas en Git.** El workflow solicita fuentes oficiales cada día a las 11:00 UTC = 07:00 de Venezuela. Por seguridad, la ejecución programada permanece en modo prueba hasta configurar la variable de Actions `RADAR_ENABLE_EMAIL=true`. GitHub Actions puede iniciar tarde. **Las tareas programadas solo se ejecutan desde la rama predeterminada**; este PR en desarrollo no activa los envíos. Tampoco se ha autorizado fusionar con la versión pública.

## Limitaciones verificadas y tareas por cerrar
1. **Prueba integral de desarrollo superada en GitHub Actions**: consulta FRED, consulta SEC, generación HTML, pruebas unitarias y artefacto HTML. No se ha probado envío SMTP real ni ejecución cron desde la rama principal.
2. **Bloqueo SEC reproducido**: en la prueba del 14/11/2026, los nueve accesos desde GitHub Actions recibieron HTTP 403; posteriormente se cambió el proceso para detener solicitudes tras el primer 403. FRED sí devolvió datos. La SEC puede limitar solicitudes por sus controles de acceso y no corresponde eludirlos. Si persiste, será necesario usar un proveedor autorizado o infraestructura habilitada conforme a sus condiciones.
3. El informe incluye contabilidad histórica oficial, **no cotizaciones por empresa**, múltiplos de valoración, consenso de analistas ni guías futuras verificadas.
4. Los feeds oficiales Fed, BLS y SEC pueden fallar o publicar menos de 5–10 noticias al día; **no equivalen a medios independientes ni análisis periodístico contrastado**.
5. La cobertura sectorial y los fondos SPY, QQQ, DIA e IWM siguen pendientes; Nasdaq Composite no equivale a Nasdaq 100. El informe incorpora interpretación basada en VIX, diferencial de crédito y curva de rendimientos cuando hay observaciones.
6. Faltan prueba de Gmail real, calidad de datos y comprobación de horario antes de publicar.

La automatización propuesta utiliza GitHub Actions y Google y no depende de una suscripción a ChatGPT Plus.

## Cierre operativo — lo que ya funciona y lo que impide la activación

**Previsualización sin enviar correo:** el workflow `daily-wall-street.yml` admite `workflow_dispatch` con `preview_only=true` como valor predeterminado. Las pruebas automáticas de la rama mediante `test-wall-street.yml` ya generan un HTML descargable sin secretos. El modo de envío real exige `preview_only=false` y configuración previa de Gmail. Una vez publicado en `main`, el programa diario crea una previsualización sin correo por defecto; solo envía tras configurar `RADAR_ENABLE_EMAIL=true` y los secretos Gmail.

**No activar hasta completar estas dependencias:**
1. Fuente de datos empresariales autorizada, accesible desde GitHub (SEC devolvió HTTP 403). Si la SEC no entrega cifras de al menos tres compañías, el informe se identifica expresamente como **edición macroeconómica de cobertura parcial** y no inventa datos empresariales.
2. Secretos Gmail `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `REPORT_TO` establecidos exclusivamente en Settings → Secrets and variables → Actions. Confirmar remitente y destinatario; no compartir contraseñas en chats ni repositorios.
3. Revisar si el alcance editorial final es suficiente: faltan cotizaciones de acciones, análisis sectorial completo y 5–10 noticias verificadas y analizadas cuando las fuentes oficiales no publican esa cantidad.
4. Tras verificar un envío Gmail, autorizar la fusión a `main`; solo entonces funcionará la programación diaria. La página pública no se ha modificado por este trabajo.

**Criterio de entrega:** una prueba satisfactoria de sintaxis y generación no significa que un correo haya sido enviado. Registrar por separado el éxito del SMTP y la recepción efectiva del destinatario.

## Edición de cierre de desarrollo (15/11/2026)

- En ausencia de datos SEC, el informe **ya no se bloquea solo por ese motivo**: puede generarse y remitirse como edición macroeconómica parcial, con advertencia en encabezado y asunto. Esto no sustituye el objetivo de cobertura empresarial y noticias completas.
- **Se mantiene la protección** que cancela el informe con indicadores macroeconómicos esenciales insuficientes o vencidos.
- Enviar correos sigue requiriendo secretos Gmail configurados, una prueba real de recepción y el workflow en la rama predeterminada. Ninguno de esos pasos se sustituye por la prueba automática sin correo.
- No fusionar a `main` ni modificar la página pública sin permiso explícito.

## Validación editorial y de correo — 15/11/2026

- Se incorporó la fuente oficial **BEA** (`https://apps.bea.gov/rss/rss.xml`) junto a los feeds oficiales de Fed, BLS y SEC. Se aceptan solamente enlaces HTTPS de dominios institucionales permitidos. Una fuente no accesible se identifica como tal y no se sustituye por artículos inventados.
- La lista de comunicados oficiales se ordena por **relevancia temática** (Fed, inflación, empleo, PIB, actividad) y después por fecha; es un orden editorial automático, **no una evaluación verificada del impacto bursátil**.
- Cada noticia recuperada presenta su fuente, fecha y enlace, más una nota de *relevancia potencial* basada en el tema del título. Sin leer la publicación completa no se puede afirmar el dato publicado, su sorpresa respecto al consenso ni la reacción efectiva de los mercados.
- La estructura del correo HTML se prueba sin enviar mensajes. La entrega efectiva requiere que el usuario configure las tres credenciales de Gmail y compruebe recepción; **no se afirma que hubo envío** si GitHub solo generó un artefacto.
- Restricciones pendientes: SEC HTTP 403 desde GitHub Actions, fallos de acceso al feed BLS, cobertura de empresas/sectores incompleta y falta de un proveedor de cotizaciones actualizadas con términos autorizados. La modalidad macroeconómica parcial debe mantener avisos visibles.

## Activación segura de Gmail (sin compartir claves)

1. GitHub → repositorio → Settings → Secrets and variables → Actions → Repository secrets: guardar `GMAIL_USER`, `GMAIL_APP_PASSWORD` y `REPORT_TO`. La contraseña de aplicación se genera en la cuenta de Google del remitente; no es la contraseña principal y depende de los requisitos de seguridad de Google.
2. GitHub → Actions → `Radar diario Wall Street (Gmail)` → Run workflow: seleccionar `preview_only=false` para una prueba de SMTP real **solo después de configurar secretos**. Verificar la recepción en Gmail.
3. GitHub → Settings → Secrets and variables → Actions → Variables → agregar `RADAR_ENABLE_EMAIL` con valor `true` **solo tras recibir el correo de prueba**. Hasta entonces, el cron de las 11:00 UTC genera únicamente previsualizaciones.
4. La captura FRED de este informe utiliza `scripts/update_wall_street_data.py`, independiente del actualizador público `scripts/update_data.py`, para conservar el comportamiento existente del sitio.

## Activación autorizada del envío diario — 15/11/2026

El usuario confirmó la recepción real de un correo de prueba el 15/11/2026 (GitHub Actions 43739855377, SMTP aceptó el envío) y autorizó activar la entrega diaria. A partir de la incorporación de este cambio en `main`, el evento `schedule` a las **11:00 UTC (07:00 de Venezuela)** ejecuta el envío SMTP real. Las ejecuciones manuales mantienen `preview_only=true` por defecto; elegir `false` realiza un envío real. GitHub Actions no garantiza ejecución al minuto exacto: el inicio puede retrasarse. Si faltan secretos o datos macro esenciales, la ejecución falla explícitamente sin fingir entrega. Los límites de SEC y fuentes de noticias permanecen; se identifica la edición macroeconómica parcial.

La variable opcional `RADAR_ENABLE_EMAIL` ya no controla el cron, porque el usuario autorizó explícitamente el envío después de confirmar la recepción. Las instrucciones de activación por variable anteriores quedan reemplazadas por esta sección.

## Mejora editorial y referencias — 15/11/2026

- Nuevas referencias: petróleo WTI/Brent con series de FRED (EIA), oro spot XAU/USD de Gold API y BTC/USDT de la API pública de Binance. Cada fila indica moneda/unidad, momento de observación, fuente y vigencia; se omiten cambios cuando no hay datos. BTC/USDT **no equivale** exactamente a BTC/USD.
- El informe recoge, además del titular, la **descripción publicada por la institución** si la ofrece su feed. Se eliminan etiquetas HTML. Para producir un auténtico resumen factual **en español**, puede añadirse el secreto opcional `GEMINI_API_KEY` en GitHub Actions; el motor realiza una sola llamada con las descripciones públicas, prohíbe añadir datos no presentes y limita el tamaño de respuesta. El modelo configurado es `gemini-3.5-flash-lite`; confirmar disponibilidad y cuotas en el proyecto de Google. Sin esa clave, el correo identifica claramente que no hay un resumen factual traducido y mantiene el enlace original y la explicación de impacto potencial. **La explicación genérica no sustituye un resumen de los hechos.**
- Los proveedores externos de oro/criptomonedas pueden fallar o restringir acceso. No se hacen reintentos, no se sustituyen por cifras inventadas y se muestra `No disponible` si falla la consulta.
- Esta mejora se valida en desarrollo antes de incorporarse a `main`; el envío diario previamente configurado no se interrumpe.

## Presentación y amplitud — 15/11/2026

- Escenarios favorable, neutral y adverso se muestran en líneas separadas.
- El diagnóstico cuantitativo concluye expresamente qué revelan las lecturas disponibles, sin proyectar indebidamente la evolución de la bolsa.
- Se suman TSM (Taiwan Semiconductor Manufacturing; CIK 0001046179) y SPCX (SpaceX; CIK 0001181412). SEC puede seguir bloqueado con HTTP 403; además, TSM presenta 20-F (el extractor existente usa únicamente 10-K) y SPCX no dispone necesariamente de dos ejercicios completos comparables tras su reciente salida a bolsa. No se inventarán cifras.
- Las cifras anuales se presentan en millones USD, con fecha fiscal, variación anual cuando sea comparable y margen neto explicado en términos sencillos.
- El módulo `scripts/update_breadth.py` consulta porcentajes de acciones por encima de SMA20/SMA50/SMA200 de S&P 500 y Nasdaq-100, con origen y fecha: ChartRow para S&P 500 y ChartVault para Nasdaq-100. Son publicaciones de proveedores independientes, **no datos certificados por los gestores del índice**. Las series históricas basadas en componentes actuales pueden tener sesgo de supervivencia; el denominador válido puede variar según la media. Los resultados se omiten si falta el trío o si tienen más de 7 días.
- CI de la rama verificó 32 pruebas, ambas fuentes de amplitud disponibles y generación HTML en modo de prueba.

## Soporte internacional y trimestral — 15/11/2026

Se amplía la lectura SEC para **TSM**: cuando no haya hechos US-GAAP anuales, el extractor busca hechos IFRS (`ifrs-full`) de formularios 20-F, con unidad **TWD** y periodos completos de 330–380 días. No convierte TWD a USD ni mezcla monedas. Para **SPCX**, se muestran por separado importes de formularios 10-Q con periodos individuales de 70–105 días; se descartan totales acumulados de varios trimestres. Las comparaciones son entre los periodos disponibles, no necesariamente interanuales. Si SEC bloquea el acceso HTTP 403, el informe sigue mostrando ausencia de datos sin inventarlos.

La redacción automatizada de noticias sigue dependiendo del secreto opcional `GEMINI_API_KEY`; la ausencia de este secreto no está resuelta con estos cambios. Se conserva el cron del envío diario por Gmail.

## Noticias en español sin facturación — 15/11/2026

Con la exigencia de costo **$0**, el flujo diario usa **Argos Translate**, software abierto que se ejecuta localmente en el runner público de GitHub Actions, para traducir al español los extractos de las descripciones oficiales RSS/Atom. El informe distingue:
- «Qué ocurrió»: una o dos frases presentes en la descripción de la fuente oficial, traducidas localmente; **no** añade datos ni constituye análisis independiente
- «Por qué importa»: contexto macroeconómico condicional, sin atribuir al titular cifras ni reacciones verificadas
- Titular traducido, título original y enlace directo oficial

No se utilizan llamadas a la API de Gemini ni servicios de pago en la tarea programada. No se requiere `GEMINI_API_KEY`, tarjeta, cuenta nueva ni facturación. La instalación del paquete y del modelo en-es se realiza únicamente en el entorno de ejecución, puede fallar por disponibilidad de red/modelo y no interrumpe el informe; en tal caso se indica claramente que no hay traducción disponible. La traducción automática puede tener errores y debe contrastarse con la fuente. GitHub Actions es gratuito para repositorios públicos con ejecutores estándar, sujeto a las políticas vigentes del proveedor. Los repositorios privados y otros recursos pueden implicar cargos y quedan fuera del alcance.

## Revisión integral de calidad y gráficos — 15/11/2026

La sección «Pulso de los mercados» ya solo contempla **oro XAU/USD, petróleo WTI de Estados Unidos y Bitcoin BTC/USDT**; se elimina Brent de datos y presentación. Cada activo tiene ficha breve, variación de 20 sesiones cuando puede calcularse, lectura de MA20/MA50/MA200, fuente, fecha y gráfico PNG cuando hay al menos 20 cierres recientes. Cada empresa del informe también tiene su propia ficha, gráfico y valoración de tendencia técnica independiente de sus estados financieros. Las imágenes se adjuntan al email como partes MIME de tipo PNG referenciadas por Content-ID (CID), para visualizarlas en Gmail sin enlaces externos a gráficos. El HTML conservado como artefacto en GitHub requiere consultar los PNG guardados junto a él.

Fuentes gratuitas para históricos: Binance (BTC/USDT), FRED/EIA (WTI) y Stooq para oro y acciones, con alternativa de Yahoo Finance solo para acciones si Stooq rechaza la descarga. Las interfaces no oficiales están sujetas a cambios, restricciones de redistribución y posibles errores: si falla, el informe muestra «sin datos» y no inventa precios, MA ni gráficos. Las series se consultan exclusivamente para el correo personal del propietario. No se añade facturación ni tarjeta. El paquete Python `matplotlib` genera imágenes en el ejecutor público de GitHub.

**Corrección contable crítica:** la selección US-GAAP ahora evalúa todas las etiquetas alternativas para escoger el cierre fiscal más reciente; anteriormente podía combinar ingresos NVDA de 2022 y beneficio/caja de 2026, o capex de 2012. Todas las métricas representadas en una misma sección corresponden ahora al mismo cierre; se rechazan variaciones interanuales si los cierres no están separados por aproximadamente un año. Separa la conclusión de resultados contables del comportamiento en bolsa.

**Noticias:** se priorizan comunicados con temas económicos; se intenta obtener dos párrafos del cuerpo de fuentes oficiales para hasta cinco noticias, y se excluyen notas de relevancia no identificable. Titular español una vez, fecha y fuente; hecho traducido solo cuando aporta más información que el título; explicación sectorial condicional y comprobable, sin instrucciones genéricas. No es análisis de sentimiento ni predicción. Puede haber menos de cinco noticias si las fuentes no proporcionan contenido suficiente.

**Diagnóstico macro:** se presenta una interpretación anual del PCE y PCE subyacente frente al objetivo de inflación de la Fed, usando la lectura anterior del mismo mes un año antes cuando esté disponible. Se indica explícitamente que superar el objetivo no equivale a una señal de compra o venta. Las tres hipótesis de escenario permanecen en líneas separadas.

La entrega Gmail de las 07:00 de Venezuela y el diseño web público no se alteran. Los gráficos no justifican por sí mismos una recomendación de inversión. Revisar los términos de las fuentes antes de cualquier redistribución comercial.
