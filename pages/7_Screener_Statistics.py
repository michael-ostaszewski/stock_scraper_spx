# ────────────────────────────────────────────────────────────────────────────────
# Algorithm Trend Analysis – how often do individual stocks land in our Top-N?
# ────────────────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from collections import Counter
from datetime import datetime

# ----------------------------------------------------------------------------- #
# Streamlit page config & global CSS
# ----------------------------------------------------------------------------- #
st.set_page_config(page_title="Algorithm Trend Analysis")

st.markdown(
    """
    <style>
    /* Bold metric values & labels */
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        font-weight: bold;
    }

    /* Full-width blue buttons */
    div.stButton > button {
        width: 100%;
        color: #ffffff;
        background-image: linear-gradient(to right, #034980, #0277bd);
        border: 2px solid #0277bd;
        font-size: 16px;
        font-weight: bold;
        transition: background-image 0.3s ease, transform 0.3s ease;
    }
    div.stButton > button:hover {
        background-image: linear-gradient(to right, #388e3c, #66bb6a);
        transform: scale(1.02);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------- #
# 1. Re-use the cached loader from the first page (import if the function exists)
# ----------------------------------------------------------------------------- #
try:
    df = load_data()  # noqa: F821  ← comes from your first page
except NameError:

    @st.cache_data
    def load_data():
        url = (
            "https://raw.githubusercontent.com/"
            "michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
        )
        return pd.read_csv(url, delimiter=";")

    df = load_data()

# Ensure the date column is datetime
DATE_COL = "Date of record"
df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

# ----------------------------------------------------------------------------- #
# 2. Sidebar – analysis parameters
# ----------------------------------------------------------------------------- #
st.sidebar.markdown("### Trend-analysis parameters")

# Date pickers (default: min → max available)
all_dates = sorted(d for d in df[DATE_COL].dropna().unique())
start_date = st.sidebar.date_input("Start date", value=all_dates[0])
end_date = st.sidebar.date_input("End date", value=all_dates[-1])

if pd.Timestamp(start_date) > pd.Timestamp(end_date):
    st.sidebar.error("Start date must be before end date")

# Slider: how many top stocks per day?
top_n = st.sidebar.slider(
    "Number of top stocks per day",
    min_value=1,
    max_value=20,
    value=3,
    step=1,
    help="The algorithm will take the *N* highest-ranked stocks for **each** date.",
)

# Sector filter
sector_options = ["All Sectors"] + sorted(df["Sector"].dropna().unique())
chosen_sector = st.sidebar.selectbox("Filter by sector", sector_options, index=0)

# Additional selection filters
st.sidebar.markdown("#### Selection filters")
min_ss = st.sidebar.slider("Smart Score ≥", 0.0, 10.0, 7.0, 1.0)
min_sc = st.sidebar.slider("Score ≥", 0.0, 10.0, 2.0, 0.5)
max_sc = st.sidebar.slider("Score ≤", 0.0, 10.0, 6.0, 0.5)
min_lfp = st.sidebar.slider("Low Forecast % ≥", -50.0, 100.0, -5.0, 0.5, help=(
        "This metric compares the current stock price to the lowest analyst forecast over the next 12 months. "
        "For example, a value of –5 means the minimum forecasted price can be no more than 5% below today’s price. "
        "You can also set a positive value – e.g. +10 means the minimum forecast must be at least 110% of the current price "
        "(i.e. $110 if today’s price is $100)."
    )
)
min_an = st.sidebar.slider("Minimum number of analysts", 0, 100, 0, 1)

# ----------------------------------------------------------------------------- #
# 3. Helper – replicate scoring filter (same logic as on the first page)
# ----------------------------------------------------------------------------- #
REQUIRED = [
    "Stock",
    "Sector",
    "Price",
    "Low Forecast Percent",
    "Median Forecast Percent",
    "High Forecast Percent",
    "Smart Score",
    "Score",
    "P/E ratio",
    "Number of analysts",
]


def daily_scoring(day_df: pd.DataFrame, sector: str, n: int) -> pd.DataFrame:
    """Return the Top-*n* stocks for a single day after applying the dynamic filter."""
    sc = day_df[REQUIRED].sort_values("Score", ascending=False, ignore_index=True)

    sc = sc[
        (sc["Smart Score"] >= min_ss)
        & (sc["Score"] >= min_sc)
        & (sc["Score"] <= max_sc)
        & (sc["Low Forecast Percent"] >= min_lfp)
        & (sc["Number of analysts"] >= min_an)
    ]

    if sector != "All Sectors":
        sc = sc[sc["Sector"] == sector]

    return sc.head(n)


# ----------------------------------------------------------------------------- #
# 4. Crunch the numbers across the chosen date range
# ----------------------------------------------------------------------------- #
mask_range = (df[DATE_COL] >= pd.Timestamp(start_date)) & (
    df[DATE_COL] <= pd.Timestamp(end_date)
)
df_range = df[mask_range].copy()

unique_stocks: list[str] = []
daily_counter: list[Counter] = []

for day, day_df in df_range.groupby(DATE_COL):
    picks = daily_scoring(day_df, chosen_sector, top_n)
    unique_stocks.extend(picks["Stock"].tolist())
    daily_counter.append(Counter(picks["Stock"].tolist()))

# Aggregate counts
freq = Counter(unique_stocks)

st.header("Algorithm Trend Analysis")
st.caption(
    f"Date range: **{start_date}** → **{end_date}**  | "
    f"Top-{top_n} per day  | "
    f"{'Sector: ' + chosen_sector if chosen_sector != 'All Sectors' else 'All sectors'}  | "
    f"Filters → SS≥{min_ss}, Score∈[{min_sc},{max_sc}], LFP≥{min_lfp}%, Analysts≥{min_an}"
)

# ----------------------------------------------------------------------------- #
# 5. Display results
# ----------------------------------------------------------------------------- #
if not freq:
    st.warning("No stocks met the criteria in the selected interval.")
    st.stop()

# Counter → DataFrame and sort by frequency
freq_df = pd.DataFrame(freq.items(), columns=["Stock", "Occurrences"]).sort_values(
    "Occurrences", ascending=False, ignore_index=True
)

total_unique = len(freq_df)
total_days = len(df_range[DATE_COL].unique())

# --- METRICS (now above the chart, full width, bold via CSS) ------------------ #
m1, m2 = st.columns(2)
m1.metric("Unique stocks in selection", total_unique)
m2.metric("Total trading days analysed", total_days)

# --- BAR CHART --------------------------------------------------------------- #
fig = px.bar(
    freq_df,
    x="Stock",
    y="Occurrences",
    title="How often did a stock appear in the daily Top list?",
    labels={"Occurrences": "Number of appearances"},
)
fig.update_layout(xaxis_title="Ticker", yaxis_title="Frequency")
st.plotly_chart(fig, use_container_width=True)

# Optional raw table
with st.expander("Show data table"):
    st.dataframe(freq_df, use_container_width=True)

# ----------------------------------------------------------------------------- #
# 6. Heat-map – daily presence of each frequent stock
# ----------------------------------------------------------------------------- #
st.markdown("---")
st.subheader("Daily presence heat-map")

# (Opcjonalny checkbox – zostawiony w komentarzu; odkomentuj, jeśli zechcesz wrócić
#  do wersji „on-demand”)
# if not st.checkbox("Display heat-map (may be slow on large ranges)"):
#     st.stop()

# Build presence matrix
heat_index = sorted(freq)  # stable ticker order
heat_cols = sorted(df_range[DATE_COL].unique())
heat_matrix = pd.DataFrame(0, index=heat_index, columns=heat_cols, dtype=int)

for (day, _), counter in zip(df_range.groupby(DATE_COL), daily_counter):
    for ticker in counter:
        heat_matrix.at[ticker, day] = 1

# Discrete colour scale: white (0) / blue (1)
colorscale = [(0.0, "#1f77b4"), (1.0, "#ffffff")]

fig_hm = px.imshow(
    heat_matrix,
    aspect="auto",
    title="Presence (1) / absence (0) of each stock in the Top-N list",
    labels=dict(x="Date", y="Stock", color="Picked"),
    color_continuous_scale=colorscale,
    zmin=0,
    zmax=1,
)
fig_hm.update_coloraxes(
    colorbar=dict(tickmode="array", tickvals=[0, 1], ticktext=["0", "1"])
)

st.plotly_chart(fig_hm, use_container_width=True)

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
