"""
Centralized output formatting for tvfetch skill scripts.

Dual-mode:
  - TTY (human in terminal): Rich tables, panels, colors — trading terminal aesthetic
  - Pipe (Claude running script): Tagged sections === NAME === for AI parsing
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# ── Dual-mode detection ──────────────────────────────────────────────────────

def _is_tty() -> bool:
    """Return True when stdout is a real terminal (not piped to Claude)."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

# ── Color scheme — trading terminal aesthetic ────────────────────────────────

_UP = "green"
_DOWN = "red"
_HEADER = "bold cyan"
_NEUTRAL = "yellow"
_DIM = "dim"
_VALUE = "bold white"
_BORDER = "cyan"

TIMEFRAME_LABELS: dict[str, str] = {
    "1": "1 min", "3": "3 min", "5": "5 min", "10": "10 min",
    "15": "15 min", "30": "30 min", "45": "45 min",
    "60": "1 hour", "120": "2 hour", "180": "3 hour", "240": "4 hour",
    "1D": "Daily", "1W": "Weekly", "1M": "Monthly",
}


def _clr(val: float, invert: bool = False) -> str:
    """Return 'green' for positive, 'red' for negative."""
    if invert:
        return _DOWN if val > 0 else _UP if val < 0 else _NEUTRAL
    return _UP if val > 0 else _DOWN if val < 0 else _NEUTRAL


def _fmt_price(val: float) -> str:
    """Format price with commas. Auto-detect decimal places."""
    if abs(val) >= 100:
        return f"{val:,.2f}"
    elif abs(val) >= 1:
        return f"{val:,.4f}"
    else:
        return f"{val:.6f}"


def _fmt_pct(val: float) -> str:
    """Format percentage with sign."""
    return f"{val:+.2f}%"


# ══════════════════════════════════════════════════════════════════════════════
#  FETCH RESULT
# ══════════════════════════════════════════════════════════════════════════════

def print_fetch_result(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    source: str,
    auth_mode: str,
    warnings: list[str] | None = None,
    max_rows: int = 20,
) -> None:
    if _is_tty():
        _rich_fetch_result(symbol, timeframe, df, source, auth_mode, warnings, max_rows)
    else:
        _tagged_fetch_result(symbol, timeframe, df, source, auth_mode, warnings, max_rows)


def _rich_fetch_result(symbol, timeframe, df, source, auth_mode, warnings, max_rows):
    console = Console(highlight=False)
    tf_label = TIMEFRAME_LABELS.get(timeframe, timeframe)

    # Header info
    header = Text()
    if not df.empty:
        date_from = df.index[0].strftime("%Y-%m-%d")
        date_to = df.index[-1].strftime("%Y-%m-%d")
        header.append(f"  Period: {date_from} → {date_to}\n", style=_DIM)

        latest = df.iloc[-1]
        header.append("  Latest: ", style=_DIM)
        header.append(f"{_fmt_price(latest['close'])}", style=_VALUE)

        if len(df) >= 2:
            prev = df.iloc[-2]["close"]
            change_pct = (latest["close"] - prev) / prev * 100
            header.append("   Change: ", style=_DIM)
            header.append(_fmt_pct(change_pct), style=_clr(change_pct))
        header.append("\n")

    if warnings:
        for w in warnings:
            header.append(f"  ⚠ {w}\n", style=_NEUTRAL)

    title = f" {symbol} │ {tf_label} │ {len(df):,} bars │ {source} "
    console.print(Panel(header, title=title, border_style=_BORDER, box=box.ROUNDED, padding=(0, 1)))

    if not df.empty:
        table = Table(box=box.SIMPLE_HEAVY, show_edge=False, pad_edge=False, expand=False)
        table.add_column("Date", style=_DIM, min_width=12)
        table.add_column("Open", justify="right", min_width=12)
        table.add_column("High", justify="right", min_width=12, style=_UP)
        table.add_column("Low", justify="right", min_width=12, style=_DOWN)
        table.add_column("Close", justify="right", min_width=12)
        table.add_column("Volume", justify="right", min_width=12, style=_DIM)

        display = df.tail(max_rows)
        for idx, row in display.iterrows():
            close_style = _UP if row["close"] >= row["open"] else _DOWN
            table.add_row(
                idx.strftime("%Y-%m-%d %H:%M"),
                _fmt_price(row["open"]),
                _fmt_price(row["high"]),
                _fmt_price(row["low"]),
                f"[{close_style}]{_fmt_price(row['close'])}[/{close_style}]",
                f"{row['volume']:,.2f}",
            )

        if len(df) > max_rows:
            console.print(f"  [dim]showing last {max_rows} of {len(df):,} bars[/dim]")
        console.print(table)


