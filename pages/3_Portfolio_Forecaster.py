import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.parse
import datetime
import plotly.express as px
import yfinance as yf


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
This tab is used to analyze stock price forecasts in your portfolio.

1. You can upload a **CSV file** with a list of your stocks (see the detailed instruction how to prepare CSV file below).
2. **Or** add stocks manually using the form below.

After entering data, you will automatically see analysis and charts for your portfolio. """)

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
# 6. CSV file upload section
# ======================================================================
st.markdown("#### Upload a CSV file with a list of stocks in your portfolio:")
st.markdown(custom_html, unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["csv"])
if uploaded_file is not None:
    # If it's a new file, merge it with the portfolio; otherwise ignore
    if uploaded_file.name != st.session_state["last_uploaded_file_name"]:
        try:
            csv_df = pd.read_csv(uploaded_file, delimiter=';')
            # Make sure we have all required columns (or add them empty)
            for col in ["Symbol", "Type", "Volume", "Open price", "Open time"]:
                if col not in csv_df.columns:
                    csv_df[col] = ""

            st.session_state["user_portfolio_df"] = pd.concat(
                [st.session_state["user_portfolio_df"], csv_df],
                ignore_index=True
            ).fillna("")
            st.session_state["last_uploaded_file_name"] = uploaded_file.name
            st.success(f"Successfully loaded CSV file: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error loading CSV file: {e}")
    else:
        st.info("This same CSV file has already been processed previously (not duplicating data).")

# st.markdown("<hr>", unsafe_allow_html=True)

st.markdown(
    """
    <div style="display: flex; align-items: center; margin: 20px 0;">
      <hr style="flex: 1; border: none; border-top: 1px solid #ccc;">
      <span style="margin: 0 10px; color: #888; font-size: 14px;">or/and</span>
      <hr style="flex: 1; border: none; border-top: 1px solid #ccc;">
    </div>
    """,
    unsafe_allow_html=True
)


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

# Display 3 metrics in columns:
col1, col2, col3 = st.columns(3)
col1.metric("Number of stocks in portfolio", f"{num_unique_tickers}")
col2.metric("Investment amount", f"{total_investment:.2f} USD")
col3.metric("Current investment value", f"{total_current_value:.2f} USD", delta=f"{percent_diff:+.2f}%")


with st.expander("History of the current portfolio value over time"):

    # 1. Load data from your full database (instead of scoring/filtered_data):
    df_all = load_forecast_data()

    # 2. Copy the data from the portfolio (what is in session_state).
    portfolio_df = st.session_state["user_portfolio_df"].copy()
    portfolio_df["Symbol"] = portfolio_df["Symbol"].str.upper()

    # 3. Convert BUY to positive volume, SELL to negative:
    def net_volume(row):
        t = str(row["Type"]).upper()
        vol_str = str(row["Volume"]).replace(",", ".")
        try:
            vol = float(vol_str)
        except ValueError:
            vol = 0.0
        return vol if t == "BUY" else (-abs(vol))

    portfolio_df["Volume"] = portfolio_df.apply(net_volume, axis=1)

    # 4. Group to get total (net) volume for each Symbol:
    portfolio_agg = (
        portfolio_df
        .groupby("Symbol", as_index=False)["Volume"]
        .sum()
        .rename(columns={"Volume": "NetVolume"})
    )

    # 5. Prepare historical data from df_all:
    df_all["Stock"] = df_all["Stock"].str.upper()
    df_all["Date of record"] = pd.to_datetime(df_all["Date of record"], errors="coerce")

    df_all["Price"] = (
        df_all["Price"]
        .astype(str)
        .str.replace(",", ".")
    )
    df_all["Price"] = pd.to_numeric(df_all["Price"], errors="coerce").fillna(0)

    # 6. Filter only those tickers that are in the portfolio (by NetVolume):
    df_all_portfolio = df_all[df_all["Stock"].isin(portfolio_agg["Symbol"])].copy()

    # 7. For each (Date, Stock), take the LAST entry of that day (if multiple entries exist):
    df_daily = (
        df_all_portfolio
        .sort_values(["Stock", "Date of record"])
        .groupby(["Date of record", "Stock"], as_index=False)
        .last()
    )

    # 8. Merge df_daily with NetVolume to have the number of shares for each stock:
    merged = df_daily.merge(
        portfolio_agg,
        left_on="Stock",
        right_on="Symbol",
        how="left"
    )

    # 9. Calculate value (Price * NetVolume):
    merged["PortfolioValue"] = merged["Price"] * merged["NetVolume"]

    # 10. Sum all stocks' values for each day:
    daily_portfolio = (
        merged
        .groupby("Date of record", as_index=False)["PortfolioValue"]
        .sum()
        .sort_values("Date of record")
    )

    # 11. Create an area chart (in green):
    fig = px.area(
        daily_portfolio,
        x="Date of record",
        y="PortfolioValue",
        labels={"PortfolioValue": "Portfolio value (USD)", "Date of record": ""},
        color_discrete_sequence=["green"]
    )

    # Limit the Y-axis range to ±20% of the current portfolio value:
    if not daily_portfolio.empty:
        current_value = daily_portfolio["PortfolioValue"].iloc[-1]
        y_min = current_value * 0.8
        y_max = current_value * 1.2
        fig.update_yaxes(range=[y_min, y_max])

    # 12. Display the chart
    st.plotly_chart(fig, use_container_width=True)


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

            st.header("Portfolio Allocation")
            # st.write("Net value perspective (BUY - SELL).")

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

        c1,c2,c3 = st.columns(3)
        c1.metric("Median – Low Forecast",    f"{wa_low:.2f}%")
        c2.metric("Median – Median Forecast", f"{wa_median:.2f}%")
        c3.metric("Median – High Forecast",   f"{wa_high:.2f}%")

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



# ------------------------------------------------------------------
#   PORÓWNANIE PORTFELA Z INDEKSAMI (yfinance)
# ------------------------------------------------------------------
# with st.expander("Portfolio vs. indeksy (S&P 500 / NASDAQ / Dow Jones)"):

st.markdown("---")
st.header("Portfolio vs index benchmarks")

if daily_portfolio.empty:
    st.info("Brak historii portfela – nie można narysować porównania.")
else:
    # ----------------------------------------------------------
    # 1) Zakres dat = dokładnie taki jak w daily_portfolio
    # ----------------------------------------------------------
    start_date = daily_portfolio["Date of record"].min().date()
    end_date   = daily_portfolio["Date of record"].max().date() + pd.Timedelta(days=1)

    # ----------------------------------------------------------
    # 2) Funkcja pobierająca indeks z yfinance
    # ----------------------------------------------------------
    @st.cache_data(show_spinner=False)
    def load_index(symbol: str, start, end):
        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            interval="1d",
            auto_adjust=True,  # skorygowane ceny
        )

        # 1) Wybieramy kolumnę z ceną zamknięcia
        price_col = "Adj Close" if "Adj Close" in df.columns else "Close"

        # 2) df[price_col] może być Series **lub** DataFrame (MultiIndex kolumn).
        #    W obu przypadkach sprowadzamy do DataFrame z jedną kolumną = symbol.
        if isinstance(df[price_col], pd.Series):
            df_price = df[price_col].rename(symbol).to_frame()
        else:  # DataFrame
            df_price = df[[price_col]].copy()
            df_price.columns = [symbol]

        # 3) Porządkujemy indeks
        df_price.index = pd.to_datetime(df_price.index).tz_localize(None)
        return df_price


    idx_symbols = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ Composite",
        "^DJI": "Dow Jones",

        "^RUT": "Russell 2000",
        "^NDX": "NASDAQ 100",
        "^MID": "S&P 400 MidCap",
        "^W5000": "Wilshire 5000",

        "URTH": "MSCI World (ETF)",
        "EEM": "MSCI EM (ETF)",
        # "^STOXX50E": "Euro STOXX 50",
        "^N225": "Nikkei 225"
    }

    idx_frames = []
    for sym, nice_name in idx_symbols.items():
        df_i = load_index(sym, start_date, end_date)
        df_i.columns = [nice_name]  # <- tu zmieniamy kolumnę
        idx_frames.append(df_i)
    df_indices = pd.concat(idx_frames, axis=1)

    # ----------------------------------------------------------
    # 3) Łączymy z historią portfela
    # ----------------------------------------------------------
    port_series = (
        daily_portfolio
        .set_index("Date of record")["PortfolioValue"]
        .rename("Portfolio")
    )

    perf_df = pd.concat([port_series, df_indices], axis=1).sort_index()

    # Jeśli portfolio ma luki w datach, forward-fill żeby indeksy miały komplet:
    perf_df["Portfolio"] = perf_df["Portfolio"].ffill()

    # ----------------------------------------------------------
    # 4) Normalizacja do 100 = pierwszy dzień
    # ----------------------------------------------------------
    for col in perf_df.columns:
        first_val = perf_df[col].iloc[0]
        perf_df[col] = perf_df[col] / first_val * 100


    # ── 1.  przełącznik nad wykresem ────────────────────────────────────────────
    bench_opts = ["S&P 500", "NASDAQ Composite", "Dow Jones",
                  "Russell 2000", "NASDAQ 100", "S&P 400 MidCap",
                  "Wilshire 5000", "MSCI World (ETF)", "MSCI EM (ETF)", "Nikkei 225"]

    default_opts = ["S&P 500", "NASDAQ Composite", "Dow Jones"]  # start bez bałaganu

    show_bench = st.multiselect(
        "Benchmarks to display:",
        options=bench_opts,
        default=default_opts
    )
    # (linię Portfolio zostawiamy na stałe – nie ma w selectorze)
    # Portfolio linia jest obowiązkowa – nie dodajemy jej do multiselectu

    # ── 2.  konstrukcja wykresu ────────────────────────────────────────────────
    fig_perf = go.Figure()

    # • Portfolio (zawsze):
    fig_perf.add_trace(
        go.Scatter(
            x=perf_df.index,
            y=perf_df["Portfolio"],
            name="Portfolio",
            mode="lines",
            line=dict(width=3)
        )
    )

    # • Benchmarks wybrane w multiselect:
    for col in show_bench:
        fig_perf.add_trace(
            go.Scatter(
                x=perf_df.index,
                y=perf_df[col],
                name=col,
                mode="lines",
                line=dict(width=1.8, dash="dot")
            )
        )

    # ── 3.  wygląd & renderowanie ─────────────────────────────────────────────
    fig_perf.update_layout(
        yaxis_title="Normalized value",
        xaxis_title="Date",
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_perf, use_container_width=True)


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