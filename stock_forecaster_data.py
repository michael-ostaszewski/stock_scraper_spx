from __future__ import annotations

from contextlib import contextmanager
import re
import time

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import URL, Engine


DAY_SNAPSHOT_QUERY = text(
    """
    select
        stock as "Stock",
        price as "Price",
        sector as "Sector",
        pe_ratio as "P/E ratio",
        number_of_analysts as "Number of analysts",
        buy_recommendation as "Buy Recommendation",
        hold_recommendation as "Hold Recommendation",
        sell_recommendation as "Sell Recommendation",
        smart_score as "Smart Score",
        score as "Score",
        low_forecast_percent as "Low Forecast Percent",
        median_forecast_percent as "Median Forecast Percent",
        high_forecast_percent as "High Forecast Percent",
        dividend_yield as "Dividend yield",
        market_cap_clear as "Market cap clear",
        date_of_record as "Date of record"
    from market.stocks_data
    where date_of_record = :selected_date
    order by stock asc
    """
)

DAILY_METRICS_MV_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        low_forecast_percent_median as "Low Forecast Percent",
        median_forecast_percent_median as "Median Forecast Percent",
        high_forecast_percent_median as "High Forecast Percent",
        fear_greed_index_avg as "Fear & Greed Index",
        smart_score_avg as "Smart Score"
    from market.mv_spx_daily_metrics
    order by date_of_record asc
    """
)

DAILY_METRICS_COLUMNS = [
    "Date of record",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Fear & Greed Index",
    "Smart Score",
]

FEAR_GREED_MV_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        fear_greed_index_avg as "Fear & Greed Index"
    from market.mv_spx_daily_metrics
    order by date_of_record asc
    """
)

FEAR_GREED_COLUMNS = ["Date of record", "Fear & Greed Index"]

SELECTED_STOCKS_DAILY_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        percentile_cont(0.5) within group (order by low_forecast_percent) as "Low Forecast Percent",
        percentile_cont(0.5) within group (order by median_forecast_percent) as "Median Forecast Percent",
        percentile_cont(0.5) within group (order by high_forecast_percent) as "High Forecast Percent"
    from market.stocks_data
    where stock in :stocks
      and smart_score > 7
      and score > 2
      and low_forecast_percent > -5
      and score < 6
    group by date_of_record
    order by date_of_record asc
    """
).bindparams(bindparam("stocks", expanding=True))

TURTLE_SIGNAL_QUERY_TEMPLATE = """
    select
        date_of_record as "Date of record",
        stock as "Stock",
        sector as "Sector",
        price as "Price",
        high20_y as "High20_y",
        low10_y as "Low10_y",
        {signal_column} as "Signal"
    from market.mv_spx_turtle_signals
    where date_of_record = :selected_date
      and {signal_column} is not null
    order by stock asc
"""

TURTLE_HISTORY_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        stock as "Stock",
        sector as "Sector",
        price as "Price",
        range_1d as "1-day range"
    from market.stocks_data
    order by date_of_record asc, stock asc
    """
)


def _log_timing(label: str, started_at: float):
    elapsed = time.perf_counter() - started_at
    print(f"[perf] {label}: {elapsed:.3f}s")


def estimate_df_payload_kb(df: pd.DataFrame) -> float:
    if not isinstance(df, pd.DataFrame):
        return 0.0
    return float(df.memory_usage(index=True, deep=True).sum()) / 1024.0


def _current_session_user_id() -> str:
    try:
        from app_auth import get_session_user_id

        return get_session_user_id()
    except Exception:
        return "anonymous"


def log_loader_telemetry(
    page_name: str,
    loader_name: str,
    df: pd.DataFrame,
    cache_state: str = "miss",
):
    rows_returned = len(df.index) if isinstance(df, pd.DataFrame) else 0
    approx_kb = estimate_df_payload_kb(df)
    user_id = _current_session_user_id()
    print(
        "[telemetry] "
        f"page_name={page_name} "
        f"loader_name={loader_name} "
        f"rows_returned={rows_returned} "
        f"approx_kb={approx_kb:.1f} "
        f"cache_state={cache_state} "
        f"user_id={user_id}"
    )


@contextmanager
def performance_block(label: str):
    started_at = time.perf_counter()
    try:
        yield
    finally:
        _log_timing(label, started_at)


