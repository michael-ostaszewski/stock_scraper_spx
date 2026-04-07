import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sector_explorer_data import (
    load_available_dates,
    load_sector_day_snapshot,
    load_sector_history_metrics,
    performance_block,
)


st.set_page_config(page_title="Sector Explorer")

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {
        font-weight: bold;
    }
    [data-testid="stMetricLabel"] {
        font-weight: bold;
    }
    div.stButton > button {
        width: 100%;
        color: #ffffff;
        background-image: linear-gradient(to right, #034980, #0277bd);
        border: 2px solid #0277bd;
        font-size: 16px;
        font-weight: bold;
        transition: background-image 0.3s ease, transform 0.3s ease;
    }
    .full-width-blue-button > button:hover {
        background-image: linear-gradient(to right, #388e3c, #66bb6a);
        transform: scale(1.02);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Sector Explorer")
st.markdown(
    """
    Explore S&P 500 companies **by sector** and **by date**.
    Use the sidebar to pick a trading date; the default is the most recent
    date available in the data set.
    """
)


def parse_mcap(value: str):
    if not isinstance(value, str):
        return None

    match = re.fullmatch(r"\s*([\d.,]+)\s*([BMKbmk]?)\s*", value)
    if not match:
        return None

    num, suffix = match.groups()
    num = float(num.replace(",", "").replace(" ", ""))
    factor = {"B": 1e9, "M": 1e6, "K": 1e3, "": 1}.get(suffix.upper(), 1)
    return num * factor


def default_sector(data: pd.DataFrame) -> str:
    if "Market cap clear" in data.columns and pd.api.types.is_numeric_dtype(data["Market cap clear"]):
        total_market_cap = data.groupby("Sector")["Market cap clear"].sum(numeric_only=True)
        if not total_market_cap.empty:
            return total_market_cap.idxmax()

    if "Market cap" in data.columns:
        tmp = data.copy()
        tmp["__mcap__"] = tmp["Market cap"].apply(parse_mcap)
        total_market_cap = tmp.groupby("Sector")["__mcap__"].sum(min_count=1)
        if total_market_cap.notna().any():
            return total_market_cap.idxmax()

    return data["Sector"].dropna().mode().iat[0]


available_dates = load_available_dates()
if not available_dates:
    st.error("No dates available in the database.")
    st.stop()

default_date = available_dates[-1]
chosen_date = st.sidebar.date_input(
    "Date selector",
    value=default_date,
    min_value=available_dates[0],
    max_value=default_date,
)
data_version = default_date.isoformat()

day_df = load_sector_day_snapshot(chosen_date, data_version)
if day_df.empty:
    st.error("No data for the selected date.")
    st.stop()

if "Sector" not in day_df.columns:
    st.error("Column **'Sector'** not found in the data – can't build Sector Explorer.")
    st.stop()

sector_options = sorted(day_df["Sector"].dropna().astype(str).unique())
initial_sector = default_sector(day_df)

sector = st.selectbox(
    "Choose a sector:",
    options=sector_options,
    index=sector_options.index(initial_sector) if initial_sector in sector_options else 0,
)

sector_df = day_df[day_df["Sector"] == sector].copy()
if sector_df.empty:
    st.error("No data found in this sector for the selected date.")
    st.stop()

sector_history_df = load_sector_history_metrics(sector, data_version)

st.dataframe(sector_df, use_container_width=True)
st.markdown("<hr>", unsafe_allow_html=True)


st.header(f"Market Cap Share inside **{sector}**")

if "Market cap clear" in sector_df.columns:
    sector_source = sector_df.copy()
    sector_source["Market cap clear"] = pd.to_numeric(sector_source["Market cap clear"], errors="coerce")
elif "Market cap" in sector_df.columns:
    sector_source = sector_df.copy()
    sector_source["Market cap clear"] = sector_source["Market cap"].apply(parse_mcap)
else:
    sector_source = sector_df.copy()
    sector_source["Market cap clear"] = None

sector_source = sector_source.dropna(subset=["Market cap clear"]).copy()
if sector_source.empty:
    st.warning("Market‑cap data missing; cannot draw sector pie chart.")
else:
    total_sector_cap = sector_source["Market cap clear"].sum()
    st.metric(
        f"Total Market Cap — {sector}",
        f"{total_sector_cap / 1e9:,.2f} B USD",
    )

    fig_sector_pie = px.pie(
        sector_source,
        names="Stock",
        values="Market cap clear",
        hover_data=["Market cap clear"],
        labels={"Market cap clear": "Market Cap"},
    )
    fig_sector_pie.update_layout(showlegend=False, height=650, width=650)
    st.plotly_chart(fig_sector_pie, use_container_width=False)

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Mean Forecast Prices vs. Current Prices")
st.markdown(
    """
    Mean **High /Median /Low** forecast prices vs. mean **current price**
    for the sector over the whole time series.
    """
)

forecast_usd_cols = ["High Forecast", "Median Forecast", "Low Forecast"]
forecast_cols_needed = ["Date of record", "Price"] + forecast_usd_cols

if any(column not in sector_history_df.columns for column in forecast_cols_needed):
    st.warning("Required forecast‑price columns are missing in the data.")
else:
    with performance_block("build_sector_forecast_history_chart"):
        usd_plot_df = (
            sector_history_df[forecast_cols_needed]
            .dropna(subset=["Date of record"])
            .sort_values("Date of record")
        )

        if usd_plot_df.empty:
            st.info("No historical forecast-price data available for this sector.")
        else:
            label_map = {
                "High Forecast": "High Forecast (mean)",
                "Median Forecast": "Mean Forecast",
                "Low Forecast": "Low Forecast (mean)",
            }

            fig_usd = go.Figure()
            for column in forecast_usd_cols:
                fig_usd.add_trace(
                    go.Scatter(
                        x=usd_plot_df["Date of record"],
                        y=usd_plot_df[column],
                        mode="lines+markers",
                        name=label_map[column],
                    )
                )

            fig_usd.add_trace(
                go.Scatter(
                    x=usd_plot_df["Date of record"],
                    y=usd_plot_df["Price"],
                    mode="lines+markers",
                    name="Current Price",
                    line=dict(dash="dash", width=3, color="green"),
                    marker=dict(size=4, color="green"),
                    fill="tozeroy",
                    fillcolor="rgba(0,255,0,0.20)",
                )
            )

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


st.header("Market-cap weighted Smart Score")
st.markdown("Average **Smart Score** for the selected sector over time, weighted by company market cap.")

smart_cols = ["Date of record", "Weighted Smart Score"]
if any(column not in sector_history_df.columns for column in smart_cols):
    st.warning("Required Smart Score columns are missing in the data.")
else:
    with performance_block("build_sector_smart_score_chart"):
        smart_plot_df = (
            sector_history_df[smart_cols]
            .dropna(subset=["Date of record", "Weighted Smart Score"])
            .sort_values("Date of record")
        )

        if smart_plot_df.empty:
            st.info("No valid data to compute market-cap weighted Smart Score for this sector.")
        else:
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


st.header(f"Dividend Timeline – {sector}")

div_cols = ["Stock", "Ex-dividend date", "Dividend pay date", "Dividend yield"]
missing_dividend_cols = [column for column in div_cols if column not in sector_df.columns]
if missing_dividend_cols:
    st.warning(f"Missing dividend columns: {', '.join(missing_dividend_cols)}")
else:
    sector_div = sector_df[
        sector_df["Dividend yield"].notna() & (sector_df["Dividend yield"] > 0)
    ].copy()

    if sector_div.empty:
        st.info(f"No dividend-paying companies found in {sector}.")
    else:
        sector_div["Ex-dividend date"] = pd.to_datetime(sector_div["Ex-dividend date"], errors="coerce")
        sector_div["Dividend pay date"] = pd.to_datetime(sector_div["Dividend pay date"], errors="coerce")

        fig_div_tl = px.timeline(
            sector_div,
            x_start="Ex-dividend date",
            x_end="Dividend pay date",
            y="Stock",
            hover_data={
                "Stock": True,
                "Ex-dividend date": "|%Y-%m-%d",
                "Dividend pay date": "|%Y-%m-%d",
                "Dividend yield": ":.2f",
            },
            color="Stock",
            title=f"Ex-Dividend → Dividend Pay Dates ({sector}, {chosen_date})",
        )

        today = pd.Timestamp.now(tz=None).floor("D")
        fig_div_tl.update_xaxes(
            tickformat="%Y-%m-%d",
            range=[today - pd.DateOffset(days=30), today + pd.DateOffset(days=90)],
            showgrid=True,
            gridcolor="rgba(128,128,128,0.2)",
        )
        fig_div_tl.update_yaxes(showgrid=True, gridcolor="rgba(64,64,64,0.2)")
        fig_div_tl.add_vline(
            x=today,
            line_width=2,
            line_dash="solid",
            line_color="rgba(0,128,0,0.8)",
        )
        fig_div_tl.update_layout(
            xaxis_title="Date",
            yaxis_title="Stock",
            height=min(100 + 35 * len(sector_div), 800),
            showlegend=False,
            dragmode="pan",
        )

        avg_yield = sector_div["Dividend yield"].mean()
        payer_cnt = sector_div["Stock"].nunique()
        total_companies = sector_df["Stock"].nunique()

        col1, col2, col3 = st.columns(3)
        col1.metric("All companies in sector", f"{total_companies}")
        col2.metric("Companies paying dividends", f"{payer_cnt}")
        col3.metric("Average Dividend Yield", f"{avg_yield:.2f}%")

        st.plotly_chart(fig_div_tl, use_container_width=True)

        no_dividend_stocks = sector_df[
            sector_df["Dividend yield"].isna() | (sector_df["Dividend yield"] == 0)
        ]["Stock"].unique()

        if len(no_dividend_stocks) > 0:
            st.markdown(f"**Companies in {sector} with no dividend:**")
            st.write(", ".join(no_dividend_stocks))
        else:
            st.info("All companies in this sector pay dividends.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Average P/E Ratio by Sector")

if "P/E ratio" not in day_df.columns:
    st.warning("Kolumna **'P/E ratio'** nie istnieje w danych – nie mogę narysować wykresu.")
else:
    pe_df = day_df.copy()
    pe_df["P/E ratio"] = pd.to_numeric(pe_df["P/E ratio"], errors="coerce")
    pe_df = pe_df[(pe_df["P/E ratio"] <= 1000) | (pe_df["P/E ratio"].isna())]

    avg_pe_global = pe_df["P/E ratio"].median()

    col1, _, _ = st.columns(3)
    col1.metric("Actual Average P/E in SP500", f"{avg_pe_global:.2f}")

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
            title=f"Average P/E Ratio by Sector ({chosen_date})",
        )
        fig_pe.update_layout(
            xaxis_tickangle=-45,
            yaxis_title="Average P/E",
            xaxis_title="Sector",
            height=600,
            margin=dict(l=40, r=20, t=80, b=120),
        )
        st.plotly_chart(fig_pe, use_container_width=True)


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
Website made by @Michał Ostaszewski
</p>
""",
    unsafe_allow_html=True,
)
