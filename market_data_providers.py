from __future__ import annotations

from collections.abc import Mapping
from io import StringIO

import pandas as pd
import requests
import streamlit as st
from pandas.errors import ParserError

from sp500_index_analyzer_data import load_sp500_historical_metrics


def _resolve_stooq_apikey() -> str:
    candidates: list[str | None] = []
    cfg = st.secrets.get("stooq", {})
    if isinstance(cfg, Mapping) or hasattr(cfg, "get"):
        candidates.extend([cfg.get("apikey"), cfg.get("api_key"), cfg.get("key")])
    candidates.extend(
        [
            st.secrets.get("STOOQ_API_KEY"),
            st.secrets.get("stooq_api_key"),
            st.secrets.get("stooq_apikey"),
        ]
    )
    for val in candidates:
        if val is None:
            continue
        text = str(val).strip()
        if text:
            return text
    return ""


def _finalize_close_series(df: pd.DataFrame, date_col: str, close_col: str) -> pd.Series:
    if df.empty or date_col not in df.columns or close_col not in df.columns:
        return pd.Series(dtype=float)
    tmp = df[[date_col, close_col]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce").dt.tz_localize(None)
    tmp[close_col] = pd.to_numeric(tmp[close_col], errors="coerce")
    tmp = tmp.dropna(subset=[date_col, close_col]).sort_values(date_col)
    if tmp.empty:
        return pd.Series(dtype=float)
    # If source has duplicate dates, keep the latest row for each date.
    tmp = tmp.drop_duplicates(subset=[date_col], keep="last")
    s = pd.Series(tmp[close_col].to_numpy(), index=tmp[date_col].dt.normalize())
    return s.sort_index()


def _download_stooq_close(symbol: str, interval: str = "d") -> pd.Series:
    apikey = _resolve_stooq_apikey()
    url = f"https://stooq.com/q/d/l/?s={symbol}&i={interval}"
    if apikey:
        url = f"{url}&apikey={apikey}"

    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    payload = resp.text

    if "Get your apikey" in payload and "get_apikey" in payload:
        raise ValueError(
            "Stooq requires an API key for CSV download. "
            "Add `stooq.apikey` (or `STOOQ_API_KEY`) to `.streamlit/secrets.toml`."
        )

    try:
        df = pd.read_csv(StringIO(payload))
    except ParserError as exc:
        preview = "\n".join(payload.splitlines()[:7])
        raise ValueError(f"Stooq returned a non-CSV response. First lines:\n{preview}") from exc

    s = _finalize_close_series(df, "Date", "Close")
    if s.empty:
        raise ValueError("Stooq returned empty or malformed CSV payload.")
    return s


def _download_yfinance_close(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    try:
        import yfinance as yf
    except Exception as exc:
        raise ValueError("yfinance fallback is unavailable (module not installed).") from exc

    df = yf.download(
        symbol,
        start=start.strftime("%Y-%m-%d"),
        end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        raise ValueError(f"No data from Yahoo Finance for ticker: {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if "Adj Close" in df.columns:
        close_col = "Adj Close"
    elif "Close" in df.columns:
        close_col = "Close"
    else:
        raise ValueError("Yahoo Finance payload missing Close/Adj Close.")

    tmp = df.reset_index()
    date_col = "Date" if "Date" in tmp.columns else tmp.columns[0]
    s = _finalize_close_series(tmp, date_col, close_col)
    if s.empty:
        raise ValueError("Yahoo Finance returned empty/malformed close series.")
    return s


def _download_sp500_db_close(start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    df = load_sp500_historical_metrics()
    if df.empty:
        raise ValueError("S&P 500 DB source returned empty data.")
    s = _finalize_close_series(df, "Date", "Price")
    if s.empty:
        raise ValueError("S&P 500 DB source missing Date/Price.")
    s = s[(s.index >= start.normalize()) & (s.index <= end.normalize())]
    if s.empty:
        raise ValueError("S&P 500 DB source has no rows in selected range.")
    return s


def _clip_series(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    if s.empty:
        return s
    clipped = s[(s.index >= start.normalize()) & (s.index <= end.normalize())]
    return clipped.dropna().sort_index()


@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def load_benchmark_close_series(
    preferred_source: str,
    stooq_symbol: str,
    yfinance_symbol: str,
    start_iso: str,
    end_iso: str,
    allow_sp500_db_fallback: bool = False,
) -> tuple[pd.Series, str, list[str]]:
    start = pd.to_datetime(start_iso)
    end = pd.to_datetime(end_iso)
    if pd.isna(start) or pd.isna(end):
        return pd.Series(dtype=float), "none", ["invalid date range"]

    source_chain: list[str]
    pref = str(preferred_source or "").strip().lower()
    if pref == "stooq":
        source_chain = ["stooq", "yfinance"]
    else:
        source_chain = ["yfinance"]
    if allow_sp500_db_fallback:
        source_chain.append("sp500_db")

    errors: list[str] = []
    for source in source_chain:
        try:
            if source == "stooq":
                series = _download_stooq_close(stooq_symbol, interval="d")
            elif source == "yfinance":
                series = _download_yfinance_close(yfinance_symbol, start=start, end=end)
            else:
                series = _download_sp500_db_close(start=start, end=end)
            series = _clip_series(series, start=start, end=end)
            if series.empty:
                raise ValueError("empty series after range clip")
            return series, source, errors
        except Exception as exc:  # noqa: BLE001 - capture source-specific failures
            errors.append(f"{source}: {exc}")

    return pd.Series(dtype=float), "none", errors
