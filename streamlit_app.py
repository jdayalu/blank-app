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
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

CHART_DIR_HOME = Path.home() / "spx_daily_outlook"
DEFAULT_ALLOWED = ("josephdayalu@gmail.com", "anilgrao@gmail.com")
PACIFIC = ZoneInfo("America/Los_Angeles")
SERIES_NAME = "option_mark_series.json"
CHART_NAME_RE = re.compile(
    r"^(?P<symbol>[a-z0-9]+)_"
    r"(?P<strike>[\d.]+)_"
    r"(?P<side>call|put)"
    r"(?:_exp(?P<expiration>\d{4}-\d{2}-\d{2}))?"
    r"_(?P<session>\d{4}-\d{2}-\d{2})_"
    r"(?:(?P<interval>\d+m)_first(?P<minutes>\d+)|intraday)"
    r"\.(?:png|html)$",
    re.IGNORECASE,
)
SPX_1M_RE = re.compile(
    r"^spx_1m_(?P<session>\d{4}-\d{2}-\d{2})\.(?:png|html)$",
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


def _as_dt(stamp: str) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=PACIFIC)
    return when


def _session_iso(stamp: str, when: datetime | None = None) -> str:
    if when is None:
        when = _as_dt(stamp)
    if when:
        return when.astimezone(PACIFIC).date().isoformat()
    raw = str(stamp)[:10]
    try:
        date.fromisoformat(raw)
        return raw
    except ValueError:
        return ""


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
    strike: float | None = None
    side: str = ""
    expiration: str = ""
    session_iso: str = ""

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def plotly_name(self) -> str:
        if self.filename.lower() in {"spx_index_chart.png", "spx_intraday_plotly.html"}:
            return "spx_intraday_plotly.html"
        if SPX_1M_RE.match(self.filename):
            return f"{self.stem}.html"
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
    one_min = SPX_1M_RE.match(path.name)
    html_name = f"{path.stem}.html"
    if path.name.lower() == "spx_intraday_plotly.html":
        html_name = "spx_intraday_plotly.html"
    has_plotly = (folder / html_name).is_file()
    if one_min:
        session_day = one_min.group("session")
        return ChartCard(
            filename=path.name,
            symbol="SPX",
            title="S&P 500 1-minute",
            subtitle=f"cash session · {_fmt_day(session_day)}",
            session=_fmt_day(session_day),
            kind="index-1m",
            mtime=path.stat().st_mtime,
            has_plotly=(folder / f"{path.stem}.html").is_file(),
            session_iso=session_day,
        )
    if match:
        symbol = match.group("symbol").upper()
        side = match.group("side").upper()
        strike = float(match.group("strike"))
        expiration = match.group("expiration") or ""
        session_day = match.group("session")
        interval = match.group("interval") or "intraday"
        minutes = match.group("minutes") or ""
        title = f"{symbol} {strike:g} {side}"
        bits = (
            [f"{interval} · first {minutes} min", _fmt_day(session_day)]
            if minutes
            else ["intraday", _fmt_day(session_day)]
        )
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
            strike=strike,
            side=side,
            expiration=expiration,
            session_iso=session_day,
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
            session_iso="",
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


def _history_points(folder: Path) -> list[dict]:
    try:
        from option_recs_db import query_option_price_history

        rows = []
        for row in query_option_price_history():
            mark = row["mark"]
            if mark is None:
                continue
            stamp = str(row["scanned_at"])
            when = _as_dt(stamp)
            session = _session_iso(stamp, when)
            if not session:
                continue
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
                    "session": session,
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
        when = _as_dt(stamp)
        session = _session_iso(stamp, when)
        if not session:
            continue
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
                "session": session,
            }
        )
    return rows


