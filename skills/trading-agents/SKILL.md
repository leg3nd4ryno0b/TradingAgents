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
| Analistas | los 4 |
| Rondas de debate de inversión | 1 (alcista y bajista hablan una vez cada uno) |
| Rondas de debate de riesgo | 1 (cada uno de los 3 habla una vez) |
| Idioma | el del usuario |
| Contexto de cartera | si el usuario dice que ya tiene posición, tamaño o tolerancia al riesgo, pásalo al Trader y al Portfolio Manager |

## Paso 1 — Datos reales

Los agentes del original trabajan con herramientas de datos; sin ellas, el
análisis es invención. Consigue datos en este orden y anota en el informe qué
fuente usaste:

1. **Script incluido** (preferido; calcula los mismos indicadores que el original):
   ```bash
   python <ruta-de-la-skill>/scripts/fetch_data.py TICKER --date YYYY-MM-DD --out datos_TICKER.md
   ```
   Instala `yfinance` y `pandas` solo si faltan. Si termina con
   `SIN_ACCESO_YAHOO`, la red no permite Yahoo: pasa a la opción 2.
2. **Conector de bróker** si está disponible (p. ej. Interactive Brokers:
   `get_price_snapshot`, `get_price_history`, `get_earnings_insight`). Con el
   historial de precios, calcula los indicadores importando `compute_indicators`
   del script (recibe un DataFrame con columnas `Open, High, Low, Close, Volume`).
3. **Búsqueda web**: precio actual, máx/mín 52 semanas, ratios, últimos
   resultados trimestrales, noticias de la semana. Cita la fuente y la fecha de
   cada número.
4. Si nada funciona, pide al usuario que pegue los datos o un CSV. No sigas con
   números inventados: un informe con niveles de precio inventados es peor que
   ninguno, porque parece accionable.

Además, para los analistas de **noticias y sentimiento**, haz búsquedas web de la
última semana (empresa, sector, macro, y sentimiento en redes) si hay búsqueda
disponible. El script solo trae titulares de Yahoo.

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
de posición.

## Paso 5 — Debate de riesgo

Por cada ronda: **Agresivo → Conservador → Neutral** (roles 9–11), cada uno
respondiendo a los otros dos sobre la propuesta del Trader.

## Paso 6 — Portfolio Manager

El **Portfolio Manager** (rol 12) decide el rating final. Si en la carpeta de
trabajo hay un informe anterior de este mismo ticker (`informe_TICKER_*.md`),
compáralo con el precio actual y pásale al PM la lección (¿la decisión
anterior acertó?). Así emula la memoria del original.

## Paso 7 — Entrega

Guarda todo en `informe_TICKER_YYYY-MM-DD.md` con esta estructura:

```markdown
# TradingAgents — TICKER — YYYY-MM-DD
**Rating final: <Buy|Overweight|Hold|Underweight|Sell>** · Entrada: X · Stop: Y · Fuente de datos: ...

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
