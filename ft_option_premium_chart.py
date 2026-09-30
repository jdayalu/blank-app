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
        "INTRADAY OPTIONS EXECUTION",
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
    ax.set_ylabel("Option premium ($)", fontfamily=serif, fontsize=10, color=FT_INK, labelpad=8)
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


def ft_premium_figure(
    frame: pd.DataFrame,
    *,
    symbol: str,
    strike: float,
    side: str,
    company: str | None = None,
    trigger: str | None = None,
    source: str = "Source: Live trading terminal log",
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
        f"INTRADAY OPTIONS EXECUTION</span><br>"
        f"<span style='font-family:Georgia,DejaVu Serif,serif;font-size:22px;"
        f"font-weight:700;color:{FT_INK}'>"
        f"{headline(symbol, strike, side, company=company)}</span><br>"
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
                "text": "Option premium ($)",
                "font": {"family": "Georgia, DejaVu Serif, serif", "size": 13, "color": FT_INK},
            },
            "showgrid": True,
            "gridcolor": FT_GRID,
            "griddash": "solid",
            "showline": False,
            "ticks": "",
            "tickprefix": "$",
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
