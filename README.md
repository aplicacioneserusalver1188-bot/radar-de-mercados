# Bitácora — Radar de Mercados

## Propósito

Tablero personal para observar señales de mercado y liquidez. No da recomendaciones de compra o venta: ayuda a comparar tendencias y cambios entre indicadores.

## Dirección pública

https://aplicacioneserusalver1188-bot.github.io/radar-de-mercados/

## Indicadores activos

| Indicador | Frecuencia | Fuente |
| --- | --- | --- |
| High Yield OAS | Diaria | ICE BofA vía FRED |
| Treasury de EE. UU. a 10 años | Diaria | U.S. Treasury vía FRED |
| SOFR | Diaria | New York Fed vía FRED |
| Diésel minorista de EE. UU. | Semanal | EIA vía FRED |
| RRP overnight | Diaria | New York Fed vía FRED |
| TGA, cuenta del Tesoro | Semanal | Board of Governors vía FRED |
| Reservas bancarias | Semanal | Board of Governors vía FRED |
| VIX | Diaria | Cboe vía FRED |
| Inflación CPI anual | Mensual | BLS vía FRED |
| Solicitudes iniciales de desempleo | Semanal | U.S. Employment and Training Administration vía FRED |
| Sentimiento del consumidor | Mensual | Universidad de Michigan vía FRED |
| Variación del empleo no agrícola (Nonfarm Payrolls) | Mensual | BLS vía FRED |
| Índice Nacional de Condiciones Financieras (NFCI) | Semanal | Reserva Federal de Chicago vía FRED |

## Cómo se actualiza

1. GitHub Actions ejecuta el archivo `scripts/update_data.py` cada día laborable.
2. Ese archivo descarga las series públicas y guarda los resultados en `data/market.json`.
3. `index.html` lee ese archivo y muestra las tarjetas y gráficos.

Para comprobar una actualización en cualquier momento: en GitHub, abrir **Actions** → **Actualizar datos de mercado** → **Run workflow**. Un resultado **Success** significa que los datos se guardaron correctamente.

## Cómo publicar un cambio visual

1. Sustituir `index.html` en la raíz del repositorio.
2. Confirmar el cambio con **Commit changes**.
3. Esperar aproximadamente un minuto para que GitHub Pages publique la versión nueva.
4. Recargar la página con `Ctrl + F5` si el navegador muestra una versión anterior.

## Estado actual

- Gráficos con vistas diaria, semanal, mensual y de un año.
- Cada gráfico muestra valor actual, variación frente al dato anterior y escala vertical.
- Las lecturas y sus gráficos están juntos.
- El tablero reúne doce lecturas: VIX, crédito, Treasury, inflación, diésel, tres señales de liquidez, desempleo inicial, sentimiento del consumidor, empleo no agrícola y condiciones financieras.
- Cada indicador tiene un semáforo educativo y el radar de atención se muestra como un medidor visual de 0 a 100.
- Se puede alternar entre fondo claro y oscuro; la elección queda guardada en ese navegador.
- La pestaña **Cómo leer el radar** explica las relaciones económicas, las fuentes y los límites de la lectura.
- Cada tarjeta incluye una microficha **¿Qué es?** con definición, lectura, utilidad y fuente del indicador.
- La guía incluye un mapa de instituciones, fuentes y responsables consultados el 2 de octubre de 2026.
- TGA y reservas se muestran en miles de millones de USD para facilitar su lectura.
- El tablero se publica gratuitamente con GitHub Pages.

## Pendientes, en orden sugerido

1. Revisar los umbrales de los semáforos después de observar el tablero durante varias semanas.
2. Permitir elegir colores individuales de las líneas y áreas de los gráficos.
3. Definir alertas opcionales fuera del navegador, sin almacenar credenciales en GitHub.
4. Evaluar una conexión local de solo lectura a Interactive Brokers solo si aporta valor adicional al dato público.

## Seguridad

No guardar contraseñas, claves API ni datos de inicio de sesión de un broker en este repositorio. La futura conexión a Interactive Brokers debe funcionar localmente y solo para lectura de datos.
