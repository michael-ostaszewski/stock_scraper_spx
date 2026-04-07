from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text

from stock_forecaster_data import get_engine, log_loader_telemetry, performance_block


BACKTESTER_HISTORY_COLUMNS = [
    "Date of record",
    "Stock",
    "Sector",
    "Closing Price",
    "Low Forecast",
    "Smart Score",
    "Score",
    "Low Forecast Percent",
    "Number of analysts",
]

NUMERIC_COLUMNS = [
    "Closing Price",
    "Low Forecast",
    "Smart Score",
    "Score",
    "Low Forecast Percent",
    "Number of analysts",
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

BACKTESTER_UNIVERSE_QUERY = text(
    """
    select
        coalesce(
            (
                select array_agg(stock order by stock)
                from (
                    select distinct stock
                    from market.stocks_data
                ) stocks
            ),
            '{}'::text[]
        ) as tickers,
        coalesce(
            (
                select array_agg(sector order by sector)
                from (
                    select distinct sector
                    from market.stocks_data
                    where sector is not null
                ) sectors
            ),
            '{}'::text[]
        ) as sectors
    """
)

BACKTESTER_HISTORY_VIEW_QUERY = text(
    """
    select *
    from market.view_portfolio_backtester_history
    where "Date of record" between :start_date and :end_date
    order by "Date of record" asc, "Stock" asc
    """
)

BACKTESTER_HISTORY_BASE_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        stock as "Stock",
        sector as "Sector",
        closing_price as "Closing Price",
        low_forecast as "Low Forecast",
        smart_score as "Smart Score",
        score as "Score",
        low_forecast_percent as "Low Forecast Percent",
        number_of_analysts as "Number of analysts"
    from market.stocks_data
    where date_of_record between :start_date and :end_date
    order by date_of_record asc, stock asc
    """
)

CANDIDATE_COLUMNS = [
    "Stock",
    "Closing Price",
    "Low Forecast",
    "Smart Score",
    "Score",
    "Low Forecast Percent",
    "Number of analysts",
]


@dataclass
class BacktestPreparedData:
    days: tuple[pd.Timestamp, ...]
    day_candidates: dict[pd.Timestamp, pd.DataFrame]
    day_quotes: dict[pd.Timestamp, dict[str, tuple[float, float]]]
    last_day_quotes: dict[str, float]

    @property
    def is_empty(self) -> bool:
        return len(self.days) == 0


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=BACKTESTER_HISTORY_COLUMNS)


def _empty_market() -> BacktestPreparedData:
    return BacktestPreparedData(
        days=tuple(),
        day_candidates={},
        day_quotes={},
        last_day_quotes={},
    )


def _normalize_stock(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().upper().removesuffix(".US")


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    with performance_block(label):
        with get_engine().connect() as conn:
            df = pd.read_sql_query(query, conn, params=params)
    log_loader_telemetry("Portfolio Backtester", label, df, cache_state="miss")
    return df


def _prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_history()

    prepared = df.copy()
    prepared["Date of record"] = pd.to_datetime(prepared["Date of record"], errors="coerce")
    prepared["Stock"] = prepared["Stock"].map(_normalize_stock)
    for column in NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    prepared = prepared.dropna(
        subset=[
            "Date of record",
            "Stock",
            "Closing Price",
            "Low Forecast",
            "Score",
            "Smart Score",
            "Low Forecast Percent",
        ]
    )
    prepared = prepared.sort_values(["Date of record", "Stock"]).reset_index(drop=True)
    return prepared


@st.cache_data(ttl=600)
def load_available_dates() -> list[date]:
    try:
        df = _read_sql_df("load_backtester_available_dates_mv", AVAILABLE_DATES_MV_QUERY)
    except Exception as exc:
        print(f"[perf] load_backtester_available_dates_mv fallback: {exc}")
        df = _read_sql_df("load_backtester_available_dates_base", AVAILABLE_DATES_BASE_QUERY)

    if df.empty or "Date of record" not in df.columns:
        return []

    return sorted(
        pd.to_datetime(df["Date of record"], errors="coerce").dropna().dt.date.tolist()
    )


@st.cache_data(ttl=600)
def load_backtester_universe(data_version: str) -> dict[str, list[str]]:
    del data_version
    df = _read_sql_df("load_backtester_universe", BACKTESTER_UNIVERSE_QUERY)
    if df.empty:
        return {"tickers": [], "sectors": []}

    row = df.iloc[0]
    tickers = [_normalize_stock(value) for value in (row["tickers"] or [])]
    sectors = [str(value) for value in (row["sectors"] or []) if str(value).strip()]
    return {
        "tickers": [value for value in tickers if value],
        "sectors": sectors,
    }


@st.cache_data(ttl=600)
def load_backtest_history(start_date: date, end_date: date, data_version: str) -> pd.DataFrame:
    del data_version
    if start_date > end_date:
        return _empty_history()

    params = {"start_date": start_date, "end_date": end_date}
    try:
        df = _read_sql_df(
            "load_backtest_history_view",
            BACKTESTER_HISTORY_VIEW_QUERY,
            params=params,
        )
    except Exception as exc:
        print(f"[perf] load_backtest_history_view fallback: {exc}")
        df = _read_sql_df(
            "load_backtest_history_base",
            BACKTESTER_HISTORY_BASE_QUERY,
            params=params,
        )
    return _prepare_history(df)


def prepare_backtest_market(
    history_df: pd.DataFrame,
    sector_choice: str,
    exclude_tickers: list[str] | tuple[str, ...],
) -> BacktestPreparedData:
    with performance_block("prepare_backtest_market"):
        if history_df.empty:
            return _empty_market()

        working = history_df.copy()
        exclude_set = {_normalize_stock(value) for value in exclude_tickers if value}

        if sector_choice != "All Sectors":
            working = working[working["Sector"] == sector_choice].copy()

        if exclude_set:
            working = working[~working["Stock"].isin(exclude_set)].copy()

        if working.empty:
            return _empty_market()

        day_candidates: dict[pd.Timestamp, pd.DataFrame] = {}
        day_quotes: dict[pd.Timestamp, dict[str, tuple[float, float]]] = {}
        last_day_quotes: dict[str, float] = {}

        grouped = working.groupby("Date of record", sort=True)
        days = tuple(grouped.groups.keys())

        for day, day_df in grouped:
            sorted_day = day_df.sort_values("Score", ascending=False, kind="mergesort")
            day_candidates[day] = sorted_day[CANDIDATE_COLUMNS].reset_index(drop=True)
            quotes = {
                row["Stock"]: (float(row["Closing Price"]), float(row["Low Forecast"]))
                for _, row in day_df[["Stock", "Closing Price", "Low Forecast"]].iterrows()
            }
            day_quotes[day] = quotes

        if days:
            last_day_quotes = {
                ticker: price_low[0]
                for ticker, price_low in day_quotes[days[-1]].items()
            }

        return BacktestPreparedData(
            days=days,
            day_candidates=day_candidates,
            day_quotes=day_quotes,
            last_day_quotes=last_day_quotes,
        )
