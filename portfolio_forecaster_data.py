from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from stock_forecaster_data import get_engine, log_loader_telemetry, performance_block


PORTFOLIO_DAY_SNAPSHOT_COLUMNS = [
    "Stock",
    "Date of record",
    "Sector",
    "Price",
    "Low Forecast",
    "Median Forecast",
    "High Forecast",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Smart Score",
    "Score",
    "P/E ratio",
    "Number of analysts",
]

PORTFOLIO_HISTORY_COLUMNS = [
    "Stock",
    "Date of record",
    "Time of record",
    "Price",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Smart Score",
    "Dividend yield",
    "Ex-dividend date",
    "Dividend pay date",
]

AVAILABLE_DATES_MV_QUERY = text(
    """
    select date_of_record as "Date of record"
    from market.mv_spx_daily_metrics
    order by date_of_record asc
    """
)

AVAILABLE_DATES_BASE_QUERY = text(
    """
    select distinct date_of_record as "Date of record"
    from market.stocks_data
    order by date_of_record asc
    """
)

PORTFOLIO_DAY_SNAPSHOT_VIEW_QUERY = text(
    """
    select *
    from market.view_portfolio_forecaster_day_snapshot
    where "Date of record" = :selected_date
    order by "Stock" asc
    """
)

PORTFOLIO_DAY_SNAPSHOT_BASE_QUERY = text(
    """
    select
        stock as "Stock",
        date_of_record as "Date of record",
        sector as "Sector",
        price as "Price",
        low_forecast as "Low Forecast",
        median_forecast as "Median Forecast",
        high_forecast as "High Forecast",
        low_forecast_percent as "Low Forecast Percent",
        median_forecast_percent as "Median Forecast Percent",
        high_forecast_percent as "High Forecast Percent",
        smart_score as "Smart Score",
        score as "Score",
        pe_ratio as "P/E ratio",
        number_of_analysts as "Number of analysts"
    from market.stocks_data
    where date_of_record = :selected_date
    order by stock asc
    """
)

PORTFOLIO_HISTORY_VIEW_QUERY = text(
    """
    select *
    from market.view_portfolio_forecaster_history
    where "Stock" in :stocks
    order by "Stock" asc, "Date of record" asc, "Time of record" asc
    """
).bindparams(bindparam("stocks", expanding=True))

PORTFOLIO_HISTORY_BASE_QUERY = text(
    """
    select
        stock as "Stock",
        date_of_record as "Date of record",
        time_of_record as "Time of record",
        price as "Price",
        low_forecast_percent as "Low Forecast Percent",
        median_forecast_percent as "Median Forecast Percent",
        high_forecast_percent as "High Forecast Percent",
        smart_score as "Smart Score",
        dividend_yield as "Dividend yield",
        ex_dividend_date as "Ex-dividend date",
        dividend_pay_date as "Dividend pay date"
    from market.stocks_data
    where stock in :stocks
    order by stock asc, date_of_record asc, time_of_record asc
    """
).bindparams(bindparam("stocks", expanding=True))

STOCK_UNIVERSE_QUERY = text(
    """
    select distinct stock as "Stock"
    from market.stocks_data
    order by stock asc
    """
)

DAY_NUMERIC_COLUMNS = [
    "Price",
    "Low Forecast",
    "Median Forecast",
    "High Forecast",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Smart Score",
    "Score",
    "P/E ratio",
    "Number of analysts",
]

HISTORY_NUMERIC_COLUMNS = [
    "Price",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Smart Score",
    "Dividend yield",
]

