from __future__ import annotations

import time
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text

from stock_forecaster_data import get_engine, log_loader_telemetry, performance_block


SCANNER_AVAILABLE_DATES_QUERY = text(
    """
    select record_date
    from market.mv_finviz_snapshot_dates
    order by record_date asc
    """
)

SCANNER_SNAPSHOT_BY_DATE_QUERY = text(
    """
    select *
    from market.view_finviz_snapshot_scanner
    where record_date = :selected_date
    order by "Ticker" asc
    """
)


DATE_COLUMNS = [
    "recorded_at_utc",
    "record_date",
    "IPO",
    "Dividend Ex-Date",
    "ingested_at",
]


def _log_timing(label: str, started_at: float):
    elapsed = time.perf_counter() - started_at
    print(f"[perf] {label}: {elapsed:.3f}s")


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    started_at = time.perf_counter()
    with get_engine().connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    _log_timing(label, started_at)
    log_loader_telemetry("Stock Scanner", label, df, cache_state="miss")
    return df


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out.columns = [c.replace("\xa0", " ").strip() for c in out.columns]

    for column in DATE_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_datetime(out[column], errors="coerce")

    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_scanner_available_dates() -> list[date]:
    with performance_block("load_scanner_available_dates"):
        df = _read_sql_df(
            "load_scanner_available_dates",
            SCANNER_AVAILABLE_DATES_QUERY,
        )
    if df.empty or "record_date" not in df.columns:
        return []
    dates = pd.to_datetime(df["record_date"], errors="coerce").dropna().dt.date.tolist()
    return sorted(set(dates))


@st.cache_data(ttl=300, show_spinner=False)
def load_scanner_snapshot_for_date(selected_date: date) -> pd.DataFrame:
    with performance_block("load_scanner_snapshot_for_date"):
        df = _read_sql_df(
            "load_scanner_snapshot_for_date",
            SCANNER_SNAPSHOT_BY_DATE_QUERY,
            params={"selected_date": selected_date},
        )
    return _prepare(df)


@st.cache_data(ttl=300, show_spinner=False)
def load_finviz_snapshot_clean() -> pd.DataFrame:
    dates = load_scanner_available_dates()
    if not dates:
        return pd.DataFrame()
    return load_scanner_snapshot_for_date(dates[-1])
