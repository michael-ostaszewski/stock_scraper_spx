from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text

from stock_forecaster_data import (
    get_engine,
    log_loader_telemetry,
    performance_block,
    should_skip_heavy_fallback,
)


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

SECTOR_OPTIONS_VIEW_QUERY = text(
    """
    select distinct sector as "Sector"
    from market.mv_screener_statistics_candidates
    where date_of_record = :latest_date
      and sector is not null
    order by sector asc
    """
)

SECTOR_OPTIONS_BASE_QUERY = text(
    """
    select distinct sector as "Sector"
    from market.stocks_data
    where date_of_record = :latest_date
      and sector is not null
    order by sector asc
    """
)

TOP_PICKS_ALL_VIEW_QUERY = text(
    """
    with selected_dates as (
        select date_of_record
        from market.mv_spx_daily_metrics
        where date_of_record between :start_date and :end_date
    )
    select
        d.date_of_record as "Date of record",
        ranked."Stock",
        ranked."Rank"
    from selected_dates d
    cross join lateral (
        select
            stock as "Stock",
            row_number() over (
                order by score desc nulls last, stock asc
            ) as "Rank"
        from market.mv_screener_statistics_candidates
        where date_of_record = d.date_of_record
          and smart_score >= :min_ss
          and score >= :min_sc
          and score <= :max_sc
          and low_forecast_percent >= :min_lfp
          and number_of_analysts >= :min_an
        order by score desc nulls last, stock asc
        limit :top_n
    ) ranked
    order by d.date_of_record asc, ranked."Rank" asc, ranked."Stock" asc
    """
)

TOP_PICKS_SECTOR_VIEW_QUERY = text(
    """
    with selected_dates as (
        select date_of_record
        from market.mv_spx_daily_metrics
        where date_of_record between :start_date and :end_date
    )
    select
        d.date_of_record as "Date of record",
        ranked."Stock",
        ranked."Rank"
    from selected_dates d
    cross join lateral (
        select
            stock as "Stock",
            row_number() over (
                order by score desc nulls last, stock asc
            ) as "Rank"
        from market.mv_screener_statistics_candidates
        where date_of_record = d.date_of_record
          and sector = :sector
          and smart_score >= :min_ss
          and score >= :min_sc
          and score <= :max_sc
          and low_forecast_percent >= :min_lfp
          and number_of_analysts >= :min_an
        order by score desc nulls last, stock asc
        limit :top_n
    ) ranked
    order by d.date_of_record asc, ranked."Rank" asc, ranked."Stock" asc
    """
)

TOP_PICKS_ALL_BASE_QUERY = text(
    """
    with selected_dates as (
        select distinct date_of_record
        from market.stocks_data
        where date_of_record between :start_date and :end_date
    )
    select
        d.date_of_record as "Date of record",
        ranked."Stock",
        ranked."Rank"
    from selected_dates d
    cross join lateral (
        select
            stock as "Stock",
            row_number() over (
                order by score desc nulls last, stock asc
            ) as "Rank"
        from market.stocks_data
        where date_of_record = d.date_of_record
          and smart_score >= :min_ss
          and score >= :min_sc
          and score <= :max_sc
          and low_forecast_percent >= :min_lfp
          and number_of_analysts >= :min_an
        order by score desc nulls last, stock asc
        limit :top_n
    ) ranked
    order by d.date_of_record asc, ranked."Rank" asc, ranked."Stock" asc
    """
)

TOP_PICKS_SECTOR_BASE_QUERY = text(
    """
    with ranked as (
        select
            date_of_record as "Date of record",
            stock as "Stock",
            row_number() over (
                partition by date_of_record
                order by score desc nulls last, stock asc
            ) as "Rank"
        from market.stocks_data
        where date_of_record between :start_date and :end_date
          and sector = :sector
          and smart_score >= :min_ss
          and score >= :min_sc
          and score <= :max_sc
          and low_forecast_percent >= :min_lfp
          and number_of_analysts >= :min_an
    )
    select "Date of record", "Stock", "Rank"
    from ranked
    where "Rank" <= :top_n
    order by "Date of record" asc, "Rank" asc, "Stock" asc
    """
)

TOP_PICKS_COLUMNS = ["Date of record", "Stock", "Rank"]


