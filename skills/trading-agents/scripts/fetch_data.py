#!/usr/bin/env python3
"""Collect the market data a TradingAgents-style analysis needs, as one Markdown file.

Usage:
    python fetch_data.py TICKER [--date YYYY-MM-DD] [--out data.md]

Sections: verified price snapshot, last 30 sessions of OHLCV, technical
indicators (computed locally with pandas, the same set TradingAgents offers its
market analyst), company profile and key ratios, quarterly financial
statements, insider transactions and recent news headlines.

Every section is fetched independently: if one fails (no network, field
missing for an ETF/crypto, Yahoo rate limit), the file says so in that section
and the rest is still written, so the analyst can say "not available" instead
of guessing. Requires: yfinance, pandas (installed on first run if missing).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta


def _ensure_deps() -> None:
    try:
        import pandas  # noqa: F401
        import yfinance  # noqa: F401
    except ImportError:
        print("Installing yfinance + pandas...", file=sys.stderr)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "yfinance", "pandas"],
            check=False,
        )


_ensure_deps()

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

# --------------------------------------------------------------------------- #
# Indicators (same names as TradingAgents' market analyst toolset)
# --------------------------------------------------------------------------- #


def _wilder(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1 / n, adjust=False).mean()


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, low, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    out["close_10_ema"] = c.ewm(span=10, adjust=False).mean()
    out["close_50_sma"] = c.rolling(50).mean()
    out["close_200_sma"] = c.rolling(200).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macds"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macdh"] = out["macd"] - out["macds"]
    delta = c.diff()
    gain, loss = _wilder(delta.clip(lower=0), 14), _wilder(-delta.clip(upper=0), 14)
    out["rsi"] = 100 - 100 / (1 + gain / loss)
    out["boll"] = c.rolling(20).mean()
    std = c.rolling(20).std()
    out["boll_ub"], out["boll_lb"] = out["boll"] + 2 * std, out["boll"] - 2 * std
    tr = pd.concat([h - low, (h - c.shift()).abs(), (low - c.shift()).abs()], axis=1).max(axis=1)
    out["atr"] = _wilder(tr, 14)
    out["vwma"] = (c * v).rolling(14).sum() / v.rolling(14).sum()  # stockstats default window
    return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _fmt(x, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "n/d"
    if isinstance(x, (int, float)):
        if abs(x) >= 1e9:
            return f"{x / 1e9:,.2f}B"
        if abs(x) >= 1e6:
            return f"{x / 1e6:,.2f}M"
        return f"{x:,.{nd}f}"
    return str(x)


def _table(df: pd.DataFrame, nd: int = 2) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(["fecha", *cols]) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        label = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
        lines.append("| " + " | ".join([label, *(_fmt(v, nd) for v in row.values)]) + " |")
    return "\n".join(lines)


def _section(title: str, fn) -> str:
    try:
        body = fn()
    except Exception as exc:  # one failed section must not sink the others
        body = f"_No disponible: {type(exc).__name__}: {exc}_"
    return f"## {title}\n\n{body}\n"


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #


def build_report(ticker: str, trade_date: date) -> str:
    t = yf.Ticker(ticker)
    end = trade_date + timedelta(days=1)  # yfinance end is exclusive
    try:
        hist = t.history(start=trade_date - timedelta(days=420), end=end, auto_adjust=False)
    except Exception as exc:
        raise SystemExit(
            f"SIN_ACCESO_YAHOO: no se pudo contactar Yahoo Finance ({type(exc).__name__}). "
            "Probablemente la red de este entorno no permite *.finance.yahoo.com. "
            "Usa las fuentes alternativas descritas en SKILL.md (paso 1)."
        ) from None
    if hist.empty:
        raise SystemExit(f"Sin datos de precio para {ticker} hasta {trade_date}. ¿Ticker correcto?")
    hist.index = hist.index.tz_localize(None)
    ind = compute_indicators(hist)
    last = hist.index[-1]

    def snapshot() -> str:
        r, i = hist.iloc[-1], ind.iloc[-1]
        prev = hist["Close"].iloc[-2] if len(hist) > 1 else float("nan")
        chg = (r["Close"] / prev - 1) * 100
        hi52 = hist["High"].iloc[-252:].max()
        lo52 = hist["Low"].iloc[-252:].min()
        rows = [
            ("Última sesión", last.strftime("%Y-%m-%d")),
            ("Cierre", _fmt(r["Close"])),
            ("Variación diaria %", _fmt(chg)),
            ("Apertura / Máx / Mín", f"{_fmt(r['Open'])} / {_fmt(r['High'])} / {_fmt(r['Low'])}"),
            ("Volumen", _fmt(r["Volume"], 0)),
            ("Máx / Mín 52 semanas", f"{_fmt(hi52)} / {_fmt(lo52)}"),
            ("Rend. 1M / 3M / 6M %", " / ".join(
                _fmt((r["Close"] / hist["Close"].iloc[-n] - 1) * 100) if len(hist) > n else "n/d"
                for n in (21, 63, 126))),
        ] + [(k, _fmt(i[k])) for k in ind.columns if k != "close"]
        note = ""
        if last.date() < trade_date:
            note = f"\n_La fecha pedida ({trade_date}) no fue sesión; se usa la última sesión disponible._\n"
        return "Fuente de verdad para cualquier precio o valor de indicador citado.\n" + note + "\n" + "\n".join(
            ["| dato | valor |", "|---|---|", *(f"| {k} | {v} |" for k, v in rows)])

    def ohlcv() -> str:
        cols = ["Open", "High", "Low", "Close", "Volume"]
        return _table(hist[cols].tail(30))

    def indicators() -> str:
        weekly = ind.drop(columns="close").iloc[::-5].head(12).iloc[::-1]
        return "Valores cada 5 sesiones (≈ semanal), últimas 12 semanas:\n\n" + _table(weekly)

    def profile() -> str:
        info = t.info or {}
        keys = [
            ("longName", "Nombre"), ("quoteType", "Tipo"), ("sector", "Sector"),
            ("industry", "Industria"), ("country", "País"), ("currency", "Moneda"),
            ("marketCap", "Capitalización"), ("enterpriseValue", "Enterprise value"),
            ("trailingPE", "P/E (trailing)"), ("forwardPE", "P/E (forward)"),
            ("pegRatio", "PEG"), ("priceToBook", "P/B"), ("priceToSalesTrailing12Months", "P/S"),
            ("enterpriseToEbitda", "EV/EBITDA"), ("profitMargins", "Margen neto"),
            ("operatingMargins", "Margen operativo"), ("grossMargins", "Margen bruto"),
            ("returnOnEquity", "ROE"), ("returnOnAssets", "ROA"),
            ("revenueGrowth", "Crec. ingresos (yoy)"), ("earningsGrowth", "Crec. beneficios (yoy)"),
            ("totalCash", "Caja total"), ("totalDebt", "Deuda total"), ("debtToEquity", "Deuda/Patrimonio"),
            ("currentRatio", "Current ratio"), ("freeCashflow", "Free cash flow"),
            ("dividendYield", "Dividend yield"), ("beta", "Beta"),
            ("shortPercentOfFloat", "Short % float"), ("heldPercentInsiders", "% insiders"),
            ("heldPercentInstitutions", "% instituciones"),
            ("recommendationKey", "Consenso analistas"), ("targetMeanPrice", "Precio objetivo medio"),
            ("numberOfAnalystOpinions", "Nº analistas"),
        ]
        rows = [(label, _fmt(info.get(k), 4 if isinstance(info.get(k), float) and abs(info.get(k)) < 1 else 2))
                for k, label in keys if info.get(k) is not None]
        summary = (info.get("longBusinessSummary") or "")[:1200]
        note = ("_Nota: el perfil y los ratios son los actuales de Yahoo, no los de la fecha pedida._\n\n"
                if trade_date < date.today() - timedelta(days=3) else "")
        return note + "\n".join(["| dato | valor |", "|---|---|", *(f"| {a} | {b} |" for a, b in rows)]) + (
            f"\n\n**Descripción:** {summary}" if summary else "")

    def statement(attr: str, wanted: list[str]):
        def run() -> str:
            df = getattr(t, attr)
            if df is None or df.empty:
                return "_Sin datos._"
            df = df.loc[:, [c for c in df.columns if pd.Timestamp(c).date() <= trade_date]].iloc[:, :4]
            rows = [r for r in wanted if r in df.index]
            if not rows:
                return "_Sin las partidas habituales._"
            return _table(df.loc[rows].T.sort_index())
        return run

    def insiders() -> str:
        df = t.insider_transactions
        if df is None or df.empty:
            return "_Sin transacciones reportadas._"
        cols = [c for c in ("Start Date", "Insider", "Position", "Transaction", "Text", "Shares", "Value") if c in df.columns]
        df = df[cols].head(15)
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(str(_fmt(v, 0)).replace("|", "/")[:80] for v in r.values) + " |")
        return "\n".join(lines)

    def news() -> str:
        items = t.news or []
        lines = []
        for it in items[:20]:
            c = it.get("content", it)
            title = c.get("title")
            if not title:
                continue
            when = c.get("pubDate") or c.get("displayTime") or ""
            if not when and it.get("providerPublishTime"):
                when = datetime.fromtimestamp(it["providerPublishTime"]).isoformat()
            src = (c.get("provider") or {}).get("displayName") or c.get("publisher", "")
            summ = (c.get("summary") or "")[:300]
            lines.append(f"- **{when[:10]}** · {src} — {title}" + (f"\n  {summ}" if summ else ""))
        if not lines:
            return "_Sin titulares._"
        hdr = ("_Yahoo solo entrega titulares recientes; si la fecha de análisis es pasada, "
               "descarta los posteriores a ella._\n\n") if trade_date < date.today() - timedelta(days=3) else ""
        return hdr + "\n".join(lines)

    parts = [
        f"# Datos de mercado: {ticker.upper()} — fecha de análisis {trade_date}\n",
        _section("1. Snapshot verificado", snapshot),
        _section("2. OHLCV — últimas 30 sesiones", ohlcv),
        _section("3. Indicadores técnicos", indicators),
        _section("4. Perfil y ratios", profile),
        _section("5. Estado de resultados (trimestral)", statement(
            "quarterly_income_stmt",
            ["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Diluted EPS", "EBITDA"])),
        _section("6. Balance (trimestral)", statement(
            "quarterly_balance_sheet",
            ["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity",
             "Cash And Cash Equivalents", "Total Debt", "Net Debt"])),
        _section("7. Flujo de caja (trimestral)", statement(
            "quarterly_cashflow",
            ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
             "Repurchase Of Capital Stock", "Cash Dividends Paid"])),
        _section("8. Transacciones de insiders", insiders),
        _section("9. Noticias recientes", news),
    ]
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker", help="Símbolo de Yahoo Finance, p. ej. NVDA, SPY, BTC-USD, GGAL.BA")
    ap.add_argument("--date", default=date.today().isoformat(), help="Fecha de análisis YYYY-MM-DD (por defecto hoy)")
    ap.add_argument("--out", help="Archivo de salida .md (por defecto, salida estándar)")
    a = ap.parse_args()
    report = build_report(a.ticker, datetime.strptime(a.date, "%Y-%m-%d").date())
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Datos guardados en {a.out}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