HISTORY_DATE_COLUMNS = [
    "Date of record",
    "Ex-dividend date",
    "Dividend pay date",
]


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def normalize_symbol(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().upper().removesuffix(".US")


def normalize_portfolio_tickers(user_df: pd.DataFrame) -> tuple[str, ...]:
    required_columns = {"Symbol", "Type", "Volume"}
    if user_df.empty or not required_columns.issubset(user_df.columns):
        return tuple()

    working = user_df.copy()
    working["Symbol"] = working["Symbol"].map(normalize_symbol)
    working = working[working["Symbol"] != ""].copy()
    if working.empty:
        return tuple()

    working["Volume"] = pd.to_numeric(
        working["Volume"].astype(str).str.replace(",", "."),
        errors="coerce",
    ).fillna(0.0)
    working["NetVolume"] = working.apply(
        lambda row: row["Volume"] if str(row["Type"]).upper() == "BUY" else -abs(row["Volume"]),
        axis=1,
    )
    grouped = (
        working.groupby("Symbol", as_index=False)["NetVolume"]
        .sum()
    )
    tickers = grouped.loc[grouped["NetVolume"].abs() > 0, "Symbol"].tolist()
    return tuple(sorted(tickers))


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    with performance_block(label):
        with get_engine().connect() as conn:
            df = pd.read_sql_query(query, conn, params=params)
    log_loader_telemetry("Portfolio Forecaster", label, df, cache_state="miss")
    return df


def _prepare_day_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_df(PORTFOLIO_DAY_SNAPSHOT_COLUMNS)

    prepared = df.copy()
    prepared["Stock"] = prepared["Stock"].map(normalize_symbol)
    prepared["Date of record"] = pd.to_datetime(prepared["Date of record"], errors="coerce")
    for column in DAY_NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    prepared = prepared.sort_values(["Stock"]).reset_index(drop=True)
    return prepared


def _prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_df(PORTFOLIO_HISTORY_COLUMNS)

    prepared = df.copy()
    prepared["Stock"] = prepared["Stock"].map(normalize_symbol)
    for column in HISTORY_DATE_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_datetime(prepared[column], errors="coerce")
    for column in HISTORY_NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    if "Time of record" in prepared.columns:
        prepared["Time of record"] = prepared["Time of record"].fillna("").astype(str)
    prepared = prepared.sort_values(
        ["Stock", "Date of record", "Time of record"]
    ).reset_index(drop=True)
    return prepared


@st.cache_data(ttl=600)
def load_available_dates() -> list[date]:
    try:
        df = _read_sql_df("load_available_dates_mv", AVAILABLE_DATES_MV_QUERY)
    except Exception as exc:
        print(f"[perf] load_available_dates_mv fallback: {exc}")
        df = _read_sql_df("load_available_dates_base", AVAILABLE_DATES_BASE_QUERY)

    if df.empty or "Date of record" not in df.columns:
        return []

    dates = pd.to_datetime(df["Date of record"], errors="coerce").dropna().dt.date.tolist()
    return sorted(dates)


@st.cache_data(ttl=600)
def load_portfolio_day_snapshot(selected_date: date, data_version: str) -> pd.DataFrame:
    del data_version
    try:
        df = _read_sql_df(
            "load_portfolio_day_snapshot_view",
            PORTFOLIO_DAY_SNAPSHOT_VIEW_QUERY,
            params={"selected_date": selected_date},
        )
    except Exception as exc:
        print(f"[perf] load_portfolio_day_snapshot_view fallback: {exc}")
        df = _read_sql_df(
            "load_portfolio_day_snapshot_base",
            PORTFOLIO_DAY_SNAPSHOT_BASE_QUERY,
            params={"selected_date": selected_date},
        )
    return _prepare_day_snapshot(df)


@st.cache_data(ttl=600)
def load_portfolio_history(tickers_key: tuple[str, ...], data_version: str) -> pd.DataFrame:
    del data_version
    if not tickers_key:
        return _empty_df(PORTFOLIO_HISTORY_COLUMNS)

    try:
        df = _read_sql_df(
            "load_portfolio_history_view",
            PORTFOLIO_HISTORY_VIEW_QUERY,
            params={"stocks": list(tickers_key)},
        )
    except Exception as exc:
        print(f"[perf] load_portfolio_history_view fallback: {exc}")
        df = _read_sql_df(
            "load_portfolio_history_base",
            PORTFOLIO_HISTORY_BASE_QUERY,
            params={"stocks": list(tickers_key)},
        )
    return _prepare_history(df)


@st.cache_data(ttl=600)
def load_stock_universe(data_version: str) -> set[str]:
    del data_version
    df = _read_sql_df("load_stock_universe", STOCK_UNIVERSE_QUERY)
    if df.empty or "Stock" not in df.columns:
        return set()
    return {normalize_symbol(value) for value in df["Stock"].dropna().tolist() if normalize_symbol(value)}
