# Revisión privada verificada — 17 de octubre de 2026

## Resultado

Publicada la versión 51 de **Observatorio RM — revisión** en:

https://observatorio-rm-review-20261013.increiblepero18.chatgpt.site/consultor

Se conservó acceso exclusivo del propietario: un usuario permitido, sin grupos ni visitantes externos. No se modificó main del repositorio GitHub ni el tablero público de GitHub Pages. No se utilizaron Gemini, Wolfram ni servicios de pago.

Código de aplicación verificado: `0eef95a70bbc77ecabe2705d9d230d5351a686bf` en `dev/observatorio-rm-fuentes-20261013`. La fuente de transporte del alojamiento privado y el paquete publicado corresponden a `2a78087d37f33d122388d46fcb95be69b16e9e7c`; se verificó igualdad de los archivos de aplicación mediante SHA-256 antes de empaquetar.

## Problemas corregidos

- El servidor empaquetado no incluía los últimos cambios SEC y DCF; se reconstruyó.
- NVIDIA usa `nvda:MarketableSecuritiesAndEquitySecuritiesFVNI` para sus inversiones corrientes. Se añadió extracción Inline XBRL con validación del emisor, cierre, moneda USD, escala, ausencia de dimensiones y rechazo de valores contradictorios. No se sustituyó el total por un subconjunto de títulos de deuda.
- El CapEx de NVIDIA FY2026 está etiquetado `PaymentsToAcquireProductiveAssets`. Se añadió esta alternativa y se explicó que incluye intangibles cuando la SEC los agrupa.
- Se ampliaron las pruebas reales para comprobar todos los insumos y el informe DCF, en lugar de limitarse a ingresos y EPS.

## Pruebas

- 21 pruebas JavaScript aprobadas.
- 11 pruebas Python aprobadas.
- Construcción y sintaxis del servidor aprobadas.
- [GitHub Actions: éxito, incluida validación SEC real](https://github.com/aplicacioneserusalver1188-bot/radar-de-mercados/actions/runs/39073369875).
- Publicación privada: estado `succeeded`, versión 51.
- Consulta real en el servidor publicado: HTTP 200, NVDA, 10-K al 25 de enero de 2026, narrativas disponibles.
- Verificación en navegador: informe financiero, tres escenarios, cinco filas anuales por escenario, valoración por acción, doce enlaces SEC y anexo técnico desplegado. Sin NaN ni Infinity. Sin desbordamiento horizontal de la página en la vista de escritorio comprobada.

## Valores observados en la prueba de integración

FCF inicial: 96.676 millones USD = CFO de 102.718 millones menos inversión de 6.042 millones. Efectivo: 10.605 millones; inversiones corrientes: 51.951 millones; deuda corriente: 999 millones; deuda no corriente: 7.469 millones; promedio ponderado de acciones diluidas: 24.514 millones.

| Escenario ilustrativo | USD/acción |
| --- | ---: |
| Conservador | 50,16 |
| Base | 88,04 |
| Optimista | 145,17 |

Estas cifras son salidas de sensibilidad con supuestos explícitos, no precios objetivo ni estimaciones oficiales. El anexo explica el uso de flujo operativo después de intereses, el descuento ilustrativo y el promedio anual de acciones.

## Método y límites de acceso

El navegador directo quedó en la verificación de inicio de sesión de ChatGPT. Se utilizó el acceso de servicio documentado por Sites para comprobar el sitio publicado y mostrarlo mediante un puente local de solo lectura. El puente añadió la autorización únicamente en el servidor local y solo hacia el origen privado autorizado; no modificó la audiencia ni envió el token al navegador. No se sirvió una copia local del código para simular la publicación. Se cerró el puente al terminar.

El acceso interactivo normal del propietario seguirá requiriendo iniciar sesión con la cuenta autorizada. No falta permiso de publicación y no quedan tareas pendientes de esta entrega de revisión. El anexo y los supuestos DCF siguen siendo ilustrativos; no se ha autorizado ni realizado un despliegue del tablero público.

## Correcciones posteriores a la versión 51 (pendientes de nueva publicación en Sites)

Se corrigió el análisis específico de NVIDIA y se añadieron trimestres 10-Q independientes de la base anual, sensibilidad del descuento/crecimiento y un DCF alternativo FCFE sujeto a disponibilidad de emisiones y amortizaciones de deuda del mismo ejercicio.

**Advertencia financiera:** el DCF anterior basado en CFO − CapEx no constituye por sí solo FCFF descontado con WACC ni FCFE descontado al coste de capital propio. El puente experimental a USD/acción se conserva solo para auditoría y no debe interpretarse como valor razonable. El modelo FCFE alternativo se omite si faltan movimientos de deuda comparables; sus tasas son supuestos, no CAPM estimado.

Se corrigió además una interpolación condicional mal formada en el informe de NVIDIA y se incorporó una prueba que compila todo el JavaScript embebido del Consultor, además de las pruebas funcionales existentes.

**Estado de despliegue:** estos cambios están en la rama de desarrollo, no en la versión 51 publicada. Se requiere publicación posterior en el mismo sitio privado, comprobación SEC real de NVDA y verificación visual autenticada. No afirmar que la versión privada actual contiene estas mejoras sin nueva verificación. No se modificó producción pública ni main.
