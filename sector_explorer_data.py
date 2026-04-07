from __future__ import annotations

import time
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text

from stock_forecaster_data import get_engine, log_loader_telemetry, performance_block


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

SECTOR_DAY_SNAPSHOT_VIEW_QUERY = text(
    """
    select *
    from market.view_sector_explorer_snapshot
    where "Date of record" = :selected_date
    order by "Sector" asc, "Stock" asc
    """
)

SECTOR_DAY_SNAPSHOT_BASE_QUERY = text(
    """
    select
        stock as "Stock",
        price as "Price",
        change as "Change",
        percent_change as "Percent Change",
        closing_price as "Closing Price",
        sector as "Sector",
        industry as "Industry",
        employees as "Employees",
        founded as "Founded",
        website as "Website",
        range_1d as "1-day range",
        range_52w as "52-week range",
        market_cap as "Market cap",
        market_cap_clear as "Market cap clear",
        pe_ratio as "P/E ratio",
        next_earnings_date as "Next earnings date",
        dividend_yield as "Dividend yield",
        ex_dividend_date as "Ex-dividend date",
        dividend_pay_date as "Dividend pay date",
        number_of_analysts as "Number of analysts",
        buy_recommendation as "Buy Recommendation",
        hold_recommendation as "Hold Recommendation",
        sell_recommendation as "Sell Recommendation",
        smart_score as "Smart Score",
        score as "Score",
        high_forecast as "High Forecast",
        high_forecast_percent as "High Forecast Percent",
        median_forecast as "Median Forecast",
        median_forecast_percent as "Median Forecast Percent",
        low_forecast as "Low Forecast",
        low_forecast_percent as "Low Forecast Percent",
        total_revenue_value as "Total revenue Value",
        total_revenue_change as "Total revenue Change",
        net_income_value as "Net income Value",
        net_income_change as "Net income Change",
        earnings_per_share_value as "Earnings per share Value",
        earnings_per_share_change as "Earnings per share Change",
        net_profit_margin_value as "Net profit margin Value",
        net_profit_margin_change as "Net profit margin Change",
        free_cash_flow_value as "Free cash flow Value",
        free_cash_flow_change as "Free cash flow Change",
        debt_to_equity_ratio_value as "Debt-to-equity ratio Value",
        debt_to_equity_ratio_change as "Debt-to-equity ratio Change",
        date_of_record as "Date of record",
        time_of_record as "Time of record",
        page_load_time_s as "Page Load Time (s)",
        dynamic_element_load_time_s as "Dynamic Element Load Time (s)",
        fear_greed_index as "Fear & Greed Index",
        sub_price_1d as "1d-sub_price",
        percent_change_1d as "1d-percent_change",
        sub_price_5d as "5d-sub_price",
        percent_change_5d as "5d-percent_change",
        sub_price_1m as "1m-sub_price",
        percent_change_1m as "1m-percent_change",
        sub_price_6m as "6m-sub_price",
        percent_change_6m as "6m-percent_change",
        sub_price_ytd as "YTD-sub_price",
        percent_change_ytd as "YTD-percent_change",
        sub_price_1y as "1y-sub_price",
        percent_change_1y as "1y-percent_change",
        sub_price_5y as "5y-sub_price",
        percent_change_5y as "5y-percent_change",
        null::numeric as "Dow Index Value",
        null::numeric as "Dow Index Change",
        null::numeric as "Dow Index % Change",
        null::numeric as "S&P 500 Value",
        null::numeric as "S&P 500 Change",
        null::numeric as "S&P 500 % Change",
        null::numeric as "NASDAQ Value",
        null::numeric as "NASDAQ Change",
        null::numeric as "NASDAQ % Change"
    from market.stocks_data
    where date_of_record = :selected_date
    order by sector asc, stock asc
    """
)

SECTOR_HISTORY_QUERY = text(
    """
    select
        date_of_record as "Date of record",
        avg(high_forecast) as "High Forecast",
        avg(median_forecast) as "Median Forecast",
        avg(low_forecast) as "Low Forecast",
        avg(price) as "Price",
        sum(
            case
                when smart_score is not null
                 and market_cap_clear is not null
                 and market_cap_clear > 0
                then smart_score * market_cap_clear
            end
        ) / nullif(
            sum(
                case
                    when smart_score is not null
                     and market_cap_clear is not null
                     and market_cap_clear > 0
                    then market_cap_clear
                end
            ),
            0
        ) as "Weighted Smart Score"
    from market.stocks_data
    where sector = :sector
    group by date_of_record
    order by date_of_record asc
    """
)

