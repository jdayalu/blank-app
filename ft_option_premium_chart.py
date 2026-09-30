#!/usr/bin/env python3
"""Financial Times editorial style for intraday option premium charts.

Matplotlib/pandas write the email PNG. Plotly uses the same palette and
callouts for the Streamlit gallery.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

import pandas as pd

PACIFIC = ZoneInfo("America/Los_Angeles")
OUT_DIR = Path.home() / "spx_daily_outlook"

FT_BG = "#fff1e5"
FT_TEAL = "#0d7680"
FT_TEAL_FILL = "rgba(13, 118, 128, 0.08)"
FT_CLARET = "#990f3d"
FT_INK = "#111111"
FT_SUB = "#55504a"
FT_GRID = "#e8dcd0"
FT_SPINE = "#262a33"
FT_LINEWIDTH = 2.4

COMPANY_NAMES = {
    "AAPL": "Apple",
    "AKAM": "Akamai",
    "AMZN": "Amazon",
    "CBOE": "Cboe",
    "GOOG": "Alphabet",
    "GOOGL": "Alphabet",
    "MDB": "MongoDB",
    "META": "Meta",
    "MSFT": "Microsoft",
    "NFLX": "Netflix",
    "NVDA": "Nvidia",
    "SNDK": "Sandisk",
    "SPX": "S&P 500",
    "TSLA": "Tesla",
    "XOM": "Exxon Mobil",
}

SAMPLE_TIMES = [
    "06:34",
    "06:36",
    "06:51",
    "07:00",
    "07:30",
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:15",
    "11:30",
    "11:45",
    "12:00",
    "12:15",
    "12:30",
    "12:45",
    "12:50",
    "13:00",
]
SAMPLE_PRICES = [
    4.45,
    5.38,
    5.43,
    6.55,
    6.63,
    5.33,
    5.80,
    5.43,
    5.35,
    5.45,
    5.75,
    5.83,
    5.53,
    8.13,
    6.38,
    5.10,
    4.80,
    5.03,
    6.03,
    6.63,
    6.13,
]


def company_name(symbol: str, override: str | None = None) -> str:
    if override:
        return override.strip()
    return COMPANY_NAMES.get(symbol.strip().upper(), symbol.strip().upper())


def side_word(side: str) -> str:
    return "Call" if str(side).upper().startswith("C") else "Put"


def headline(symbol: str, strike: float, side: str, *, company: str | None = None) -> str:
    name = company_name(symbol, company)
    ticker = symbol.strip().upper()
    return f"{name} (${ticker}) {strike:g} {side_word(side)} Option Premium"


def subtitle_text(prices: list[float], *, trigger: str | None = None) -> str:
    lo, hi = min(prices), max(prices)
    rang = f"Intraday contract range: ${lo:.2f} – ${hi:.2f}"
    if trigger:
        return f"Underlying trigger: {trigger} | {rang}"
    return rang


def _clock(value: datetime) -> str:
    hour = value.astimezone(PACIFIC).hour if value.tzinfo else value.hour
    minute = value.minute
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def _parse_clock(raw: object, session_day: date) -> datetime:
    if isinstance(raw, datetime):
        value = raw
        if value.tzinfo is None:
            value = value.replace(tzinfo=PACIFIC)
        return value.astimezone(PACIFIC)
    text = str(raw).strip()
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=PACIFIC)
        return value.astimezone(PACIFIC)
    except ValueError:
        pass
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            parsed = datetime.strptime(text.replace(".", ""), fmt).time()
            return datetime.combine(session_day, parsed, tzinfo=PACIFIC)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {raw!r}")


def premium_frame(
    times: list[object],
    prices: list[float],
    *,
    session_day: date | None = None,
) -> pd.DataFrame:
    if len(times) != len(prices):
        raise ValueError("times and prices must be the same length")
    day = session_day or datetime.now(PACIFIC).date()
    rows = [
        {"time": _parse_clock(stamp, day), "price": float(price)}
        for stamp, price in zip(times, prices)
        if price is not None
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values("time").reset_index(drop=True)


def frame_from_points(
    points: list[tuple[object, float]] | tuple[tuple[object, float], ...],
    *,
    session_day: date | None = None,
) -> pd.DataFrame:
    times = [item[0] for item in points]
    prices = [float(item[1]) for item in points]
    return premium_frame(times, prices, session_day=session_day)


def ohlc_frame(
    bars: list[dict] | tuple[dict, ...],
    *,
    session_day: date | None = None,
) -> pd.DataFrame:
    day = session_day or datetime.now(PACIFIC).date()
    rows = []
    for bar in bars:
        stamp = bar.get("ts") or bar.get("time")
        if stamp is None:
            continue
        try:
            rows.append(
                {
                    "time": _parse_clock(stamp, day),
                    "open": float(bar["o"] if "o" in bar else bar["open"]),
                    "high": float(bar["h"] if "h" in bar else bar["high"]),
                    "low": float(bar["l"] if "l" in bar else bar["low"]),
                    "close": float(bar["c"] if "c" in bar else bar["close"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values("time").reset_index(drop=True)


def _serif() -> str:
    return "Georgia, DejaVu Serif, serif"


def _sans() -> str:
    return "Arial, DejaVu Sans, sans-serif"


def _mpl_font(preferred: tuple[str, ...], fallback: str) -> str:
    from matplotlib import font_manager

    available = {item.name for item in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            return name
    return fallback


def _naive_pt(value: object) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(PACIFIC)
    else:
        stamp = stamp.tz_convert(PACIFIC)
    return stamp.tz_localize(None).to_pydatetime()


def _extrema(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    first = frame.iloc[0]
    last = frame.iloc[-1]
    hod = frame.loc[frame["price"].idxmax()]
    return first, hod, last


def render_ft_premium_png(
    frame: pd.DataFrame,
    *,
    dest: Path,
    symbol: str,
    strike: float,
    side: str,
    company: str | None = None,
    trigger: str | None = None,
    source: str = "Source: Live trading terminal log",
    title: str | None = None,
    ylabel: str = "Option premium ($)",
    kicker: str = "INTRADAY OPTIONS EXECUTION",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dest = dest.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    prices = [float(value) for value in frame["price"]]
    first, hod, last = _extrema(frame)
    serif = _mpl_font(("Georgia", "DejaVu Serif", "Times New Roman"), "DejaVu Serif")
    sans = _mpl_font(("Arial", "Helvetica", "DejaVu Sans"), "DejaVu Sans")

    fig, ax = plt.subplots(figsize=(11.2, 7.0), dpi=200, facecolor=FT_BG)
    ax.set_facecolor(FT_BG)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.74, bottom=0.14)

    fig.text(
        0.09,
        0.955,
        kicker,
        fontfamily=sans,
        fontsize=8.5,
        fontweight="bold",
        color=FT_TEAL,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.905,
        title or headline(symbol, strike, side, company=company),
        fontfamily=serif,
        fontsize=15,
        fontweight="bold",
        color=FT_INK,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.855,
        subtitle_text(prices, trigger=trigger),
        fontfamily=serif,
        fontsize=9.5,
        fontstyle="italic",
        color=FT_SUB,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.035,
        source if source.lower().startswith("source") else f"Source: {source}",
        fontfamily=sans,
        fontsize=8,
        color=FT_SUB,
        transform=fig.transFigure,
    )

    plot_x = [_naive_pt(ts) for ts in frame["time"]]
    first_x = _naive_pt(first["time"])
    hod_x = _naive_pt(hod["time"])
    last_x = _naive_pt(last["time"])
    ax.plot(
        plot_x,
        frame["price"],
        color=FT_TEAL,
        linewidth=FT_LINEWIDTH,
        solid_capstyle="round",
        zorder=3,
    )
    y_min = min(prices) - max((max(prices) - min(prices)) * 0.18, 0.35)
    y_max = max(prices) + max((max(prices) - min(prices)) * 0.22, 0.45)
    ax.set_ylim(y_min, y_max)
    ax.fill_between(plot_x, frame["price"], y_min, color=FT_TEAL, alpha=0.08, zorder=1)

    ax.scatter([first_x], [first["price"]], s=28, color=FT_TEAL, zorder=4)
    ax.scatter([last_x], [last["price"]], s=28, color=FT_TEAL, zorder=4)
    ax.scatter([hod_x], [hod["price"]], s=90, color=FT_CLARET, zorder=5, edgecolors=FT_BG, linewidths=1.2)

    ax.annotate(
        f"${first['price']:.2f} ({_clock(first['time'])})",
        xy=(first_x, first["price"]),
        xytext=(12, 14),
        textcoords="offset points",
        fontfamily=sans,
        fontsize=8.5,
        color=FT_INK,
        zorder=6,
    )
    hod_up = hod["price"] >= last["price"]
    ax.annotate(
        f"{_clock(hod['time'])} (${hod['price']:.2f})",
        xy=(hod_x, hod["price"]),
        xytext=(0, 22 if hod_up else -28),
        textcoords="offset points",
        fontfamily=serif,
        fontsize=10,
        fontweight="bold",
        color=FT_CLARET,
        ha="center",
        arrowprops={
            "arrowstyle": "-|>",
            "color": FT_CLARET,
            "lw": 1.6,
            "shrinkA": 0,
            "shrinkB": 4,
        },
        zorder=6,
    )
    if hod["time"] != last["time"] or abs(float(hod["price"]) - float(last["price"])) > 1e-9:
        ax.annotate(
            f"${last['price']:.2f}",
            xy=(last_x, last["price"]),
            xytext=(-8, 14),
            textcoords="offset points",
            fontfamily=sans,
            fontsize=8.5,
            color=FT_INK,
            ha="right",
            zorder=6,
        )

    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color(FT_SPINE)
    ax.spines["bottom"].set_linewidth(1.2)
    ax.yaxis.grid(True, color=FT_GRID, linestyle="-", linewidth=0.8)
    ax.xaxis.grid(True, color=FT_GRID, linestyle=":", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, colors=FT_SUB, labelsize=8.5)
    ax.tick_params(axis="x", length=4, colors=FT_SUB, labelsize=8, pad=6)
    ax.set_ylabel(ylabel, fontfamily=serif, fontsize=10, color=FT_INK, labelpad=8)
    ax.yaxis.label.set_fontfamily(serif)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(sans)
    from matplotlib.dates import AutoDateLocator, DateFormatter

    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    if len(frame) > 12:
        ax.xaxis.set_major_locator(AutoDateLocator(maxticks=10))
    fig.savefig(
        dest,
        dpi=200,
        bbox_inches="tight",
        facecolor=FT_BG,
        edgecolor="none",
    )
    plt.close(fig)
    return dest


def render_ft_ohlc_png(
    frame: pd.DataFrame,
    *,
    dest: Path,
    symbol: str,
    strike: float,
    side: str,
    company: str | None = None,
    trigger: str | None = None,
    source: str = "Source: Yahoo Finance 1-minute OHLC",
    interval_label: str = "1-MINUTE OHLC",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.dates import AutoDateLocator, DateFormatter, date2num
    from matplotlib.patches import Rectangle

    dest = dest.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    needed = {"time", "open", "high", "low", "close"}
    if frame.empty or not needed.issubset(frame.columns):
        raise ValueError("OHLC frame needs time, open, high, low, close")

    highs = [float(value) for value in frame["high"]]
    lows = [float(value) for value in frame["low"]]
    hi_row = frame.loc[frame["high"].idxmax()]
    lo_row = frame.loc[frame["low"].idxmin()]
    last = frame.iloc[-1]
    serif = _mpl_font(("Georgia", "DejaVu Serif", "Times New Roman"), "DejaVu Serif")
    sans = _mpl_font(("Arial", "Helvetica", "DejaVu Sans"), "DejaVu Sans")
    interval_note = interval_label.replace("-", " ").title()
    sub = subtitle_text(highs + lows, trigger=trigger)
    if "Intraday contract range" in sub:
        sub = sub.replace(
            "Intraday contract range",
            f"{interval_note}  ·  session range",
        )

    fig, ax = plt.subplots(figsize=(11.2, 7.0), dpi=200, facecolor=FT_BG)
    ax.set_facecolor(FT_BG)
    fig.subplots_adjust(left=0.09, right=0.90, top=0.74, bottom=0.14)

    fig.text(
        0.09,
        0.955,
        f"INTRADAY OPTIONS EXECUTION  ·  {interval_label}",
        fontfamily=sans,
        fontsize=8.5,
        fontweight="bold",
        color=FT_TEAL,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.905,
        headline(symbol, strike, side, company=company),
        fontfamily=serif,
        fontsize=15,
        fontweight="bold",
        color=FT_INK,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.855,
        sub,
        fontfamily=serif,
        fontsize=9.5,
        fontstyle="italic",
        color=FT_SUB,
        transform=fig.transFigure,
    )
    fig.text(
        0.09,
        0.035,
        source if source.lower().startswith("source") else f"Source: {source}",
        fontfamily=sans,
        fontsize=8,
        color=FT_SUB,
        transform=fig.transFigure,
    )

    plot_x = [_naive_pt(ts) for ts in frame["time"]]
    xs = [date2num(ts) for ts in plot_x]
    session_hi = float(hi_row["high"])
    session_lo = float(lo_row["low"])
    y_min = session_lo - max((session_hi - session_lo) * 0.16, 0.35)
    y_max = session_hi + max((session_hi - session_lo) * 0.20, 0.45)
    ax.set_ylim(y_min, y_max)
    session_day = plot_x[0].date()
    x_left = datetime.combine(session_day, datetime.min.time()).replace(hour=6, minute=25)
    x_right = datetime.combine(session_day, datetime.min.time()).replace(hour=13, minute=5)
    ax.set_xlim(x_left, x_right)
    span = max(date2num(x_right) - date2num(x_left), 1.0 / 1440.0)
    # Size bars from the session span so sparse option prints stay readable.
    body_w = max(span / max(len(xs) * 1.55, 1), span * 0.008, 3.0 / 1440.0)
    half = body_w * 0.62
    min_body = max((y_max - y_min) * 0.028, 0.16)

    for x, open_px, high_px, low_px, close_px in zip(
        xs, frame["open"], frame["high"], frame["low"], frame["close"]
    ):
        open_px = float(open_px)
        high_px = float(high_px)
        low_px = float(low_px)
        close_px = float(close_px)
        up = close_px >= open_px
        color = FT_TEAL if up else FT_CLARET
        ax.plot(
            [x, x],
            [low_px, high_px],
            color=color,
            linewidth=1.35,
            solid_capstyle="round",
            zorder=3,
        )
        ax.plot([x - half, x], [open_px, open_px], color=color, linewidth=2.0, zorder=4)
        ax.plot([x, x + half], [close_px, close_px], color=color, linewidth=2.0, zorder=4)
        body_lo = min(open_px, close_px)
        body_hi = max(open_px, close_px)
        height = max(body_hi - body_lo, min_body)
        if body_hi - body_lo < min_body:
            body_lo = (open_px + close_px) / 2.0 - height / 2.0
        ax.add_patch(
            Rectangle(
                (x - body_w / 2.0, body_lo),
                body_w,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.4,
                alpha=0.92,
                zorder=4,
            )
        )

    ax.axhline(session_hi, color=FT_CLARET, linestyle=(0, (4, 3)), linewidth=1.25, zorder=2)
    ax.axhline(session_lo, color=FT_TEAL, linestyle=(0, (4, 3)), linewidth=1.25, zorder=2)

    hi_x = _naive_pt(hi_row["time"])
    lo_x = _naive_pt(lo_row["time"])
    last_x = _naive_pt(last["time"])
    ax.scatter([hi_x], [session_hi], s=78, color=FT_CLARET, zorder=5, edgecolors=FT_BG, linewidths=1.1)
    ax.scatter([lo_x], [session_lo], s=78, color=FT_TEAL, zorder=5, edgecolors=FT_BG, linewidths=1.1)

    ax.annotate(
        f"HIGH  {_clock(hi_row['time'])}  (${session_hi:.2f})",
        xy=(hi_x, session_hi),
        xytext=(0, 20),
        textcoords="offset points",
        fontfamily=serif,
        fontsize=10,
        fontweight="bold",
        color=FT_CLARET,
        ha="center",
        arrowprops={
            "arrowstyle": "-|>",
            "color": FT_CLARET,
            "lw": 1.5,
            "shrinkA": 0,
            "shrinkB": 4,
        },
        zorder=6,
    )
    ax.annotate(
        f"LOW  {_clock(lo_row['time'])}  (${session_lo:.2f})",
        xy=(lo_x, session_lo),
        xytext=(0, -26),
        textcoords="offset points",
        fontfamily=serif,
        fontsize=10,
        fontweight="bold",
        color=FT_TEAL,
        ha="center",
        arrowprops={
            "arrowstyle": "-|>",
            "color": FT_TEAL,
            "lw": 1.5,
            "shrinkA": 0,
            "shrinkB": 4,
        },
        zorder=6,
    )
    ax.annotate(
        f"${float(last['close']):.2f}",
        xy=(last_x, float(last["close"])),
        xytext=(-8, 12),
        textcoords="offset points",
        fontfamily=sans,
        fontsize=8.5,
        color=FT_INK,
        ha="right",
        zorder=6,
    )
    ax.text(
        1.01,
        session_hi,
        f"HIGH  ${session_hi:.2f}",
        transform=ax.get_yaxis_transform(),
        fontfamily=sans,
        fontsize=8,
        fontweight="bold",
        color=FT_CLARET,
        va="center",
        clip_on=False,
    )
    ax.text(
        1.01,
        session_lo,
        f"LOW  ${session_lo:.2f}",
        transform=ax.get_yaxis_transform(),
        fontfamily=sans,
        fontsize=8,
        fontweight="bold",
        color=FT_TEAL,
        va="center",
        clip_on=False,
    )

    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color(FT_SPINE)
    ax.spines["bottom"].set_linewidth(1.2)
    ax.yaxis.grid(True, color=FT_GRID, linestyle="-", linewidth=0.8)
    ax.xaxis.grid(True, color=FT_GRID, linestyle=":", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, colors=FT_SUB, labelsize=8.5)
    ax.tick_params(axis="x", length=4, colors=FT_SUB, labelsize=8, pad=6)
    ax.set_ylabel("Option premium ($)", fontfamily=serif, fontsize=10, color=FT_INK, labelpad=8)
    ax.yaxis.label.set_fontfamily(serif)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(sans)
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    if len(frame) > 12:
        ax.xaxis.set_major_locator(AutoDateLocator(maxticks=10))
    fig.savefig(
        dest,
        dpi=200,
        bbox_inches="tight",
        facecolor=FT_BG,
        edgecolor="none",
    )
    plt.close(fig)
    return dest


def ft_premium_figure(
    frame: pd.DataFrame,
    *,
    symbol: str,
    strike: float,
    side: str,
    company: str | None = None,
    trigger: str | None = None,
    source: str = "Source: Live trading terminal log",
    title: str | None = None,
    ylabel: str = "Option premium ($)",
    kicker: str = "INTRADAY OPTIONS EXECUTION",
    tickprefix: str = "$",
):
    import plotly.graph_objects as go

    prices = [float(value) for value in frame["price"]]
    times = list(frame["time"])
    first, hod, last = _extrema(frame)
    y_min = min(prices) - max((max(prices) - min(prices)) * 0.18, 0.35)
    y_max = max(prices) + max((max(prices) - min(prices)) * 0.22, 0.45)
    title = (
        f"<span style='font-family:Arial,DejaVu Sans,sans-serif;font-size:11px;"
        f"font-weight:700;color:{FT_TEAL};letter-spacing:0.04em'>"
        f"{kicker}</span><br>"
        f"<span style='font-family:Georgia,DejaVu Serif,serif;font-size:22px;"
        f"font-weight:700;color:{FT_INK}'>"
        f"{title or headline(symbol, strike, side, company=company)}</span><br>"
        f"<span style='font-family:Georgia,DejaVu Serif,serif;font-size:13px;"
        f"font-style:italic;color:{FT_SUB}'>"
        f"{subtitle_text(prices, trigger=trigger)}</span>"
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times,
            y=[y_min] * len(times),
            mode="lines",
            line={"width": 0, "color": FT_TEAL},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=prices,
            mode="lines",
            name=f"{symbol} {strike:g}{side_word(side)[0]}",
            line={"color": FT_TEAL, "width": FT_LINEWIDTH, "shape": "linear"},
            fill="tonexty",
            fillcolor=FT_TEAL_FILL,
            hovertemplate="%{x|%-I:%M %p}<br>$%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[hod["time"]],
            y=[hod["price"]],
            mode="markers",
            marker={"size": 14, "color": FT_CLARET, "line": {"color": FT_BG, "width": 1}},
            name="HOD",
            hovertemplate="HOD %{x|%-I:%M %p}<br>$%{y:.2f}<extra></extra>",
            showlegend=False,
        )
    )
    annotations = [
        {
            "x": first["time"],
            "y": first["price"],
            "text": f"${first['price']:.2f} ({_clock(first['time'])})",
            "showarrow": False,
            "yshift": 16,
            "xshift": 8,
            "font": {"family": "Arial, DejaVu Sans, sans-serif", "size": 11, "color": FT_INK},
        },
        {
            "x": hod["time"],
            "y": hod["price"],
            "text": f"<b>{_clock(hod['time'])} (${hod['price']:.2f})</b>",
            "showarrow": True,
            "arrowhead": 3,
            "arrowcolor": FT_CLARET,
            "arrowwidth": 1.6,
            "ay": -36,
            "font": {"family": "Georgia, DejaVu Serif, serif", "size": 13, "color": FT_CLARET},
        },
        {
            "text": source if source.lower().startswith("source") else f"Source: {source}",
            "xref": "paper",
            "yref": "paper",
            "x": 0,
            "y": -0.16,
            "showarrow": False,
            "font": {"family": "Arial, DejaVu Sans, sans-serif", "size": 11, "color": FT_SUB},
        },
    ]
    if hod["time"] != last["time"] or abs(float(hod["price"]) - float(last["price"])) > 1e-9:
        annotations.append(
            {
                "x": last["time"],
                "y": last["price"],
                "text": f"${last['price']:.2f}",
                "showarrow": False,
                "yshift": 16,
                "xshift": -6,
                "xanchor": "right",
                "font": {"family": "Arial, DejaVu Sans, sans-serif", "size": 11, "color": FT_INK},
            }
        )
    fig.update_layout(
        title={"text": title, "x": 0.0, "xanchor": "left", "y": 0.95},
        paper_bgcolor=FT_BG,
        plot_bgcolor=FT_BG,
        font={"family": "Arial, DejaVu Sans, sans-serif", "color": FT_INK},
        height=560,
        margin={"l": 56, "r": 24, "t": 110, "b": 72},
        showlegend=False,
        hovermode="x unified",
        annotations=annotations,
        xaxis={
            "showgrid": True,
            "gridcolor": FT_GRID,
            "griddash": "dot",
            "showline": True,
            "linecolor": FT_SPINE,
            "linewidth": 1.2,
            "ticks": "outside",
            "tickfont": {"family": "Arial, DejaVu Sans, sans-serif", "size": 11, "color": FT_SUB},
            "tickformat": "%-I:%M",
        },
        yaxis={
            "title": {
                "text": ylabel,
                "font": {"family": "Georgia, DejaVu Serif, serif", "size": 13, "color": FT_INK},
            },
            "showgrid": True,
            "gridcolor": FT_GRID,
            "griddash": "solid",
            "showline": False,
            "ticks": "",
            "tickprefix": tickprefix,
            "tickfont": {"family": "Arial, DejaVu Sans, sans-serif", "size": 11, "color": FT_SUB},
            "range": [y_min, y_max],
            "zeroline": False,
        },
    )
    return fig


def write_sample_mdb_chart(dest: Path | None = None) -> Path:
    session_day = date(2026, 9, 29)
    frame = premium_frame(SAMPLE_TIMES, SAMPLE_PRICES, session_day=session_day)
    path = dest or (OUT_DIR / "mdb_345_call_intraday_ft.png")
    written = render_ft_premium_png(
        frame,
        dest=path,
        symbol="MDB",
        strike=345,
        side="CALL",
        company="MongoDB",
        trigger="above $344",
    )
    print(f"Wrote FT premium chart {written}", file=sys.stderr)
    return written


def main() -> int:
    dests = [
        OUT_DIR / "mdb_345_call_intraday_ft.png",
        Path(__file__).resolve().parent / "mdb_345_call_intraday_ft.png",
        Path(__file__).resolve().parent / "chart_html" / "mdb_345_call_intraday_ft.png",
    ]
    last = None
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        last = write_sample_mdb_chart(dest)
    print(last)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