def _tagged_fetch_result(symbol, timeframe, df, source, auth_mode, warnings, max_rows):
    """Plain tagged output for Claude parsing."""
    print("=== FETCH RESULT ===")
    print(f"SYMBOL: {symbol}")
    print(f"TIMEFRAME: {timeframe}")
    print(f"BARS: {len(df)}")
    print(f"SOURCE: {source}")
    print(f"AUTH_MODE: {auth_mode}")
    if not df.empty:
        print(f"DATE_FROM: {df.index[0].strftime('%Y-%m-%d')}")
        print(f"DATE_TO: {df.index[-1].strftime('%Y-%m-%d')}")
        latest = df.iloc[-1]
        print(f"LATEST_OPEN: {latest['open']:.4f}")
        print(f"LATEST_HIGH: {latest['high']:.4f}")
        print(f"LATEST_LOW: {latest['low']:.4f}")
        print(f"LATEST_CLOSE: {latest['close']:.4f}")
        print(f"LATEST_VOLUME: {latest['volume']:.2f}")
        if len(df) >= 2:
            prev_close = df.iloc[-2]["close"]
            change_pct = (latest["close"] - prev_close) / prev_close * 100
            print(f"PREV_CLOSE: {prev_close:.4f}")
            print(f"CHANGE_PCT: {change_pct:+.2f}%")
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    if not df.empty:
        print("=== DATA TABLE ===")
        display = df.tail(max_rows)
        print(f"{'Datetime (UTC)':<22} {'Open':>12} {'High':>12} {'Low':>12} {'Close':>12} {'Volume':>14}")
        print("-" * 88)
        for idx, row in display.iterrows():
            print(f"{idx.strftime('%Y-%m-%d %H:%M'):<22} {row['open']:>12.4f} {row['high']:>12.4f} {row['low']:>12.4f} {row['close']:>12.4f} {row['volume']:>14.2f}")
        if len(df) > max_rows:
            print(f"... ({len(df) - max_rows} earlier bars not shown)")
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS RESULT
# ══════════════════════════════════════════════════════════════════════════════

def print_analysis_result(stats: dict[str, Any]) -> None:
    if _is_tty():
        _rich_analysis_result(stats)
    else:
        _tagged_analysis_result(stats)


def _rich_analysis_result(stats):
    console = Console(highlight=False)
    symbol = stats.get("SYMBOL", "")
    tf_label = stats.get("TIMEFRAME_LABEL", stats.get("TIMEFRAME", ""))
    bars = stats.get("BARS", 0)

    body = Text()

    # Period
    body.append(f"  Period: {stats.get('DATE_FROM', '')} → {stats.get('DATE_TO', '')}\n", style=_DIM)
    body.append(f"  Latest: ", style=_DIM)
    body.append(f"{_fmt_price(stats.get('LATEST_CLOSE', 0))}\n\n", style=_VALUE)

    # Returns
    ret = stats.get("PERIOD_RETURN_PCT", 0)
    ann_ret = stats.get("ANN_RETURN_PCT", 0)
    body.append("  Return: ", style=_DIM)
    body.append(f"{_fmt_pct(ret)}", style=_clr(ret))
    body.append("       Ann. Return: ", style=_DIM)
    body.append(f"{_fmt_pct(ann_ret)}\n", style=_clr(ann_ret))

    # Volatility & Sharpe
    vol = stats.get("ANN_VOLATILITY_PCT", 0)
    sharpe = stats.get("SHARPE_RATIO", 0)
    body.append(f"  Volatility: {vol:.1f}%", style=_DIM)
    body.append(f"     Sharpe: ", style=_DIM)
    body.append(f"{sharpe:.2f}\n", style=_clr(sharpe))

    # Max Drawdown
    dd = stats.get("MAX_DRAWDOWN_PCT", 0)
    body.append("  Max Drawdown: ", style=_DIM)
    body.append(f"{dd:.1f}%", style=_DOWN)
    body.append(f"  ({stats.get('MAX_DD_START', '')} → {stats.get('MAX_DD_END', '')})\n\n", style=_DIM)

    # Period High/Low
    body.append(f"  High: {_fmt_price(stats.get('PERIOD_HIGH', 0))} ({stats.get('PERIOD_HIGH_DATE', '')})", style=_UP)
    body.append(f"   Low: {_fmt_price(stats.get('PERIOD_LOW', 0))} ({stats.get('PERIOD_LOW_DATE', '')})\n\n", style=_DOWN)

    # Moving Averages
    body.append("  ── Moving Averages ──\n", style=_HEADER)
    for period in [20, 50, 200]:
        key = f"SMA_{period}"
        val = stats.get(key, "N/A")
        above_key = f"ABOVE_SMA{period}"
        above = stats.get(above_key)
        if val != "N/A":
            arrow = "▲" if above else "▼"
            clr = _UP if above else _DOWN
            label = "ABOVE" if above else "BELOW"
            body.append(f"  SMA {period}:  {_fmt_price(val)}  ", style=_DIM)
            body.append(f"{arrow} {label}\n", style=clr)
        else:
            body.append(f"  SMA {period}:  N/A (need {period}+ bars)\n", style=_DIM)

    # RSI
    rsi = stats.get("RSI_14", "N/A")
    body.append("\n")
    if rsi != "N/A":
        rsi_clr = _DOWN if rsi > 70 else _UP if rsi < 30 else _NEUTRAL
        rsi_label = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
        body.append(f"  RSI(14): ", style=_DIM)
        body.append(f"{rsi:.1f}  {rsi_label}\n", style=rsi_clr)
    else:
        body.append(f"  RSI(14): N/A\n", style=_DIM)

    # Trend
    trend = stats.get("TREND", "sideways")
    trend_clr = _UP if trend == "uptrend" else _DOWN if trend == "downtrend" else _NEUTRAL
    body.append(f"  Trend: ", style=_DIM)
    body.append(f"{trend.title()}\n\n", style=trend_clr)

    # Interpretation
    interp = stats.get("INTERPRETATION", "")
    if interp:
        body.append(f"  {interp}\n", style="italic dim")

    title = f" {symbol} Analysis │ {tf_label} │ {bars} bars "
    console.print(Panel(body, title=title, border_style=_BORDER, box=box.ROUNDED, padding=(0, 1)))


