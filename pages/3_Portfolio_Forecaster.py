import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.parse
import datetime
import plotly.express as px
import yfinance as yf
import numpy as np
import hashlib, hmac
import time
from openai import OpenAI
import io
import re
from plotly.subplots import make_subplots

# ======================================================================
# 1. Global CSS styles for buttons
#    - Red style for the "Clear current portfolio data" button
#    - Default green style for other st.button() elements
# ======================================================================

# st.set_page_config(
#     layout="wide",
#     # initial_sidebar_state="expanded"
# )

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

# ======================================================================
# 2. Loading forecast data (from GitHub) + initial configuration
# ======================================================================
@st.cache_data
def load_forecast_data():
    """Loads the main forecast data from a CSV file on GitHub."""
    file_url = "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
    data = pd.read_csv(file_url, delimiter=';')
    return data

df_forecasts = load_forecast_data()

# Convert date if there is a "Date of record" column
if "Date of record" in df_forecasts.columns:
    df_forecasts["Date of record"] = pd.to_datetime(df_forecasts["Date of record"], errors='coerce')


# ======================================================================
# 3. Sidebar: Date selection (if "Date of record" exists)
# ======================================================================
if "Date of record" in df_forecasts.columns:
    unique_dates = sorted(df_forecasts["Date of record"].dropna().unique())
    max_date = unique_dates[-1] if len(unique_dates) > 0 else None
    selected_date = st.sidebar.date_input("Date selector", value=max_date)
    # Filter forecasts by date
    filtered_data = df_forecasts[df_forecasts["Date of record"] == pd.Timestamp(selected_date)]
    if filtered_data.empty:
        st.sidebar.warning("No forecast data for the selected date.")
else:
    filtered_data = df_forecasts


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
# example_csv_path = "/Users/michal/PycharmProjects/Stock Scraper/Example csv file portfolio forecaster/xtb stock list.csv"
# example_df = pd.read_csv(example_csv_path, delimiter=';')

@st.cache_data
def load_example_portfolio():
    url = (
        "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/refs/heads/main/Example%20csv%20file%20portfolio%20forecaster/xtb%20stock%20list.csv"
    )
    return pd.read_csv(url, delimiter=';')

try:
    example_df = load_example_portfolio()
except Exception as e:
    # awaryjny mini‑przykład, żeby aplikacja nigdy nie padła
    example_df = pd.DataFrame({
        "Symbol": ["AAPL", "MSFT"],
        "Type":   ["BUY", "BUY"],
        "Volume": [1, 2],
        "Open time": ["" , ""],
        "Open price": [0, 0],
    })


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
    <a class="download-link" href="https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/refs/heads/main/Example%20csv%20file%20portfolio%20forecaster/xtb%20stock%20list.csv">
    Download sample CSV file here
