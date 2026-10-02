# Bitácora del proyecto — Radar de Mercados

Actualizada: 2 de octubre de 2026.

## Propósito

Crear un tablero educativo de mercados de Estados Unidos. Sirve para observar relaciones entre riesgo, crédito, tasas, liquidez, inflación, energía, empleo y confianza. No da recomendaciones de compra, venta ni predicciones.

## Dirección pública

https://aplicacioneserusalver1188-bot.github.io/radar-de-mercados/

## Lo que ya está construido

- Tablero de datos públicos con gráficos de tendencia, escalas verticales y consulta de fecha y valor al pasar el ratón.
- Vistas diaria, semanal, mensual y de un año.
- Fondo claro u oscuro, elegido por cada persona en su navegador.
- Un semáforo por indicador: tranquilo, atención o atención elevada.
- Radar de atención general de 0 a 100 en formato de velocímetro.
- Explicación educativa mediante la pestaña **Cómo leer el radar**.
- Microfichas **¿Qué es?** para explicar cada indicador, su lectura y fuente.
- Definiciones en español primero; el nombre técnico en inglés aparece entre paréntesis.
- Bitácora principal: `README.md`.

## Las doce lecturas del tablero

1. Índice de volatilidad (VIX).
2. Diferencial de bonos de alto rendimiento (High Yield OAS).
3. Bono del Tesoro de Estados Unidos a 10 años (Treasury 10Y).
4. Inflación anual de precios (CPI).
5. Diésel minorista de Estados Unidos.
6. Acuerdo de recompra inversa nocturno (ON RRP).
7. Cuenta General del Tesoro (TGA).
8. Reservas bancarias.
9. Solicitudes iniciales de desempleo.
10. Sentimiento del consumidor.
11. Variación del empleo no agrícola (Nonfarm Payrolls).
12. Índice Nacional de Condiciones Financieras (NFCI).

## Fuentes públicas

El actualizador obtiene series desde FRED, que distribuye series de la Reserva Federal, BLS, EIA, Reserva Federal de Chicago, Universidad de Michigan y otras fuentes oficiales. El VIX se obtiene desde la serie diaria pública distribuida por FRED.

## Cómo se actualiza el tablero

1. GitHub Actions ejecuta `scripts/update_data.py`.
2. El actualizador descarga las series y guarda `data/market.json`.
3. `index.html` lee ese archivo y dibuja el tablero.
4. GitHub Pages publica la página desde la rama `main`.

Para forzar una actualización: GitHub → **Actions** → **Actualizar datos de mercado** → **Run workflow**. Un resultado **Success** confirma que los datos se guardaron.

## Archivos correctos para publicar

- `index.html`: cambios visuales, semáforos, gráficos, radar y guía.
- `scripts/update_data.py`: descarga las series públicas, incluidas las lecturas 10, 11 y 12.
- `README.md`: resumen público breve.
- `BITACORA-PROYECTO.md`: este registro de continuidad.

Carpeta de trabajo preparada para subir:

`outputs/rrp-publicar/`

## Último cambio preparado

- Se reconstruyó el radar de atención como velocímetro de 0 a 100, con marcas cada 10 puntos y números por fuera del arco.
- Se añadieron al actualizador y al tablero: sentimiento del consumidor, empleo no agrícola y condiciones financieras nacionales.
- Se mejoró la explicación del ON RRP con una descripción técnica de su propósito, funcionamiento y límites de interpretación.
- Las doce tarjetas se separaron en dos pestañas de seis: **Panorama principal** y **Liquidez y economía**.

## Próximos pendientes sugeridos

1. Publicar `index.html` y `scripts/update_data.py`, ejecutar el actualizador y comprobar que aparezcan las doce tarjetas.
2. Revisar visualmente el nuevo velocímetro y ajustar tamaños, posiciones o colores si es necesario.
3. Completar las fichas educativas y la guía para los doce indicadores.
4. Revisar los umbrales de cada semáforo después de varias semanas de observación.
5. Más adelante: alertas opcionales, diario de observaciones y herramientas educativas. No incorporar recomendaciones personalizadas de inversión.

## Principios de seguridad y comunicación

- No guardar contraseñas, claves API ni datos de cuentas de bróker en GitHub.
- Usar solo fuentes públicas o conexiones locales de lectura, si en el futuro se justifican.
- No presentar el radar como asesoría financiera.
- Explicar siempre cada sigla: nombre en español primero y nombre técnico en inglés entre paréntesis.