def _tagged_analysis_result(stats):
    print("=== ANALYSIS RESULT ===")
    for key, val in stats.items():
        if isinstance(val, float):
            print(f"{key}: {val:.4f}")
        elif isinstance(val, datetime):
            print(f"{key}: {val.strftime('%Y-%m-%d')}")
        elif isinstance(val, bool):
            print(f"{key}: {'true' if val else 'false'}")
        else:
            print(f"{key}: {val}")
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATOR RESULT
# ══════════════════════════════════════════════════════════════════════════════

def print_indicator_result(
    symbol: str,
    timeframe: str,
    latest_close: float,
    indicators: dict[str, Any],
    signals: list[str],
) -> None:
    if _is_tty():
        _rich_indicator_result(symbol, timeframe, latest_close, indicators, signals)
    else:
        _tagged_indicator_result(symbol, timeframe, latest_close, indicators, signals)


def _rich_indicator_result(symbol, timeframe, latest_close, indicators, signals):
    console = Console(highlight=False)
    tf_label = TIMEFRAME_LABELS.get(timeframe, timeframe)

    body = Text()
    body.append(f"  Close: ", style=_DIM)
    body.append(f"{_fmt_price(latest_close)}\n\n", style=_VALUE)

    # Indicator values
    for name, val in indicators.items():
        body.append(f"  {name:<16}", style=_DIM)
        if isinstance(val, float):
            body.append(f"{_fmt_price(val)}\n", style=_VALUE)
        else:
            body.append(f"{val}\n", style=_VALUE)

    # Signals
    if signals:
        body.append(f"\n  ── Signals ──\n", style=_HEADER)
        for sig in signals:
            if sig.startswith("BULLISH"):
                body.append(f"  ● {sig}\n", style=_UP)
            elif sig.startswith("BEARISH"):
                body.append(f"  ● {sig}\n", style=_DOWN)
            else:
                body.append(f"  ○ {sig}\n", style=_NEUTRAL)

    title = f" {symbol} Indicators │ {tf_label} "
    console.print(Panel(body, title=title, border_style=_BORDER, box=box.ROUNDED, padding=(0, 1)))


def _tagged_indicator_result(symbol, timeframe, latest_close, indicators, signals):
    print("=== INDICATORS ===")
    print(f"SYMBOL: {symbol}")
    print(f"TIMEFRAME: {timeframe}")
    print(f"LATEST_CLOSE: {latest_close:.4f}")
    for name, val in indicators.items():
        if isinstance(val, float):
            print(f"{name}: {val:.4f}")
        else:
            print(f"{name}: {val}")
    if signals:
        print("=== SIGNALS ===")
        for sig in signals:
            print(sig)
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  COMPARE RESULT
# ══════════════════════════════════════════════════════════════════════════════

def print_compare_result(table: str, stats: dict[str, Any]) -> None:
    if _is_tty():
        _rich_compare_result(table, stats)
    else:
        _tagged_compare_result(table, stats)


def _rich_compare_result(table_str, stats):
    console = Console(highlight=False)
    symbols = stats.get("SYMBOLS", "")
    tf = stats.get("TIMEFRAME", "")
    bars = stats.get("BARS", 0)

    title = f" Compare: {symbols} │ {tf} │ {bars} bars "
    console.print(Panel(table_str, title=title, border_style=_BORDER, box=box.ROUNDED, padding=(0, 1)))


