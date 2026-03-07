import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional

# ---------- CONFIG -----------------------------------------------------------
st.set_page_config(page_title="Sector Explorer",
                   # layout="wide"
                   )

######### początek kodu CSS - tu jest kod CSS do stylizowania strony - początek ########
st.markdown(
    """
    <style>
    /* This CSS makes metric values bold */
    [data-testid="stMetricValue"] {
        font-weight: bold;
    }
    /* Optionally: make metric labels bold as well */
    [data-testid="stMetricLabel"] {
        font-weight: bold;
    }
    </style>
    <style>
    div.stButton > button {
    width: 100%;
        color: #ffffff; /* White text */
        background-image: linear-gradient(to right, #034980, #0277bd); /* Dark blue gradient */
        border: 2px solid #0277bd;
        font-size: 16px;
        font-weight: bold;
        transition: background-image 0.3s ease, transform 0.3s ease;
    }
    .full-width-blue-button > button:hover {
        background-image: linear-gradient(to right, #388e3c, #66bb6a); /* Green gradient on hover */
        transform: scale(1.02);
    }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Sector Explorer")
st.markdown("""
Explore S&P 500 companies **by sector** and **by date**.  
Use the sidebar to pick a trading date; the default is the most recent
date available in the data set.
""")

# ---------- LOAD DATA --------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    url = (
        "https://raw.githubusercontent.com/"
        "michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
    )
    df_ = pd.read_csv(url, delimiter=";")

    # Parse the date column once so downstream widgets can work with datetime
    if "Date of record" in df_.columns:
        df_["Date of record"] = pd.to_datetime(
            df_["Date of record"], errors="coerce"
        ).dt.date  # keep only the date portion
    return df_


df = load_data()
df_full = load_data()        # cały zbiór
df      = df_full.copy()     # potem filtrujesz go po dacie w sidebarze

if "Sector" not in df.columns:
    st.error("Column **'Sector'** not found in the data – can't build Sector Explorer.")
    st.stop()

# ---------- SIDEBAR ― DATE SELECTOR -----------------------------------------
sidebar = st.sidebar
if "Date of record" in df.columns:
    available_dates = sorted(df["Date of record"].dropna().unique())
    default_date = available_dates[-1]  # latest
    chosen_date = sidebar.date_input(
        "Date selector", value=default_date, min_value=available_dates[0], max_value=default_date
    )
    df = df[df["Date of record"] == chosen_date]
else:
    sidebar.info("No **'Date of record'** column – showing all dates.")
    chosen_date = None  # fallback, not used further

if df.empty:
    st.error("No data for the selected date.")
    st.stop()

# ── helper: parse “36.15B”, “250M”, “1.2K” → float USD ───────────────────────
def parse_mcap(value: str) -> Optional[float]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*([\d.,]+)\s*([BMKbmk]?)\s*", value)
    if not match:
        return None
    num, suffix = match.groups()
    num = float(num.replace(",", "").replace(" ", ""))
    factor = {"B": 1e9, "M": 1e6, "K": 1e3, "": 1}.get(suffix.upper(), 1)
    return num * factor

# ---------- DETERMINE DEFAULT SECTOR (largest m‑cap for *this* date) ---------
def default_sector(data: pd.DataFrame) -> str:
    if "Market cap clear" in data.columns and pd.api.types.is_numeric_dtype(
        data["Market cap clear"]
    ):
        tot = data.groupby("Sector")["Market cap clear"].sum(numeric_only=True)
        if not tot.empty:
            return tot.idxmax()

    if "Market cap" in data.columns:
        tmp = data.copy()
        tmp["__mcap__"] = tmp["Market cap"].apply(parse_mcap)
        tot = tmp.groupby("Sector")["__mcap__"].sum(min_count=1)
        if tot.notna().any():
            return tot.idxmax()

    return data["Sector"].dropna().mode().iat[0]


# ---------- SECTOR SELECTOR --------------------------------------------------
sector_options = sorted(df["Sector"].dropna().astype(str).unique())
initial_sector = default_sector(df)

sector = st.selectbox(
    "Choose a sector:",
    options=sector_options,
    index=sector_options.index(initial_sector) if initial_sector in sector_options else 0,
)

sector_df = df[df["Sector"] == sector]

if sector_df.empty:
    st.error("No data found in this sector for the selected date.")
    st.stop()

# ---------- DISPLAY RAW DATA -------------------------------------------------
st.dataframe(sector_df, use_container_width=True)
st.markdown("<hr>", unsafe_allow_html=True)


# ---------- MARKET‑CAP PIE (inside chosen sector) ----------------------------
st.header(f"Market Cap Share inside **{sector}**")

# Upewniamy się, że mamy kolumnę numeryczną z kapitalizacją
if "Market cap clear" in sector_df.columns:
    sector_df["Market cap clear"] = pd.to_numeric(
        sector_df["Market cap clear"], errors="coerce"
    )
elif "Market cap" in sector_df.columns:
    sector_df["Market cap clear"] = sector_df["Market cap"].apply(parse_mcap)
else:
    sector_df["Market cap clear"] = None

sector_source = sector_df.dropna(subset=["Market cap clear"]).copy()
if sector_source.empty:
    st.warning("Market‑cap data missing; cannot draw sector pie chart.")
else:
    # suma kapitalizacji w sektorze
    total_sector_cap = sector_source["Market cap clear"].sum()
    st.metric(
        f"Total Market Cap — {sector}",
        f"{total_sector_cap / 1e9:,.2f} B USD",
    )

    # udział każdej spółki
    fig_sector_pie = px.pie(
        sector_source,
        names="Stock",
        values="Market cap clear",
        # title=f"{sector}: Company Share in Sector Market Cap",
        hover_data=["Market cap clear"],
        labels={"Market cap clear": "Market Cap"},
    )
    fig_sector_pie.update_layout(showlegend=False, height=650, width=650)
    st.plotly_chart(fig_sector_pie, use_container_width=False)

st.markdown("<hr>", unsafe_allow_html=True)

# ------------------------------------------------------------------
#  HISTORICAL CHART 2 – FORECAST USD vs PRICE  (full time range)
# ------------------------------------------------------------------
st.header("Mean Forecast Prices vs. Current Prices")
st.markdown("""Mean **High /Median /Low** forecast prices vs. mean **current price**
for the sector over the whole time series.
""")

sector_hist = df_full[df_full["Sector"] == sector]

forecast_usd_cols = ["High Forecast", "Median Forecast", "Low Forecast"]
cols_needed = forecast_usd_cols + ["Price", "Date of record"]

if any(col not in sector_hist.columns for col in cols_needed):
    st.warning("Required forecast‑price columns are missing in the data.")
else:
    usd_plot_df = (
        sector_hist[cols_needed]
        .groupby("Date of record", as_index=False)
        .mean(numeric_only=True)
        .sort_values("Date of record")
    )

    label_map = {
        "High Forecast": "High Forecast (mean)",
        "Median Forecast": "Mean Forecast",  # ← nowa etykieta
        "Low Forecast": "Low Forecast (mean)",
    }

    fig_usd = go.Figure()
    for col in forecast_usd_cols:
        fig_usd.add_trace(go.Scatter(
            x=usd_plot_df["Date of record"],
            y=usd_plot_df[col],
            mode="lines+markers",
            name=label_map[col]))

    fig_usd.add_trace(go.Scatter(
        x=usd_plot_df["Date of record"],
        y=usd_plot_df["Price"],
        mode="lines+markers",
        name="Current Price",
        line=dict(dash="dash", width=3, color="green"),
        marker=dict(size=4, color="green"),
        fill="tozeroy",
        fillcolor="rgba(0,255,0,0.20)",
    ))

    y_min = usd_plot_df[forecast_usd_cols + ["Price"]].min().min()
    y_max = usd_plot_df[forecast_usd_cols + ["Price"]].max().max()
    pad = 0.15 * (y_max - y_min or 1)

    fig_usd.update_layout(
        yaxis=dict(range=[y_min - pad, y_max + pad]),
        xaxis_title="Date",
        yaxis_title="Price (USD)",
    )
    st.plotly_chart(fig_usd, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ------------------------------------------------------------------
#  HISTORICAL CHART 3 – SMART SCORE (market-cap weighted)
# ------------------------------------------------------------------
st.header("Market-cap weighted Smart Score")
st.markdown("Average **Smart Score** for the selected sector over time, weighted by company market cap.")

smart_cols = ["Date of record", "Smart Score"]
if any(col not in sector_hist.columns for col in smart_cols):
    st.warning("Required Smart Score columns are missing in the data.")
else:
    smart_hist = sector_hist.copy()
    smart_hist["Smart Score"] = pd.to_numeric(
        smart_hist["Smart Score"].astype(str).str.replace(",", "."),
        errors="coerce"
    )

    # Build numeric market-cap weights
    if "Market cap clear" in smart_hist.columns:
        smart_hist["__mcap__"] = pd.to_numeric(smart_hist["Market cap clear"], errors="coerce")
    elif "Market cap" in smart_hist.columns:
        smart_hist["__mcap__"] = smart_hist["Market cap"].apply(parse_mcap)
    else:
        smart_hist["__mcap__"] = pd.NA

    smart_hist = smart_hist[
        smart_hist["Date of record"].notna()
        & smart_hist["Smart Score"].notna()
        & smart_hist["__mcap__"].notna()
        & (smart_hist["__mcap__"] > 0)
    ].copy()

    if smart_hist.empty:
        st.info("No valid data to compute market-cap weighted Smart Score for this sector.")
    else:
        smart_hist["__weighted__"] = smart_hist["Smart Score"] * smart_hist["__mcap__"]

        smart_plot_df = (
            smart_hist.groupby("Date of record", as_index=False)
            .agg(weighted_sum=("__weighted__", "sum"), mcap_sum=("__mcap__", "sum"))
            .sort_values("Date of record")
        )
        smart_plot_df["Weighted Smart Score"] = smart_plot_df["weighted_sum"] / smart_plot_df["mcap_sum"]

        fig_smart = go.Figure()
        fig_smart.add_trace(
            go.Scatter(
                x=smart_plot_df["Date of record"],
                y=smart_plot_df["Weighted Smart Score"],
                mode="lines+markers",
                name="Weighted Smart Score",
                hovertemplate="%{x|%Y-%m-%d}<br>Weighted Smart Score: %{y:.2f}<extra></extra>",
            )
        )
        fig_smart.update_layout(
            xaxis_title="Date",
            yaxis_title="Smart Score (weighted by market cap)",
            margin=dict(t=20),
        )
        st.plotly_chart(fig_smart, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)




# -------------------------------------------------
# Dividend Timeline – all payers in the sector
# -------------------------------------------------
st.header(f"Dividend Timeline – {sector}")

div_cols = ["Stock", "Ex-dividend date", "Dividend pay date", "Dividend yield"]
missing = [c for c in div_cols if c not in sector_df.columns]
if missing:
    st.warning(f"Missing dividend columns: {', '.join(missing)}")
else:
    # keep only rows with a positive dividend yield
    sector_div = sector_df[(sector_df["Dividend yield"].notna()) &
                           (sector_df["Dividend yield"] > 0)].copy()

    if sector_div.empty:
        st.info(f"No dividend-paying companies found in {sector}.")
    else:
        # date strings → datetime
        sector_div["Ex-dividend date"] = pd.to_datetime(sector_div["Ex-dividend date"],
                                                        errors="coerce")
        sector_div["Dividend pay date"] = pd.to_datetime(sector_div["Dividend pay date"],
                                                         errors="coerce")

        # build the timeline
        fig_div_tl = px.timeline(
            sector_div,
            x_start="Ex-dividend date",
            x_end="Dividend pay date",
            y="Stock",
            hover_data={
                "Stock": True,
                "Ex-dividend date": "|%Y-%m-%d",
                "Dividend pay date": "|%Y-%m-%d",
                # value is already in percent-points → avoid “×100” formatter
                "Dividend yield": ":.2f"
            },
            color="Stock",
            title=f"Ex-Dividend → Dividend Pay Dates ({sector}, {chosen_date})"
                    if chosen_date else
                  f"Ex-Dividend → Dividend Pay Dates ({sector})"
        )

        # focus the x-axis on a ±30/ +90 day window around today
        today = pd.Timestamp.now(tz=None).floor("D")
        fig_div_tl.update_xaxes(
            tickformat="%Y-%m-%d",
            range=[today - pd.DateOffset(days=30),
                   today + pd.DateOffset(days=90)],
            showgrid=True, gridcolor="rgba(128,128,128,0.2)"
        )
        fig_div_tl.update_yaxes(showgrid=True, gridcolor="rgba(64,64,64,0.2)")
        fig_div_tl.add_vline(
            x=today, line_width=2, line_dash="solid", line_color="rgba(0,128,0,0.8)"
        )
        fig_div_tl.update_layout(
            xaxis_title="Date",
            yaxis_title="Stock",
            height=min(100 + 35 * len(sector_div), 800),  # auto-height
            showlegend=False,
            dragmode="pan",
        )

        # quick summary metrics
        avg_yield = sector_div["Dividend yield"].mean()
        payer_cnt  = sector_div["Stock"].nunique()

        total_companies = sector_df["Stock"].nunique()  # liczba wszystkich spółek

        col1, col2, col3 = st.columns(3)
        col1.metric("All companies in sector", f"{total_companies}")
        col2.metric("Companies paying dividends", f"{payer_cnt}")
        col3.metric("Average Dividend Yield", f"{avg_yield:.2f}%")

        st.plotly_chart(fig_div_tl, use_container_width=True)

        # lista spółek bez dywidendy
        no_dividend_stocks = sector_df[sector_df["Dividend yield"].isna() | (sector_df["Dividend yield"] == 0)][
            "Stock"].unique()

        if len(no_dividend_stocks) > 0:
            st.markdown(f"**Companies in {sector} with no dividend:**")
            st.write(", ".join(no_dividend_stocks))
        else:
            st.info("All companies in this sector pay dividends.")

st.markdown("<hr>", unsafe_allow_html=True)

# ---------- AVERAGE P/E RATIO BY SECTOR -------------------------------------
st.header("Average P/E Ratio by Sector")

if "P/E ratio" not in df.columns:
    st.warning("Kolumna **'P/E ratio'** nie istnieje w danych – nie mogę narysować wykresu.")
else:
    # konwersja do float + odrzucenie ekstremalnych P/E (>1000)
    pe_df = df.copy()
    pe_df["P/E ratio"] = pd.to_numeric(pe_df["P/E ratio"], errors="coerce")
    pe_df = pe_df[(pe_df["P/E ratio"] <= 1000) | (pe_df["P/E ratio"].isna())]

    # ---------- GLOBAL P/E METRICS (nad wykresem) ---------------------------
    total_companies_global  = df["Stock"].nunique()
    # companies_with_valid_pe = pe_df["Stock"].nunique()
    avg_pe_global           = pe_df["P/E ratio"].median()

    col1, col2, col3 = st.columns(3)
    # col1.metric("All companies (selected date)", f"{total_companies_global}")
    # col2.metric("Companies with P/E ≤ 1000",     f"{companies_with_valid_pe}")
    col1.metric("Actual Average P/E in SP500",                   f"{avg_pe_global:.2f}")

    # ---------- ŚREDNIE P/E DLA SEKTORÓW ------------------------------------
    pe_by_sector = (
        pe_df.dropna(subset=["P/E ratio"])
             .groupby("Sector", as_index=False)["P/E ratio"]
             .mean()
             .sort_values("P/E ratio", ascending=False)
             .round(2)
    )

    if pe_by_sector.empty:
        st.info("Brak danych P/E dla wybranego dnia.")
    else:
        fig_pe = px.bar(
            pe_by_sector,
            x="Sector",
            y="P/E ratio",
            labels={"P/E ratio": "Average P/E"},
            title=f"Average P/E Ratio by Sector ({chosen_date})"
                   if chosen_date else
                   "Average P/E Ratio by Sector",
        )
        fig_pe.update_layout(
            xaxis_tickangle=-45,
            yaxis_title="Average P/E",
            xaxis_title="Sector",
            height=600,
            margin=dict(l=40, r=20, t=80, b=120),
        )
        st.plotly_chart(fig_pe, use_container_width=True)



# ---------- FOOTER -----------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    """
**Disclaimer:** Investing involves risk; you may lose some or all of your capital.  
This page is for **information only** and is **not** financial advice.
"""
)
st.markdown(
    """
<p style="font-size: 12px; text-align: left; color: gray;">
Website made by @Michał Ostaszewski
</p>
""",
    unsafe_allow_html=True,
)