@st.cache_resource
def get_engine() -> Engine:
    cfg = st.secrets.get("supabase_db_reader")
    if not cfg:
        cfg = st.secrets["supabase_db"]
    url = URL.create(
        "postgresql+psycopg",
        username=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=int(cfg["port"]),
        database=cfg["dbname"],
    )
    return create_engine(
        url,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=1,
        max_overflow=2,
    )


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    started_at = time.perf_counter()
    with get_engine().connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    _log_timing(label, started_at)
    log_loader_telemetry("Stock Forecaster", label, df, cache_state="miss")
    return df


def _finalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    if "Date of record" in df.columns:
        df["Date of record"] = pd.to_datetime(df["Date of record"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def get_last_date() -> pd.Timestamp:
    df = _read_sql_df(
        "get_last_date",
        text("select max(date_of_record) as max_date from market.stocks_data"),
    )
    return pd.to_datetime(df.loc[0, "max_date"])


@st.cache_data(ttl=300)
def get_read_model_status(data_version: str) -> dict[str, object]:
    del data_version
    df = _read_sql_df(
        "get_read_model_status",
        text(
            """
            select
                to_regclass('market.mv_spx_daily_metrics') is not null as has_daily_metrics,
                to_regclass('market.mv_spx_turtle_signals') is not null as has_turtle_signals,
                (select max(date_of_record) from market.stocks_data) as stocks_max_date,
                case
                    when to_regclass('market.mv_spx_daily_metrics') is not null
                        then (select max(date_of_record) from market.mv_spx_daily_metrics)
                    else null
                end as daily_metrics_mv_max_date
            """
        ),
    )
    row = df.iloc[0]
    stocks_max_date = pd.to_datetime(row["stocks_max_date"], errors="coerce")
    daily_metrics_mv_max_date = pd.to_datetime(
        row["daily_metrics_mv_max_date"], errors="coerce"
    )
    daily_metrics_is_fresh = (
        bool(row["has_daily_metrics"])
        and pd.notna(stocks_max_date)
        and pd.notna(daily_metrics_mv_max_date)
        and stocks_max_date == daily_metrics_mv_max_date
    )
    return {
        "has_daily_metrics": bool(row["has_daily_metrics"]),
        "has_turtle_signals": bool(row["has_turtle_signals"]),
        "stocks_max_date": stocks_max_date,
        "daily_metrics_mv_max_date": daily_metrics_mv_max_date,
        "daily_metrics_is_fresh": bool(daily_metrics_is_fresh),
    }


@st.cache_data(ttl=300)
def load_day_snapshot(date_val: pd.Timestamp, data_version: str) -> pd.DataFrame:
    del data_version
    df = _read_sql_df(
        "load_day_snapshot",
        DAY_SNAPSHOT_QUERY,
        params={"selected_date": pd.Timestamp(date_val).date()},
    )
    return _finalize_dates(df)


@st.cache_data(ttl=600)
def load_daily_market_metrics(data_version: str) -> pd.DataFrame:
    status = get_read_model_status(data_version)
    if status["has_daily_metrics"]:
        if not status["daily_metrics_is_fresh"]:
            print(
                "[perf] load_daily_market_metrics_mv stale read-model: "
                f"mv_max_date={status['daily_metrics_mv_max_date']} "
                f"stocks_max_date={status['stocks_max_date']}"
            )
        try:
            return _finalize_dates(
                _read_sql_df("load_daily_market_metrics_mv", DAILY_METRICS_MV_QUERY)
            )
        except Exception as exc:
            print(f"[perf] load_daily_market_metrics_mv unavailable: {exc}")
    else:
        print("[perf] load_daily_market_metrics_mv unavailable: read-model missing")
    return _finalize_dates(pd.DataFrame(columns=DAILY_METRICS_COLUMNS))


@st.cache_data(ttl=600)
def load_fear_greed_timeseries(data_version: str) -> pd.DataFrame:
    del data_version
    try:
        return _finalize_dates(
            _read_sql_df("load_fear_greed_timeseries_mv", FEAR_GREED_MV_QUERY)
        )
    except Exception as exc:
        print(f"[perf] load_fear_greed_timeseries_mv unavailable: {exc}")
    return _finalize_dates(pd.DataFrame(columns=FEAR_GREED_COLUMNS))


@st.cache_data(ttl=600)
def load_selected_stocks_daily_metrics(
    stocks_key: tuple[str, ...],
    data_version: str,
) -> pd.DataFrame:
    del data_version
    if not stocks_key:
        return pd.DataFrame(
            columns=[
                "Date of record",
                "Low Forecast Percent",
                "Median Forecast Percent",
                "High Forecast Percent",
            ]
        )

    df = _read_sql_df(
        "load_selected_stocks_daily_metrics",
        SELECTED_STOCKS_DAILY_QUERY,
        params={"stocks": list(stocks_key)},
    )
    return _finalize_dates(df)


def _split_range(value: str):
    if pd.isna(value):
        return [None, None]
    parts = str(value).replace("\n", " ").strip().split()
    if len(parts) != 2:
        return [None, None]

    numbers: list[float] = []
    for part in parts:
        cleaned = re.sub(r"[^\d\.\-]", "", part)
        if not cleaned:
            return [None, None]
        try:
            numbers.append(float(cleaned))
        except ValueError:
            return [None, None]

    low_raw, high_raw = numbers
    return [min(low_raw, high_raw), max(low_raw, high_raw)]


@st.cache_data(ttl=600)
def _load_turtle_signal_history_legacy(data_version: str) -> pd.DataFrame:
    del data_version
    df_all = _finalize_dates(_read_sql_df("load_turtle_signal_history_legacy", TURTLE_HISTORY_QUERY))
    if df_all.empty:
        return df_all

    with performance_block("build_turtle_signals_legacy"):
        df_all[["Low", "High"]] = (
            df_all["1-day range"].apply(_split_range).apply(pd.Series)
        )
        df_all = df_all.dropna(subset=["Low", "High", "Price", "Date of record"])
        df_all = df_all.sort_values(["Stock", "Date of record"])

        df_all["High20"] = (
            df_all.groupby("Stock")["High"]
            .transform(lambda s: s.rolling(20, min_periods=20).max())
        )
        df_all["Low10"] = (
            df_all.groupby("Stock")["Low"]
            .transform(lambda s: s.rolling(10, min_periods=10).min())
        )

        df_all["High20_y"] = df_all.groupby("Stock")["High20"].shift(1)
        df_all["Low10_y"] = df_all.groupby("Stock")["Low10"].shift(1)
        df_all["Close_y"] = df_all.groupby("Stock")["Price"].shift(1)

        df_all["RawSignal"] = np.select(
            [
                (df_all["Price"] > df_all["High20_y"]) & (df_all["Close_y"] <= df_all["High20_y"]),
                (df_all["Price"] < df_all["Low10_y"]) & (df_all["Close_y"] >= df_all["Low10_y"]),
            ],
            ["BUY", "SELL"],
            default=None,
        )

        def swing_filter(series):
            out, state = [], "FLAT"
            for signal in series:
                if signal == "BUY" and state != "LONG":
                    out.append("BUY")
                    state = "LONG"
                elif signal == "SELL" and state == "LONG":
                    out.append("SELL")
                    state = "FLAT"
                else:
                    out.append(None)
            return out

        df_all["FiltSignal"] = (
            df_all.groupby("Stock")["RawSignal"].transform(swing_filter)
        )

    return df_all[
        [
            "Date of record",
            "Stock",
            "Sector",
            "Price",
            "High20_y",
            "Low10_y",
            "RawSignal",
            "FiltSignal",
        ]
    ].copy()


@st.cache_data(ttl=600)
def load_turtle_signals(
    selected_date: pd.Timestamp,
    mode: str,
    data_version: str,
) -> pd.DataFrame:
    status = get_read_model_status(data_version)
    signal_column = "filt_signal" if mode == "filtered" else "raw_signal"

    if status["has_turtle_signals"]:
        try:
            query = text(TURTLE_SIGNAL_QUERY_TEMPLATE.format(signal_column=signal_column))
            df = _read_sql_df(
                "load_turtle_signals_mv",
                query,
                params={"selected_date": pd.Timestamp(selected_date).date()},
            )
            return _finalize_dates(df)
        except Exception as exc:
            print(f"[perf] load_turtle_signals_mv fallback: {exc}")

    df_legacy = _load_turtle_signal_history_legacy(data_version)
    if df_legacy.empty:
        return df_legacy

    signal_name = "FiltSignal" if mode == "filtered" else "RawSignal"
    today = pd.Timestamp(selected_date)
    return df_legacy[
        (df_legacy["Date of record"] == today) & df_legacy[signal_name].notna()
    ].copy()