</a>
</details>
"""

# ======================================================================
# 6. Unified upload: CSV *or* XLSX (auto-transform for XLSX)
# ======================================================================

st.markdown("#### Upload XLSX file from your XTB with full history of your portfolio:")

@st.cache_data
def _load_example_portfolio():  # zachowujemy poprzednią pomocniczą funkcję
    url = (
        "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/refs/heads/main/Example%20csv%20file%20portfolio%20forecaster/xtb%20stock%20list.csv"
    )
    return pd.read_csv(url, delimiter=';')

try:
    _example_df = _load_example_portfolio()
except Exception:
    _example_df = pd.DataFrame({
        "Symbol": ["AAPL", "MSFT"],
        "Type":   ["BUY", "BUY"],
        "Volume": [1, 2],
        "Open time": ["" , ""],
        "Open price": [0, 0],
    })

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

# # # Calculate the number of unique stocks in the portfolio
# num_unique_tickers = portfolio_df.groupby("Symbol").apply(
#     lambda df: (df["Volume"] * df["Type"].apply(lambda t: 1 if str(t).upper() == "BUY" else -1)).sum() != 0
# ).sum()

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


# 1) Interpret SELL as negative volume:
portfolio_df["NetVolume"] = portfolio_df.apply(
    lambda row: row["Volume"] if str(row["Type"]).upper() == "BUY" else -abs(row["Volume"]),
    axis=1
)

# Calculate the investment amount based on purchase data (from NetVolume):
total_investment = (portfolio_df["NetVolume"] * portfolio_df["Open price"]).sum()

# Calculate the current investment value:
# Assume that `filtered_data` contains forecasts for the selected date, and the 'Price' column is the current price.
# Make sure the symbols are compared in the same format (e.g., uppercase).
portfolio_df["Symbol"] = portfolio_df["Symbol"].str.upper()
filtered_data["Stock"] = filtered_data["Stock"].str.upper()

# Calculate the current investment value (also with NetVolume):
merged_df = portfolio_df.merge(filtered_data[["Stock", "Price"]], left_on="Symbol", right_on="Stock", how="left")
merged_df["Price"] = merged_df["Price"].fillna(0)
total_current_value = (merged_df["NetVolume"] * merged_df["Price"]).sum()

# We calculate the percentage difference between total_current_value and total_investment
if total_investment != 0:
    percent_diff = ((total_current_value - total_investment) / total_investment) * 100
else:
    percent_diff = 0

st.header("Portfolio Summary and Allocation")
            # st.write("Net value perspective (BUY - SELL).")

# Display 3 metrics in columns:
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


if "Sector" in df_forecasts.columns and 'portfolio_grouped' in locals() and not portfolio_grouped.empty:
    # 1) Merge: join portfolio_grouped with sector data
    df_sector_merge = portfolio_grouped.merge(
        df_forecasts[["Stock", "Sector"]].drop_duplicates(subset=["Stock"]),
        left_on="Symbol",
        right_on="Stock",
        how="left"
    )
    # Stocks not found in df_forecasts get "Unknown Sector"
    df_sector_merge["Sector"] = df_sector_merge["Sector"].fillna("Unknown Sector")

    # 2) Group by sector – sum the Invested and combine tickers into one string
    df_sector_grouped = df_sector_merge.groupby("Sector", as_index=False).agg({
        "Invested": "sum",
        "Symbol": lambda x: ", ".join(x.unique())
    })

    # Filter out sectors with Invested ≤ 0
    df_sector_grouped = df_sector_grouped[df_sector_grouped["Invested"] > 0]

    if df_sector_grouped.empty:
        st.info("No positive investment values in the sector breakdown.")
    else:
        # Round the Invested value
        df_sector_grouped["Invested"] = df_sector_grouped["Invested"].round(2)

        # Create a pie chart; pass ticker list as customdata
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


# # --------------------------------------------------------------
# # 12-Month Forecast Returns (Detailed vs. Compressed dropdown)
# # --------------------------------------------------------------
st.header("12‑Month Forecast Returns")

# 1) Copy portfolio, compute NetVolume
user_df = st.session_state["user_portfolio_df"].copy()
user_df["Symbol"] = user_df["Symbol"].str.upper()

def to_net_volume(row):
    t = str(row["Type"]).upper()
    v = float(str(row["Volume"]).replace(",", ".") or 0)
    return v if t == "BUY" else -abs(v)

user_df["NetVolume"] = user_df.apply(to_net_volume, axis=1)

# 2) Forecast rows for tickers we actually hold
portfolio_tickers = user_df["Symbol"].unique().tolist()
scoring = filtered_data[filtered_data["Stock"].isin(portfolio_tickers)].copy()

if scoring.empty:
    st.warning("No forecasts available for the stocks in your portfolio on the selected date.")
else:
    # ---------- A) 3 headline metrics --------------------------------------
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

    # ---------- B) Select box with 5 modes ---------------------------------
    view_mode = st.selectbox(
        "Forecast view:",
        options=["Detailed", "Compressed", "Low only", "Median only", "High only"],
        index=0
    )

    forecast_cols = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]

    fig = go.Figure()
    detailed_idx, comp_idx = [], []

    # ---------- C‑1) Detailed traces (per ticker × 3 levels) ---------------
    df_det = df_forecasts[df_forecasts["Stock"].isin(portfolio_tickers)].copy()
    df_det["Date of record"] = pd.to_datetime(df_det["Date of record"], errors="coerce")

    for tk in portfolio_tickers:
        dtk = df_det[df_det["Stock"] == tk]
        if dtk.empty: continue
        for col in forecast_cols:
            yvals = dtk[col].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0).round(2)
            fig.add_trace(
                go.Scatter(
                    x=dtk["Date of record"],
                    y=yvals,
                    mode="lines+markers",
                    name=f"{tk} – {col}",
                    visible=True        # will adjust below
                )
            )
            detailed_idx.append(len(fig.data)-1)

    # ---------- C‑2) Compressed (value‑weighted) traces --------------------
    df_portfolio_net = (
        user_df.groupby("Symbol", as_index=False)["NetVolume"].sum()
        .rename(columns={"Symbol": "Stock"})
    )
    df_w = (
        df_det.sort_values(["Stock","Date of record"])
              .groupby(["Stock","Date of record"], as_index=False).last()
              .merge(df_portfolio_net, on="Stock", how="left")
    )
    df_w["Price"] = df_w["Price"].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0)
    df_w["stock_value"] = df_w["NetVolume"] * df_w["Price"]

    def w_avg(g,col):
        num = (g[col]*g["stock_value"]).sum()
        den = g["stock_value"].sum()
        return num/den if den else 0

    df_cmp = df_w.groupby("Date of record", as_index=False).apply(
        lambda g: pd.Series({
            "Weighted Low":    w_avg(g,"Low Forecast Percent"),
            "Weighted Median": w_avg(g,"Median Forecast Percent"),
            "Weighted High":   w_avg(g,"High Forecast Percent")
        })
    ).reset_index()

    if not df_cmp.empty:
        for col in ["Weighted Low","Weighted Median","Weighted High"]:
            fig.add_trace(
                go.Scatter(
                    x=df_cmp["Date of record"],
                    y=df_cmp[col].round(2),
                    mode="lines+markers",
                    name=f"Compressed – {col}",
                    visible=False
                )
            )
            comp_idx.append(len(fig.data)-1)

    # ---------- D) Prepare index lists for Low / Median / High only --------
    low_idx    = [i for i,tr in enumerate(fig.data) if "Low"    in tr.name]
    med_idx    = [i for i,tr in enumerate(fig.data) if "Median" in tr.name]
    high_idx   = [i for i,tr in enumerate(fig.data) if "High"   in tr.name and "Low" not in tr.name]

    # ---------- E) Visibility switch ---------------------------------------
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

    # ---------- F) Layout tweaks -------------------------------------------
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Forecast (%)",
        margin=dict(t=20)
    )

    all_y = []
    for tr in fig.data:
        if tr.visible and tr.y is not None:
            # tr.y → ndarray → .tolist() daje zwykłą listę
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

        # ---- prices daily from your database ----
        df_all_prices = load_forecast_data().copy()
        if "Date of record" not in df_all_prices.columns:
            st.warning("No 'Date of record' in your price database, cannot compute return/XIRR.")
            df_all_prices["Date of record"] = pd.NaT

        df_all_prices["Date of record"] = pd.to_datetime(df_all_prices["Date of record"], errors="coerce")
        df_all_prices["Date"] = df_all_prices["Date of record"].dt.normalize()

        df_all_prices["Stock"] = df_all_prices["Stock"].astype(str).str.strip().str.upper()
        df_all_prices["Stock"] = df_all_prices["Stock"].str.replace(r"\.US$", "", regex=True)

        df_all_prices["Price"] = pd.to_numeric(
            df_all_prices["Price"].astype(str).str.replace(",", "."),
            errors="coerce"
        ).fillna(0.0)

        df_px_daily = (
            df_all_prices
            .dropna(subset=["Date", "Stock"])
            .sort_values(["Stock", "Date of record"])
            .groupby(["Date", "Stock"], as_index=False)
            .last()
        )
        px_pivot = df_px_daily.pivot(index="Date", columns="Stock", values="Price").sort_index()

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

        allowed = set(df_all_prices["Stock"].dropna().unique().tolist())

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

            holdings_eval = _build_daily_holdings(dp, start_prev, end_day)

            px_eval = px_pivot.reindex(holdings_eval.index).ffill().fillna(0.0)

            common_cols = [c for c in holdings_eval.columns if c in px_eval.columns]
            missing_prices = sorted(list(set(holdings_eval.columns) - set(common_cols)))

            mv = (holdings_eval[common_cols] * px_eval[common_cols]).sum(axis=1)
            equity = cash_eval + mv

            start_equity = float(equity.iloc[0])   # end of start_prev
            end_equity   = float(equity.iloc[-1])  # end of end_day

            # ---- simple return (fixed: include transfer + withdrawal in net_contrib) ----
            ext_types = ["deposit", "transfer", "withdrawal"]
            net_contrib = df_period.loc[df_period["Type_norm"].isin(ext_types), "Amount"].sum()  # net cash into the account

            profit = end_equity - start_equity - float(net_contrib)
            denom = start_equity + float(net_contrib)
            simple_return = (profit / denom) if denom != 0 else np.nan

            # ---- XIRR (fixed: include transfer, correct dates) ----
            flows = []
            flows.append((start_prev.date(), -start_equity))

            ext = df_period[df_period["Type_norm"].isin(ext_types)].copy()
            # Flow convention: investor perspective cashflow = -Amount (Amount>0 is money into account)
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

            # ---- UI metrics ----
            # r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            # r1c1.metric("Sum of deposits (Deposit + Transfer-in)", f"{deposits_sum:,.2f} USD")
            # r1c2.metric("Sum of dividends", f"{dividends_sum:,.2f} USD")
            # r1c3.metric("Dividend withholding tax (net)", f"{(-withholding_tax_sum):,.2f} USD")
            # r1c4.metric("Free-funds interest (net)", f"{ff_interest_net:,.2f} USD")
            #
            # r2c1, r2c2 = st.columns(2)
            # r2c1.metric("Simple return", f"{(simple_return*100):.2f}%" if np.isfinite(simple_return) else "n/a")
            # r2c2.metric("XIRR (money-weighted)", f"{(irr*100):.2f}%" if irr is not None else "n/a")

            # ---- UI metrics (3-column layout) ----

            # Row 1: cash ops summary
            c1, c2, c3 = st.columns(3)
            c1.metric("Sum of deposits (Deposit + Transfer-in)", f"{deposits_sum:,.2f} USD")
            c2.metric("Sum of dividends", f"{dividends_sum:,.2f} USD")
            c3.metric("Dividend withholding tax (net)", f"{(-withholding_tax_sum):,.2f} USD")

            # Row 2: interest + equity endpoints
            c4, c5, c6 = st.columns(3)
            c4.metric("Free-funds interest (net)", f"{ff_interest_net:,.2f} USD")
            c5.metric(f"Start equity (end of {start_prev.date()})", f"{start_equity:,.2f} USD")
            c6.metric(f"End equity (end of {end_day.date()})", f"{end_equity:,.2f} USD")

            # Row 3: returns
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
        # allowed symbols only from your price database (stock universe)
        df_all_prices = load_forecast_data().copy()
        df_all_prices["Stock"] = df_all_prices["Stock"].astype(str).str.strip().str.upper()
        df_all_prices["Stock"] = df_all_prices["Stock"].str.replace(r"\.US$", "", regex=True)
        allowed = set(df_all_prices["Stock"].dropna().unique().tolist())

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
    df_scores = load_forecast_data().copy()
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

                    # Small table for current portfolio composition (latest date in range)
                    latest_day = holdings_all.index.max()
                    latest_pos_abs = holdings_all.loc[latest_day].abs()
                    latest_pos_abs = latest_pos_abs[latest_pos_abs > 0]

                    if not latest_pos_abs.empty:
                        score_latest = score_eval.loc[latest_day] if latest_day in score_eval.index else pd.Series(dtype=float)
                        score_map = score_latest.to_dict()

                        # Latest available price per ticker (from forecast DB)
                        df_prices_latest = load_forecast_data().copy()
                        df_prices_latest["Date of record"] = pd.to_datetime(df_prices_latest["Date of record"], errors="coerce")
                        df_prices_latest["Stock"] = (
                            df_prices_latest["Stock"].astype(str).str.strip().str.upper()
                                            .str.replace(r"\.US$", "", regex=True)
                        )
                        df_prices_latest["Price"] = pd.to_numeric(
                            df_prices_latest["Price"].astype(str).str.replace(",", "."),
                            errors="coerce"
                        )
                        df_prices_latest = df_prices_latest.dropna(subset=["Date of record", "Stock", "Price"])
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
    @st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
    def _load_benchmark_series(source_key: str, symbol: str, start_iso: str, end_iso: str) -> pd.Series:
        start = pd.to_datetime(start_iso)
        end = pd.to_datetime(end_iso)

        if source_key == "stooq":
            s_enc = urllib.parse.quote(symbol)
            url = f"https://stooq.com/q/d/l/?s={s_enc}&i=d"
            df = pd.read_csv(url)
            if "Date" not in df.columns or "Close" not in df.columns:
                raise ValueError(f"Unexpected Stooq format for {symbol}")
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date")
            df = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
            s = pd.to_numeric(df["Close"], errors="coerce")
            s.index = df["Date"].dt.normalize()
            return s.dropna()

        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False
        )
        if df is None or df.empty:
            return pd.Series(dtype=float)

        price_col = "Adj Close" if "Adj Close" in df.columns else "Close"
        if price_col not in df.columns:
            return pd.Series(dtype=float)

        s = df[price_col]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        return s.dropna()

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
    df_prices = load_forecast_data().copy()
    if "Date of record" not in df_prices.columns:
        st.warning("No 'Date of record' in your price database, cannot compute market value.")
    else:
        df_prices["Date of record"] = pd.to_datetime(df_prices["Date of record"], errors="coerce")
        df_prices["Date"] = df_prices["Date of record"].dt.normalize()

        df_prices["Stock"] = df_prices["Stock"].astype(str).str.strip().str.upper()
        df_prices["Stock"] = df_prices["Stock"].str.replace(r"\.US$", "", regex=True)

        df_prices["Price"] = pd.to_numeric(
            df_prices["Price"].astype(str).str.replace(",", "."),
            errors="coerce"
        ).fillna(0.0)

        df_px_daily = (
            df_prices
            .dropna(subset=["Date", "Stock"])
            .sort_values(["Stock", "Date of record"])
            .groupby(["Date", "Stock"], as_index=False)
            .last()
        )

        px_pivot = df_px_daily.pivot(index="Date", columns="Stock", values="Price").sort_index()

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
        for bench_name in bench_selected:
            sym = bench_catalog[bench_name][bench_source_key]
            try:
                s_price = _load_benchmark_series(bench_source_key, sym, start_iso, end_iso)
                if s_price is None or s_price.empty:
                    continue

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

            except Exception:
                continue

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
                sym = bench_catalog[bn][bench_source_key]

                # price series
                s_price = _load_benchmark_series(bench_source_key, sym, start_iso, end_iso) \
                    .reindex(total_equity.index).ffill().bfill()

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

# 2) Prepare df_forecasts: we only take columns relevant to dividends
df_div_full = df_forecasts[[
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
    # st.info("No dividend-paying stocks (or yield = 0).")
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
        df_price_latest = (
            df_forecasts
            .dropna(subset=["Stock", "Date of record", "Price"])
            .copy()
        )
        df_price_latest["Price"] = (
            df_price_latest["Price"].astype(str).str.replace(",", ".").astype(float, errors="ignore")
        )
        df_price_latest["Date of record"] = pd.to_datetime(df_price_latest["Date of record"], errors="coerce")
        df_price_latest = df_price_latest.sort_values(["Stock", "Date of record"])
        df_price_latest = df_price_latest.groupby("Stock", as_index=False).last()

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
        # st.write("""Each row is a separate (Ex-div date -> Dividend pay date).""")

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

        # # ------------------------------------------------------
        # # 5) Wyświetlenie
        # # ------------------------------------------------------
        # st.markdown(styled.to_html(), unsafe_allow_html=True)
        # ——————————————————————————————————————————————————————————————————
        # 4-b) Wyświetlenie w 4 kolumnach według sygnału
        # ——————————————————————————————————————————————————————————————————
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
#  CORRELATION MAP (from df_forecasts) — with ordering
# ============================
# st.markdown("---")
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
        # 1) UI
        # c1, c2, c3, c4 = st.columns([1,1,1,1])
        # with c1:
        #     window_rows = c1.selectbox("Window (last N trading rows)", [60, 120, 250], index=1)
        # with c2:
        #     ret_kind = c2.selectbox("Returns", ["Percent (pct_change)", "Log (diff of log)"], index=0)
        # with c3:
        #     corr_kind = c3.selectbox("Correlation", ["Pearson", "Spearman", "Kendall", "Up/Down (sign Pearson)"], index=0)
        #
        # # Czy jest scipy? (opcjonalny tryb hierarchiczny)
        # try:
        #     import scipy.cluster.hierarchy as sch
        #     have_scipy = True
        # except Exception:
        #     have_scipy = False
        #
        # order_options = ["Original", "Cluster similar (spectral)"]
        # if have_scipy:
        #     order_options.append("Cluster similar (hierarchical)")
        #
        # with c4:
        #     order_mode = c4.selectbox("Order heatmap", order_options, index=1)

        # 1) UI (2×2)
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

        # 2) Przygotuj ceny z df_forecasts
        df_all = df_forecasts.copy()
        df_all["Stock"] = df_all["Stock"].astype(str).str.upper()
        df_all["Date of record"] = pd.to_datetime(df_all["Date of record"], errors="coerce")

        # Price -> float (czyścimy)
        price_str = (
            df_all["Price"]
              .astype(str)
              .str.replace("\u00A0", " ", regex=False)
              .str.replace(",", "", regex=False)
              .str.replace(r"[^0-9.\-]", "", regex=True)
        )
        df_all["Price"] = pd.to_numeric(price_str, errors="coerce")
        df_all = df_all.dropna(subset=["Date of record", "Price"])

        # Ostatni rekord w danym dniu
        sort_keys = ["Stock", "Date of record"]
        if "Time of record" in df_all.columns:
            df_all["Time of record"] = df_all["Time of record"].astype(str)
            sort_keys.append("Time of record")
        df_all = df_all.sort_values(sort_keys)
        df_daily_last = df_all.groupby(["Date of record", "Stock"], as_index=False).last()

        # Pivot
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

                # # 8) Pobranie CSV
                # st.download_button(
                #     "Download correlation matrix (CSV)",
                #     data=C.to_csv().encode(),
                #     file_name=f"correlation_{corr_kind.lower()}_{len(wide)}rows.csv",
                #     mime="text/csv"
                # )


# ============================
#  AI PORTFOLIO COMMENTARY (RAG-style prompt → OpenAI)
#  — place at the very end of portfolio_forecaster page
# ============================

def _hash_sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _safe_rerun():
    # backward compatible rerun
    try:
        st.rerun()
    except Exception:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()

def render_section_logout(section_key: str, label: str = "🔒 Log out of this section"):
    ss_key = f"{section_key}__authed"
    if st.session_state.get(ss_key, False):
        if st.button(label, key=f"{section_key}__logout_main", use_container_width=True):
            st.session_state[ss_key] = False
            _safe_rerun()

def check_section_access(section_key: str) -> bool:
    """
    Minimal password gate for a single section.

    Expected secrets structure:
      [auth]
      passwords_plain = ["your_password1", "another_password2"]   # optional
      passwords_sha256 = ["<sha256>", "<sha256>"]                  # optional
    """
    ss_key = f"{section_key}__authed"

    # Already authenticated in this session?
    if st.session_state.get(ss_key, False):
        return True

    cfg = st.secrets.get("auth", {})
    plains = set(cfg.get("passwords_plain", []))
    hashes = set(cfg.get("passwords_sha256", []))

    if not plains and not hashes:
        st.error("No passwords configured under st.secrets['auth']. Protection disabled.")
        return False

    with st.expander("🔒 This section is password-protected — click to unlock", expanded=True):
        pw = st.text_input("Password", type="password", key=f"{section_key}__pw")
        ok_clicked = st.button("Unlock", key=f"{section_key}__unlock", use_container_width=True)

        if ok_clicked:
            is_ok = any(hmac.compare_digest(pw, p) for p in plains) or (
                pw and any(hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), h) for h in hashes)
            )
            if is_ok:
                st.session_state[ss_key] = True
                st.success("Access granted.")
                _safe_rerun()
            else:
                st.error("Invalid password.")

    return False

st.markdown("<hr>", unsafe_allow_html=True)
# st.markdown("---")
st.header("AI portfolio commentary")

# ---- USE: wrap your AI commentary section with the gate ----
if check_section_access("portfolio_ai_comment"):

    with st.expander("Generate AI summary for my portfolio"):

        # simple rate limit (reuse your pattern)
        if "last_click_time_portfolio" not in st.session_state:
            st.session_state["last_click_time_portfolio"] = 0.0

        # ——— Guardrails / data requirements ———
        if portfolio_df.empty:
            st.info("Your portfolio is empty — add/upload positions first.")
        elif "Stock" not in filtered_data.columns:
            st.info("No forecast universe loaded for the selected date.")
        else:
            # Build a clean, compact view of current portfolio joined with forecasts
            # 1) copy & normalize the portfolio (BUY positive, SELL negative)
            _p = portfolio_df.copy()
            _p["Symbol"] = _p["Symbol"].astype(str).str.upper()
            _p["Volume"] = (
                _p["Volume"].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0.0)
            )
            _p["Open price"] = (
                _p["Open price"].astype(str).str.replace(",", ".").astype(float, errors="ignore").fillna(0.0)
            )
            _p["NetVolume"] = _p.apply(
                lambda r: r["Volume"] if str(r["Type"]).upper() == "BUY" else -abs(r["Volume"]),
                axis=1
            )

            # 2) aggregate to net position per ticker
            pos = (
                _p.groupby("Symbol", as_index=False)
                  .agg({"NetVolume":"sum"})
            )
            pos = pos[pos["NetVolume"] != 0]   # leave only open positions

            if pos.empty:
                st.info("All positions net to zero — nothing to analyze.")
            else:
                # 3) latest prices/forecasts for the selected date
                uni = filtered_data.copy()
                uni["Stock"] = uni["Stock"].astype(str).str.upper()

                # numeric clean-up
                def _to_num(s):
                    return pd.to_numeric(
                        s.astype(str).str.replace(",", "."),
                        errors="coerce"
                    )
                for c in ["Price","Low Forecast","Median Forecast","High Forecast",
                          "Low Forecast Percent","Median Forecast Percent","High Forecast Percent",
                          "P/E ratio","Smart Score","Score","Number of analysts"]:
                    if c in uni.columns:
                        uni[c] = _to_num(uni[c])

                # Deduplicate to the last row per stock for that date (if multiple)
                if "Date of record" in uni.columns:
                    uni = (uni.sort_values(["Stock","Date of record"])
                              .groupby("Stock", as_index=False).last())

                # 4) merge portfolio net positions with forecasts
                merged_port = pos.merge(
                    uni,
                    left_on="Symbol", right_on="Stock",
                    how="left"
                )

                # average open price for context (value-weighted by signed volume)
                _p_signed = _p.copy()
                _p_signed["SignedCost"] = _p_signed["NetVolume"] * _p_signed["Open price"]
                avg_open = (
                    _p_signed.groupby("Symbol", as_index=False)
                             .agg({"NetVolume":"sum","SignedCost":"sum"})
                )
                avg_open["Avg Open Price"] = avg_open.apply(
                    lambda r: (r["SignedCost"]/r["NetVolume"]) if r["NetVolume"] else float("nan"),
                    axis=1
                )
                merged_port = merged_port.merge(
                    avg_open[["Symbol","Avg Open Price"]],
                    on="Symbol", how="left"
                )

                # helpful deltas (% distance to forecast bands)
                merged_port["Position Value (est.)"] = merged_port["NetVolume"] * merged_port["Price"]
                merged_port["% below Low"]    = ((merged_port["Low Forecast"] - merged_port["Price"]) / merged_port["Low Forecast"] * 100.0)
                merged_port["% to Median"]    = ((merged_port["Median Forecast"] - merged_port["Price"]) / merged_port["Median Forecast"] * 100.0)
                merged_port["% above High"]   = ((merged_port["Price"] - merged_port["High Forecast"]) / merged_port["High Forecast"] * 100.0)

                # Compact table for the LLM
                cols_for_llm = [
                    "Symbol","Sector","NetVolume","Price","Avg Open Price",
                    "Low Forecast","Median Forecast","High Forecast",
                    "Low Forecast Percent","Median Forecast Percent","High Forecast Percent",
                    "Smart Score","Score","P/E ratio","Number of analysts",
                    "Position Value (est.)","% below Low","% to Median","% above High"
                ]
                cols_for_llm = [c for c in cols_for_llm if c in merged_port.columns]
                df_llm = merged_port[cols_for_llm].copy()

                # light rounding to reduce token size
                for c in df_llm.columns:
                    if pd.api.types.is_float_dtype(df_llm[c]):
                        df_llm[c] = df_llm[c].round(4)

                # portfolio-level aggregates (context for the model)
                port_ctx = {
                    "total_investment_est": float(total_investment) if "total_investment" in locals() else None,
                    "total_current_value_est": float(total_current_value) if "total_current_value" in locals() else None,
                    "n_positions": int(df_llm.shape[0])
                }

                # ——— Prompt builder (EN) ———
                def build_portfolio_prompt(df_payload: pd.DataFrame, context: dict) -> str:
                    payload_csv = df_payload.to_csv(index=False)
                    guidance = f"""
