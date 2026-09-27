#!/usr/bin/env python3
"""Streamlit gallery for Plotly option premium charts.

Local:
  streamlit run streamlit_charts.py --server.port 8767

Streamlit Community Cloud:
  https://koptions.streamlit.app
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

CHART_DIR_HOME = Path.home() / "spx_daily_outlook"
DEFAULT_ALLOWED = ("dayalujoseph@gmail.com", "anilgrao@gmail.com")
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
    symbols = ["All"] + sorted({card.symbol for card in cards})

    st.sidebar.markdown("**Kuttanad Monitoring**")
    st.sidebar.caption(email)
    picked_symbol = st.sidebar.radio("Symbol", symbols, index=0)
    visible = [card for card in cards if picked_symbol == "All" or card.symbol == picked_symbol]
    if not visible:
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
