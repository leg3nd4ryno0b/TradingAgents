---
name: trading-agents
description: 'Emula el framework multi-agente TradingAgents (TauricResearch) para analizar una acción, ETF o cripto como lo haría una firma de trading: 4 analistas (técnico, sentimiento, noticias, fundamentales), debate alcista vs. bajista, Research Manager, Trader, debate de riesgo (agresivo/conservador/neutral) y un Portfolio Manager que emite la calificación final Buy / Overweight / Hold / Underweight / Sell con entrada y stop-loss. Úsala siempre que el usuario pida analizar un ticker, "¿compro / vendo / mantengo X?", una tesis de inversión, un informe tipo research de una acción, una recomendación de trading, comparar el caso bull vs. bear, o mencione TradingAgents, aunque no nombre la skill. También en inglés ("should I buy NVDA", "analyze TSLA", "trading decision for AAPL").'
---

# TradingAgents (emulado)

TradingAgents es un programa de Python que simula una firma de trading con
varios agentes LLM que se pasan informes y debaten. Aquí haces lo mismo sin
instalar nada: tú encarnas cada rol, en orden, y el valor está en que cada rol
**solo ve sus entradas** y defiende de verdad su postura. Si mezclas los roles
o suavizas el debate, el resultado se vuelve una opinión única con más pasos.

Las consignas de cada rol están en `references/roles.md`. Léelo antes del paso 2.

## Parámetros

Toma del pedido del usuario (o usa el valor por defecto sin preguntar):

| Parámetro | Por defecto |
|---|---|
| Ticker (formato Yahoo: `NVDA`, `SPY`, `BTC-USD`, `GGAL.BA`) | obligatorio; si es ambiguo, pregunta |
| Fecha de análisis | hoy |
| Horizonte | sin fecha fija (posición de semanas a meses). Si el usuario da una fecha de salida, todos los roles juzgan *ese* plazo: una buena empresa puede ser una mala operación de una semana |
| Analistas | los 4 |
| Rondas de debate de inversión | 1 (alcista y bajista hablan una vez cada uno) |
| Rondas de debate de riesgo | 1 (cada uno de los 3 habla una vez) |
| Idioma | el del usuario |
| Contexto de cartera | posiciones, caja, tolerancia al riesgo. Si hay un conector de bróker con lectura de cuenta y el usuario pide usar "su cartera", léela; si no, usa lo que diga. Pásalo al Trader y al Portfolio Manager |
| Reglas de tamaño | posición máxima 5 % de la cartera por activo, y riesgo por operación ≤ 1 % de la cartera. Un monto máximo del usuario ("hasta 100 $") reemplaza solo el tope de posición; la regla del 1 % sigue salvo que el usuario la cambie, calculada sobre la cartera actual (antes de depositar). Declara en el informe qué reglas usaste |

## Paso 1 — Datos reales

Los agentes del original trabajan con herramientas de datos; sin ellas, el
análisis es invención. Consigue datos en este orden y anota en el informe qué
fuente usaste:

1. **Script incluido** (preferido; calcula los mismos indicadores que el original):
   ```bash
   python <ruta-de-la-skill>/scripts/fetch_data.py TICKER --date YYYY-MM-DD --out datos_TICKER.md
   ```
   Instala `yfinance` y `pandas` solo si faltan. Si termina con
   `SIN_ACCESO_YAHOO` (o ya sabes que Yahoo está bloqueado en este entorno),
   pasa a la opción 2.
2. **Conector de bróker** si está disponible (p. ej. Interactive Brokers:
   `get_price_history` diario, `get_price_snapshot`). Pide **~260 barras
   diarias**: bastan para la SMA200 y su arranque, y cada barra extra es texto
   que hay que copiar. Si el resultado del conector quedó guardado en un
   archivo, pasa esa ruta directamente; si no, escribe la respuesta tal cual en
   `barras.json`. Luego:
   ```bash
   python <ruta-de-la-skill>/scripts/fetch_data.py TICKER --prices barras.json --date YYYY-MM-DD --out datos_TICKER.md
   ```
   Acepta el formato en columnas del conector (`{"time": [...], "open": [...]}`),
   una lista de filas, CSV, o el archivo de resultado de la herramienta con el
   JSON dentro de un bloque de texto. Lo que traiga el snapshot y no esté en el
   archivo (último precio en vivo con su hora, after-hours, volatilidad
   implícita, máx/mín 13 y 26 semanas) añádelo como sección «1b».
3. **Búsqueda web**: precio actual, máx/mín 52 semanas, ratios, últimos
   resultados trimestrales, noticias de la semana. Cita la fuente y la fecha de
   cada número.
4. Si nada funciona, pide al usuario que pegue los datos o un CSV. No sigas con
   números inventados: un informe con niveles de precio inventados es peor que
   ninguno, porque parece accionable.

Con las opciones 2 o 3, las secciones 4–9 del archivo de datos quedan como
encabezados por completar: escribe ahí lo que encuentres en la web o el
conector (fuente y fecha en cada dato), o «no disponible». Así cada analista
sigue leyendo sus secciones de un solo archivo, sea cual sea la fuente.

