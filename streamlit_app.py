#!/usr/bin/env python3
"""Streamlit gallery for Plotly option premium charts.

Local:
  streamlit run streamlit_charts.py --server.port 8767

Streamlit Community Cloud:
  https://koptions.streamlit.app
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

CHART_DIR_HOME = Path.home() / "spx_daily_outlook"
DEFAULT_ALLOWED = ("josephdayalu@gmail.com", "anilgrao@gmail.com")
CHART_NAME_RE = re.compile(
    r"^(?P<symbol>[a-z0-9]+)_"
    r"(?P<strike>[\d.]+)_"
    r"(?P<side>call|put)"
    r"(?:_exp(?P<expiration>\d{4}-\d{2}-\d{2}))?"
    r"_(?P<session>\d{4}-\d{2}-\d{2})_"
    r"(?P<interval>\d+m)_first(?P<minutes>\d+)\.(?:png|html)$",
    re.IGNORECASE,
)
MONTHS = (
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _fmt_day(raw: str) -> str:
    try:
        value = date.fromisoformat(raw[:10])
    except ValueError:
        return raw
    return f"{MONTHS[value.month]}-{value.day:02d}"


@dataclass(frozen=True)
class ChartCard:
    filename: str
    symbol: str
    title: str
    subtitle: str
    session: str
    kind: str
    mtime: float
    has_plotly: bool = False

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def plotly_name(self) -> str:
        if self.filename.lower() in {"spx_index_chart.png", "spx_intraday_plotly.html"}:
            return "spx_intraday_plotly.html"
        return f"{self.stem}.html"


def _chart_dir() -> Path:
    raw = (os.environ.get("CHART_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    local = Path(__file__).resolve().parent / "chart_html"
    if local.is_dir() and (any(local.glob("*.html")) or any(local.glob("*.png"))):
        return local
    return CHART_DIR_HOME


def _allowed_emails() -> set[str]:
    secrets = {}
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}
    raw = (
        os.environ.get("CHART_GALLERY_ALLOWED_EMAILS")
        or str(secrets.get("CHART_GALLERY_ALLOWED_EMAILS") or "")
        or ",".join(DEFAULT_ALLOWED)
    )
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _require_email() -> str | None:
    allowed = _allowed_emails()
    secrets = {}
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}
    force = (
        os.environ.get("STREAMLIT_REQUIRE_LOGIN")
        or str(secrets.get("STREAMLIT_REQUIRE_LOGIN") or "")
        or ""
    ).strip()
    if force.lower() not in {"1", "true", "yes"}:
        return next(iter(allowed), "local")
    current = str(st.session_state.get("email") or "").strip().lower()
    if current in allowed:
        return current
    st.title("Chart gallery")
    st.write("Enter an allow-listed email to view the Plotly charts.")
    typed = st.text_input("Email", placeholder="you@gmail.com").strip().lower()
    if st.button("Continue", type="primary") and typed:
        if typed in allowed:
            st.session_state.email = typed
            st.rerun()
        st.error(f"{typed} is not on the allow-list.")
    return None


def _parse_chart(path: Path, folder: Path) -> ChartCard | None:
    match = CHART_NAME_RE.match(path.name)
    html_name = f"{path.stem}.html"
    if path.name.lower() == "spx_intraday_plotly.html":
        html_name = "spx_intraday_plotly.html"
    has_plotly = (folder / html_name).is_file()
    if match:
        symbol = match.group("symbol").upper()
        side = match.group("side").lower()
        strike = match.group("strike")
        expiration = match.group("expiration")
        session_day = match.group("session")
        interval = match.group("interval")
        minutes = match.group("minutes")
        title = f"{symbol} {strike} {side}"
        bits = [f"{interval} · first {minutes} min", _fmt_day(session_day)]
        if expiration:
            bits.insert(0, f"exp {_fmt_day(expiration)}")
        return ChartCard(
            filename=path.name,
            symbol=symbol,
            title=title,
            subtitle=" · ".join(bits),
            session=_fmt_day(session_day),
            kind=f"first{minutes}",
            mtime=path.stat().st_mtime,
            has_plotly=has_plotly,
        )
    if path.name.lower() in {"spx_index_chart.png", "spx_intraday_plotly.html"}:
        return ChartCard(
            filename=path.name,
            symbol="SPX",
            title="SPX index",
            subtitle="session chart",
            session="",
            kind="index",
            mtime=path.stat().st_mtime,
            has_plotly=(folder / "spx_intraday_plotly.html").is_file(),
        )
    return None


def _load_marks(folder: Path) -> dict:
    path = folder / "latest_option_marks.json"
    if not path.is_file():
        home = CHART_DIR_HOME / "latest_option_marks.json"
        path = home if home.is_file() else path
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _money(value: object) -> str:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


def _show_latest_prices(folder: Path, symbol: str) -> None:
    payload = _load_marks(folder)
    if not payload:
        return
    stamp = payload.get("generated_display") or payload.get("spx_display") or payload.get("scan_display")
    st.subheader("Latest option prices")
    if stamp:
        st.caption(f"Last SPX refresh {stamp}")

    futures = [row for row in (payload.get("futures") or []) if isinstance(row, dict)]
    if futures:
        cols = st.columns(len(futures))
        for column, row in zip(cols, futures):
            last = row.get("last")
            change = float(row.get("change") or 0)
            pct = float(row.get("change_pct") or 0)
            sign = "+" if change >= 0 else ""
            column.metric(
                str(row.get("label") or ""),
                f"{float(last):.2f}" if last is not None else "—",
                f"{sign}{change:.2f} ({sign}{pct:.2f}%)",
            )

    spx_rows = list(payload.get("spx") or [])
    if spx_rows:
        cols = st.columns(min(4, max(1, len(spx_rows))))
        for column, row in zip(cols, spx_rows):
            side = str(row.get("side") or "").upper()
            strike = row.get("strike")
            label = f"SPX {strike:g} {side}" if isinstance(strike, (int, float)) else f"SPX {side}"
            column.metric(label, _money(row.get("mark")), help=str(row.get("occ") or ""))

    option_rows = [
        row
        for row in (payload.get("options") or [])
        if isinstance(row, dict) and row.get("mark") is not None
    ]
    if symbol != "All":
        option_rows = [row for row in option_rows if str(row.get("symbol") or "").upper() == symbol]
    if not option_rows:
        return
    table = []
    for row in option_rows:
        change = row.get("mark_change")
        table.append(
            {
                "Symbol": row.get("symbol"),
                "Side": row.get("side"),
                "Strike": row.get("strike"),
                "Exp": row.get("expiration"),
                "Mark": row.get("mark"),
                "Prev": row.get("prev_mark"),
                "Δ": change,
                "RVOL": row.get("rvol"),
            }
        )
    st.dataframe(table, hide_index=True, use_container_width=True)


def _history_points(folder: Path) -> list[dict]:
    try:
        from option_recs_db import query_option_price_history

        rows = []
        for row in query_option_price_history():
            mark = row["mark"]
            if mark is None:
                continue
            stamp = str(row["scanned_at"])
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                when = None
            rows.append(
                {
                    "symbol": str(row["symbol"] or "").upper(),
                    "side": str(row["side"] or "").upper(),
                    "strike": float(row["strike"]),
                    "expiration": row["expiration"] or "",
                    "source": row["source"] or "",
                    "mark": float(mark),
                    "scanned_at": stamp,
                    "when": when,
                }
            )
        if rows:
            return rows
    except Exception:
        pass
    payload = _load_marks(folder)
    rows = []
    for row in payload.get("history") or []:
        if not isinstance(row, dict) or row.get("mark") is None or row.get("strike") is None:
            continue
        stamp = str(row.get("scanned_at") or "")
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            when = None
        rows.append(
            {
                "symbol": str(row.get("symbol") or "").upper(),
                "side": str(row.get("side") or "").upper(),
                "strike": float(row["strike"]),
                "expiration": row.get("expiration") or "",
                "source": row.get("source") or "",
                "mark": float(row["mark"]),
                "scanned_at": stamp,
                "when": when,
            }
        )
    return rows


def _contract_label(row: dict) -> str:
    strike = row["strike"]
    exp = row["expiration"]
    bit = f"{row['symbol']} {strike:g} {row['side']}"
    return f"{bit} · {exp}" if exp else bit


def _show_history_graph(folder: Path, symbol: str) -> None:
    rows = _history_points(folder)
    if symbol != "All":
        rows = [row for row in rows if row["symbol"] == symbol]
    if not rows:
        return
    labels = sorted({_contract_label(row) for row in rows})
    default = 0
    for index, label in enumerate(labels):
        if label.startswith("SPX "):
            default = index
            break
    chosen = st.selectbox("Historical price", labels, index=min(default, len(labels) - 1))
    series = [row for row in rows if _contract_label(row) == chosen]
    series.sort(key=lambda item: item["when"] or item["scanned_at"])
    if len(series) < 1:
        return
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.line_chart({"mark": [row["mark"] for row in series]})
        return
    fig = go.Figure(
        data=[
            go.Scatter(
                x=[row["when"] or row["scanned_at"] for row in series],
                y=[row["mark"] for row in series],
                mode="lines+markers",
                name=chosen,
                line={"color": "#5b4ee5", "width": 2},
                marker={"size": 8, "color": "#5b4ee5"},
            )
        ]
    )
    fig.update_layout(
        title=f"{chosen} mark history",
        height=420,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        paper_bgcolor="#f6f3ec",
        plot_bgcolor="#fff",
        font={"color": "#121212"},
        yaxis_title="Mark $",
        xaxis_title="Scan time",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    last = series[-1]
    first = series[0]
    delta = last["mark"] - first["mark"]
    st.caption(
        f"{len(series)} prints · first ${first['mark']:.2f} · "
        f"last ${last['mark']:.2f} · Δ {delta:+.2f}"
    )


def list_charts(folder: Path) -> list[ChartCard]:
    if not folder.is_dir():
        return []
    seen: dict[str, ChartCard] = {}
    for path in [*folder.glob("*.png"), *folder.glob("*.html")]:
        if path.name.lower() in {"debug_login_form.html", "spx_landing.html"}:
            continue
        card = _parse_chart(path, folder)
        if not card:
            continue
        key = card.plotly_name if card.has_plotly else card.filename
        prior = seen.get(key)
        if prior is None or (card.has_plotly and not prior.has_plotly) or card.mtime > prior.mtime:
            seen[key] = card
    cards = list(seen.values())
    cards.sort(key=lambda item: (-item.mtime, item.symbol, item.filename))
    return cards


def main() -> None:
    st.set_page_config(page_title="Option charts", page_icon="📈", layout="wide")
    email = _require_email()
    if not email:
        return

    folder = _chart_dir()
    cards = list_charts(folder)
    marks = _load_marks(folder)
    mark_symbols = {
        str(row.get("symbol") or "").upper()
        for row in (marks.get("options") or [])
        if isinstance(row, dict) and row.get("symbol")
    }
    mark_symbols.update(
        {
            str(row.get("symbol") or "").upper()
            for row in (marks.get("history") or [])
            if isinstance(row, dict) and row.get("symbol")
        }
    )
    if marks.get("spx"):
        mark_symbols.add("SPX")
    symbols = ["All"] + sorted({card.symbol for card in cards} | mark_symbols)

    st.sidebar.markdown("**Kuttanad Monitoring**")
    st.sidebar.caption(email)
    picked_symbol = st.sidebar.radio("Symbol", symbols, index=0)
    _show_latest_prices(folder, picked_symbol)
    _show_history_graph(folder, picked_symbol)
    visible = [card for card in cards if picked_symbol == "All" or card.symbol == picked_symbol]
    if not visible:
        if not marks:
            st.warning(f"No charts in {folder}")
        return

    labels = [f"{card.title} · {card.subtitle}" for card in visible]
    chosen = st.sidebar.selectbox("Chart", labels, index=0)
    card = visible[labels.index(chosen)]

    st.title(card.title)
    st.caption(f"{card.subtitle} · {folder}")

    html_path = folder / card.plotly_name
    png_path = folder / f"{card.stem}.png"
    if card.filename.lower().endswith(".png"):
        png_path = folder / card.filename
    if html_path.is_file():
        components.html(html_path.read_text(encoding="utf-8"), height=780, scrolling=False)
    elif png_path.is_file():
        st.image(str(png_path), use_container_width=True)
    else:
        st.error("No Plotly HTML or PNG for this chart.")


if __name__ == "__main__":
    main()
