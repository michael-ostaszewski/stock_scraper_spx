import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.parse
import datetime
import plotly.express as px
import numpy as np
import json
import time
from openai import OpenAI
import io
import re
from plotly.subplots import make_subplots

from app_auth import require_auth
from portfolio_forecaster_data import (
    PORTFOLIO_DAY_SNAPSHOT_COLUMNS,
    PORTFOLIO_HISTORY_COLUMNS,
    load_available_dates,
    load_portfolio_day_snapshot,
    load_portfolio_history,
    load_stock_universe,
    normalize_portfolio_tickers,
)
from stock_forecaster_data import performance_block
from market_data_providers import load_benchmark_close_series

require_auth("Portfolio Forecaster")

st.markdown("""
<style>
/* Default (green) style for all buttons */
div.stButton > button {
    display: inline-block;
    background-color: #28a745; /* green */
    color: white;
    padding: 8px 16px;
    border: 2px solid #1e7e34; /* darker green */
    border-radius: 4px;
    text-decoration: none;
    font-weight: normal;
    width: 100%;
    text-align: center;
    margin: 0.4em 0;
}
div.stButton > button:hover {
    background-color: #218838;
}

/* This CSS makes metric values bold */
[data-testid="stMetricValue"] {
    font-weight: bold;
}
/* Optionally: make metric labels bold as well */
[data-testid="stMetricLabel"] {
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

def _empty_day_snapshot() -> pd.DataFrame:
    return pd.DataFrame(columns=PORTFOLIO_DAY_SNAPSHOT_COLUMNS)


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=PORTFOLIO_HISTORY_COLUMNS)


def _prepare_history_daily_last(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df.empty:
        return _empty_history()

    daily_last = history_df.copy()
    sort_keys = ["Stock", "Date of record"]
    if "Time of record" in daily_last.columns:
        daily_last["Time of record"] = daily_last["Time of record"].fillna("").astype(str)
        sort_keys.append("Time of record")

    daily_last = (
        daily_last.sort_values(sort_keys)
        .groupby(["Date of record", "Stock"], as_index=False)
        .last()
    )
    return daily_last.reset_index(drop=True)


def _build_price_pivot(daily_last_df: pd.DataFrame) -> pd.DataFrame:
    if daily_last_df.empty:
        return pd.DataFrame()

    required_columns = {"Date of record", "Stock", "Price"}
    if not required_columns.issubset(daily_last_df.columns):
        return pd.DataFrame()

    working = daily_last_df.copy()
    working["Date"] = pd.to_datetime(working["Date of record"], errors="coerce").dt.normalize()
    working = working.dropna(subset=["Date", "Stock", "Price"])
    if working.empty:
        return pd.DataFrame()

    return working.pivot(index="Date", columns="Stock", values="Price").sort_index()


def _build_latest_history_by_stock(daily_last_df: pd.DataFrame) -> pd.DataFrame:
    if daily_last_df.empty:
        return _empty_history()

    return (
        daily_last_df.sort_values(["Stock", "Date of record"])
        .groupby("Stock", as_index=False)
        .last()
    )


available_dates = load_available_dates()
if available_dates:
    max_date = available_dates[-1]
    selected_date = st.sidebar.date_input(
        "Date selector",
        value=max_date,
        min_value=available_dates[0],
        max_value=max_date,
    )
    data_version = max_date.isoformat()
else:
    max_date = datetime.date.today()
    selected_date = st.sidebar.date_input("Date selector", value=max_date)
    data_version = ""
    st.sidebar.warning("No forecast dates available in the database.")

filtered_data = _empty_day_snapshot()
portfolio_history = _empty_history()
portfolio_history_daily_last = _empty_history()
xtb_history = _empty_history()
xtb_history_daily_last = _empty_history()


# ======================================================================
# 4. session_state for our portfolio
# ======================================================================
if "user_portfolio_df" not in st.session_state:
    # Columns we want (including 'Type' and optionally 'Open time')
    st.session_state["user_portfolio_df"] = pd.DataFrame(columns=[
        "Symbol", "Type", "Volume", "Open price", "Open time"
    ])

# We remember whether we have already uploaded a given file
if "last_uploaded_file_name" not in st.session_state:
    st.session_state["last_uploaded_file_name"] = None


# ======================================================================
# Title and description
# ======================================================================
st.title("Portfolio Forecaster")
st.markdown("""
This tab helps you analyze stock price forecasts for your portfolio.

1. Upload a CSV file with your stock list (see the detailed instructions below), **or** add stocks manually using the form.
2. To include your full XTB history, export the report from **Account History → Export → Range (All) → Format: Excel (.xlsx)**, then upload the downloaded file **unchanged**.
3. After entering data, the app will automatically show analysis and charts for your portfolio.

Notes:
- Your data is **not stored** anywhere; it is used only in your current session.
- The analysis currently supports **U.S. stocks only**, limited to the **Russell 1000** universe.
""")

st.markdown("<hr>", unsafe_allow_html=True)
# ======================================================================
# 5. CSV instructions + example file
# ======================================================================
@st.cache_data
def load_example_portfolio():
    example_df = pd.DataFrame({
        "Symbol": ["AAPL", "MSFT"],
        "Type": ["BUY", "BUY"],
        "Volume": [1, 2],
        "Open time": ["", ""],
        "Open price": [123.45, 410.00],
    })
    return example_df


example_df = load_example_portfolio()


html_table = example_df.head(3).to_html(index=False, border=0)
csv_data = example_df.to_csv(index=False, sep=';')
csv_data_encoded = urllib.parse.quote(csv_data)

custom_html = f"""
<style>
    .custom-table {{
        width: 100%;
        margin: 0 auto;
    }}
    .custom-table table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .custom-table th {{
        text-align: left;
    }}
    details {{
        background-color: transparent;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        border: 1px solid #808080;
    }}
    summary {{
        font-size: 16px;
        font-weight: bold;
        color: white;
        cursor: pointer;
    }}
    p.explanation {{
        color: white;
        margin: 10px 0;
        font-size: 14px;
    }}
    a.download-link {{
        display: inline-block;
        background-color: #28a745; 
        color: white;
        padding: 8px 16px;
        border: 2px solid #1e7e34;
        border-radius: 4px;
        text-decoration: none;
        font-weight: normal;
        width: 100%;
        text-align: center;
        margin-top: 10px;
    }}
    a.download-link:hover {{
        background-color: #218838;
    }}
</style>
<details>
    <summary>Learn more about how to prepare the CSV file to upload your stock list:</summary>
    <p class="explanation">
        An example column format is:<br>
        <strong>Symbol;Type;Volume;Open time;Open price</strong><br>
        Where <strong>Symbol, Type, Volume, Open price</strong> are required (Type = BUY/SELL), 
        and <strong>Open time</strong> is optional.
    </p>
    <div class="custom-table">
        {html_table}
    </div>
    <a class="download-link" download="xtb_stock_list_sample.csv" href="data:text/csv;charset=utf-8,{csv_data_encoded}">
    Download sample CSV file here
</a>
</details>
"""

st.markdown(custom_html, unsafe_allow_html=True)

# ======================================================================
# 6. Unified upload: CSV *or* XLSX (auto-transform for XLSX)
# ======================================================================

st.markdown("#### Upload XLSX file from your XTB with full history of your portfolio:")

st.caption("Accepted formats: **.csv**, **.xlsx**, **.xls**")
uploaded_any = st.file_uploader("", type=["csv", "xlsx", "xls"])

# ---------- helpers specific for XLSX transform ----------
def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    def norm(s):
        s = str(s).strip()
        return s, s.lower().replace(" ", "").replace("_", "")
    mapping = {c: norm(c) for c in df.columns}
    df.attrs["__simple_cols__"] = mapping
    return df

def _find_column(df: pd.DataFrame, candidates) -> str:
    mapping = df.attrs.get("__simple_cols__", {})
    simp_to_orig = {v[1]: k for k, v in mapping.items()}
    cand_simplified = [c.lower().replace(" ", "").replace("_", "") for c in candidates]
    for cs in cand_simplified:
        if cs in simp_to_orig:
            return simp_to_orig[cs]
    # fallback: zawieranie
    for cs in cand_simplified:
        for simp, orig in ((v[1], k) for k, v in mapping.items()):
            if cs in simp:
                return orig
    raise KeyError(f"Column not found for patterns: {candidates}")

def _coerce_number(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x).strip().replace(" ", "").replace("\u00a0", "").replace("\xa0", "")
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return np.nan

def _parse_datetime_flex(x):
    if pd.isna(x) or str(x).strip() == "":
        return ""
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        dt = pd.to_datetime(x, errors="coerce")
    else:
        s = str(x).strip()
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
        if pd.isna(dt):
            dt = pd.to_datetime(s, errors="coerce", dayfirst=False, infer_datetime_format=True)
    if pd.isna(dt):
        return ""
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def _process_xlsx_to_df(uploaded_file) -> pd.DataFrame:
    """
    Przyjmuje UploadedFile (XLSX/XLS), zwraca DataFrame w docelowym formacie:
    columns = ["Symbol", "Type", "Volume", "Open price", "Open time"]
    """
    # czytamy bytes do pamięci, by móc używać wielokrotnie (ExcelFile + parse)
    raw = uploaded_file.read()
    bio = io.BytesIO(raw)

    # Wybór arkusza: nazwa zawiera BOTH "OPEN" i "POSITION" (case-insensitive)
    xls = pd.ExcelFile(bio, engine="openpyxl")
    sheet_candidates = [n for n in xls.sheet_names if ("OPEN" in n.upper() and "POSITION" in n.upper())]
    if not sheet_candidates:
        raise ValueError(
            "No worksheet matching 'OPEN*POSITION*' found. Sheets: " + ", ".join(xls.sheet_names)
        )
    sheet_name = sheet_candidates[0]

    # parse wymaga odświeżenia wskaźnika pliku (nowy BytesIO)
    bio2 = io.BytesIO(raw)
    df = pd.read_excel(bio2, sheet_name=sheet_name, engine="openpyxl", skiprows=10, header=0)

    # sprzątanie
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df = _normalize_cols(df)

    # usuń wiersze z "total"
    mask_total = df.astype(str).apply(lambda col: col.str.contains("total", case=False, na=False)).any(axis=1)
    df = df.loc[~mask_total].copy()

    # usuń ostatni wiersz (często stopka)
    if len(df) > 0:
        df = df.iloc[:-1, :].copy()

    # mapowanie kolumn
    col_symbol   = _find_column(df, ["Symbol", "Ticker", "Instrument"])
    col_type     = _find_column(df, ["Type", "Side", "Action", "Operation"])
    col_volume   = _find_column(df, ["Volume", "Qty", "Quantity", "Amount", "Size"])
    col_opentime = _find_column(df, ["OpenTime", "Open time", "Open_time", "Time open", "Opened time"])
    col_openpx   = _find_column(df, ["OpenPrice", "Open price", "Open_price", "Price open"])

    df = df[[col_symbol, col_type, col_volume, col_opentime, col_openpx]].copy()
    df.columns = ["Symbol", "Type", "Volume", "Open time", "Open price"]

    # formatowanie
    df["Symbol"] = (
        df["Symbol"].astype(str).str.strip().str.upper()
          .str.replace(r"\.us$", "", case=False, regex=True)  # utnij .us
    )
    df["Type"] = df["Type"].astype(str).str.strip().str.upper()
    df["Volume"] = df["Volume"].map(_coerce_number)
    df["Open price"] = df["Open price"].map(_coerce_number)
    df["Open time"] = df["Open time"].map(_parse_datetime_flex)

    # usuń puste
    df = df[(df["Symbol"] != "") & (df["Open time"] != "")]
    df = df.dropna(subset=["Volume", "Open price"])

    # Dla Twojej aplikacji lepiej trzymać liczby jako floaty (konwersje robisz później)
    # więc NIE zamieniam na stringi z przecinkiem – zostawiam float.
    # Kolejność kolumn zgodna z resztą aplikacji:
    return df[["Symbol", "Type", "Volume", "Open price", "Open time"]].reset_index(drop=True)

# ---------- main upload handler ----------
if uploaded_any is not None:
    # sprawdź duplikat po nazwie pliku
    if uploaded_any.name != st.session_state["last_uploaded_file_name"]:
        try:
            name_lower = uploaded_any.name.lower()
            if name_lower.endswith(".csv"):
                # CSV (jak wcześniej): średnik, brakujące kolumny → dopełniamy
                csv_df = pd.read_csv(uploaded_any, delimiter=';')
                for col in ["Symbol", "Type", "Volume", "Open price", "Open time"]:
                    if col not in csv_df.columns:
                        csv_df[col] = ""
                # normalizacja symboli (zgodnie z tym co robimy przy XLSX)
                csv_df["Symbol"] = (
                    csv_df["Symbol"].astype(str).str.strip().str.upper()
                          .str.replace(r"\.us$", "", case=False, regex=True)
                )
                # dopinamy
                st.session_state["user_portfolio_df"] = pd.concat(
                    [st.session_state["user_portfolio_df"], csv_df[["Symbol","Type","Volume","Open price","Open time"]]],
                    ignore_index=True
                ).fillna("")
                st.session_state["last_uploaded_file_name"] = uploaded_any.name
                st.success(f"Successfully loaded CSV file: {uploaded_any.name}")

            # elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
            elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
                # zapisz bytes raportu XTB do session_state (będzie używane w sekcjach poniżej)
                st.session_state["xtb_report_bytes"] = uploaded_any.getvalue()
            #     # XLSX/XLS → transformacja do docelowych kolumn
                df_x = _process_xlsx_to_df(uploaded_any)
                # dopinamy (floaty zostają; reszta appki już radzi sobie z konwersjami)
                st.session_state["user_portfolio_df"] = pd.concat(
                    [st.session_state["user_portfolio_df"], df_x],
                    ignore_index=True
                )
                st.session_state["last_uploaded_file_name"] = uploaded_any.name
                st.success(f"Successfully processed Excel file: {uploaded_any.name}")

            else:
                st.error("Unsupported file type. Please upload .csv, .xlsx or .xls.")

        except Exception as e:
            st.error(f"Error while processing file '{uploaded_any.name}': {e}")

    else:
        st.info("This same file has already been processed previously (not duplicating data).")


# ======================================================================
# 7. Manually adding a stock: (Symbol, Type, Volume, Open price – required, Open time – optional)
# ======================================================================
st.markdown("#### Add a stock manually:")

col_left, col_right = st.columns(2)
with col_left:
    symbol_input = st.text_input("Symbol (e.g. AMD):", key="manual_symbol")
    trans_type = st.selectbox("Transaction type:", ["BUY", "SELL"], key="manual_type")
with col_right:
    volume_input = st.text_input("Volume (e.g. 1.0):", key="manual_volume")
    open_price_input = st.text_input("Open price (e.g. 123.45):", key="manual_open_price")

# Date and time – optional
date_time_expander = st.expander("Open time (Date and time) – optional", expanded=False)
with date_time_expander:
    st.write("Select the transaction date and time (optional).")
    now_dt = datetime.datetime.now()
    transaction_date = st.date_input("Transaction date:", value=now_dt.date())
    transaction_time = st.time_input("Transaction time: (if you do not enter an exact time, the current time will be used by default):", value=now_dt.time())
    open_time_str = f"{transaction_date.strftime('%d/%m/%Y')} {transaction_time.strftime('%H:%M:%S')}"

add_btn = st.button("Add stock to portfolio")
if add_btn:
    # Check mandatory fields: Symbol, Type, Volume, Open price
    if symbol_input and trans_type and volume_input and open_price_input:
        try:
            vol = float(volume_input.replace(",", "."))
            price = float(open_price_input.replace(",", "."))
            # If trans_type = SELL, we interpret volume as negative in calculations
            # (but in raw data we keep it as the user entered – Volume>0 + Type=SELL)
            # Net volume will be calculated later in the aggregator

            # Build a new record (Open time is optional)
            row_data = {
                "Symbol": symbol_input.strip().upper(),
                "Type": trans_type,
                "Volume": vol,
                "Open price": price,
                "Open time": open_time_str if date_time_expander else ""
            }
            st.session_state["user_portfolio_df"] = pd.concat([
                st.session_state["user_portfolio_df"],
                pd.DataFrame([row_data])
            ], ignore_index=True)
            st.success(f"Added {symbol_input.upper()} (Type={trans_type}, Volume={vol}, Open={price}).")
        except ValueError:
            st.error("Invalid format for Volume or Open price. Use numeric values (dot or comma).")
    else:
        st.warning("To add data to the portfolio, you must fill out: Symbol, Type, Volume, Open price. (Open time is optional).")

st.markdown("<hr>", unsafe_allow_html=True)


# Displaying the portfolio table
st.markdown("### Current stocks in your portfolio:")
user_df = st.session_state["user_portfolio_df"]  # shortcut to data
if user_df.empty:
    st.info("No data. Please upload a file or add a stock manually.")
else:
    display_df = user_df.copy()
    display_df.index = range(1, len(display_df) + 1)  # numbering from 1
    display_df = display_df.rename_axis("No. Transaction")  # index name

    # Dropdowns for filtering:
    col1, col2, col3 = st.columns(3)
    with col1:
        options = [5, 10, 20, 50, "All"]
        num_rows = st.selectbox("Number of rows to display", options=options, index=0)
    with col2:
        selected_type = st.selectbox("Select transaction type", options=["All", "BUY", "SELL"], index=0)
    with col3:
        unique_symbols = sorted(display_df["Symbol"].unique())
        selected_symbol = st.selectbox("Select symbol", options=["All"] + unique_symbols, index=0)

    if selected_type != "All":
        display_df = display_df[display_df["Type"] == selected_type]
    if selected_symbol != "All":
        display_df = display_df[display_df["Symbol"] == selected_symbol]

    if num_rows == "All":
        df_to_show = display_df
    else:
        df_to_show = display_df.head(num_rows)
    st.dataframe(df_to_show, use_container_width=True)

    # Buttons to clear the portfolio – displayed only if the portfolio is not empty:
    clear_clicked = st.button("Clear current portfolio data")
    if clear_clicked:
        st.session_state["show_clear_confirmation"] = True

    if st.session_state.get("show_clear_confirmation", False):
        confirm_clear = st.checkbox("I confirm that I want to clear the portfolio data", key="confirm_clear")
        if st.button("Confirm clearing"):
            if confirm_clear:
                st.session_state["user_portfolio_df"] = pd.DataFrame(columns=[
                    "Symbol", "Type", "Volume", "Open price", "Open time"
                ])
                st.session_state["last_uploaded_file_name"] = None
                st.success("Portfolio data has been cleared. Refresh the page to see changes.")
                st.session_state["show_clear_confirmation"] = False
            else:
                st.error("You must confirm that you want to clear the portfolio data.")

st.markdown("<hr>", unsafe_allow_html=True)

# Calculate the number of unique stocks in the portfolio:
portfolio_df = st.session_state["user_portfolio_df"].copy()

# Convert "Volume" and "Open price" columns to numeric (float)
if not portfolio_df.empty:
    portfolio_df["Volume"] = pd.to_numeric(
        portfolio_df["Volume"].astype(str).str.replace(",", "."),
        errors="coerce"
    ).fillna(0)
    portfolio_df["Open price"] = pd.to_numeric(
        portfolio_df["Open price"].astype(str).str.replace(",", "."),
        errors="coerce"
    ).fillna(0)

if portfolio_df.empty:
    num_unique_tickers = 0
else:
    signed_volume = (
        portfolio_df["Volume"].astype(str).str.replace(",", ".").astype(float, errors="ignore")
        * portfolio_df["Type"].str.upper().map({"BUY": 1, "SELL": -1})
    )

    num_unique_tickers = (
        portfolio_df.assign(SignedVolume=signed_volume)
        .groupby("Symbol")["SignedVolume"]
        .sum()                # wolumen netto każdej spółki
        .ne(0)                # True, gdy wolumen netto ≠ 0
        .sum()                # zliczamy True → int
    )


# Convert columns to float if necessary:
try:
    portfolio_df["Volume"] = portfolio_df["Volume"].astype(str).str.replace(",", ".").astype(float)
    portfolio_df["Open price"] = portfolio_df["Open price"].astype(str).str.replace(",", ".").astype(float)
except Exception as e:
    st.error("Error converting Volume or Open price: " + str(e))


portfolio_df["Symbol"] = (
    portfolio_df["Symbol"]
    .astype(str)
    .str.strip()
    .str.upper()
    .str.replace(r"\.US$", "", regex=True)
)

portfolio_df["NetVolume"] = portfolio_df.apply(
    lambda row: row["Volume"] if str(row["Type"]).upper() == "BUY" else -abs(row["Volume"]),
    axis=1
)

open_portfolio_tickers = normalize_portfolio_tickers(portfolio_df)
portfolio_tickers = list(open_portfolio_tickers)
portfolio_context = {
    "tickers": open_portfolio_tickers,
    "has_open_positions": bool(open_portfolio_tickers),
}

if available_dates and portfolio_context["has_open_positions"]:
    filtered_data = load_portfolio_day_snapshot(selected_date, data_version).copy()
    portfolio_history = load_portfolio_history(open_portfolio_tickers, data_version).copy()
    if filtered_data.empty:
        st.sidebar.warning("No forecast data for the selected date.")
else:
    filtered_data = _empty_day_snapshot()
    portfolio_history = _empty_history()

portfolio_history_daily_last = _prepare_history_daily_last(portfolio_history)
portfolio_history_latest = _build_latest_history_by_stock(portfolio_history_daily_last)

total_investment = (portfolio_df["NetVolume"] * portfolio_df["Open price"]).sum()

if not filtered_data.empty and "Stock" in filtered_data.columns:
    filtered_data["Stock"] = filtered_data["Stock"].astype(str).str.upper()

merged_df = portfolio_df.merge(filtered_data[["Stock", "Price"]], left_on="Symbol", right_on="Stock", how="left")
merged_df["Price"] = merged_df["Price"].fillna(0)
total_current_value = (merged_df["NetVolume"] * merged_df["Price"]).sum()

if total_investment != 0:
    percent_diff = ((total_current_value - total_investment) / total_investment) * 100
else:
    percent_diff = 0

st.header("Portfolio Summary and Allocation")

col1, col2, col3 = st.columns(3)
col1.metric("Number of stocks in portfolio", f"{num_unique_tickers}")
col2.metric("Investment amount", f"{total_investment:.2f} USD")
col3.metric("Current investment value", f"{total_current_value:.2f} USD", delta=f"{percent_diff:+.2f}%")


# ======================================================================
# 10. Pie chart of portfolio allocation by purchased stocks
# ======================================================================
if not user_df.empty and {"Symbol", "Type", "Volume", "Open price"}.issubset(user_df.columns):
    # Convert Volume, Open price to float
    df_temp = user_df.copy()
    try:
        df_temp["Volume"] = df_temp["Volume"].astype(str).str.replace(",", ".").astype(float)
        df_temp["Open price"] = df_temp["Open price"].astype(str).str.replace(",", ".").astype(float)
    except ValueError:
        st.warning("Invalid values in Volume or Open price – cannot draw a chart.")
    else:
        # BUY => positive volume, SELL => negative volume
        def volume_with_sign(row):
            if str(row["Type"]).upper() == "SELL":
                return -abs(row["Volume"])
            else:
                return abs(row["Volume"])

        df_temp["CalcVolume"] = df_temp.apply(volume_with_sign, axis=1)
        df_temp["Invested"] = df_temp["CalcVolume"] * df_temp["Open price"]

        # Group by Symbol => net volume and net invested
        portfolio_grouped = df_temp.groupby("Symbol", as_index=False).agg({
            "CalcVolume": "sum",
            "Invested": "sum"
        })

        # For stocks with net Invested <= 0, skip them in the pie chart (no sense in a "negative" wedge)
        portfolio_grouped = portfolio_grouped[portfolio_grouped["Invested"] > 0]
        if portfolio_grouped.empty:
            st.info("All positions in your portfolio have 0 or negative value (e.g., SELL>BUY). No data to chart.")
        else:
            portfolio_grouped["Invested"] = portfolio_grouped["Invested"].round(2)

            fig_pie = go.Figure(
                data=[go.Pie(
                    labels=portfolio_grouped["Symbol"],
                    values=portfolio_grouped["Invested"],
                    customdata=portfolio_grouped["CalcVolume"],
                    textinfo='label+percent',
                    hovertemplate='%{label}: %{value:.2f} USD Invested<br>Volume: %{customdata:.2f}<extra></extra>',
                    showlegend=False
                )]
            )
            fig_pie.update_layout(
                title="Portfolio Allocation by Stocks",
                height=600
            )
            st.plotly_chart(fig_pie, use_container_width=True)


if "Sector" in filtered_data.columns and 'portfolio_grouped' in locals() and not portfolio_grouped.empty:
    df_sector_merge = portfolio_grouped.merge(
        filtered_data[["Stock", "Sector"]].drop_duplicates(subset=["Stock"]),
        left_on="Symbol",
        right_on="Stock",
        how="left"
    )
    df_sector_merge["Sector"] = df_sector_merge["Sector"].fillna("Unknown Sector")

    df_sector_grouped = df_sector_merge.groupby("Sector", as_index=False).agg({
        "Invested": "sum",
        "Symbol": lambda x: ", ".join(x.unique())
    })

    df_sector_grouped = df_sector_grouped[df_sector_grouped["Invested"] > 0]

    if df_sector_grouped.empty:
        st.info("No positive investment values in the sector breakdown.")
    else:
        df_sector_grouped["Invested"] = df_sector_grouped["Invested"].round(2)

        fig_sector = go.Figure(
            data=[go.Pie(
                labels=df_sector_grouped["Sector"],
                values=df_sector_grouped["Invested"],
                customdata=df_sector_grouped["Symbol"],
                textinfo="label+percent",
                hovertemplate="%{label}: %{value:.2f} USD<br>Stocks: %{customdata}<extra></extra>",
                showlegend=False
            )]
        )
        fig_sector.update_layout(
            title="Portfolio Allocation by Sector",
            height=600
        )
        st.plotly_chart(fig_sector, use_container_width=True)
else:
    st.info("No 'Sector' column in forecasts or the 'portfolio_grouped' variable was not defined – cannot generate sector breakdown.")

st.markdown("<hr>", unsafe_allow_html=True)

st.header("12‑Month Forecast Returns")

user_df = portfolio_df.copy()
scoring = filtered_data[filtered_data["Stock"].isin(portfolio_tickers)].copy()
merged = pd.DataFrame()
wa_median = np.nan

if scoring.empty:
    st.warning("No forecasts available for the stocks in your portfolio on the selected date.")
else:
    merged = scoring.merge(
        user_df[["Symbol", "NetVolume"]],
        left_on="Stock", right_on="Symbol", how="inner"
    )
    merged["Price"] = (
        merged["Price"].astype(str).str.replace(",", ".")
        .astype(float, errors="ignore").fillna(0)
    )
    merged["stock_value"] = merged["NetVolume"] * merged["Price"]
    tot_val = merged["stock_value"].sum()

    if tot_val == 0:
        st.warning("Total portfolio value = 0 (or no valid data).")
    else:
        merged["weight"] = merged["stock_value"] / tot_val
        for col in ["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]:
            merged[col] = merged[col].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0)

        wa_low    = (merged["weight"] * merged["Low Forecast Percent"]).sum()
        wa_median = (merged["weight"] * merged["Median Forecast Percent"]).sum()
        wa_high   = (merged["weight"] * merged["High Forecast Percent"]).sum()

        r1c1, r1c2, r1c3 = st.columns(3)
        r1c1.metric("Median – Low Forecast",    f"{wa_low:.2f}%")
        r1c2.metric("Median – Median Forecast", f"{wa_median:.2f}%")
        r1c3.metric("Median – High Forecast",   f"{wa_high:.2f}%")

    view_mode = st.selectbox(
        "Forecast view:",
        options=["Detailed", "Compressed", "Low only", "Median only", "High only"],
        index=0
    )

    forecast_cols = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]

    fig = go.Figure()
    detailed_idx, comp_idx = [], []

    with performance_block("build_portfolio_forecast_chart"):
        df_det = portfolio_history_daily_last[
            portfolio_history_daily_last["Stock"].isin(portfolio_tickers)
        ].copy()

        for tk in portfolio_tickers:
            dtk = df_det[df_det["Stock"] == tk]
            if dtk.empty:
                continue
            for col in forecast_cols:
                yvals = (
                    dtk[col]
                    .astype(str)
                    .str.replace(",", ".")
                    .astype(float, errors="ignore")
                    .fillna(0)
                    .round(2)
                )
                fig.add_trace(
                    go.Scatter(
                        x=dtk["Date of record"],
                        y=yvals,
                        mode="lines+markers",
                        name=f"{tk} – {col}",
                        visible=True
                    )
                )
                detailed_idx.append(len(fig.data) - 1)

        df_portfolio_net = (
            user_df.groupby("Symbol", as_index=False)["NetVolume"].sum()
            .rename(columns={"Symbol": "Stock"})
        )
        df_w = df_det.merge(df_portfolio_net, on="Stock", how="left")
        df_w["Price"] = df_w["Price"].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0)
        df_w["stock_value"] = df_w["NetVolume"] * df_w["Price"]

        def w_avg(g, col):
            num = (g[col] * g["stock_value"]).sum()
            den = g["stock_value"].sum()
            return num / den if den else 0

        df_cmp = df_w.groupby("Date of record", as_index=False).apply(
            lambda g: pd.Series({
                "Weighted Low": w_avg(g, "Low Forecast Percent"),
                "Weighted Median": w_avg(g, "Median Forecast Percent"),
                "Weighted High": w_avg(g, "High Forecast Percent")
            })
        ).reset_index()

        if not df_cmp.empty:
            for col in ["Weighted Low", "Weighted Median", "Weighted High"]:
                fig.add_trace(
                    go.Scatter(
                        x=df_cmp["Date of record"],
                        y=df_cmp[col].round(2),
                        mode="lines+markers",
                        name=f"Compressed – {col}",
                        visible=False
                    )
                )
                comp_idx.append(len(fig.data) - 1)

    low_idx    = [i for i,tr in enumerate(fig.data) if "Low"    in tr.name]
    med_idx    = [i for i,tr in enumerate(fig.data) if "Median" in tr.name]
    high_idx   = [i for i,tr in enumerate(fig.data) if "High"   in tr.name and "Low" not in tr.name]

    total = len(fig.data)
    vis_all_det  = [i in detailed_idx for i in range(total)]
    vis_all_cmp  = [i in comp_idx     for i in range(total)]
    vis_low      = [i in low_idx      for i in range(total)]
    vis_med      = [i in med_idx      for i in range(total)]
    vis_high     = [i in high_idx     for i in range(total)]

    if   view_mode == "Detailed":      chosen_vis = vis_all_det
    elif view_mode == "Compressed":    chosen_vis = vis_all_cmp
    elif view_mode == "Low only":      chosen_vis = vis_low
    elif view_mode == "Median only":   chosen_vis = vis_med
    else:                              chosen_vis = vis_high     # "High only"

    for i,tr in enumerate(fig.data):
        tr.visible = chosen_vis[i]

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Forecast (%)",
        margin=dict(t=20)
    )

    all_y = []
    for tr in fig.data:
        if tr.visible and tr.y is not None:
            all_y.extend([v for v in tr.y.tolist() if pd.notnull(v)])

    if all_y:
        pad = 0.05 * (max(all_y) - min(all_y)) or 1
        fig.update_yaxes(range=[min(all_y) - pad, max(all_y) + pad])

    # red‑green background
    fig.add_shape(type="rect", x0=0,x1=1,xref="paper",
                  y0=-500,y1=0,yref="y",
                  fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=0,x1=1,xref="paper",
                  y0=0,y1=500,yref="y",
                  fillcolor="rgba(0,255,0,0.1)", line_width=0, layer="below")

    st.plotly_chart(fig, use_container_width=True)



# ============================================================
#   NEW SECTION 1: CASH OPERATION HISTORY (XTB)  [FIXED]
#   - deposit sum includes TRANSFER-in (currency conversions)
#   - XIRR uses deposits+transfers+withdrawals as external flows
#   - holdings include initial positions opened before the range
#   - Free-funds Interest is displayed (already included in equity)
# ============================================================

st.markdown("---")
st.header("Cash operations and return (XTB)")

# ---- helpers ----
def _xtb_find_sheet(sheet_names, must_have_keywords):
    must = [m.lower() for m in must_have_keywords]
    for s in sheet_names:
        low = s.lower()
        if all(m in low for m in must):
            return s
    return None

@st.cache_data(show_spinner=False)
def _xtb_read_cash_ops(raw_bytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(raw_bytes), engine="openpyxl")
    sh = _xtb_find_sheet(xls.sheet_names, ["cash", "operation"])
    if not sh:
        raise ValueError(f"No CASH OPERATION HISTORY sheet found. Sheets: {xls.sheet_names}")

    df = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=sh, engine="openpyxl", skiprows=10)

    # usuń puste / Total
    if "Type" in df.columns:
        df = df[df["Type"].notna()].copy()

    # konwersje
    df["Time"] = pd.to_datetime(df.get("Time"), errors="coerce")
    df = df.dropna(subset=["Time"]).copy()

    df["Amount"] = pd.to_numeric(df.get("Amount"), errors="coerce").fillna(0.0)
    df["Type"] = df.get("Type").astype(str)

    # normy do porównań
    df["Type_norm"] = df["Type"].astype(str).str.strip().str.lower()
    df["Date"] = df["Time"].dt.normalize()

    return df

def _xnpv(rate: float, cashflows):
    t0 = cashflows[0][0]
    total = 0.0
    for d, cf in cashflows:
        years = (d - t0).days / 365.0
        total += cf / ((1.0 + rate) ** years)
    return total

def _xirr(cashflows, guess=0.1):
    amts = [a for _, a in cashflows]
    if not (any(a < 0 for a in amts) and any(a > 0 for a in amts)):
        return None

    rate = guess
    for _ in range(100):
        t0 = cashflows[0][0]
        f = 0.0
        df = 0.0
        for d, cf in cashflows:
            t = (d - t0).days / 365.0
            denom = (1.0 + rate) ** t
            f += cf / denom
            df += -t * cf / denom / (1.0 + rate)

        if abs(f) < 1e-8:
            return rate
        if df == 0 or not np.isfinite(df):
            break

        new_rate = rate - f / df
        if new_rate <= -0.9999 or not np.isfinite(new_rate):
            break
        if abs(new_rate - rate) < 1e-10:
            return new_rate
        rate = new_rate

    # secant fallback
    r0, r1 = -0.5, guess
    f0 = _xnpv(r0, cashflows)
    f1 = _xnpv(r1, cashflows)
    for _ in range(200):
        if f1 == f0:
            return None
        r2 = r1 - f1 * (r1 - r0) / (f1 - f0)
        if r2 <= -0.9999 or not np.isfinite(r2):
            r2 = (r1 + r0) / 2.0
        f2 = _xnpv(r2, cashflows)
        if abs(f2) < 1e-8:
            return r2
        r0, f0 = r1, f1
        r1, f1 = r2, f2

    return None


# ---- main ----
raw_xtb = st.session_state.get("xtb_report_bytes", None)
if not raw_xtb:
    st.info("Upload the full XTB XLSX report first (the file with multiple sheets).")
else:
    try:
        df_cash = _xtb_read_cash_ops(raw_xtb)
    except Exception as e:
        st.error(f"Could not read CASH OPERATION HISTORY: {e}")
        df_cash = pd.DataFrame()

    if df_cash.empty:
        st.warning("No cash operation data found in the report.")
    else:
        min_d = df_cash["Date"].min().date()
        max_d = df_cash["Date"].max().date()

        # date selectors
        default_from = max(min_d, (max_d - datetime.timedelta(days=90)))
        col_a, col_b = st.columns(2)
        with col_a:
            d_from = st.date_input("Date from", value=default_from, min_value=min_d, max_value=max_d, key="xtb_cash_from")
        with col_b:
            d_to = st.date_input("Date to", value=max_d, min_value=min_d, max_value=max_d, key="xtb_cash_to")

        if d_from > d_to:
            d_from, d_to = d_to, d_from

        start_day  = pd.Timestamp(d_from).normalize()
        end_day    = pd.Timestamp(d_to).normalize()
        start_prev = start_day - pd.Timedelta(days=1)

        df_period = df_cash[(df_cash["Date"] >= start_day) & (df_cash["Date"] <= end_day)].copy()

        # ---- sums requested (fixed) ----
        # Deposit sum = DEPOSIT + TRANSFER that increase USD funds (inflows only)
        inflow_mask = (
            df_period["Type_norm"].isin(["deposit", "transfer"])
            & (df_period["Amount"] > 0)
        )
        deposits_sum = df_period.loc[inflow_mask, "Amount"].sum()

        dividends_sum = df_period.loc[
            df_period["Type_norm"].str.contains("divid", na=False),
            "Amount"
        ].sum()

        withholding_tax_sum = df_period.loc[
            df_period["Type_norm"].eq("withholding tax"),
            "Amount"
        ].sum()  # zwykle ujemne

        # free funds interest (display only; it's already part of equity via cash balance)
        ff_interest_sum = df_period.loc[df_period["Type_norm"].eq("free-funds interest"), "Amount"].sum()
        ff_interest_tax = df_period.loc[df_period["Type_norm"].eq("free-funds interest tax"), "Amount"].sum()
        ff_interest_net = ff_interest_sum + ff_interest_tax

        # withdrawals (net)
        withdrawals_sum = df_period.loc[df_period["Type_norm"].eq("withdrawal"), "Amount"].sum()  # zwykle ujemne

        # ---- equity time series ----
        # cash balance daily from ALL ops (includes purchases/sales/fees/dividends/interest etc.)
        df_cash_daily = df_cash.groupby("Date", as_index=True)["Amount"].sum().sort_index()
        full_idx = pd.date_range(df_cash_daily.index.min(), end_day, freq="D")
        cash_balance_full = df_cash_daily.reindex(full_idx, fill_value=0.0).cumsum()

        idx_eval = pd.date_range(start_prev, end_day, freq="D")
        cash_eval = cash_balance_full.reindex(idx_eval, method="ffill").fillna(0.0)

        # ---- positions from XTB ----
        @st.cache_data(show_spinner=False)
        def _xtb_read_positions(raw_bytes: bytes):
            xls = pd.ExcelFile(io.BytesIO(raw_bytes), engine="openpyxl")
            sh_closed = _xtb_find_sheet(xls.sheet_names, ["closed", "position"])
            sh_open   = _xtb_find_sheet(xls.sheet_names, ["open", "position"])
            if not sh_closed:
                raise ValueError(f"No CLOSED POSITION HISTORY sheet found. Sheets: {xls.sheet_names}")

            df_closed = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=sh_closed, engine="openpyxl", skiprows=12)
            df_open = None
            if sh_open:
                df_open = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=sh_open, engine="openpyxl", skiprows=10)
            return df_closed, df_open

        def _norm_symbol(s):
            if pd.isna(s):
                return ""
            s = str(s).strip().upper()
            s = re.sub(r"\.US$", "", s, flags=re.I)
            return s

        def _prep_positions(df_closed, df_open, allowed_symbols: set):
            dc = df_closed[["Symbol", "Type", "Volume", "Open time", "Close time"]].copy()
            dc["Open time"]  = pd.to_datetime(dc["Open time"], errors="coerce")
            dc["Close time"] = pd.to_datetime(dc["Close time"], errors="coerce")
            dc = dc.dropna(subset=["Open time", "Close time"]).copy()

            dc["Symbol"] = dc["Symbol"].map(_norm_symbol)
            dc = dc[dc["Symbol"] != ""].copy()

            dc["signed_volume"] = pd.to_numeric(dc["Volume"], errors="coerce").fillna(0.0) * (
                dc["Type"].astype(str).str.upper().map({"BUY": 1, "SELL": -1}).fillna(1)
            )
            dc["open_date"] = dc["Open time"].dt.normalize()
            dc["close_date"] = dc["Close time"].dt.normalize()

            if df_open is not None and not df_open.empty:
                do = df_open[["Symbol", "Type", "Volume", "Open time"]].copy()
                do["Open time"] = pd.to_datetime(do["Open time"], errors="coerce")
                do = do.dropna(subset=["Open time"]).copy()

                do["Symbol"] = do["Symbol"].map(_norm_symbol)
                do = do[do["Symbol"] != ""].copy()

                do["signed_volume"] = pd.to_numeric(do["Volume"], errors="coerce").fillna(0.0) * (
                    do["Type"].astype(str).str.upper().map({"BUY": 1, "SELL": -1}).fillna(1)
                )
                do["open_date"] = do["Open time"].dt.normalize()
                do["close_date"] = pd.NaT

                dp = pd.concat(
                    [dc[["Symbol", "signed_volume", "open_date", "close_date"]],
                     do[["Symbol", "signed_volume", "open_date", "close_date"]]],
                    ignore_index=True
                )
            else:
                dp = dc[["Symbol", "signed_volume", "open_date", "close_date"]].copy()

            before = dp["Symbol"].nunique()
            dp = dp[dp["Symbol"].isin(allowed_symbols)].copy()
            after = dp["Symbol"].nunique()
            dropped = before - after
            return dp, dropped

        def _build_daily_holdings(dp, start_day, end_day):
            """
            Holdings at END OF EACH DAY.
            Includes initial holdings opened before start_day and not closed before start_day.
            """
            idx = pd.date_range(start_day, end_day, freq="D")

            # initial holdings at start_day (positions already open before start_day)
            init_mask = (dp["open_date"] < start_day) & (dp["close_date"].isna() | (dp["close_date"] >= start_day))
            init = dp.loc[init_mask].groupby("Symbol")["signed_volume"].sum()

            # deltas within the window
            ev_open = (
                dp.loc[(dp["open_date"] >= start_day) & (dp["open_date"] <= end_day)]
                .groupby(["open_date", "Symbol"])["signed_volume"].sum()
                .reset_index(name="Delta")
                .rename(columns={"open_date": "Date"})
            )

            dp_close = dp.dropna(subset=["close_date"]).copy()
            ev_close = (
                dp_close.loc[(dp_close["close_date"] >= start_day) & (dp_close["close_date"] <= end_day)]
                .groupby(["close_date", "Symbol"])["signed_volume"].sum()
                .reset_index(name="Delta")
                .rename(columns={"close_date": "Date"})
            )
            ev_close["Delta"] = -ev_close["Delta"]

            events = pd.concat([ev_open, ev_close], ignore_index=True)

            wide = (
                events.pivot_table(index="Date", columns="Symbol", values="Delta", aggfunc="sum")
                .reindex(idx)
                .fillna(0.0)
            )

            holdings = wide.cumsum()

            # add initial holdings to all days
            for sym, val in init.items():
                if sym in holdings.columns:
                    holdings[sym] = holdings[sym] + float(val)
                else:
                    holdings[sym] = float(val)

            holdings = holdings.reindex(idx).fillna(0.0)
            holdings.index.name = "Date"
            return holdings.sort_index(axis=1)

        allowed = load_stock_universe(data_version)

        try:
            df_closed, df_open = _xtb_read_positions(raw_xtb)
            dp, dropped_cnt = _prep_positions(df_closed, df_open, allowed)
        except Exception as e:
            st.error(f"Could not read CLOSED/OPEN position sheets: {e}")
            dp = pd.DataFrame()

        if dp.empty:
            st.warning("No positions found (or no matching symbols in your price database). Return/XIRR cannot be computed.")
        else:
            if dropped_cnt > 0:
                st.info(f"Skipped {dropped_cnt} instruments not found in your price database (e.g. crypto, indices).")

            xtb_tickers = tuple(sorted(dp["Symbol"].dropna().unique().tolist()))
            xtb_history = load_portfolio_history(xtb_tickers, data_version).copy()
            xtb_history_daily_last = _prepare_history_daily_last(xtb_history)
            px_pivot = _build_price_pivot(xtb_history_daily_last)

            if px_pivot.empty:
                st.warning("No daily prices available for the instruments from your XTB report.")
            else:
                holdings_eval = _build_daily_holdings(dp, start_prev, end_day)

                px_eval = px_pivot.reindex(holdings_eval.index).ffill().fillna(0.0)

                common_cols = [c for c in holdings_eval.columns if c in px_eval.columns]
                missing_prices = sorted(list(set(holdings_eval.columns) - set(common_cols)))

                mv = (holdings_eval[common_cols] * px_eval[common_cols]).sum(axis=1)
                equity = cash_eval + mv

                start_equity = float(equity.iloc[0])   # end of start_prev
                end_equity   = float(equity.iloc[-1])  # end of end_day

                ext_types = ["deposit", "transfer", "withdrawal"]
                net_contrib = df_period.loc[df_period["Type_norm"].isin(ext_types), "Amount"].sum()

                profit = end_equity - start_equity - float(net_contrib)
                denom = start_equity + float(net_contrib)
                simple_return = (profit / denom) if denom != 0 else np.nan

                flows = []
                flows.append((start_prev.date(), -start_equity))

                ext = df_period[df_period["Type_norm"].isin(ext_types)].copy()
                ext["Flow"] = -ext["Amount"].astype(float)

                ext_daily = (
                    ext.assign(_d=ext["Date"].dt.date)
                    .groupby("_d", as_index=False)["Flow"]
                    .sum()
                    .rename(columns={"_d": "Date"})
                    .sort_values("Date")
                )

                for row in ext_daily.itertuples(index=False):
                    dt = row.Date
                    if not isinstance(dt, datetime.date):
                        dt = pd.Timestamp(dt).date()
                    flows.append((dt, float(row.Flow)))

                flows.append((end_day.date(), +end_equity))

                irr = _xirr(flows, guess=0.1)

                c1, c2, c3 = st.columns(3)
                c1.metric("Sum of deposits (Deposit + Transfer-in)", f"{deposits_sum:,.2f} USD")
                c2.metric("Sum of dividends", f"{dividends_sum:,.2f} USD")
                c3.metric("Dividend withholding tax (net)", f"{(-withholding_tax_sum):,.2f} USD")

                c4, c5, c6 = st.columns(3)
                c4.metric("Free-funds interest (net)", f"{ff_interest_net:,.2f} USD")
                c5.metric(f"Start equity (end of {start_prev.date()})", f"{start_equity:,.2f} USD")
                c6.metric(f"End equity (end of {end_day.date()})", f"{end_equity:,.2f} USD")

                c7, c8, c9 = st.columns(3)
                c7.metric("Net external cashflow (deposit+transfer+withdrawal)", f"{float(net_contrib):,.2f} USD")
                c8.metric("Simple return", f"{(simple_return * 100):.2f}%" if np.isfinite(simple_return) else "n/a")
                c9.metric("XIRR (money-weighted)", f"{(irr * 100):.2f}%" if irr is not None else "n/a")

                with st.expander("Details (optional)"):
                    st.write(f"Start equity (end of {start_prev.date()}): {start_equity:,.2f} USD")
                    st.write(f"End equity (end of {end_day.date()}): {end_equity:,.2f} USD")
                    st.write(f"Net external cashflow in period (deposit+transfer+withdrawal): {net_contrib:,.2f} USD")

                    if missing_prices:
                        st.warning(
                            "Missing prices for: "
                            + ", ".join(missing_prices[:30])
                            + (" ..." if len(missing_prices) > 30 else "")
                        )

                    st.markdown("**Daily external flows used for XIRR**")
                    st.dataframe(ext_daily, use_container_width=True)

                    st.markdown("**Cash operations (latest 200 in selected range)**")
                    cols_show = [c for c in ["Time", "Type", "Symbol", "Amount", "Comment"] if c in df_period.columns]
                    show_ops = df_period[cols_show].sort_values("Time", ascending=False).head(200)
                    st.dataframe(show_ops, use_container_width=True)



# ============================================================
#   NEW SECTION 2: HOLDINGS TIMELINE (day-by-day)
#   - when you held which stock and how many shares
# ============================================================

st.markdown("---")
st.header("Holdings timeline (XTB)")

raw_xtb = st.session_state.get("xtb_report_bytes", None)
if not raw_xtb:
    st.info("Upload the full XTB XLSX report first (the file with multiple sheets).")
else:
    # Reuse date range from Section 1 if present, else make a local selector
    d_from = st.session_state.get("xtb_cash_from", None)
    d_to   = st.session_state.get("xtb_cash_to", None)

    # if user did not open Section 1 yet, fallback
    if not isinstance(d_from, datetime.date) or not isinstance(d_to, datetime.date):
        st.caption("Pick date range for holdings timeline")
        col_a, col_b = st.columns(2)
        with col_a:
            d_from = st.date_input("Date from (timeline)", value=datetime.date.today() - datetime.timedelta(days=90), key="xtb_hold_from")
        with col_b:
            d_to = st.date_input("Date to (timeline)", value=datetime.date.today(), key="xtb_hold_to")

    if d_from > d_to:
        d_from, d_to = d_to, d_from

    start_day = pd.Timestamp(d_from).normalize()
    end_day   = pd.Timestamp(d_to).normalize()

    # --- read positions again (cached in Section 1, but safe to call) ---
    try:
        # helpers from Section 1 should already exist if you pasted both sections in one file
        df_closed, df_open = _xtb_read_positions(raw_xtb)
    except Exception as e:
        st.error(f"Could not read CLOSED/OPEN position sheets: {e}")
        df_closed, df_open = pd.DataFrame(), pd.DataFrame()

    if df_closed.empty and (df_open is None or df_open.empty):
        st.warning("No positions found in the XTB report.")
    else:
        allowed = load_stock_universe(data_version)

        dp, dropped_cnt = _prep_positions(df_closed, df_open, allowed)

        if dp.empty:
            st.warning("No matching instruments found in your price database (timeline cannot be built).")
        else:
            if dropped_cnt > 0:
                st.info(f"Skipped {dropped_cnt} instruments not found in your price database (e.g. crypto, indices).")

            holdings = _build_daily_holdings(dp, start_day, end_day)

            EPS = 0.001

            # Utnij mikro-resztki wolumenu do zera
            holdings = holdings.where(holdings.abs() >= EPS, 0.0)

            # (opcjonalnie) usuń tickery, które po tym ucięciu są zerowe przez cały okres
            holdings = holdings.loc[:, (holdings.abs().sum(axis=0) >= EPS)]

            holdings_all = holdings.copy()  # pełny zestaw do sumy Total
            xtb_tickers = tuple(sorted(holdings_all.columns.tolist()))
            xtb_history = load_portfolio_history(xtb_tickers, data_version).copy()
            xtb_history_daily_last = _prepare_history_daily_last(xtb_history)

            # filter UI (optional): choose which tickers to show
            all_syms = list(holdings.columns)
            default_syms = all_syms[:min(15, len(all_syms))]
            show_syms = st.multiselect(
                "Tickers to display (optional):",
                options=all_syms,
                default=default_syms
            )
            if show_syms:
                holdings = holdings[show_syms].copy()

            # Build segments: one bar per constant-holding period
            segments = []
            idx = holdings.index

            for sym in holdings.columns:
                s = holdings[sym]
                # points where holdings changes
                change = s.ne(s.shift(1, fill_value=0))
                change_dates = idx[change]

                for i, seg_start in enumerate(change_dates):
                    vol = float(s.loc[seg_start])
                    if abs(vol) < EPS:
                        continue
                    seg_end = (change_dates[i + 1] - pd.Timedelta(days=1)) if (i + 1) < len(change_dates) else idx[-1]

                    # px.timeline wants x_end, so add +1 day to make it inclusive
                    segments.append({
                        "Stock": sym,
                        "Start": seg_start,
                        "End": seg_end + pd.Timedelta(days=1),
                        "Volume": vol
                    })

            seg_df = pd.DataFrame(segments)
            if seg_df.empty:
                st.info("No non-zero holdings in the selected date range.")
            else:
                st.caption("Bars are split whenever your position size changes. Volume is shown in hover.")
                fig_hold = px.timeline(
                    seg_df,
                    x_start="Start",
                    x_end="End",
                    y="Stock",
                    color="Stock",
                    hover_data={
                        "Stock": True,
                        "Start": "|%Y-%m-%d",
                        "End": "|%Y-%m-%d",
                        "Volume": ":.4f"
                    },
                    title="When you held each stock (with daily position size)"
                )
                fig_hold.update_layout(
                    height=600,
                    showlegend=False,
                    xaxis_title="Date",
                    yaxis_title="Stock",
                    dragmode="pan"
                )
                fig_hold.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
                fig_hold.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

                st.plotly_chart(fig_hold, use_container_width=True)

                with st.expander("Daily holdings table (optional)"):
                    st.dataframe(holdings.reset_index(), use_container_width=True)

# ============================================================
#   SMART SCORE (weighted by position size) timeline
# ============================================================

st.markdown("---")
st.header("Smart Score portfela (ważony wielkością pozycji)")

if "holdings_all" not in locals() or holdings_all.empty:
    st.info("Brak danych o pozycjach z XTB. Najpierw wgraj pełny raport XLSX i upewnij się, że sekcja Holdings timeline działa.")
else:
    df_scores = xtb_history_daily_last.copy()
    required_cols = {"Stock", "Date of record", "Smart Score"}

    if not required_cols.issubset(df_scores.columns):
        st.warning("Brakuje wymaganych kolumn do Smart Score (Stock, Date of record, Smart Score).")
    else:
        # Normalize inputs
        df_scores["Date of record"] = pd.to_datetime(df_scores["Date of record"], errors="coerce")
        df_scores["Date"] = df_scores["Date of record"].dt.normalize()
        df_scores["Stock"] = (
            df_scores["Stock"].astype(str).str.strip().str.upper()
                      .str.replace(r"\.US$", "", regex=True)
        )
        df_scores["Smart Score"] = pd.to_numeric(
            df_scores["Smart Score"].astype(str).str.replace(",", "."),
            errors="coerce"
        )

        df_scores = df_scores.dropna(subset=["Date", "Stock", "Smart Score"]).copy()
        if df_scores.empty:
            st.info("Brak danych Smart Score w bazie prognoz.")
        else:
            # Last record per stock per day
            df_scores = (
                df_scores.sort_values(["Stock", "Date of record"])
                         .groupby(["Date", "Stock"], as_index=False)
                         .last()
            )

            score_pivot = (
                df_scores.pivot(index="Date", columns="Stock", values="Smart Score")
                         .sort_index()
            )

            # Align to holdings timeline and forward-fill last known score
            score_eval = score_pivot.reindex(holdings_all.index).ffill()

            # Weigh by absolute position size (shares)
            weights = holdings_all.abs().copy()
            common_cols = [c for c in weights.columns if c in score_eval.columns]
            missing_scores = sorted(list(set(weights.columns) - set(common_cols)))

            if not common_cols:
                st.info("Brak wspólnych tickerów pomiędzy pozycjami a bazą Smart Score.")
            else:
                s = score_eval[common_cols]
                w = weights[common_cols]

                w_masked = w.where(s.notna(), 0.0)
                weight_sum = w_masked.sum(axis=1)
                weighted_sum = (s.fillna(0.0) * w_masked).sum(axis=1)
                wa_score = weighted_sum / weight_sum.replace(0, np.nan)

                plot_series = wa_score.dropna()
                if plot_series.empty:
                    st.info("Nie udało się wyliczyć średniej ważonej Smart Score dla wybranego okresu.")
                else:
                    with performance_block("build_portfolio_smart_score_chart"):
                        fig_score = go.Figure()
                        fig_score.add_trace(go.Scatter(
                            x=plot_series.index,
                            y=plot_series.values,
                            mode="lines+markers",
                            name="Smart Score (ważony)",
                            hovertemplate="%{x|%Y-%m-%d}<br>Smart Score: %{y:.2f}<extra></extra>"
                        ))
                        fig_score.update_layout(
                            height=500,
                            xaxis_title="Date",
                            yaxis_title="Smart Score (weighted by position size)",
                            margin=dict(t=20)
                        )
                    st.plotly_chart(fig_score, use_container_width=True)

                    latest_day = holdings_all.index.max()
                    latest_pos_abs = holdings_all.loc[latest_day].abs()
                    latest_pos_abs = latest_pos_abs[latest_pos_abs > 0]

                    if not latest_pos_abs.empty:
                        score_latest = score_eval.loc[latest_day] if latest_day in score_eval.index else pd.Series(dtype=float)
                        score_map = score_latest.to_dict()
                        df_prices_latest = _build_latest_history_by_stock(xtb_history_daily_last)
                        latest_price_map = (
                            df_prices_latest.sort_values(["Stock", "Date of record"])
                                            .groupby("Stock", as_index=True)["Price"]
                                            .last()
                                            .to_dict()
                        )

                        smartscore_table = pd.DataFrame({
                            "Ticker": latest_pos_abs.index,
                            "Liczba akcji": latest_pos_abs.values
                        })
                        smartscore_table["Smart Score"] = smartscore_table["Ticker"].map(score_map)
                        smartscore_table["Price"] = smartscore_table["Ticker"].map(latest_price_map)
                        smartscore_table["Wielkość pozycji (USD)"] = (
                            smartscore_table["Liczba akcji"] * smartscore_table["Price"]
                        )
                        smartscore_table = (
                            smartscore_table[["Ticker", "Smart Score", "Wielkość pozycji (USD)"]]
                            .sort_values("Wielkość pozycji (USD)", ascending=False, ignore_index=True)
                        )

                        st.caption(f"Skład na dzień: {latest_day.date()}")
                        st.dataframe(
                            smartscore_table,
                            hide_index=True,
                            use_container_width=True
                        )

                if missing_scores:
                    st.info(
                        "Brak Smart Score dla części tickerów (pominięte w średniej): "
                        + ", ".join(missing_scores[:30])
                        + (" ..." if len(missing_scores) > 30 else "")
                    )

# ============================================================
#   HOLDINGS MARKET VALUE (area) + CASH + BENCHMARKS
#   Added benchmark mode:
#   - Switch portfolio to benchmark + DCA (USD)
#     (initial Total equity invested at start + all later deposits invested)
# ============================================================

st.markdown("---")
st.subheader("Holdings market value over time")

if "holdings_all" not in locals() or holdings_all.empty:
    st.info("No holdings data available for this section. Make sure the Holdings timeline section runs first.")
else:
    # ----------------------------
    # UI: slice selection
    # ----------------------------
    all_syms_for_value = list(holdings_all.columns)
    default_subset = all_syms_for_value[:min(10, len(all_syms_for_value))]

    selected_syms_value = st.multiselect(
        "Tickers to highlight as a slice:",
        options=all_syms_for_value,
        default=default_subset,
        key="mv_slice_syms"
    )

    # ----------------------------
    # UI: benchmarks
    # ----------------------------
    bench_catalog = {
        "S&P 500":            {"stooq": "^spx", "yfinance": "^GSPC"},
        "Nasdaq Composite":   {"stooq": "^ndq", "yfinance": "^IXIC"},
        "Nasdaq 100":         {"stooq": "^ndx", "yfinance": "^NDX"},
        "Dow Jones":          {"stooq": "^dji", "yfinance": "^DJI"},
        "Russell 2000 (ETF)": {"stooq": "iwm.us", "yfinance": "IWM"},
    }

    bcol1, bcol2, bcol3 = st.columns([1.2, 2.2, 1.2])
    with bcol1:
        bench_source = st.selectbox(
            "Benchmark source:",
            options=["Stooq (recommended)", "yfinance"],
            index=0,
            key="bench_source"
        )
        bench_source_key = "stooq" if bench_source.startswith("Stooq") else "yfinance"

    with bcol2:
        bench_selected = st.multiselect(
            "Benchmarks to display:",
            options=list(bench_catalog.keys()),
            default=["S&P 500"],
            key="bench_selected"
        )

    with bcol3:
        base_mode = st.selectbox(
            "Benchmark scale:",
            options=[
                "Switch portfolio to benchmark + DCA (USD)",
                "DCA deposits into benchmark (USD)",
                "Match portfolio start (USD)",
                "0% = start",
                "100 = start",
            ],
            index=0,
            key="bench_base_mode"
        )

        # Normalizacja ma sens tylko przy trybach %/100
        enable_norm = base_mode in ["0% = start", "100 = start"]
        show_portfolio_norm = st.checkbox(
            "Add portfolio normalized",
            value=enable_norm,
            disabled=not enable_norm,
            key="bench_show_port_norm"
        )

    # ----------------------------
    # helpers: benchmarks fetch
    # ----------------------------
    def _normalize_series(s: pd.Series, mode: str) -> pd.Series:
        s = s.dropna()
        if s.empty:
            return s
        first = float(s.iloc[0])
        if first == 0:
            return pd.Series(index=s.index, data=np.nan)
        if mode == "0% = start":
            return (s / first - 1.0) * 100.0
        return (s / first) * 100.0

    def _anchor_to_portfolio_usd(bench_price: pd.Series, portfolio_start_usd: float) -> pd.Series:
        bench_price = bench_price.dropna()
        if bench_price.empty or portfolio_start_usd == 0:
            return pd.Series(dtype=float)
        b0 = float(bench_price.iloc[0])
        if b0 == 0:
            return pd.Series(dtype=float)
        return portfolio_start_usd * (bench_price / b0)

    def _dca_value_from_deposits(bench_price: pd.Series, deposit_daily: pd.Series, initial_usd: float = 0.0) -> pd.Series:
        """
        DCA: each day you deposit X, buy X/price shares at that day's close.
        If initial_usd > 0, also buy initial_usd at the first day (same price as day 1).
        """
        bench_price = bench_price.reindex(deposit_daily.index).ffill().bfill()

        shares = 0.0
        vals = []

        idx = deposit_daily.index
        for i, dt in enumerate(idx):
            px = float(bench_price.loc[dt]) if pd.notna(bench_price.loc[dt]) else 0.0
            dep = float(deposit_daily.loc[dt]) if pd.notna(deposit_daily.loc[dt]) else 0.0

            if px > 0:
                if i == 0 and initial_usd > 0:
                    shares += initial_usd / px
                if dep > 0:
                    shares += dep / px
                vals.append(shares * px)
            else:
                vals.append(np.nan)

        s_val = pd.Series(vals, index=idx).ffill()
        return s_val

    # ----------------------------
    # 1) Portfolio holdings value from your price DB
    # ----------------------------
    px_pivot = _build_price_pivot(xtb_history_daily_last)
    if px_pivot.empty:
        st.warning("No 'Date of record' in your price database, cannot compute market value.")
    else:
        px_eval = px_pivot.reindex(holdings_all.index).ffill()
        px_eval = px_eval.reindex(columns=holdings_all.columns).fillna(0.0)

        mv_by_ticker = holdings_all.mul(px_eval)
        holdings_mv = mv_by_ticker.sum(axis=1)

        selected_mv = mv_by_ticker[selected_syms_value].sum(axis=1) if selected_syms_value else holdings_mv * 0.0
        other_mv = (holdings_mv - selected_mv)

        # ----------------------------
        # 2) CASH and deposits from XTB cash ops
        # ----------------------------
        raw_xtb = st.session_state.get("xtb_report_bytes", None)
        cash_eod = None
        deposits_cum = None
        deposit_daily = None

        if raw_xtb is not None:
            try:
                df_cash_all = _xtb_read_cash_ops(raw_xtb).copy()
                start_d = holdings_all.index.min()
                end_d = holdings_all.index.max()

                cash_daily_change = (
                    df_cash_all.groupby("Date", as_index=True)["Amount"]
                    .sum()
                    .sort_index()
                )
                full_idx = pd.date_range(cash_daily_change.index.min(), end_d, freq="D")
                cash_balance_full = cash_daily_change.reindex(full_idx, fill_value=0.0).cumsum()
                cash_eod = cash_balance_full.reindex(holdings_all.index, method="ffill").fillna(0.0)

                df_cash_range = df_cash_all[(df_cash_all["Date"] >= start_d) & (df_cash_all["Date"] <= end_d)].copy()

                inflow_mask = (
                    df_cash_range["Type_norm"].isin(["deposit", "transfer"])
                    & (df_cash_range["Amount"] > 0)
                )
                deposit_daily = (
                    df_cash_range.loc[inflow_mask]
                    .groupby("Date", as_index=True)["Amount"]
                    .sum()
                    .reindex(holdings_all.index, fill_value=0.0)
                )
                deposits_cum = deposit_daily.cumsum()
                # "Kapitał wniesiony" = startowe equity + dopłaty od startu okresu
                # deposits_cum_anchored = portfolio_start_usd + deposits_cum


            except Exception as e:
                st.info(f"Could not compute cash/deposits from XTB report: {e}")

        if cash_eod is None:
            cash_eod = holdings_mv * 0.0
        if deposit_daily is None:
            deposit_daily = pd.Series(0.0, index=holdings_all.index)

        total_equity = holdings_mv + cash_eod
        portfolio_start_usd = float(total_equity.iloc[0]) if not total_equity.empty else 0.0

        deposits_cum_anchored = None
        if deposits_cum is not None:
            deposits_cum_anchored = deposits_cum + portfolio_start_usd

        # ----------------------------
        # 3) Chart with secondary axis
        # ----------------------------
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Primary axis: stacked areas in USD
        fig.add_trace(go.Scatter(
            x=total_equity.index, y=selected_mv.values,
            name="Selected holdings",
            mode="lines",
            stackgroup="one",
            hovertemplate="%{x|%Y-%m-%d}<br>Selected: %{y:,.2f} USD<extra></extra>"
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=total_equity.index, y=other_mv.values,
            name="Other holdings",
            mode="lines",
            stackgroup="one",
            hovertemplate="%{x|%Y-%m-%d}<br>Other: %{y:,.2f} USD<extra></extra>"
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=total_equity.index, y=cash_eod.values,
            name="Cash",
            mode="lines",
            stackgroup="one",
            hovertemplate="%{x|%Y-%m-%d}<br>Cash: %{y:,.2f} USD<extra></extra>"
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=total_equity.index, y=total_equity.values,
            name="Total equity (USD)",
            mode="lines",
            hovertemplate="%{x|%Y-%m-%d}<br>Total equity: %{y:,.2f} USD<extra></extra>"
        ), secondary_y=False)

        if deposits_cum is not None:
            fig.add_trace(go.Scatter(
                x=deposits_cum.index, y=deposits_cum.values,
                name="Cumulative deposits (USD)",
                mode="lines",
                hovertemplate="%{x|%Y-%m-%d}<br>Deposits cum: %{y:,.2f} USD<extra></extra>"
            ), secondary_y=False)

        if deposits_cum is not None:
            fig.add_trace(go.Scatter(
                x=deposits_cum_anchored.index,
                y=deposits_cum_anchored.values,
                name="Start equity + deposits (capital contributed)",
                mode="lines",
                hovertemplate="%{x|%Y-%m-%d}<br>Contributed capital: %{y:,.2f} USD<extra></extra>"
            ), secondary_y=False)

        # ----------------------------
        # 4) Benchmarks
        # ----------------------------
        chart_start = total_equity.index.min().normalize()
        chart_end = total_equity.index.max().normalize()
        start_iso = chart_start.strftime("%Y-%m-%d")
        end_iso = chart_end.strftime("%Y-%m-%d")

        # Portfolio normalized (only in %/100 modes)
        if show_portfolio_norm and base_mode in ["0% = start", "100 = start"]:
            port_norm = _normalize_series(total_equity.copy(), base_mode)
            port_norm = port_norm.reindex(total_equity.index).ffill().bfill()
            fig.add_trace(go.Scatter(
                x=port_norm.index, y=port_norm.values,
                name="Portfolio (normalized)",
                mode="lines",
                hovertemplate="%{x|%Y-%m-%d}<br>Portfolio: %{y:.2f}<extra></extra>"
            ), secondary_y=True)

        # Benchmark lines
        fallback_notes: list[str] = []
        error_notes: list[str] = []
        source_name = {
            "stooq": "Stooq",
            "yfinance": "Yahoo Finance",
            "sp500_db": "S&P 500 DB",
            "none": "no source",
        }

        for bench_name in bench_selected:
            stooq_sym = bench_catalog[bench_name]["stooq"]
            yf_sym = bench_catalog[bench_name]["yfinance"]
            try:
                s_price, source_used, load_errors = load_benchmark_close_series(
                    preferred_source=bench_source_key,
                    stooq_symbol=stooq_sym,
                    yfinance_symbol=yf_sym,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    allow_sp500_db_fallback=(bench_name == "S&P 500"),
                )
                if s_price is None or s_price.empty:
                    if load_errors:
                        error_notes.append(
                            f"{bench_name}: failed to load benchmark ({' | '.join(load_errors)})"
                        )
                    continue
                if source_used != bench_source_key:
                    fallback_notes.append(
                        f"{bench_name}: using {source_name.get(source_used, source_used)} fallback "
                        f"(preferred: {source_name.get(bench_source_key, bench_source_key)})."
                    )

                s_price = s_price.reindex(total_equity.index).ffill().bfill()

                if base_mode == "DCA deposits into benchmark (USD)":
                    dca_usd = _dca_value_from_deposits(s_price, deposit_daily, initial_usd=0.0)
                    fig.add_trace(go.Scatter(
                        x=dca_usd.index, y=dca_usd.values,
                        name=f"{bench_name} (DCA deposits)",
                        mode="lines",
                        hovertemplate="%{x|%Y-%m-%d}<br>" + bench_name + " DCA: %{y:,.2f} USD<extra></extra>"
                    ), secondary_y=False)

                elif base_mode == "Switch portfolio to benchmark + DCA (USD)":
                    dca_full_usd = _dca_value_from_deposits(s_price, deposit_daily, initial_usd=portfolio_start_usd)
                    fig.add_trace(go.Scatter(
                        x=dca_full_usd.index, y=dca_full_usd.values,
                        name=f"{bench_name} (switch + DCA)",
                        mode="lines",
                        hovertemplate="%{x|%Y-%m-%d}<br>" + bench_name + " switch+DCA: %{y:,.2f} USD<extra></extra>"
                    ), secondary_y=False)

                elif base_mode == "Match portfolio start (USD)":
                    s_usd = _anchor_to_portfolio_usd(s_price, portfolio_start_usd)
                    s_usd = s_usd.reindex(total_equity.index).ffill().bfill()
                    fig.add_trace(go.Scatter(
                        x=s_usd.index, y=s_usd.values,
                        name=f"{bench_name} (anchored USD)",
                        mode="lines",
                        hovertemplate="%{x|%Y-%m-%d}<br>" + bench_name + ": %{y:,.2f} USD<extra></extra>"
                    ), secondary_y=False)

                else:
                    s_norm = _normalize_series(s_price, base_mode)
                    s_norm = s_norm.reindex(total_equity.index).ffill().bfill()
                    fig.add_trace(go.Scatter(
                        x=s_norm.index, y=s_norm.values,
                        name=f"{bench_name} (norm)",
                        mode="lines",
                        hovertemplate="%{x|%Y-%m-%d}<br>" + bench_name + ": %{y:.2f}<extra></extra>"
                    ), secondary_y=True)

            except Exception as exc:
                error_notes.append(f"{bench_name}: failed to render benchmark ({exc})")
                continue

        for msg in sorted(set(fallback_notes)):
            st.info(msg)
        for msg in sorted(set(error_notes)):
            st.warning(msg)

        # ----------------------------
        # Layout
        # ----------------------------
        fig.update_layout(
            height=650,
            hovermode="x unified",
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            margin=dict(t=30, r=140)
        )
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Value (USD)", secondary_y=False)

        if base_mode in ["0% = start", "100 = start"]:
            y2_title = "% change since start" if base_mode == "0% = start" else "Normalized (100 = start)"
            fig.update_yaxes(title_text=y2_title, secondary_y=True, showgrid=False)
        else:
            fig.update_yaxes(title_text="", secondary_y=True, showgrid=False, showticklabels=False)

        st.caption("Tip: Double-click a legend item to isolate it, or double-click again to show all.")
        st.plotly_chart(fig, use_container_width=True)

        # ------------------------------------------------------------
        # Performance metrics vs benchmark (Switch + DCA mode) [FIXED: TWR]
        # ------------------------------------------------------------
        if base_mode == "Switch portfolio to benchmark + DCA (USD)" and bench_selected:
            try:
                bn = bench_selected[0]
                stooq_sym = bench_catalog[bn]["stooq"]
                yf_sym = bench_catalog[bn]["yfinance"]

                # price series
                s_price, source_used_metrics, load_errors_metrics = load_benchmark_close_series(
                    preferred_source=bench_source_key,
                    stooq_symbol=stooq_sym,
                    yfinance_symbol=yf_sym,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    allow_sp500_db_fallback=(bn == "S&P 500"),
                )
                if s_price is None or s_price.empty:
                    details = " | ".join(load_errors_metrics) if load_errors_metrics else "empty series"
                    st.warning(f"{bn}: benchmark series unavailable for metrics ({details}).")
                    raise RuntimeError(f"Missing benchmark series for {bn}")
                if source_used_metrics != bench_source_key:
                    source_name_metrics = {
                        "stooq": "Stooq",
                        "yfinance": "Yahoo Finance",
                        "sp500_db": "S&P 500 DB",
                    }
                    st.info(
                        f"{bn}: metrics calculated with {source_name_metrics.get(source_used_metrics, source_used_metrics)} "
                        f"fallback (preferred: {source_name_metrics.get(bench_source_key, bench_source_key)})."
                    )

                s_price = s_price.reindex(total_equity.index).ffill().bfill()

                # benchmark value series: initial = portfolio_start_usd, plus daily deposits
                dca_full_usd = _dca_value_from_deposits(
                    s_price,
                    deposit_daily,
                    initial_usd=portfolio_start_usd
                ).reindex(total_equity.index).ffill().bfill()

                # --- end values (as before) ---
                last_port = float(total_equity.iloc[-1])
                last_bench = float(dca_full_usd.iloc[-1])
                delta = last_port - last_bench
                delta_pct = (delta / last_bench * 100.0) if last_bench > 0 else np.nan

                c1, c2, c3 = st.columns(3)
                c1.metric("Portfolio total equity (end)", f"{last_port:,.2f} USD")
                c2.metric(f"{bn} switch + DCA (end)", f"{last_bench:,.2f} USD")
                c3.metric("Difference (Portfolio - Benchmark)", f"{delta:,.2f} USD",
                          delta=(f"{delta_pct:+.2f}%" if np.isfinite(delta_pct) else None))

                # --------------------------------------------------------
                # Build daily external flows (Deposit + Transfer + Withdrawal)
                # CF positive = money into account (end-of-day assumption)
                # --------------------------------------------------------
                raw_xtb = st.session_state.get("xtb_report_bytes", None)
                if raw_xtb is None:
                    st.info("No XTB report bytes in session_state. Cannot compute flow-adjusted performance.")
                    raise RuntimeError("Missing XTB report")

                df_cash_all = _xtb_read_cash_ops(raw_xtb).copy()

                d0 = total_equity.index.min()
                d1 = total_equity.index.max()

                df_rng = df_cash_all[(df_cash_all["Date"] >= d0) & (df_cash_all["Date"] <= d1)].copy()
                # ext_types = ["deposit", "transfer", "withdrawal"]
                # ext = df_rng[df_rng["Type_norm"].isin(ext_types)].copy()
                #
                # # daily net external amount (positive = money into account)
                # cf_daily = (
                #     ext.groupby("Date", as_index=True)["Amount"]
                #     .sum()
                #     .reindex(total_equity.index, fill_value=0.0)
                #     .astype(float)
                # )
                # External flows definition:
                # - deposit: always
                # - withdrawal: always
                # - transfer: ONLY positive (transfer-in to USD)
                mask_ext = (
                        df_rng["Type_norm"].eq("deposit")
                        | df_rng["Type_norm"].eq("withdrawal")
                        | (df_rng["Type_norm"].eq("transfer") & (df_rng["Amount"] > 0))
                )

                ext = df_rng.loc[mask_ext].copy()

                cf_daily = (
                    ext.groupby("Date", as_index=True)["Amount"]
                    .sum()
                    .reindex(total_equity.index, fill_value=0.0)
                    .astype(float)
                )


                # --------------------------------------------------------
                # Flow-adjusted daily returns (Time-Weighted Return)
                # r_t = (E_t - CF_t)/E_{t-1} - 1
                # Assumption: CF_t happens at end of day t (matches your EOD equity series)
                # --------------------------------------------------------
                def _twr_returns(equity: pd.Series, cf: pd.Series) -> pd.Series:
                    e = equity.astype(float).copy()
                    f = cf.reindex(e.index).astype(float).fillna(0.0)
                    prev = e.shift(1)

                    r = (e - f) / prev - 1.0
                    r[(prev <= 0) | (~np.isfinite(r))] = np.nan
                    return r.dropna()


                port_eq = total_equity.astype(float)
                bench_eq = dca_full_usd.astype(float)

                port_ret = _twr_returns(port_eq, cf_daily)
                bench_ret = _twr_returns(bench_eq, cf_daily)

                # align
                aligned = pd.concat([port_ret.rename("p"), bench_ret.rename("b")], axis=1).dropna()
                p = aligned["p"]
                b = aligned["b"]
                active = p - b


                # --------------------------------------------------------
                # Return indices for drawdown and total return (TWR)
                # --------------------------------------------------------
                def _return_index(r: pd.Series) -> pd.Series:
                    return (1.0 + r).cumprod()


                def _max_drawdown_from_index(idx: pd.Series) -> float:
                    if idx.empty:
                        return np.nan
                    dd = idx / idx.cummax() - 1.0
                    return float(dd.min())


                port_idx = _return_index(p)
                bench_idx = _return_index(b)

                port_twr_total = float(port_idx.iloc[-1] - 1.0) if not port_idx.empty else np.nan
                bench_twr_total = float(bench_idx.iloc[-1] - 1.0) if not bench_idx.empty else np.nan
                active_total = float((1.0 + port_twr_total) / (1.0 + bench_twr_total) - 1.0) \
                    if np.isfinite(port_twr_total) and np.isfinite(bench_twr_total) and (
                            1.0 + bench_twr_total) != 0 else np.nan

                days = (aligned.index.max() - aligned.index.min()).days
                years = (days / 365.0) if days > 0 else np.nan


                def _cagr_from_total(total_return: float, years: float) -> float:
                    if not np.isfinite(total_return) or not np.isfinite(years) or years <= 0:
                        return np.nan
                    return (1.0 + total_return) ** (1.0 / years) - 1.0


                port_cagr = _cagr_from_total(port_twr_total, years)
                bench_cagr = _cagr_from_total(bench_twr_total, years)

                port_mdd = _max_drawdown_from_index(port_idx)
                bench_mdd = _max_drawdown_from_index(bench_idx)


                # --------------------------------------------------------
                # Risk metrics (based on flow-adjusted daily returns)
                # --------------------------------------------------------
                def _ann_vol(r: pd.Series) -> float:
                    return float(r.std(ddof=0) * np.sqrt(252)) if len(r) else np.nan


                def _sharpe(r: pd.Series, rf_annual: float) -> float:
                    if r.empty:
                        return np.nan
                    rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
                    ex = r - rf_daily
                    sd = ex.std(ddof=0)
                    return float((ex.mean() / sd) * np.sqrt(252)) if sd and np.isfinite(sd) else np.nan


                def _sortino(r: pd.Series, rf_annual: float) -> float:
                    if r.empty:
                        return np.nan
                    rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
                    ex = r - rf_daily
                    downside = ex[ex < 0]
                    dd = downside.std(ddof=0)
                    return float((ex.mean() / dd) * np.sqrt(252)) if dd and np.isfinite(dd) else np.nan


                tracking_err = _ann_vol(active)
                info_ratio = float((active.mean() / active.std(ddof=0)) * np.sqrt(252)) if active.std(
                    ddof=0) else np.nan
                win_rate = float((active > 0).mean() * 100.0) if len(active) else np.nan

                port_vol = _ann_vol(p)
                bench_vol = _ann_vol(b)

                # beta, alpha, corr (optional but useful)
                beta = np.nan
                alpha_ann = np.nan
                corr = np.nan
                if len(aligned) > 5 and np.isfinite(b.var(ddof=0)) and b.var(ddof=0) > 0:
                    beta = float(np.cov(p, b, ddof=0)[0, 1] / b.var(ddof=0))
                    alpha_daily = float(p.mean() - beta * b.mean())
                    alpha_ann = alpha_daily * 252.0
                    corr = float(np.corrcoef(p, b)[0, 1])

                # --------------------------------------------------------
                # XIRR (money-weighted) for both: portfolio vs benchmark
                # Use the same external flows but different end value
                # --------------------------------------------------------
                start_date = port_eq.index[0].date()
                end_date = port_eq.index[-1].date()


                def _build_xirr_flows(end_value: float):
                    flows = [(start_date, -float(port_eq.iloc[0]))]
                    for dt, amt in cf_daily.items():
                        if abs(float(amt)) < 1e-12:
                            continue
                        flows.append((dt.date(), -float(amt)))  # investor perspective
                    flows.append((end_date, +float(end_value)))
                    return flows


                port_xirr = _xirr(_build_xirr_flows(float(port_eq.iloc[-1])), guess=0.1)
                bench_xirr = _xirr(_build_xirr_flows(float(bench_eq.iloc[-1])), guess=0.1)

                # --------------------------------------------------------
                # Risk-free for Sharpe/Sortino
                # --------------------------------------------------------
                rf_pct = st.number_input(
                    "Risk-free rate (annual, %)",
                    min_value=0.0,
                    max_value=20.0,
                    value=0.0,
                    step=0.25,
                    key="perf_rf_pct"
                )
                rf_annual = rf_pct / 100.0

                port_sh = _sharpe(p, rf_annual)
                bench_sh = _sharpe(b, rf_annual)
                port_so = _sortino(p, rf_annual)
                bench_so = _sortino(b, rf_annual)

                # --------------------------------------------------------
                # Display
                # --------------------------------------------------------
                st.markdown("#### Performance vs benchmark (range)")

                r1, r2, r3 = st.columns(3)
                r1.metric("TWR total return (Portfolio)",
                          f"{port_twr_total * 100:.2f}%" if np.isfinite(port_twr_total) else "n/a")
                r2.metric(f"TWR total return ({bn})",
                          f"{bench_twr_total * 100:.2f}%" if np.isfinite(bench_twr_total) else "n/a")
                r3.metric("Active return (TWR)", f"{active_total * 100:.2f}%" if np.isfinite(active_total) else "n/a")

                r4, r5, r6 = st.columns(3)
                r4.metric("CAGR (Portfolio, TWR)", f"{port_cagr * 100:.2f}%" if np.isfinite(port_cagr) else "n/a")
                r5.metric(f"CAGR ({bn}, TWR)", f"{bench_cagr * 100:.2f}%" if np.isfinite(bench_cagr) else "n/a")
                r6.metric("Win rate (daily)", f"{win_rate:.1f}%" if np.isfinite(win_rate) else "n/a")

                r7, r8, r9 = st.columns(3)
                r7.metric("Max drawdown (Portfolio)", f"{port_mdd * 100:.2f}%" if np.isfinite(port_mdd) else "n/a")
                r8.metric(f"Max drawdown ({bn})", f"{bench_mdd * 100:.2f}%" if np.isfinite(bench_mdd) else "n/a")
                r9.metric("Tracking error (ann.)", f"{tracking_err * 100:.2f}%" if np.isfinite(tracking_err) else "n/a")

                r10, r11, r12 = st.columns(3)
                r10.metric("Volatility (ann.) Portfolio", f"{port_vol * 100:.2f}%" if np.isfinite(port_vol) else "n/a")
                r11.metric(f"Volatility (ann.) {bn}", f"{bench_vol * 100:.2f}%" if np.isfinite(bench_vol) else "n/a")
                r12.metric("Information ratio (ann.)", f"{info_ratio:.2f}" if np.isfinite(info_ratio) else "n/a")

                r13, r14, r15 = st.columns(3)
                r13.metric("Sharpe (Portfolio)", f"{port_sh:.2f}" if np.isfinite(port_sh) else "n/a")
                r14.metric(f"Sharpe ({bn})", f"{bench_sh:.2f}" if np.isfinite(bench_sh) else "n/a")
                r15.metric("Sortino (Portfolio)", f"{port_so:.2f}" if np.isfinite(port_so) else "n/a")

                r16, r17, r18 = st.columns(3)
                r16.metric(f"Sortino ({bn})", f"{bench_so:.2f}" if np.isfinite(bench_so) else "n/a")
                r17.metric("XIRR (Portfolio)", f"{port_xirr * 100:.2f}%" if port_xirr is not None else "n/a")
                r18.metric(f"XIRR ({bn} switch+DCA)", f"{bench_xirr * 100:.2f}%" if bench_xirr is not None else "n/a")

                r19, r20, r21 = st.columns(3)
                r19.metric("Beta (Portfolio vs bench)", f"{beta:.2f}" if np.isfinite(beta) else "n/a")
                r20.metric("Alpha (annual, approx)", f"{alpha_ann * 100:.2f}%" if np.isfinite(alpha_ann) else "n/a")
                r21.metric("Correlation", f"{corr:.2f}" if np.isfinite(corr) else "n/a")

                # Optional: keep the old equity growth for context (not performance)
                with st.expander("Equity growth (includes deposits) - context only"):
                    eq_growth_port = float(port_eq.iloc[-1] / port_eq.iloc[0] - 1.0) if float(
                        port_eq.iloc[0]) != 0 else np.nan
                    eq_growth_bench = float(bench_eq.iloc[-1] / bench_eq.iloc[0] - 1.0) if float(
                        bench_eq.iloc[0]) != 0 else np.nan
                    st.write(f"Portfolio equity growth: {eq_growth_port * 100:.2f}%")
                    st.write(f"{bn} equity growth: {eq_growth_bench * 100:.2f}%")

            except Exception as e:
                st.info(f"Performance metrics error: {e}")

# -----------------------------------------------------------
# CODE TO DISPLAY DIVIDEND TIMELINE
# -----------------------------------------------------------

# 1) First, compute net volume in user_df (if SELL is not yet negative).
df_portfolio_net = user_df.copy()

def volume_with_sign(row):
    """BUY => positive volume, SELL => negative volume."""
    if str(row["Type"]).upper() == "SELL":
        return -abs(float(str(row["Volume"]).replace(",", ".")))
    else:
        return abs(float(str(row["Volume"]).replace(",", ".")))

df_portfolio_net["Volume"] = df_portfolio_net.apply(volume_with_sign, axis=1)
df_portfolio_net = df_portfolio_net.groupby("Symbol", as_index=False).agg({"Volume": "sum"})
df_portfolio_net["Symbol"] = df_portfolio_net["Symbol"].str.upper()  # standardization

# 2) Prepare dividend history for the current portfolio
df_div_full = portfolio_history[[
    "Stock",
    "Dividend yield",
    "Ex-dividend date",
    "Dividend pay date"
]].copy()
df_div_full.dropna(subset=["Stock"], inplace=True)

# 3) Merge net volume with forecast entries
df_div = df_div_full.merge(
    df_portfolio_net,
    left_on="Stock",
    right_on="Symbol",
    how="inner"   # only stocks actually in the portfolio
)

# 4) Convert "Dividend yield" to float (accounting for commas, nulls, etc.)
df_div["Dividend yield"] = (
    df_div["Dividend yield"]
    .astype(str)
    .str.replace(",", ".")
    .astype(float, errors="ignore")
    .fillna(0)
)

# Set of all stocks in your portfolio:
all_portfolio_symbols = set(df_portfolio_net["Symbol"].unique())

# Set of stocks that have at least one row with dividend > 0:
stocks_with_positive_div = set(df_div.loc[df_div["Dividend yield"] > 0, "Stock"].unique())

# Difference = stocks in the portfolio that do not have any dividend > 0
no_div_stocks = list(all_portfolio_symbols - stocks_with_positive_div)
###

# 5) Filter only those with dividend > 0
df_div = df_div[df_div["Dividend yield"] > 0]
if df_div.empty:
    if no_div_stocks:
        st.write("Stocks in your portfolio with no dividend:", ", ".join(no_div_stocks))
else:
    # 6) Parse Ex-dividend date and Dividend pay date
    df_div["Ex-dividend date"] = pd.to_datetime(df_div["Ex-dividend date"], errors="coerce")
    df_div["Dividend pay date"] = pd.to_datetime(df_div["Dividend pay date"], errors="coerce")

    # Remove rows with missing Ex-div or Pay date
    df_div = df_div.dropna(subset=["Ex-dividend date", "Dividend pay date"])
    if df_div.empty:
        st.info("All ex/pay dividend dates are unknown. No data to display in the chart.")
        if no_div_stocks:
            st.write("Stocks with no dividend:", ", ".join(no_div_stocks))
    else:
        df_price_latest = portfolio_history_latest[["Stock", "Price"]].copy()

        df_div = df_div.merge(
            df_price_latest[["Stock", "Price"]],
            on="Stock",
            how="left"
        )

        # Convert from percentage (e.g. 3.15) to decimal (0.0315)
        df_div["Dividend yield"] = df_div["Dividend yield"] / 100.0
        df_div["Annual Dividend (est.)"] = (
            df_div["Volume"] * df_div["Price"].fillna(0) * df_div["Dividend yield"]
        )
        df_div["Annual Dividend (est.) USD"] = df_div["Annual Dividend (est.)"].apply(lambda x: f"{x:.2f} USD")

        st.markdown("---")
        st.header("Dividend Timeline")
        with performance_block("build_portfolio_dividend_timeline"):
            fig_timeline = px.timeline(
                df_div,
                x_start="Ex-dividend date",
                x_end="Dividend pay date",
                y="Stock",
                hover_data={
                    "Stock": True,
                    "Ex-dividend date": "|%Y-%m-%d",
                    "Dividend pay date": "|%Y-%m-%d",
                    "Volume": ":.2f",
                    "Dividend yield": ":.2%",
                    "Annual Dividend (est.) USD": True
                },
                color="Stock",
                title="Timeline: All Ex-Dividend & Dividend Pay Dates"
            )

            today = pd.Timestamp.now().floor("D")
            fig_timeline.update_xaxes(
                tickformat="%Y-%m-%d",
                range=[
                    today - pd.DateOffset(days=30),
                    today + pd.DateOffset(days=90)
                ]
            )
            fig_timeline.update_layout(
                xaxis=dict(title="Date"),
                yaxis=dict(title="Stock"),
                height=600,
                dragmode="pan",
                showlegend=False
            )
            fig_timeline.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
            fig_timeline.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
            fig_timeline.add_vline(
                x=today,
                line_width=2,
                line_dash="solid",
                line_color="rgba(255,255,255,0.9)"
            )


        if not df_div.empty:
            stock_dividends = df_div.groupby("Stock", as_index=False)["Annual Dividend (est.)"].first()
            total_annual_dividend = stock_dividends["Annual Dividend (est.)"].sum()

            # Calculate the dividend yield (%):
            # (total_annual_dividend / total_investment) * 100
            if total_investment > 0:
                dividend_yield_percent = (total_annual_dividend / total_investment) * 100
            else:
                dividend_yield_percent = 0.0

            # Display two metrics side by side:
            col1, col2 = st.columns(2)
            col1.metric("Estimated annual dividend from the current portfolio:", f"{total_annual_dividend:.2f} USD")
            col2.metric("Dividend relative to investment", f"{dividend_yield_percent:.2f}%",
                        help="Estimated yearly dividend yield of your portfolio. "
                             "Benchmark dividend yield of whole S&P 500 index is ~1.39%")


        st.plotly_chart(fig_timeline, use_container_width=True)

        # 10) Stocks in your portfolio with no dividend:
        if no_div_stocks:
            st.info("Stocks in your portfolio with no dividend: " + ", ".join(no_div_stocks))


# =====================================================================
#  NEW SECTION – Sell / Hold signals + Raw Strength
# =====================================================================
st.markdown("---")
st.header("Portfolio signals")

# ──────────────────────────────────────────────────────────────
# PORTFOLIO HEALTH  – portfolio vs today's top‑N screener picks
# + BENCHMARK SCORE – portfolio vs whole S&P 500
# ──────────────────────────────────────────────────────────────
# 1) How many unique tickers in the current portfolio?
n_portfolio = len(portfolio_tickers)

cols_needed = [
    "Stock", "Sector", "Price",
    "Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent",
    "Smart Score", "Score"
]
med_median = filtered_data["Median Forecast Percent"].median()

if n_portfolio and all(c in filtered_data.columns for c in cols_needed):
    screener = (
        filtered_data[cols_needed]
        .copy()
        .sort_values("Score", ascending=False, ignore_index=True)
    )
    screener = screener[
        (screener["Smart Score"] > 7) &
        (screener["Score"] > 2) &
        (screener["Low Forecast Percent"] > -5) &
        (screener["Score"] < 6)
    ]
    topN = screener.head(n_portfolio)

    if not topN.empty and not merged.empty and "med_median" in globals():
        # value‑weighted median forecast for portfolio
        wa_median_port = wa_median      # already computed earlier

        # plain median forecast for today’s top‑N picks
        topN_median = (
            topN["Median Forecast Percent"]
            .astype(str).str.replace(",", ".").astype(float, errors="ignore")
            .median()
        )

        # plain median forecast for the whole index (computed earlier)
        sp500_median = med_median       # comes from the S&P‑500 section

        # ── scores ────────────────────────────────────────────
        health_score    = wa_median_port - topN_median      # portfolio vs top‑N
        benchmark_score = wa_median_port - sp500_median     # portfolio vs S&P500

        # ── display side‑by‑side ─────────────────────────────
        col_h, col_b = st.columns(2)

        col_h.metric(
            label="Portfolio Health",
            value=f"{health_score:+.2f} pp",
            help=(
                "Difference between your portfolio’s value-weighted 12-month median forecast "
                f"and the median forecast of the first {n_portfolio} equally weighted screener picks. "
                "A negative value is common, but ideally this score should be as close to zero as possible."
            )
        )

        col_b.metric(
            label="Benchmark Score (vs S&P 500)",
            value=f"{benchmark_score:+.2f} pp",
            help=(
                "Difference between your portfolio’s value-weighted 12-month median forecast "
                "and the S&P 500’s median forecast for the same date. "
                "A positive score means your portfolio is expected to outperform the S&P 500 "
                "by that many percentage points."
            )
        )

with st.expander("Quick guide to signals and strength values"):
    st.markdown("""
    • **Hold/Buy More:** % distance below the Low Forecast (higher % = deeper undervaluation and more upside = potential higher return)  
    • **Sell:** % of the way from Low → Median Forecast  
    • **Strong Sell:** % of the way from Median → High Forecast  
    • **Very Strong Sell:** % by which the price exceeds the High Forecast  
    """)


if scoring.empty:
    st.info("No forecasts available for the stocks in your portfolio – unable to generate signals.")
else:
    # ----------------------------------------------------------
    # 1) Konwersje numeryczne
    # ----------------------------------------------------------
    needed = ["Price", "Low Forecast", "Median Forecast", "High Forecast"]
    missing = [c for c in needed if c not in scoring.columns]
    if missing:
        st.error("Brak kolumn prognoz: " + ", ".join(missing))
    else:
        scoring[needed] = (
            scoring[needed]
            .apply(lambda s: s.astype(str).str.replace(",", ".").astype(float, errors="ignore"))
        )

        # ------------------------------------------------------
        # 2) Funkcje pomocnicze
        # ------------------------------------------------------
        def decide_signal(r):
            p, lo, med, hi = r["Price"], r["Low Forecast"], r["Median Forecast"], r["High Forecast"]
            if pd.isna(p) or pd.isna(lo) or pd.isna(med) or pd.isna(hi):
                return "no data"
            if p >= hi:
                return "very strong sell"
            elif p >= med:
                return "strong sell"
            elif p >= lo:
                return "sell"
            else:
                return "hold"

        def raw_strength(r) -> float:
            p, lo, med, hi = r["Price"], r["Low Forecast"], r["Median Forecast"], r["High Forecast"]
            if pd.isna(p) or pd.isna(lo) or pd.isna(med) or pd.isna(hi):
                return 0.0
            if p < lo:                # hold
                return (lo - p) / lo * 100
            elif p < med:             # sell
                return (p - lo) / (med - lo) * 100
            elif p < hi:              # strong sell
                return (p - med) / (hi - med) * 100
            else:                     # very strong sell
                return (p - hi) / hi * 100

        # ------------------------------------------------------
        # 3) Obliczenia
        # ------------------------------------------------------
        scoring["Signal"]           = scoring.apply(decide_signal, axis=1)
        scoring["Strength ( in %)"] = scoring.apply(raw_strength, axis=1).round(1)

        # ranking do sortowania
        signal_rank = {
            "hold": 0,
            "sell": 1,
            "strong sell": 2,
            "very strong sell": 3,
            "no data": 4
        }

        table = (
            scoring[["Stock", "Signal", "Strength ( in %)"]]
            .rename(columns={"Stock": "Ticker"})
            .assign(_rank=scoring["Signal"].map(signal_rank))
            .sort_values(["_rank", "Strength ( in %)"], ascending=[True, False])
            .drop(columns="_rank")
            .reset_index(drop=True)
        )

        # ------------------------------------------------------
        # 4) Kolorowanie
        # ------------------------------------------------------
        def color_signal(val):
            palette = {
                "hold":              "#009e73",
                "sell":              "#ffbf00",
                "strong sell":       "#ff8000",
                "very strong sell":  "#d62728",
                "no data":           "#7f7f7f",
            }
            return f"background-color:{palette.get(val, '#000')};color:white"


        def color_strength(val):
            # 1) Ograniczamy raw_strength do zakresu 0–200
            cap = min(max(val, 0), 200)
            # 2) Mapujemy 0–200 → 1–100
            #    norm = cap/200*99 + 1
            norm = cap / 90 * 99 + 1
            # 3) Teraz norm ∈ [1,100]. Zamieniamy na hue: 1→hue=120 (zielony), 100→hue=0 (czerwony)
            hue = (1 - norm / 100) * 120
            # 4) Generujemy kolor w HSL
            return f"background-color: hsl({hue:.0f}, 65%, 50%); color: white"


        styled = (
            table
            .style
            .applymap(color_signal,   subset=["Signal"])
            .applymap(color_strength, subset=["Strength ( in %)"])
            .format({"Strength ( in %)": "{:.2f} %"})
            .set_table_styles([
                {"selector": "thead th:nth-child(1), tbody th:nth-child(1)",
                 "props": [("display", "none")]},
                {"selector": "table", "props": [("width", "100%")]},
            ])
        )

        signals = ["hold", "sell", "strong sell", "very strong sell"]
        labels = {
            "hold": "Hold/Buy More",
            "sell": "Sell",
            "strong sell": "Strong Sell",
            "very strong sell": "Very Strong Sell",
        }

        # podziel tabelę na cztery pod-ramki
        dfs = {sig: table[table["Signal"] == sig] for sig in signals}

        # wybieramy tylko te sygnały, które mają co wyświetlać
        non_empty = [sig for sig in signals if not dfs[sig].empty]

        if not non_empty:
            st.info("Brak sygnałów do wyświetlenia.")
        else:
            cols = st.columns(len(non_empty), gap="small")
            for col, sig in zip(cols, non_empty):
                df_sig = (
                    dfs[sig]
                    .reset_index(drop=True)[["Ticker", "Strength ( in %)"]]
                )
                # nagłówek kolumny
                col.subheader(labels[sig])
                # przygotowujemy styl by ukryć index, rozciągnąć tabelę i pofarbować Strength
                styled = (
                    df_sig.style
                    # kolorowanie Strength według funkcji
                    .applymap(color_strength, subset=["Strength ( in %)"])
                    # formatowanie wyświetlania
                    .format({"Strength ( in %)": "{:.2f} %"})
                    # CSS: ukrywamy pierwszy th i td (indeks) oraz wymuszamy pełną szerokość
                    .set_table_styles([
                        {
                            "selector": "thead th:nth-child(1), tbody th:nth-child(1)",
                            "props": [("display", "none")]
                        },
                        {
                            "selector": "table",
                            "props": [("width", "100%")]
                        },
                    ])
                )
                # renderujemy
                col.markdown(styled.to_html(), unsafe_allow_html=True)



st.markdown("<hr>", unsafe_allow_html=True)


# ============================
#  CORRELATION MAP (portfolio) — with ordering
# ============================
st.header("Correlation map (portfolio)")

# 0) Zbierz tickery z aktualnego portfolio (netto != 0)
_port = st.session_state.get("user_portfolio_df", pd.DataFrame()).copy()
if _port.empty:
    st.info("Add some tickers to your portfolio first.")
else:
    _port["Symbol"] = _port["Symbol"].astype(str).str.upper()
    _port["__signed"] = _port.apply(
        lambda r: float(str(r["Volume"]).replace(",", ".") or 0.0) * (1 if str(r["Type"]).upper() == "BUY" else -1),
        axis=1
    )
    net = (
        _port.groupby("Symbol", as_index=False)["__signed"].sum()
             .rename(columns={"__signed": "NetVolume"})
    )
    tickers = net.loc[net["NetVolume"].abs() > 0, "Symbol"].tolist()

    if len(tickers) < 2:
        st.info("Need at least two tickers with non-zero net volume.")
    else:
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            window_rows = st.selectbox(
                "Window (last N trading rows)",
                [60, 120, 250],
                index=1
            )
        with row1_col2:
            ret_kind = st.selectbox(
                "Returns",
                ["Percent (pct_change)", "Log (diff of log)"],
                index=0
            )

        # Czy jest scipy? (opcjonalny tryb hierarchiczny)
        try:
            import scipy.cluster.hierarchy as sch

            have_scipy = True
        except Exception:
            have_scipy = False

        order_options = ["Original", "Cluster similar (spectral)"]
        if have_scipy:
            order_options.append("Cluster similar (hierarchical)")

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            corr_kind = st.selectbox(
                "Correlation",
                ["Pearson", "Spearman", "Kendall", "Up/Down (sign Pearson)"],
                index=0
            )
        with row2_col2:
            order_mode = st.selectbox(
                "Order heatmap",
                order_options,
                index=1 if "Cluster similar (spectral)" in order_options else 0
            )

        df_daily_last = portfolio_history_daily_last.copy()
        wide = (
            df_daily_last
            .pivot(index="Date of record", columns="Stock", values="Price")
            .sort_index()
        )

        # Tylko tickery z portfela i wszystkie obecne w danych
        present = [t for t in tickers if t in wide.columns]
        if len(present) < 2:
            st.warning("Not enough overlapping tickers found in your historical dataset.")
        else:
            wide = wide[present].ffill().dropna(how="any")
            if len(wide) > window_rows:
                wide = wide.iloc[-window_rows:]

            if wide.shape[0] < 5:
                st.warning("Not enough rows to compute stable correlations (need at least ~5).")
            else:
                # 3) Zwroty
                if "Log" in ret_kind:
                    rets = np.log(wide).diff().dropna(how="any")
                else:
                    rets = wide.pct_change().dropna(how="any")

                # 4) Korelacja
                if corr_kind == "Pearson":
                    C = rets.corr(method="pearson")
                elif corr_kind == "Spearman":
                    C = rets.corr(method="spearman")
                elif corr_kind == "Kendall":
                    C = rets.corr(method="kendall")
                else:
                    S = np.sign(rets.replace([np.inf, -np.inf], np.nan)).fillna(0.0)
                    C = S.corr(method="pearson")

                # 5) PORZĄDKOWANIE (klastrowanie podobnych)
                labels = C.columns.tolist()

                def spectral_order(corr_df: pd.DataFrame) -> list[str]:
                    """Prosty porządek „klastrowy” bez zależności: sortujemy po wektorze własnym
                    z największą wartością własną macierzy korelacji."""
                    M = corr_df.fillna(0).values
                    M = (M + M.T) / 2.0  # symetryzacja na wszelki
                    # minimalna regularyzacja, żeby uniknąć degeneracji
                    w, v = np.linalg.eigh(M + 1e-8 * np.eye(M.shape[0]))
                    vec = v[:, -1]  # eigenvector dla największej wartości własnej
                    idx = np.argsort(vec)  # lub np.argsort(-vec); kierunek nieistotny
                    return [corr_df.index[i] for i in idx]

                if order_mode == "Cluster similar (spectral)":
                    labels = spectral_order(C)
                    C = C.loc[labels, labels]
                elif order_mode == "Cluster similar (hierarchical)" and have_scipy:
                    # dystans = 1 - korelacja (obcinamy do [0,2])
                    D = 1 - C.fillna(0).values
                    D = np.clip(D, 0, 2)
                    # linkage na spłaszczonej macierzy odległości
                    Z = sch.linkage(sch.distance.squareform(D, checks=False), method="average")
                    leaf_order = sch.leaves_list(Z)
                    labels = [C.index[i] for i in leaf_order]
                    C = C.loc[labels, labels]
                # „Original” – zostawiamy bez zmian

                # 6) Heatmapa
                st.subheader("Correlation heatmap")
                with performance_block("build_portfolio_correlation_heatmap"):
                    fig_hm = px.imshow(
                        C,
                        zmin=-1, zmax=1,
                        color_continuous_scale="RdBu_r",
                        aspect="auto",
                        labels=dict(color="corr"),
                        title=f"{corr_kind} on {ret_kind.split()[0].lower()} returns · last {len(wide)} rows",
                        text_auto=False,
                    )
                    fig_hm.update_layout(margin=dict(t=40, r=10, b=10, l=10), height=520)
                st.plotly_chart(fig_hm, use_container_width=True)

                # 7) Top neg/pos pary (na nieuporządkowanej wartości C — to bez znaczenia dla zestawienia)
                pairs = []
                cols = C.columns.tolist()
                for i in range(len(cols)):
                    for j in range(i+1, len(cols)):
                        pairs.append((cols[i], cols[j], C.iloc[i, j]))
                pairs_sorted = sorted(pairs, key=lambda x: x[2])

                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**Most negative correlations**")
                    st.table(pd.DataFrame(pairs_sorted[:10], columns=["A", "B", "corr"]))
                with col_right:
                    st.markdown("**Most positive correlations**")
                    st.table(pd.DataFrame(pairs_sorted[-10:][::-1], columns=["A", "B", "corr"]))

# ============================
#  PORTFOLIO PROMPT BUILDER (PL+EN, Hybrid JSON payload)
# ============================

def _to_num_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "."), errors="coerce")


def _float_or_none(value, digits: int = 4):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _iso_date_or_none(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date().isoformat()


def _clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def _resolve_groq_api_key() -> str:
    candidates = [
        st.secrets.get("GROQ_API_KEY"),
        st.secrets.get("groq_api_key"),
    ]
    cfg = st.secrets.get("groq", {})
    if isinstance(cfg, dict) or hasattr(cfg, "get"):
        candidates.extend(
            [
                cfg.get("GROQ_API_KEY"),
                cfg.get("groq_api_key"),
                cfg.get("api_key"),
                cfg.get("key"),
            ]
        )
    for value in candidates:
        if value is None:
            continue
        txt = str(value).strip()
        if txt:
            return txt
    return ""


def _resolve_groq_model() -> str:
    cfg = st.secrets.get("groq", {})
    if isinstance(cfg, dict) or hasattr(cfg, "get"):
        model = str(cfg.get("model") or "").strip()
        if model:
            return model
    return "llama-3.3-70b-versatile"


def _valuation_band(price, low, median, high) -> str | None:
    if any(pd.isna(v) for v in [price, low, median, high]):
        return None
    if price < low:
        return "below_low"
    if price <= median:
        return "low_to_median"
    if price <= high:
        return "median_to_high"
    return "above_high"


def _build_portfolio_prompt_payload(
    portfolio_df_input: pd.DataFrame,
    filtered_data_input: pd.DataFrame,
    selected_date_input,
    total_investment_est: float | int | None,
    total_current_value_est: float | int | None,
) -> dict:
    payload_base = {
        "meta": {
            "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "selected_date": selected_date_input.isoformat() if hasattr(selected_date_input, "isoformat") else str(selected_date_input),
            "data_source": [
                "session.user_portfolio_df (uploaded XTB/CSV/manual positions)",
                "market.view_portfolio_forecaster_day_snapshot (or fallback base query)",
            ],
            "prompt_format": "hybrid_markdown_plus_json",
            "language_mode": "PL+EN",
        },
        "portfolio_summary": {
            "positions_count": 0,
            "total_cost_est": _float_or_none(total_investment_est, 2),
            "total_current_value_est": _float_or_none(total_current_value_est, 2),
            "unrealized_pnl_est": None,
            "unrealized_pnl_pct_est": None,
            "top_concentration": [],
            "sector_allocation": [],
        },
        "positions": [],
        "data_quality": {
            "issues": [],
            "missing_open_time_tickers": [],
            "missing_forecast_tickers": [],
            "missing_pe_ratio_tickers": [],
        },
    }

    if payload_base["portfolio_summary"]["total_cost_est"] is not None and payload_base["portfolio_summary"]["total_current_value_est"] is not None:
        pnl = payload_base["portfolio_summary"]["total_current_value_est"] - payload_base["portfolio_summary"]["total_cost_est"]
        payload_base["portfolio_summary"]["unrealized_pnl_est"] = round(pnl, 2)
        if payload_base["portfolio_summary"]["total_cost_est"] != 0:
            payload_base["portfolio_summary"]["unrealized_pnl_pct_est"] = round(
                100.0 * pnl / payload_base["portfolio_summary"]["total_cost_est"], 2
            )

    if portfolio_df_input.empty:
        payload_base["data_quality"]["issues"].append("Portfolio is empty.")
        return payload_base

    p = portfolio_df_input.copy()
    p["Symbol"] = p["Symbol"].astype(str).str.strip().str.upper().str.replace(r"\.US$", "", regex=True)
    p["Type"] = p["Type"].astype(str).str.strip().str.upper()
    p["Volume"] = _to_num_series(p["Volume"]).fillna(0.0)
    p["Open price"] = _to_num_series(p["Open price"]).fillna(0.0)
    p["Open time parsed"] = pd.to_datetime(p.get("Open time"), errors="coerce", dayfirst=True)
    p["NetVolume"] = p.apply(lambda r: r["Volume"] if r["Type"] == "BUY" else -abs(r["Volume"]), axis=1)

    pos = p.groupby("Symbol", as_index=False).agg({"NetVolume": "sum"})
    pos = pos[pos["NetVolume"].abs() > 0].copy()
    if pos.empty:
        payload_base["data_quality"]["issues"].append("All positions net to zero.")
        return payload_base

    buys = p[p["Type"] == "BUY"].copy()
    if not buys.empty:
        buy_agg = buys.groupby("Symbol", as_index=False).agg(
            buy_volume=("Volume", "sum"),
            buy_cost=("Open price", lambda s: float((s * buys.loc[s.index, "Volume"]).sum())),
        )
        buy_agg["avg_open_price"] = buy_agg.apply(
            lambda r: (r["buy_cost"] / r["buy_volume"]) if r["buy_volume"] else np.nan, axis=1
        )
        buy_dates = buys.groupby("Symbol", as_index=False).agg(
            first_buy_date=("Open time parsed", "min"),
            last_buy_date=("Open time parsed", "max"),
        )
    else:
        buy_agg = pd.DataFrame(columns=["Symbol", "avg_open_price"])
        buy_dates = pd.DataFrame(columns=["Symbol", "first_buy_date", "last_buy_date"])

    uni = filtered_data_input.copy() if not filtered_data_input.empty else pd.DataFrame(columns=["Stock"])
    if not uni.empty and "Stock" in uni.columns:
        uni["Stock"] = uni["Stock"].astype(str).str.strip().str.upper()
        numeric_cols = [
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
        for col in numeric_cols:
            if col in uni.columns:
                uni[col] = _to_num_series(uni[col])
        if "Date of record" in uni.columns:
            uni = uni.sort_values(["Stock", "Date of record"]).groupby("Stock", as_index=False).last()
        else:
            uni = uni.sort_values(["Stock"]).groupby("Stock", as_index=False).last()

    merged = pos.merge(uni, left_on="Symbol", right_on="Stock", how="left")
    merged = merged.merge(buy_agg[["Symbol", "avg_open_price"]], on="Symbol", how="left")
    merged = merged.merge(buy_dates, on="Symbol", how="left")

    merged["position_value_est"] = merged["NetVolume"] * merged.get("Price", np.nan)
    total_abs = merged["position_value_est"].abs().sum(skipna=True)
    if total_abs and np.isfinite(total_abs):
        merged["weight_pct"] = (merged["position_value_est"].abs() / total_abs) * 100.0
    else:
        merged["weight_pct"] = np.nan

    merged["pct_to_median"] = ((merged.get("Median Forecast", np.nan) - merged.get("Price", np.nan)) / merged.get("Median Forecast", np.nan)) * 100.0
    merged["pct_to_low"] = ((merged.get("Low Forecast", np.nan) - merged.get("Price", np.nan)) / merged.get("Low Forecast", np.nan)) * 100.0
    merged["pct_above_high"] = ((merged.get("Price", np.nan) - merged.get("High Forecast", np.nan)) / merged.get("High Forecast", np.nan)) * 100.0

    selected_ts = pd.Timestamp(selected_date_input)
    positions_payload = []
    missing_open_time = []
    missing_forecast = []
    missing_pe = []

    for _, row in merged.sort_values("Symbol").iterrows():
        ticker = str(row["Symbol"])
        first_buy = row.get("first_buy_date")
        last_buy = row.get("last_buy_date")
        days_held = None
        if pd.notna(first_buy):
            days_held = int((selected_ts.normalize() - pd.Timestamp(first_buy).normalize()).days)

        if pd.isna(first_buy):
            missing_open_time.append(ticker)

        if any(pd.isna(row.get(c)) for c in ["Price", "Low Forecast", "Median Forecast", "High Forecast"]):
            missing_forecast.append(ticker)

        if pd.isna(row.get("P/E ratio")):
            missing_pe.append(ticker)

        positions_payload.append(
            {
                "ticker": ticker,
                "sector": None if pd.isna(row.get("Sector")) else str(row.get("Sector")),
                "net_volume": _float_or_none(row.get("NetVolume"), 6),
                "avg_open_price": _float_or_none(row.get("avg_open_price"), 4),
                "current_price": _float_or_none(row.get("Price"), 4),
                "position_value_est": _float_or_none(row.get("position_value_est"), 2),
                "weight_pct": _float_or_none(row.get("weight_pct"), 2),
                "first_buy_date": _iso_date_or_none(first_buy),
                "last_buy_date": _iso_date_or_none(last_buy),
                "days_held": days_held,
                "forecast": {
                    "low": _float_or_none(row.get("Low Forecast"), 4),
                    "median": _float_or_none(row.get("Median Forecast"), 4),
                    "high": _float_or_none(row.get("High Forecast"), 4),
                    "low_percent": _float_or_none(row.get("Low Forecast Percent"), 2),
                    "median_percent": _float_or_none(row.get("Median Forecast Percent"), 2),
                    "high_percent": _float_or_none(row.get("High Forecast Percent"), 2),
                },
                "scores": {
                    "smart_score": _float_or_none(row.get("Smart Score"), 2),
                    "score": _float_or_none(row.get("Score"), 2),
                    "pe_ratio": _float_or_none(row.get("P/E ratio"), 4),
                    "analysts_count": _float_or_none(row.get("Number of analysts"), 0),
                },
                "derived_signals": {
                    "valuation_band": _valuation_band(
                        row.get("Price"), row.get("Low Forecast"), row.get("Median Forecast"), row.get("High Forecast")
                    ),
                    "pct_to_median": _float_or_none(row.get("pct_to_median"), 2),
                    "pct_to_low": _float_or_none(row.get("pct_to_low"), 2),
                    "pct_above_high": _float_or_none(row.get("pct_above_high"), 2),
                },
            }
        )

    payload_base["positions"] = positions_payload
    payload_base["portfolio_summary"]["positions_count"] = len(positions_payload)

    top_conc = (
        merged[["Symbol", "weight_pct", "position_value_est"]]
        .dropna(subset=["weight_pct"])
        .sort_values("weight_pct", ascending=False)
        .head(3)
    )
    payload_base["portfolio_summary"]["top_concentration"] = [
        {
            "ticker": str(r["Symbol"]),
            "weight_pct": _float_or_none(r["weight_pct"], 2),
            "position_value_est": _float_or_none(r["position_value_est"], 2),
        }
        for _, r in top_conc.iterrows()
    ]

    sec = merged.copy()
    sec["sector_label"] = sec.get("Sector", pd.Series(index=sec.index, dtype=object)).fillna("Unknown")
    sec["abs_value"] = sec["position_value_est"].abs()
    sec_alloc = sec.groupby("sector_label", as_index=False)["abs_value"].sum()
    total_sec = sec_alloc["abs_value"].sum()
    if total_sec and np.isfinite(total_sec):
        sec_alloc["weight_pct"] = (sec_alloc["abs_value"] / total_sec) * 100.0
    payload_base["portfolio_summary"]["sector_allocation"] = [
        {"sector": str(r["sector_label"]), "weight_pct": _float_or_none(r["weight_pct"], 2)}
        for _, r in sec_alloc.sort_values("weight_pct", ascending=False).iterrows()
    ]

    payload_base["data_quality"]["missing_open_time_tickers"] = sorted(set(missing_open_time))
    payload_base["data_quality"]["missing_forecast_tickers"] = sorted(set(missing_forecast))
    payload_base["data_quality"]["missing_pe_ratio_tickers"] = sorted(set(missing_pe))

    if missing_open_time:
        payload_base["data_quality"]["issues"].append("Some tickers have missing/invalid Open time; holding period may be null.")
    if missing_forecast:
        payload_base["data_quality"]["issues"].append("Some tickers have missing price/forecast fields in current snapshot.")
    if missing_pe:
        payload_base["data_quality"]["issues"].append("Some tickers have missing P/E ratio.")

    return _clean_for_json(payload_base)


def _build_hybrid_prompt_pl(payload: dict, extra_questions: str | None = None) -> str:
    instructions = """
## Prompt Do Deep Research Portfela (PL)

### Instrukcje
Przeanalizuj moje portfolio w horyzoncie 12 miesięcy, bazując na danych z JSON poniżej.
1. Oceń każdą pozycję: ryzyka, teza inwestycyjna, katalizatory, red flags.
2. Uwzględnij wycenę względem pasma prognoz (`valuation_band`) i metryk (`smart_score`, `score`, `pe_ratio`, `analysts_count`).
3. Zidentyfikuj koncentracje sektorowe i ryzyko pojedynczych pozycji.
4. Zaproponuj scenariusze: bazowy / byczy / niedźwiedzi dla całego portfela.
5. Wskaż, gdzie potrzebny jest dodatkowy research i jakie dane są brakujące (`data_quality`).
6. Nie dawaj porady inwestycyjnej; podaj analizę, ryzyka, hipotezy i pytania kontrolne.

### Oczekiwany format odpowiedzi
- Executive summary (5-8 punktów)
- Omówienie każdej pozycji (1 krótki akapit per ticker)
- Mapa ryzyk portfela
- Checklista dalszego researchu
""".strip()

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    parts = [
        instructions,
        "### Dane wejściowe portfela (JSON)",
        "```json",
        payload_json,
        "```",
    ]
    if extra_questions:
        parts.extend(
            [
                "### Kluczowe pytania do deep research (Groq)",
                extra_questions.strip(),
            ]
        )
    return "\n\n".join(parts)


def _build_hybrid_prompt_en(payload: dict, extra_questions: str | None = None) -> str:
    instructions = """
## Portfolio Deep-Research Prompt (EN)

### Instructions
Analyze my portfolio over a 12-month horizon using the JSON payload below.
1. Review each position: thesis strength, key risks, catalysts, and red flags.
2. Use valuation-vs-forecast context (`valuation_band`) and core metrics (`smart_score`, `score`, `pe_ratio`, `analysts_count`).
3. Highlight concentration risk (single names + sector concentration).
4. Provide base / bull / bear scenarios for the overall portfolio.
5. Explicitly list what requires further web research and which fields are incomplete (`data_quality`).
6. Do not provide financial advice; provide analytical conclusions and risk framing.

### Expected output format
- Executive summary (5-8 bullet points)
- Position-by-position review (1 short paragraph per ticker)
- Portfolio-level risk map
- Actionable research checklist
""".strip()

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    parts = [
        instructions,
        "### Portfolio payload (JSON)",
        "```json",
        payload_json,
        "```",
    ]
    if extra_questions:
        parts.extend(
            [
                "### Key Questions for Deep Research (Groq-assisted)",
                extra_questions.strip(),
            ]
        )
    return "\n\n".join(parts)


def _generate_groq_key_questions(payload: dict, language: str = "en") -> tuple[str, str]:
    api_key = _resolve_groq_api_key()
    if not api_key:
        raise ValueError("Missing Groq API key (`GROQ_API_KEY` or `[groq].api_key`).")

    model = _resolve_groq_model()
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    compact_payload = {
        "portfolio_summary": payload.get("portfolio_summary", {}),
        "positions": payload.get("positions", [])[:25],
        "data_quality": payload.get("data_quality", {}),
    }
    if language.lower().startswith("pl"):
        user_prompt = (
            "Stwórz zwięzłą listę 12 pytań do deep research dla tego portfela. "
            "Pisz po polsku. Skup się na katalizatorach, ryzykach downside, koncentracji i walidacji tezy.\n\n"
            f"PORTFOLIO_JSON:\n{json.dumps(compact_payload, ensure_ascii=False)}"
        )
    else:
        user_prompt = (
            "Create a concise list of 12 high-value due-diligence questions for this portfolio. "
            "Write in English. Focus on catalysts, downside risks, concentration, and validation checks.\n\n"
            f"PORTFOLIO_JSON:\n{json.dumps(compact_payload, ensure_ascii=False)}"
        )
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You produce concise, high-signal research questions for equity portfolio due diligence."},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=500,
        temperature=0.2,
    )
    return completion.choices[0].message.content.strip(), model


if "portfolio_prompt_text_pl" not in st.session_state:
    st.session_state["portfolio_prompt_text_pl"] = ""
if "portfolio_prompt_text_en" not in st.session_state:
    st.session_state["portfolio_prompt_text_en"] = ""
if "last_click_time_portfolio_groq" not in st.session_state:
    st.session_state["last_click_time_portfolio_groq"] = 0.0
if "portfolio_prompt_meta" not in st.session_state:
    st.session_state["portfolio_prompt_meta"] = {}

st.markdown("<hr>", unsafe_allow_html=True)
st.header("Portfolio Prompt Builder")
st.caption(
    "Generate copy-ready research prompts (Markdown + JSON) in separate Polish and English tabs for ChatGPT, Gemini or Claude, "
    "based on your uploaded portfolio and current forecast snapshot."
)

use_groq_questions = st.checkbox(
    'Add Groq-generated "Key Questions for Deep Research"',
    value=False,
    help="Optional add-on. Base prompt generation works without any API key.",
)

if st.button("Build portfolio research prompt"):
    payload = _build_portfolio_prompt_payload(
        portfolio_df_input=portfolio_df,
        filtered_data_input=filtered_data,
        selected_date_input=selected_date,
        total_investment_est=total_investment,
        total_current_value_est=total_current_value,
    )

    extra_questions_pl = None
    extra_questions_en = None
    groq_model_used = None
    if use_groq_questions:
        now = time.time()
        if now - st.session_state["last_click_time_portfolio_groq"] < 10:
            st.warning("Please wait 10 seconds before generating Groq key questions again.")
        else:
            st.session_state["last_click_time_portfolio_groq"] = now
            try:
                with st.spinner("Generating Groq key questions..."):
                    extra_questions_pl, groq_model_used = _generate_groq_key_questions(payload, language="pl")
                    extra_questions_en, _ = _generate_groq_key_questions(payload, language="en")
            except Exception as exc:
                st.error(f"Groq add-on failed: {exc}")

    prompt_text_pl = _build_hybrid_prompt_pl(payload, extra_questions=extra_questions_pl)
    prompt_text_en = _build_hybrid_prompt_en(payload, extra_questions=extra_questions_en)
    st.session_state["portfolio_prompt_text_pl"] = prompt_text_pl
    st.session_state["portfolio_prompt_text_en"] = prompt_text_en
    st.session_state["portfolio_prompt_meta"] = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "positions_count": payload.get("portfolio_summary", {}).get("positions_count"),
        "groq_model": groq_model_used,
    }

if st.session_state["portfolio_prompt_text_pl"] or st.session_state["portfolio_prompt_text_en"]:
    meta = st.session_state.get("portfolio_prompt_meta", {})
    generated_at = meta.get("generated_at")
    positions_count = meta.get("positions_count")
    groq_model = meta.get("groq_model")

    st.success(
        f"Prompt ready. Positions in payload: {positions_count if positions_count is not None else 0}."
        + (f" Groq add-on model: {groq_model}." if groq_model else "")
    )
    if generated_at:
        st.caption(f"Generated at: {generated_at}")
    st.info("Use the language tabs below. Copy and paste the prompt into ChatGPT / Gemini / Claude.")
    tab_pl, tab_en = st.tabs(["Polski", "English"])

    with tab_pl:
        if st.session_state["portfolio_prompt_text_pl"]:
            st.code(st.session_state["portfolio_prompt_text_pl"], language="markdown")
            st.download_button(
                "Download prompt PL (.md)",
                data=st.session_state["portfolio_prompt_text_pl"],
                file_name=f"portfolio_research_prompt_pl_{selected_date}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.caption("Prompt PL is not available yet.")

    with tab_en:
        if st.session_state["portfolio_prompt_text_en"]:
            st.code(st.session_state["portfolio_prompt_text_en"], language="markdown")
            st.download_button(
                "Download prompt EN (.md)",
                data=st.session_state["portfolio_prompt_text_en"],
                file_name=f"portfolio_research_prompt_en_{selected_date}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.caption("Prompt EN is not available yet.")


st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""\
Please note: Investing involves risk and you may lose some or all of your capital. 
This site is provided for informational purposes only and does not constitute financial advice.
""")

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)