def _group_history(points: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in points:
        if row["side"] not in {"CALL", "PUT"}:
            continue
        key = (
            row["symbol"],
            row["session"],
            row["side"],
            round(float(row["strike"]), 4),
            row["expiration"],
        )
        groups.setdefault(key, []).append(row)
    series = []
    for (symbol, session, side, strike, expiration), rows in groups.items():
        rows.sort(key=lambda item: item["when"] or item["scanned_at"])
        series.append(
            {
                "symbol": symbol,
                "session": session,
                "side": side,
                "strike": float(strike),
                "expiration": expiration,
                "t": [row["scanned_at"] for row in rows],
                "m": [row["mark"] for row in rows],
            }
        )
    series.sort(
        key=lambda item: (
            item["symbol"],
            item["session"],
            item["side"],
            item["strike"],
            item["expiration"],
        )
    )
    return series


@st.cache_data(show_spinner=False)
def _load_series(folder: str, series_mtime: float, marks_mtime: float) -> list[dict]:
    del series_mtime, marks_mtime
    root = Path(folder)
    path = root / SERIES_NAME
    if not path.is_file():
        home = CHART_DIR_HOME / SERIES_NAME
        path = home if home.is_file() else path
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        rows = [
            row
            for row in (payload.get("series") or [])
            if isinstance(row, dict)
            and row.get("symbol")
            and row.get("session")
            and row.get("side")
            and row.get("strike") is not None
            and row.get("t")
            and row.get("m")
        ]
        if rows:
            return rows
    return _group_history(_history_points(root))


def _file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _strike_letter(side: str) -> str:
    return "C" if str(side).upper().startswith("C") else "P"


def _strike_label(row: dict, *, with_exp: bool) -> str:
    label = f"{float(row['strike']):g}{_strike_letter(row['side'])}"
    expiration = str(row.get("expiration") or "")
    if with_exp and expiration:
        label = f"{label} · exp {_fmt_day(expiration)}"
    return label


def _index_of(options: list[str], preferred: str, fallback: int = 0) -> int:
    if preferred in options:
        return options.index(preferred)
    return min(fallback, max(0, len(options) - 1))


def _sync_query(stock: str, session: str, strike: float, side: str) -> None:
    desired = {
        "stock": stock,
        "date": session,
        "strike": f"{strike:g}",
        "side": side,
    }
    current = {key: str(st.query_params.get(key) or "") for key in desired}
    if current != desired:
        st.query_params.from_dict(desired)


def _show_futures(folder: Path) -> None:
    payload = _load_marks(folder)
    futures = [row for row in (payload.get("futures") or []) if isinstance(row, dict)]
    if not futures:
        return
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


def _match_charts(cards: list[ChartCard], row: dict) -> list[ChartCard]:
    strike = float(row["strike"])
    side = str(row["side"]).upper()
    session = str(row["session"])
    expiration = str(row.get("expiration") or "")
    matches = [
        card
        for card in cards
        if card.symbol == row["symbol"]
        and card.side == side
        and card.session_iso == session
        and card.strike is not None
        and abs(card.strike - strike) < 1e-6
    ]
    if expiration:
        exact = [card for card in matches if card.expiration == expiration]
        if exact:
            matches = exact
    matches.sort(key=lambda card: (not card.has_plotly, card.filename))
    return matches


def _show_contract_chart(row: dict) -> None:
    times = list(row.get("t") or [])
    marks = [float(value) for value in (row.get("m") or [])]
    if len(times) != len(marks) or not marks:
        st.warning("No prints for this contract.")
        return
    first, last = marks[0], marks[-1]
    delta = last - first
    cols = st.columns(4)
    cols[0].metric("Last", _money(last), f"{delta:+.2f}")
    cols[1].metric("First", _money(first))
    cols[2].metric("High", _money(max(marks)))
    cols[3].metric("Prints", str(len(marks)))
    try:
        from ft_option_premium_chart import frame_from_points, ft_premium_figure

        session = date.fromisoformat(str(row.get("session") or datetime.now(PACIFIC).date()))
        frame = frame_from_points(list(zip(times, marks)), session_day=session)
        fig = ft_premium_figure(
            frame,
            symbol=str(row["symbol"]),
            strike=float(row["strike"]),
            side=str(row["side"]),
            source="Source: Live trading terminal log",
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        try:
            import plotly.graph_objects as go
        except ImportError:
            st.line_chart({"mark": marks})
            return
        title = f"{row['symbol']} {float(row['strike']):g} {row['side']}"
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=times,
                    y=marks,
                    mode="lines",
                    name=title,
                    line={"color": "#0d7680", "width": 2.4},
                    fill="tozeroy",
                    fillcolor="rgba(13,118,128,0.08)",
                )
            ]
        )
        fig.update_layout(
            title=title,
            height=520,
            paper_bgcolor="#fff1e5",
            plot_bgcolor="#fff1e5",
            font={"color": "#111111"},
            yaxis_title="Option premium ($)",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"{len(marks)} prints · first ${first:.2f} · last ${last:.2f} · Δ {delta:+.2f} · "
        f"Source: Live trading terminal log"
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


def _show_saved_chart(folder: Path, card: ChartCard) -> None:
    st.subheader(card.title)
    st.caption(card.subtitle)
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


def main() -> None:
    st.set_page_config(page_title="Option charts", page_icon="📈", layout="wide")
    email = _require_email()
    if not email:
        return

    folder = _chart_dir()
    cards = list_charts(folder)
    series = _load_series(
        str(folder),
        _file_mtime(folder / SERIES_NAME),
        _file_mtime(folder / "latest_option_marks.json"),
    )
    _show_futures(folder)
    index_cards = [card for card in cards if card.kind == "index-1m"]
    index_cards.sort(key=lambda item: item.session_iso, reverse=True)
    if index_cards:
        _show_saved_chart(folder, index_cards[0])
        st.divider()

    if not series:
        st.sidebar.markdown("**Kuttanad Monitoring**")
        st.sidebar.caption(email)
        st.sidebar.caption("https://koptions.streamlit.app")
        if not index_cards:
            st.warning(f"No option mark history in {folder}")
        return

    symbols = sorted({row["symbol"] for row in series})
    if "SPX" in symbols:
        symbols = ["SPX"] + [name for name in symbols if name != "SPX"]

    qp_stock = str(st.query_params.get("stock") or "").upper()
    qp_date = str(st.query_params.get("date") or "")
    qp_strike = str(st.query_params.get("strike") or "")
    qp_side = str(st.query_params.get("side") or "").upper()

    st.sidebar.markdown("**Kuttanad Monitoring**")
    st.sidebar.caption(email)
    st.sidebar.caption("https://koptions.streamlit.app")

    stock_col, date_col, strike_col = st.columns(3)
    stock = stock_col.selectbox(
        "Stock",
        symbols,
        index=_index_of(symbols, qp_stock),
    )
    dates = sorted(
        {row["session"] for row in series if row["symbol"] == stock},
        reverse=True,
    )
    if not dates:
        st.warning(f"No dates for {stock}")
        return
    session = date_col.selectbox(
        "Date",
        dates,
        index=_index_of(dates, qp_date),
        format_func=_fmt_day,
    )
    day_rows = [
        row
        for row in series
        if row["symbol"] == stock and row["session"] == session
    ]
    day_rows.sort(
        key=lambda row: (
            0 if row["side"] == "CALL" else 1,
            float(row["strike"]),
            row.get("expiration") or "",
        )
    )
    if not day_rows:
        st.warning(f"No strikes for {stock} on {_fmt_day(session)}")
        return
    strike_keys = {(row["side"], round(float(row["strike"]), 4)) for row in day_rows}
    with_exp = len(strike_keys) < len(day_rows)
    labels = [_strike_label(row, with_exp=with_exp) for row in day_rows]
    default_strike = 0
    if qp_strike:
        try:
            wanted = float(qp_strike)
        except ValueError:
            wanted = None
        if wanted is not None:
            for index, row in enumerate(day_rows):
                if abs(float(row["strike"]) - wanted) < 1e-6 and (
                    not qp_side or row["side"] == qp_side
                ):
                    default_strike = index
                    break
    if default_strike == 0 and not qp_strike:
        default_strike = max(range(len(day_rows)), key=lambda index: len(day_rows[index]["t"]))
    chosen_label = strike_col.selectbox(
        "Option strike",
        labels,
        index=min(default_strike, len(labels) - 1),
    )
    chosen = day_rows[labels.index(chosen_label)]
    _sync_query(stock, session, float(chosen["strike"]), chosen["side"])
    _show_contract_chart(chosen)

    saved = _match_charts(cards, chosen)
    if saved:
        st.divider()
        st.subheader("Saved first-30 chart")
        _show_saved_chart(folder, saved[0])

    with st.expander(f"All {stock} strikes · {_fmt_day(session)}"):
        table = [
            {
                "Strike": _strike_label(row, with_exp=True),
                "Last": row["m"][-1],
                "First": row["m"][0],
                "Δ": row["m"][-1] - row["m"][0],
                "Prints": len(row["t"]),
                "Exp": row.get("expiration") or "",
            }
            for row in day_rows
        ]
        st.dataframe(table, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
