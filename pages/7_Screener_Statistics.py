import pandas as pd
import plotly.express as px
import streamlit as st

from app_auth import require_auth
from screener_statistics_data import (
    load_available_dates,
    load_sector_options,
    load_top_picks,
)
from stock_forecaster_data import performance_block


DATE_COL = "Date of record"

st.set_page_config(page_title="Algorithm Trend Analysis")
require_auth("Screener Statistics")

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

available_dates = load_available_dates()
if not available_dates:
    st.error("No screener statistics dates available in the database.")
    st.stop()

data_version = available_dates[-1].isoformat()
sector_options = ["All Sectors"] + load_sector_options(data_version)

st.sidebar.markdown("### Trend-analysis parameters")

start_date = st.sidebar.date_input(
    "Start date",
    value=available_dates[0],
    min_value=available_dates[0],
    max_value=available_dates[-1],
)
end_date = st.sidebar.date_input(
    "End date",
    value=available_dates[-1],
    min_value=available_dates[0],
    max_value=available_dates[-1],
)

if pd.Timestamp(start_date) > pd.Timestamp(end_date):
    st.sidebar.error("Start date must be before end date")
    st.stop()

top_n = st.sidebar.slider(
    "Number of top stocks per day",
    min_value=1,
    max_value=20,
    value=3,
    step=1,
    help="The algorithm will take the *N* highest-ranked stocks for **each** date.",
)

chosen_sector = st.sidebar.selectbox("Filter by sector", sector_options, index=0)

st.sidebar.markdown("#### Selection filters")
min_ss = st.sidebar.slider("Smart Score ≥", 0.0, 10.0, 7.0, 1.0)
min_sc = st.sidebar.slider("Score ≥", 0.0, 10.0, 2.0, 0.5)
max_sc = st.sidebar.slider("Score ≤", 0.0, 10.0, 6.0, 0.5)
min_lfp = st.sidebar.slider(
    "Low Forecast % ≥",
    -50.0,
    100.0,
    -5.0,
    0.5,
    help=(
        "This metric compares the current stock price to the lowest analyst forecast over the next 12 months. "
        "For example, a value of –5 means the minimum forecasted price can be no more than 5% below today’s price. "
        "You can also set a positive value – e.g. +10 means the minimum forecast must be at least 110% of the current price "
        "(i.e. $110 if today’s price is $100)."
    ),
)
min_an = st.sidebar.slider("Minimum number of analysts", 0, 100, 0, 1)

picks_df = load_top_picks(
    start_date=start_date,
    end_date=end_date,
    top_n=top_n,
    sector=chosen_sector,
    min_ss=min_ss,
    min_sc=min_sc,
    max_sc=max_sc,
    min_lfp=min_lfp,
    min_an=min_an,
    data_version=data_version,
)

selected_days = [day for day in available_dates if start_date <= day <= end_date]
total_days = len(selected_days)

st.header("Algorithm Trend Analysis")
st.caption(
    f"Date range: **{start_date}** → **{end_date}**  | "
    f"Top-{top_n} per day  | "
    f"{'Sector: ' + chosen_sector if chosen_sector != 'All Sectors' else 'All sectors'}  | "
    f"Filters → SS≥{min_ss}, Score∈[{min_sc},{max_sc}], LFP≥{min_lfp}%, Analysts≥{min_an}"
)

if picks_df.empty:
    st.warning("No stocks met the criteria in the selected interval.")
    st.stop()

freq_df = (
    picks_df.groupby("Stock", as_index=False)
    .size()
    .rename(columns={"size": "Occurrences"})
    .sort_values(["Occurrences", "Stock"], ascending=[False, True], ignore_index=True)
)

total_unique = len(freq_df)

m1, m2 = st.columns(2)
m1.metric("Unique stocks in selection", total_unique)
m2.metric("Total trading days analysed", total_days)

fig = px.bar(
    freq_df,
    x="Stock",
    y="Occurrences",
    title="How often did a stock appear in the daily Top list?",
    labels={"Occurrences": "Number of appearances"},
)
fig.update_layout(xaxis_title="Ticker", yaxis_title="Frequency")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Show data table"):
    st.dataframe(freq_df, use_container_width=True)

st.markdown("---")
st.subheader("Daily presence heat-map")

with performance_block("build_screener_heatmap"):
    heat_index = freq_df["Stock"].tolist()
    heat_cols = pd.to_datetime(selected_days)
    heat_source = picks_df.copy()
    heat_source[DATE_COL] = pd.to_datetime(heat_source[DATE_COL], errors="coerce")
    heat_source["Picked"] = 1
    heat_matrix = pd.crosstab(heat_source["Stock"], heat_source[DATE_COL])
    heat_matrix = heat_matrix.reindex(index=heat_index, columns=heat_cols, fill_value=0).astype(int)

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

st.markdown(
    """\
Please note: Investing involves risk and you may lose some or all of your capital.
This site is provided for informational purposes only and does not constitute financial advice.
"""
)

st.markdown(
    """
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""",
    unsafe_allow_html=True,
)