def _read_sql_df(label: str, query, params: dict | None = None) -> pd.DataFrame:
    with performance_block(label):
        with get_engine().connect() as conn:
            df = pd.read_sql_query(query, conn, params=params)
    log_loader_telemetry("Screener Statistics", label, df, cache_state="miss")
    return df


def _empty_top_picks() -> pd.DataFrame:
    return pd.DataFrame(columns=TOP_PICKS_COLUMNS)


def _prepare_top_picks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_top_picks()

    prepared = df.copy()
    prepared["Date of record"] = pd.to_datetime(prepared["Date of record"], errors="coerce")
    prepared["Stock"] = prepared["Stock"].astype(str).str.strip().str.upper()
    prepared["Rank"] = pd.to_numeric(prepared["Rank"], errors="coerce")
    prepared = prepared.dropna(subset=["Date of record", "Stock", "Rank"])
    prepared["Rank"] = prepared["Rank"].astype(int)
    return prepared.sort_values(["Date of record", "Rank", "Stock"]).reset_index(drop=True)


@st.cache_data(ttl=600)
def load_available_dates() -> list[date]:
    try:
        df = _read_sql_df("load_screener_available_dates_mv", AVAILABLE_DATES_MV_QUERY)
    except Exception as exc:
        if should_skip_heavy_fallback(
            exc,
            "load_screener_available_dates_mv",
            "load_screener_available_dates_base",
        ):
            return []
        print(f"[perf] load_screener_available_dates_mv fallback: {exc}")
        df = _read_sql_df("load_screener_available_dates_base", AVAILABLE_DATES_BASE_QUERY)

    if df.empty or "Date of record" not in df.columns:
        return []

    return sorted(pd.to_datetime(df["Date of record"], errors="coerce").dropna().dt.date.tolist())


@st.cache_data(ttl=600)
def load_sector_options(data_version: str) -> list[str]:
    latest_date = pd.to_datetime(data_version, errors="coerce").date()
    if pd.isna(latest_date):
        return []

    params = {"latest_date": latest_date}
    try:
        df = _read_sql_df(
            "load_screener_sector_options_view",
            SECTOR_OPTIONS_VIEW_QUERY,
            params=params,
        )
    except Exception as exc:
        if should_skip_heavy_fallback(
            exc,
            "load_screener_sector_options_view",
            "load_screener_sector_options_base",
        ):
            return []
        print(f"[perf] load_screener_sector_options_view fallback: {exc}")
        df = _read_sql_df(
            "load_screener_sector_options_base",
            SECTOR_OPTIONS_BASE_QUERY,
            params=params,
        )

    if df.empty or "Sector" not in df.columns:
        return []

    return sorted({str(value).strip() for value in df["Sector"].dropna() if str(value).strip()})


@st.cache_data(ttl=600)
def load_top_picks(
    start_date: date,
    end_date: date,
    top_n: int,
    sector: str,
    min_ss: float,
    min_sc: float,
    max_sc: float,
    min_lfp: float,
    min_an: int,
    data_version: str,
) -> pd.DataFrame:
    del data_version

    if start_date > end_date:
        return _empty_top_picks()

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "top_n": top_n,
        "sector": sector,
        "min_ss": min_ss,
        "min_sc": min_sc,
        "max_sc": max_sc,
        "min_lfp": min_lfp,
        "min_an": min_an,
    }

    use_sector_query = sector != "All Sectors"
    view_query = TOP_PICKS_SECTOR_VIEW_QUERY if use_sector_query else TOP_PICKS_ALL_VIEW_QUERY
    base_query = TOP_PICKS_SECTOR_BASE_QUERY if use_sector_query else TOP_PICKS_ALL_BASE_QUERY
    view_label = "load_screener_top_picks_sector_view" if use_sector_query else "load_screener_top_picks_all_view"
    base_label = "load_screener_top_picks_sector_base" if use_sector_query else "load_screener_top_picks_all_base"

    try:
        df = _read_sql_df(view_label, view_query, params=params)
    except Exception as exc:
        if should_skip_heavy_fallback(exc, view_label, base_label):
            return _empty_top_picks()
        print(f"[perf] {view_label} fallback: {exc}")
        df = _read_sql_df(base_label, base_query, params=params)

    return _prepare_top_picks(df)