Para los analistas de **noticias y sentimiento**, haz búsquedas web de la
última semana (empresa, sector, macro, y sentimiento en redes) si hay búsqueda
disponible. El script solo trae titulares de Yahoo.

Busca también el **calendario dentro del horizonte**: resultados de la empresa y
de pares que muevan el sector, splits, dividendos, cambios de índice,
vencimientos de opciones relevantes, Fed/CPI/empleo. **Confirma en la fuente
oficial** (relación con inversores de la empresa, BLS, Fed) toda fecha que
mueva la entrada o la salida; si solo hay fechas proyectadas, dilo. Un evento el día de salida
cambia la operación entera.

Si la fecha de análisis es pasada (backtest), descarta cualquier dato posterior
a ella: el original lo hace para no hacer trampa con información del futuro.

## Paso 2 — Equipo de analistas

Escribe los 4 informes según `references/roles.md` (roles 1–4). Son
independientes entre sí: ninguno lee el informe de otro. Si tienes una
herramienta para lanzar subagentes, puedes encargar cada analista a uno en
paralelo (pásale su consigna, sus entradas y la ruta del archivo de datos);
si no, escríbelos uno tras otro.

## Paso 3 — Debate de inversión

Por cada ronda: turno del **Alcista** y luego del **Bajista** (roles 5–6). Cada
turno responde al último argumento del otro, citando datos de los informes.
Luego el **Research Manager** (rol 7) lee solo el debate y emite el plan con su
recomendación de 5 niveles.

## Paso 4 — Trader

El **Trader** (rol 8) convierte el plan en una propuesta: Buy / Hold / Sell,
entrada y stop como precios absolutos sacados del snapshot y el ATR, y tamaño
de posición. El riesgo de la regla del 1 % es acciones × distancia al stop,
pero si el ATR supera ~5 % del precio o hubo huecos grandes recientes, calcula
también la pérdida con un hueco como el peor del último año y dimensiona con
la cifra mayor: un stop no protege de una apertura por debajo de él. Usa el
«peor hueco de apertura» del snapshot; si ese hueco vino de un evento (p. ej.
resultados) y no hay uno comparable dentro del horizonte, puedes usar el peor
hueco sin evento, mostrando las dos cifras.

En montos pequeños, suma los **costos**: comisión de compra y venta del bróker,
y el costo de transferir el dinero si lo hay. En una operación de 100 $ a una
semana, 2 $ de comisiones son la mitad del movimiento esperado.

## Paso 5 — Debate de riesgo

Por cada ronda: **Agresivo → Conservador → Neutral** (roles 9–11), cada uno
respondiendo a los otros dos sobre la propuesta del Trader.

## Paso 6 — Portfolio Manager

El **Portfolio Manager** (rol 12) decide el rating final. Si en la carpeta de
trabajo hay un informe anterior de este mismo ticker (`informe_TICKER_*.md`),
compáralo con el precio actual y pásale al PM la lección (¿la decisión
anterior acertó?). Así emula la memoria del original.

## Varios tickers a la vez

Si el usuario analiza varios activos en el mismo pedido o en pedidos seguidos
(o ya tiene posiciones del mismo sector), cada informe debe decir cómo encaja
con los demás: la regla del 1 % y el estrés de hueco se aplican también al
**grupo correlacionado** (p. ej. MU + SNDK, ambas memoria: un solo tope para
las dos), y la exposición total al sector va en el resumen. Si hay subagentes
disponibles, un análisis por ticker en paralelo funciona bien.

## Paso 7 — Entrega

Guarda todo en `informe_TICKER_YYYY-MM-DD.md` con esta estructura:

```markdown
# TradingAgents — TICKER — YYYY-MM-DD
**Rating final: <Buy|Overweight|Hold|Underweight|Sell>** · Entrada: X · Stop: Y · Tamaño: Z · Fuente de datos: ...
<!-- Con Hold: "Entrada: — (mantener)" o una entrada condicional con su condición; el stop aplica a la posición existente si la hay. -->
<!-- Con Sell/Underweight: nivel o plan de salida en lugar de la entrada. -->

## I. Informes de analistas
### Mercado (técnico) / ### Sentimiento / ### Noticias / ### Fundamentales
## II. Debate de inversión
(turnos completos) ### Plan del Research Manager
## III. Propuesta del Trader
## IV. Debate de riesgo
(turnos completos)
## V. Decisión del Portfolio Manager
## Aviso
Análisis generado por IA con fines educativos y de investigación; no es asesoramiento financiero.
```

En el chat, responde corto: el rating, entrada/stop/tamaño, las 3 razones que
decidieron, qué cambiaría la tesis, y la ruta del informe completo. No pegues
el informe entero en el chat.

## Límites

- **No ejecutes órdenes** aunque haya un conector de bróker con esa capacidad.
  Esta skill analiza; si el usuario quiere operar, que lo pida aparte y
  explícitamente.
- Sé honesto sobre la calidad de los datos: si faltan fundamentales (ETF,
  cripto) o noticias, dilo en el informe en vez de rellenar.
