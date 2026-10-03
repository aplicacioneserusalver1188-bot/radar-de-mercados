# Plan de Proyecto: Radar de Activos Digitales

## Propósito

Crear, como proyecto independiente del **Radar de Mercados**, un tablero educativo para observar el estado del mercado de criptoactivos. Su finalidad será explicar liquidez, volatilidad, apalancamiento, actividad de red y sentimiento; no dar recomendaciones de compra o venta.

## Principio de lectura

Una señal aislada no confirma una subida, una caída ni una oportunidad de inversión. El tablero deberá mostrar fuentes, fecha y frecuencia de cada dato, y usar alertas como prioridad de revisión, no como predicción.

## Estructura propuesta

### 1. Activos principales

El tablero mostrará seis tarjetas de criptoactivos líquidos. La selección deberá revisarse periódicamente por capitalización de mercado:

1. Bitcoin (BTC)
2. Ethereum (ETH)
3. Cuatro criptoactivos no-estables de mayor capitalización en ese momento

Las stablecoins, como USDT y USDC, se tratarán como indicadores de liquidez y no como tarjetas de tendencia de precio.

### 2. Doce indicadores del ecosistema

| Área | Indicador | Frecuencia deseada | Función educativa |
|---|---|---:|---|
| Mercado | Capitalización total del mercado | Diaria | Tamaño del ecosistema. |
| Mercado | Dominancia de Bitcoin | Diaria | Concentración relativa del capital en BTC. |
| Mercado | Volatilidad de BTC a 30 días | Diaria | Intensidad de los movimientos recientes. |
| Mercado | Caída desde máximo reciente | Diaria | Presión acumulada frente a un máximo de referencia. |
| Liquidez | Capitalización total de stablecoins | Diaria | Liquidez disponible dentro del ecosistema. |
| Liquidez | Flujos netos de stablecoins hacia exchanges | Diaria | Movimiento de liquidez hacia o desde plataformas de negociación. |
| Apalancamiento | Interés abierto de futuros | Diaria o intradía | Riesgo agregado en derivados. |
| Apalancamiento | Tasa de financiación | Diaria o intradía | Sesgo entre posiciones largas y cortas en contratos perpetuos. |
| Apalancamiento | Liquidaciones | Diaria o intradía | Cierres forzosos de posiciones apalancadas. |
| Flujo institucional | Flujos netos de ETF de BTC y ETH | Diaria | Participación a través de vehículos institucionales. |
| Red | Dificultad y potencia de minado de Bitcoin | Diaria | Resiliencia técnica de la red Bitcoin. |
| Sentimiento | Índice de Miedo y Codicia Cripto | Diaria | Contexto agregado del ánimo de mercado. |

## Radar Cripto de Atención

El tablero tendrá un medidor de 0 a 100, separado del radar económico. La lectura inicial propuesta es:

| Rango | Estado | Lectura |
|---:|---|---|
| 0–29 | Entorno Tranquilo | Riesgo y apalancamiento moderados. |
| 30–59 | Entorno de Atención | Conviene revisar qué bloque cambió. |
| 60–69 | Tensión Elevada | Varias señales requieren contexto. |
| 70–79 | Atención Urgente | Tensión simultánea en al menos tres áreas. |
| 80–100 | Tensión Severa | Revisión inmediata de fuentes y contexto. |

La alerta urgente requerirá dos condiciones: radar igual o superior a 70 y deterioro simultáneo en al menos tres áreas entre mercado, liquidez, apalancamiento y flujos institucionales.

## Mapa de Liquidez BTC · Pendiente

Se añadirá después como un módulo intradía independiente, no como componente dominante del radar:

- Precio actual de BTC.
- Tres muros de compra más cercanos.
- Tres muros de venta más cercanos.
- Distancia porcentual y volumen de cada muro.
- Operaciones grandes ejecutadas recientemente.
- Órdenes canceladas, para recordar que los muros pueden desaparecer.

Las paredes de compra o venta no serán señales automáticas de compra o venta. Solo describen liquidez visible en un momento y pueden cambiar rápidamente.

## Fuentes candidatas

| Tipo de dato | Fuente candidata | Nota |
|---|---|---|
| Precios, capitalización y selección de activos | CoinGecko | Verificar metodología y límites de uso. |
| Futuros, financiación, interés abierto, liquidaciones y libro de órdenes | CoinGlass | Parte del contenido requiere plan de API y clave privada. |
| Métricas en cadena y flujos hacia exchanges | Glassnode u otra fuente verificable | Algunas métricas pueden requerir licencia. |
| Dificultad de Bitcoin | Explorador público de blockchain | Dato de red, no señal de precio. |
| ETF | Emisores o fuente agregada verificable | Debe identificarse la fecha de actualización. |

## Seguridad y publicación

- Nunca guardar claves de API, contraseñas o claves de exchange dentro de GitHub, HTML o JavaScript del navegador.
- Si una fuente requiere clave privada, usar posteriormente un servicio privado que consulte la API y entregue al tablero solo datos resumidos.
- Mantener el proyecto separado del Radar de Mercados hasta que su diseño, fuentes y límites estén claros.
- Mostrar siempre fecha, fuente y frecuencia de cada lectura.

## Orden recomendado de trabajo

1. Definir la primera versión visual sin conexiones privadas.
2. Incorporar precios y capitalización de BTC, ETH y los cuatro activos no-estables seleccionados.
3. Añadir los doce indicadores que dispongan de fuente estable y permitida.
4. Diseñar el Radar Cripto de Atención y validarlo con datos históricos.
5. Añadir guía educativa, fichas por indicador y explicación de fuentes.
6. Evaluar la integración segura de CoinGlass para el Mapa de Liquidez BTC.

## Pendientes antes de comenzar

- Decidir la fuente de precios que se usará en la primera versión.
- Definir si el tablero será público, privado o de acceso limitado.
- Confirmar si se contratará una API de datos para métricas avanzadas.
- Definir cuántos años de datos históricos se usarán para calibrar el radar.

---

Última actualización: 2 de octubre de 2026.
