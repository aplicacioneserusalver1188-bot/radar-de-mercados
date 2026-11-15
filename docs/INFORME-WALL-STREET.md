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
python scripts/update_data.py
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

**No se incluyen contraseñas en Git.** El workflow solicita fuentes oficiales cada día a las 11:00 UTC = 07:00 de Venezuela. GitHub Actions puede iniciar tarde. **Las tareas programadas solo se ejecutan desde la rama predeterminada**; este PR en desarrollo no activa los envíos. Tampoco se ha autorizado fusionar con la versión pública.

## Limitaciones verificadas y tareas por cerrar
1. **Prueba integral de desarrollo superada en GitHub Actions**: consulta FRED, consulta SEC, generación HTML, pruebas unitarias y artefacto HTML. No se ha probado envío SMTP real ni ejecución cron desde la rama principal.
2. **Bloqueo SEC reproducido**: en la prueba del 14/11/2026, los nueve accesos desde GitHub Actions recibieron HTTP 403; posteriormente se cambió el proceso para detener solicitudes tras el primer 403. FRED sí devolvió datos. La SEC puede limitar solicitudes por sus controles de acceso y no corresponde eludirlos. Si persiste, será necesario usar un proveedor autorizado o infraestructura habilitada conforme a sus condiciones.
3. El informe incluye contabilidad histórica oficial, **no cotizaciones por empresa**, múltiplos de valoración, consenso de analistas ni guías futuras verificadas.
4. Los feeds oficiales Fed, BLS y SEC pueden fallar o publicar menos de 5–10 noticias al día; **no equivalen a medios independientes ni análisis periodístico contrastado**.
5. La cobertura sectorial y los fondos SPY, QQQ, DIA e IWM siguen pendientes; Nasdaq Composite no equivale a Nasdaq 100. El informe incorpora interpretación basada en VIX, diferencial de crédito y curva de rendimientos cuando hay observaciones.
6. Faltan prueba de Gmail real, calidad de datos y comprobación de horario antes de publicar.

La automatización propuesta utiliza GitHub Actions y Google y no depende de una suscripción a ChatGPT Plus.

## Cierre operativo — lo que ya funciona y lo que impide la activación

**Previsualización sin enviar correo:** el workflow `daily-wall-street.yml` admite `workflow_dispatch` con `preview_only=true` como valor predeterminado. Las pruebas automáticas de la rama mediante `test-wall-street.yml` ya generan un HTML descargable sin secretos. El modo de envío real exige `preview_only=false` y configuración previa de Gmail. La ejecución programada en `main` realiza el envío normal, pero todavía no se ha publicado esta rama.

**No activar hasta completar estas dependencias:**
1. Fuente de datos empresariales autorizada, accesible desde GitHub (SEC devolvió HTTP 403). El envío normal se cancela si no encuentra al menos tres compañías con cifras contables verificadas.
2. Secretos Gmail `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `REPORT_TO` establecidos exclusivamente en Settings → Secrets and variables → Actions. Confirmar remitente y destinatario; no compartir contraseñas en chats ni repositorios.
3. Revisar si el alcance editorial final es suficiente: faltan cotizaciones de acciones, análisis sectorial completo y 5–10 noticias verificadas y analizadas cuando las fuentes oficiales no publican esa cantidad.
4. Tras verificar un envío Gmail, autorizar la fusión a `main`; solo entonces funcionará la programación diaria. La página pública no se ha modificado por este trabajo.

**Criterio de entrega:** una prueba satisfactoria de sintaxis y generación no significa que un correo haya sido enviado. Registrar por separado el éxito del SMTP y la recepción efectiva del destinatario.
