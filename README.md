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
| VIX | Pendiente de conexión | Cboe / Interactive Brokers |

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
- El tablero se publica gratuitamente con GitHub Pages.

## Pendientes, en orden sugerido

1. Mantener el VIX visible como tarjeta y conectarlo a Interactive Brokers en modo solo lectura.
2. Permitir elegir colores de las líneas y áreas de los gráficos.
3. Añadir alertas visuales para cambios relevantes entre crédito, liquidez y volatilidad.
4. Conectar Interactive Brokers localmente, sin credenciales en GitHub y sin capacidad de enviar órdenes.

## Seguridad

No guardar contraseñas, claves API ni datos de inicio de sesión de un broker en este repositorio. La futura conexión a Interactive Brokers debe funcionar localmente y solo para lectura de datos.