NUMERIC_COLUMNS = [
    "Price",
    "Change",
    "Percent Change",
    "Closing Price",
    "Employees",
    "Founded",
    "Market cap clear",
    "P/E ratio",
    "Dividend yield",
    "Number of analysts",
    "Buy Recommendation",
    "Hold Recommendation",
    "Sell Recommendation",
    "Smart Score",
    "Score",
    "High Forecast",
    "High Forecast Percent",
    "Median Forecast",
    "Median Forecast Percent",
    "Low Forecast",
    "Low Forecast Percent",
    "Total revenue Change",
    "Net income Change",
    "Earnings per share Value",
    "Earnings per share Change",
    "Net profit margin Change",
    "Free cash flow Change",
    "Debt-to-equity ratio Value",
    "Debt-to-equity ratio Change",
    "Page Load Time (s)",
    "Dynamic Element Load Time (s)",
    "Fear & Greed Index",
    "1d-sub_price",
    "1d-percent_change",
    "5d-sub_price",
    "5d-percent_change",
    "1m-sub_price",
    "1m-percent_change",
    "6m-sub_price",
    "6m-percent_change",
    "YTD-sub_price",
    "YTD-percent_change",
    "1y-sub_price",
    "1y-percent_change",
    "5y-sub_price",
    "5y-percent_change",
    "Dow Index Value",
    "Dow Index Change",
    "Dow Index % Change",
    "S&P 500 Value",
    "S&P 500 Change",
    "S&P 500 % Change",
    "NASDAQ Value",
    "NASDAQ Change",
    "NASDAQ % Change",
]

DATE_COLUMNS = [
    "Date of record",
    "Next earnings date",
    "Ex-dividend date",
    "Dividend pay date",
]

HISTORY_NUMERIC_COLUMNS = [
    "High Forecast",
    "Median Forecast",
    "Low Forecast",
    "Price",
    "Weighted Smart Score",
]


def _log_timing(label: str, started_at: float):
    elapsed = time.perf_counter() - started_at
    print(f"[perf] {label}: {elapsed:.3f}s")


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    started_at = time.perf_counter()
    with get_engine().connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    _log_timing(label, started_at)
    log_loader_telemetry("Sector Explorer", label, df, cache_state="miss")
    return df


def _prepare_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()

    for column in DATE_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_datetime(prepared[column], errors="coerce").dt.date

    for column in NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    return prepared


def _prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()
    if "Date of record" in prepared.columns:
        prepared["Date of record"] = pd.to_datetime(prepared["Date of record"], errors="coerce")

    for column in HISTORY_NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    return prepared.sort_values("Date of record").reset_index(drop=True)


@st.cache_data(ttl=600)
def load_available_dates() -> list[date]:
    try:
        df = _read_sql_df("load_available_dates_mv", AVAILABLE_DATES_MV_QUERY)
    except Exception as exc:
        print(f"[perf] load_available_dates_mv fallback: {exc}")
        df = _read_sql_df("load_available_dates_base", AVAILABLE_DATES_BASE_QUERY)

    dates = (
        pd.to_datetime(df["Date of record"], errors="coerce")
        .dropna()
        .sort_values()
        .dt.date
        .tolist()
    )
    return dates


@st.cache_data(ttl=600)
def load_sector_day_snapshot(selected_date: date, data_version: str) -> pd.DataFrame:
    del data_version
    params = {"selected_date": pd.Timestamp(selected_date).date()}

    try:
        df = _read_sql_df("load_sector_day_snapshot_view", SECTOR_DAY_SNAPSHOT_VIEW_QUERY, params=params)
    except Exception as exc:
        print(f"[perf] load_sector_day_snapshot_view fallback: {exc}")
        df = _read_sql_df("load_sector_day_snapshot_base", SECTOR_DAY_SNAPSHOT_BASE_QUERY, params=params)

    return _prepare_snapshot(df)


@st.cache_data(ttl=600)
def load_sector_history_metrics(sector: str, data_version: str) -> pd.DataFrame:
    del data_version
    if not sector:
        return pd.DataFrame(
            columns=[
                "Date of record",
                "High Forecast",
                "Median Forecast",
                "Low Forecast",
                "Price",
                "Weighted Smart Score",
            ]
        )

    df = _read_sql_df(
        "load_sector_history_metrics",
        SECTOR_HISTORY_QUERY,
        params={"sector": sector},
    )
    return _prepare_history(df)
