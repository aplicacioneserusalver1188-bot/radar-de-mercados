# Portada Radar de Mercados — especificación de desarrollo

Fecha: 2026-11-09. Estado: diseño aprobado; implementación pendiente. Rama aislada de producción.

## Portada
- Tema oscuro por defecto; interruptor visible en encabezado superior derecho, disponible en TODAS las vistas. Preferencia persistente por navegador y sin duplicar páginas.
- Fila bursátil: S&P 500, Nasdaq 100, Dow Jones, Russell 2000 y VIX; valores, cambio porcentual, minigráficos con periodo identificado y marca de actualización.
- Fila económica: rendimiento Tesoro 10 años, oro, índice dólar DXY, petróleo WTI y Bitcoin (último). Opcional Brent en detalle.
- Navegación y tarjetas principales: Panorama del Mercado, Radar de Oportunidades, Consultor Inteligente, Academia de Economía Aplicada.
- Resumen inferior: medidor de atención, lectura rápida fundamentada, tendencias e ideas explicadas.
- Agenda semanal con eventos clicables por día: inflación, Fed, resultados empresariales, empleo, PIB y otros; mostrar hora y zona horaria, importancia, previsión, dato anterior y dato real cuando se publique, fuente y fecha de actualización.
- Academia: mostrar solo tarjeta de acceso en portada; lecciones y evaluaciones dentro de Academia.
- Consultor: mantener SPY como activo inicial cuando se abra la vista.
- Accesibilidad: contraste suficiente, diseño móvil y teclado.

## Integridad de datos
- Nunca presentar cifras ilustrativas como reales. Si no hay fuente autorizada, indicar 'Sin datos' y la fecha de último dato.
- Gráficos deben corresponder a la ventana de tiempo mostrada. Cambio diario negativo no implica tendencia de largo plazo.
- VIX: caída del índice se representa numéricamente en rojo con línea descendente; interpretación de riesgo separada del signo del movimiento.
- No inventar calendario, cotizaciones ni señales; citar proveedor y controlar límites de uso y licencias.
- Reutilizar la infraestructura FRED ya disponible; verificar cobertura de índices, oro, WTI, DXY y BTC antes de contratar o integrar nuevas fuentes.
- El Radar de Oportunidades es un módulo en desarrollo: no presentar escaneos o puntuaciones simuladas como resultados reales.

## Plan
1. Inventario y revisión de componentes existentes (main y consultor en dev).
2. Construir portada aislada y tema global, sin alterar producción.
3. Integrar navegación real, fuentes y calendario verificable.
4. Validar visualmente en escritorio/móvil, accesibilidad, consistencia temporal y regresiones.
5. Entregar enlace de revisión y solicitar aprobación antes de publicar.

No modificar main ni desplegar en producción sin autorización expresa.