def _tagged_compare_result(table_str, stats):
    print("=== COMPARISON ===")
    for key, val in stats.items():
        if isinstance(val, float):
            print(f"{key}: {val:.4f}")
        else:
            print(f"{key}: {val}")
    print("=== TABLE ===")
    print(table_str)
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  SEARCH RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def print_search_results(results: list[dict]) -> None:
    if _is_tty():
        _rich_search_results(results)
    else:
        _tagged_search_results(results)


def _rich_search_results(results):
    console = Console(highlight=False)

    table = Table(
        title=f"Search Results ({len(results)} found)",
        box=box.ROUNDED,
        border_style=_BORDER,
        title_style=_HEADER,
        show_lines=False,
    )
    table.add_column("Symbol", style="bold cyan", min_width=25)
    table.add_column("Description", min_width=30)
    table.add_column("Exchange", style=_DIM)
    table.add_column("Type", style=_DIM)
    table.add_column("Currency", style=_DIM)

    for r in results:
        table.add_row(r["symbol"], r["description"], r["exchange"], r["type"], r["currency"])

    if not results:
        console.print("[dim]No results found.[/dim]")
    else:
        console.print(table)


def _tagged_search_results(results):
    print("=== SEARCH RESULTS ===")
    print(f"COUNT: {len(results)}")
    print(f"{'Symbol':<30} {'Description':<40} {'Exchange':<12} {'Type':<10} {'Currency':<8}")
    print("-" * 104)
    for r in results:
        print(f"{r['symbol']:<30} {r['description']:<40} {r['exchange']:<12} {r['type']:<10} {r['currency']:<8}")
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  STREAM SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def print_stream_summary(
    symbols: list[str],
    duration: float,
    update_count: int,
    session_stats: dict[str, Any],
) -> None:
    if _is_tty():
        _rich_stream_summary(symbols, duration, update_count, session_stats)
    else:
        _tagged_stream_summary(symbols, duration, update_count, session_stats)


def _rich_stream_summary(symbols, duration, update_count, session_stats):
    console = Console(highlight=False)

    body = Text()
    body.append(f"  Duration: {duration:.1f}s   Updates: {update_count}\n\n", style=_DIM)

    for sym, stats in session_stats.items():
        body.append(f"  ── {sym} ──\n", style=_HEADER)
        for key, val in stats.items():
            body.append(f"    {key}: ", style=_DIM)
            if "CHANGE" in key and isinstance(val, (int, float)):
                body.append(f"{val:.4f}\n", style=_clr(val))
            elif isinstance(val, float):
                body.append(f"{_fmt_price(val)}\n", style=_VALUE)
            else:
                body.append(f"{val}\n", style=_VALUE)
        body.append("\n")

    title = f" Stream Summary │ {', '.join(symbols)} "
    console.print(Panel(body, title=title, border_style=_BORDER, box=box.ROUNDED, padding=(0, 1)))


def _tagged_stream_summary(symbols, duration, update_count, session_stats):
    print("=== STREAM SUMMARY ===")
    print(f"SYMBOLS: {', '.join(symbols)}")
    print(f"DURATION: {duration:.1f}s")
    print(f"UPDATES: {update_count}")
    for sym, stats in session_stats.items():
        print(f"--- {sym} ---")
        for key, val in stats.items():
            if isinstance(val, float):
                print(f"  {key}: {val:.4f}")
            else:
                print(f"  {key}: {val}")
    print("=== END ===")


# ══════════════════════════════════════════════════════════════════════════════
#  STREAM TICK (live update line)
# ══════════════════════════════════════════════════════════════════════════════

def print_stream_tick(symbol: str, close: float, change_pct: float, volume: float, timestamp: str, direction: str) -> None:
    """Print a single live stream tick — colored in TTY, plain in pipe."""
    if _is_tty():
        console = Console(highlight=False)
        clr = _UP if direction == "+" else _DOWN
        console.print(
            f"  {symbol:<25} [{_VALUE}]{close:>12.4f}[/{_VALUE}]  "
            f"[{clr}]{change_pct:>+8.2f}%[/{clr}]  "
            f"[{_DIM}]vol={volume:>12.2f}  {timestamp}[/{_DIM}]"
        )
    else:
        print(f"  {symbol:<25} {close:>12.4f}  {change_pct:>+8.2f}%  vol={volume:>12.2f}  {timestamp} [{direction}]")


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def print_json_output(data: dict) -> None:
    """Machine-readable JSON — same in both modes."""
    print(json.dumps(data, indent=2, default=str))


def print_warning(msg: str) -> None:
    if _is_tty():
        Console(highlight=False).print(f"  [yellow]⚠ {msg}[/yellow]")
    else:
        print(f"WARNING: {msg}")


def print_progress(current: int, total: int) -> None:
    print(f"PROGRESS: {current}/{total} bars")