You are a data-driven (quant) investment analyst. You will receive my current portfolio (table) and basic forecast metrics (Low/Median/High, %, Score, Smart Score, P/E, number of analysts) for each ticker.

Task:
1) If you have web browsing tools, briefly check only **material** fresh items (earnings, guidance, regulatory, M&A, product/recall, litigation) and upcoming catalysts (earnings date, lock-ups, conferences) for each ticker.  
   • If you **cannot** browse, say so in one sentence and proceed based solely on the provided data.  
2) For each position, assess valuation vs. forecast band: below Low (undervaluation), between Low–Median (neutral/cautious), between Median–High (overvaluation risk), or above High (hype/overvaluation).  
3) Indicate, over a 12-month horizon, whether you see **reduce/sell risk** (strong signals: above High + weak fundamentals/newsflow) or rather **hold** (no significant red flags, data supports holding), assuming I’m a conservative investor who ignores week-to-week sentiment.  
4) Give portfolio-level takeaways (2–4 sentences): key risks, sector/theme concentrations, expected return band by median, and whether “do nothing” vs. “trim X”.  
5) Do **not** give financial advice — deliver analysis, risks, and conclusions only.

**Portfolio context (estimates):**
- Number of positions: {context.get("n_positions")}
- Total cost (est.): {context.get("total_investment_est")}
- Current value (est.): {context.get("total_current_value_est")}

