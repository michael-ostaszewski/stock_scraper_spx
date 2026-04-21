from __future__ import annotations

import time

import pandas as pd
import streamlit as st
from sqlalchemy import text

from stock_forecaster_data import get_engine, log_loader_telemetry, performance_block


SP500_HISTORICAL_METRICS_QUERY = text(
    """
    select
        trade_date as "Date",
        price as "Price",
        open_price as "Open",
        high_price as "High",
        low_price as "Low",
        ath_price as "ATH_price",
        days_since_ath as "days_since_ATH",
        pct_from_ath as "pct_from_ATH",
        daily_return_pct as "daily_return_pct",
        vol_30d_ann as "vol_30d_ann",
        return_1y_pct as "return_1y_pct",
        dist_from_sma_50_pct as "dist_from_SMA_50_pct",
        dist_from_sma_100_pct as "dist_from_SMA_100_pct",
        dist_from_sma_200_pct as "dist_from_SMA_200_pct",
        roll_sharpe as "roll_sharpe",
        roll_sortino as "roll_sortino",
        drawdown_pct as "drawdown_pct",
        ulcer_252d as "ulcer_252d"
    from market.sp500_historical_metrics
    order by trade_date asc
    """
)

NUMERIC_COLUMNS = [
    "Price",
    "Open",
    "High",
    "Low",
    "ATH_price",
    "days_since_ATH",
    "pct_from_ATH",
    "daily_return_pct",
    "vol_30d_ann",
    "return_1y_pct",
    "dist_from_SMA_50_pct",
    "dist_from_SMA_100_pct",
    "dist_from_SMA_200_pct",
    "roll_sharpe",
    "roll_sortino",
    "drawdown_pct",
    "ulcer_252d",
]


def _log_timing(label: str, started_at: float):
    elapsed = time.perf_counter() - started_at
    print(f"[perf] {label}: {elapsed:.3f}s")


def _read_sql_df(label: str, query) -> pd.DataFrame:
    started_at = time.perf_counter()
    with get_engine().connect() as conn:
        df = pd.read_sql_query(query, conn)
    _log_timing(label, started_at)
    log_loader_telemetry("S&P 500 Index Analyzer", label, df, cache_state="miss")
    return df


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=300)
def load_sp500_historical_metrics() -> pd.DataFrame:
    with performance_block("load_sp500_historical_metrics"):
        df = _read_sql_df(
            "load_sp500_historical_metrics",
            SP500_HISTORICAL_METRICS_QUERY,
        )
    return _prepare_df(df)