**Portfolio data (CSV):**
{payload_csv}

Keep it concise: one “overview” paragraph, then bullet points per ticker (max 2 sentences/ticker: [valuation signal + one fact/news + one conclusion]), and a short final summary (reduce anything or hold everything) with justification. Use the numbers from the table.
"""
                    return guidance.strip()

                prompt_text = build_portfolio_prompt(df_llm, port_ctx)

                # ============================
                #  AI PORTFOLIO COMMENTARY — GPT-5 + web_search
                # ============================

                # 1) Model UI + (for GPT-5) reasoning/verbosity and web search toggles
                model_choice = st.selectbox(
                    "Choose the LLM model",
                    ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"],
                    help=("GPT-5 uses the Responses API and supports web_search. "
                          "GPT-4o stays on Chat Completions.")
                )

                use_web_search = False
                reasoning_effort = None
                text_verbosity = None

                if model_choice.startswith("gpt-5"):
                    cols = st.columns(2)
                    with cols[0]:
                        reasoning_effort = st.selectbox(
                            "Reasoning effort (GPT-5)",
                            ["minimal", "low", "medium", "high"],
                            index=2,
                            help="Controls depth of reasoning. ‘minimal/low’ are faster, ‘high’ is more thorough."
                        )
                    with cols[1]:
                        text_verbosity = st.selectbox(
                            "Verbosity (GPT-5)",
                            ["low", "medium", "high"],
                            index=1,
                            help="Steers output length. Not a hard cap."
                        )
                    use_web_search = st.checkbox(
                        "Enable web search (GPT-5 Responses tool)",
                        value=True,
                        help="Lets the model fetch fresh information and return cited sources."
                    )
                    allowed_domains_str = ""
                    if use_web_search:
                        allowed_domains_str = st.text_input(
                            "Allowed domains (optional, comma-separated, no https://)",
                            value="",
                            help="e.g., 'wsj.com, bloomberg.com, reuters.com'. Empty = no filter."
                        )

                # 2) Universal wrapper:
                #    • gpt-5*  -> Responses API (no explicit max length; no temperature)
                #    • gpt-4o* -> Chat Completions (with max_tokens)
                def _llm_generate_portfolio_comment(
                    client,
                    model: str,
                    system_text: str,
                    user_text: str,
                    reasoning: str | None = None,
                    verbosity: str | None = None,
                    web_search: bool = False,
                    allowed_domains: list[str] | None = None,
                    max_tokens_non5: int = 1400
                ) -> tuple[str, list[str]]:
                    """
                    Returns (output_text, sources_urls).
                    sources_urls — full list of URLs if web_search was used by the model.
                    """
                    messages = [
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": user_text},
                    ]

                    # GPT-5 / GPT-5-mini
                    if model.startswith("gpt-5"):
                        req = {
                            "model": model,
                            "input": messages,
                        }
                        if reasoning:
                            req["reasoning"] = {"effort": reasoning}
                        if verbosity:
                            req["text"] = {"verbosity": verbosity}

                        tools = []
                        if web_search:
                            tool_def = {"type": "web_search"}
                            if allowed_domains:
                                tool_def["filters"] = {"allowed_domains": allowed_domains[:20]}
                            tools.append(tool_def)
                        if tools:
                            req["tools"] = tools
                            req["tool_choice"] = "auto"
                            req["include"] = ["web_search_call.action.sources"]

                        # no max_output_tokens per your preference
                        resp = client.responses.create(**req)

                        out_text = getattr(resp, "output_text", None)
                        if not out_text:
                            out_text = ""
                            for item in getattr(resp, "output", []) or []:
                                if item.get("type") == "message":
                                    for c in item.get("content", []) or []:
                                        if c.get("type") == "output_text":
                                            out_text += c.get("text", "")

                        sources = []
                        try:
                            for item in resp.output or []:
                                if item.get("type") == "web_search_call":
                                    action = item.get("action", {})
                                    srcs = action.get("sources") or []
                                    for s in srcs:
                                        url = s.get("url")
                                        if url:
                                            sources.append(url)
                        except Exception:
                            pass

                        return out_text.strip(), sources

                    # GPT-4o / 4o-mini — Chat Completions
                    else:
                        cc = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=0.5,
                            max_tokens=max_tokens_non5,
                        )
                        text = cc.choices[0].message.content.strip()
                        return text, []

                # 3) Trigger
                if st.button("Generate AI commentary for my portfolio"):
                    now = time.time()
                    if now - st.session_state["last_click_time_portfolio"] < 120:
                        st.warning("Please wait 120 seconds before requesting another commentary.")
                    else:
                        st.session_state["last_click_time_portfolio"] = now
                        try:
                            client = OpenAI(api_key=st.secrets["openai"]["OPENAI_API_KEY"])
                            with st.spinner("Generating AI commentary…"):
                                out_text, sources = _llm_generate_portfolio_comment(
                                    client=client,
                                    model=model_choice,
                                    system_text=("You are a precise, concise quantitative analyst. "
                                                 "Avoid investment advice; provide analysis, risks, and conclusions."),
                                    user_text=prompt_text,
                                    reasoning=reasoning_effort if model_choice.startswith("gpt-5") else None,
                                    verbosity=text_verbosity if model_choice.startswith("gpt-5") else None,
                                    web_search=(use_web_search if model_choice.startswith("gpt-5") else False),
                                    allowed_domains=[d.strip() for d in (allowed_domains_str or "").split(",") if d.strip()] if (
                                        use_web_search and model_choice.startswith("gpt-5")
                                    ) else None,
                                )

                            st.success("Commentary ready:")
                            st.write(out_text)

                            if sources:
                                with st.expander("Sources (web search)"):
                                    for u in dict.fromkeys(sources):  # dedup
                                        st.markdown(f"- <{u}>", unsafe_allow_html=False)

                        except Exception as e:
                            st.error(f"Failed to generate commentary (model '{model_choice}'): {e}")

    render_section_logout("portfolio_ai_comment")
    pass
else:
    st.stop()  # stop rendering the rest of the page below this section (optional)




st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""\
Please note: Investing involves risk and you may lose some or all of your capital. 
This site is provided for informational purposes only and does not constitute financial advice.
""")
# st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)


st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""\
Please note: Investing involves risk and you may lose some or all of your capital. 
This site is provided for informational purposes only and does not constitute financial advice.
""")
# st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)
