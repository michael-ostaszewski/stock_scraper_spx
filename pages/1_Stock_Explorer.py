import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app_auth import require_auth
from stock_explorer_data import load_company_history, normalize_ticker, performance_block

require_auth("Stock Explorer")


def split_range(range_value: str):
    if pd.isna(range_value):
        return [np.nan, np.nan]

    parts = str(range_value).replace("\n", " ").split()
    if len(parts) != 2:
        return [np.nan, np.nan]

    try:
        low, high = map(float, parts)
    except ValueError:
        return [np.nan, np.nan]

    return [min(low, high), max(low, high)]


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
    </style>
    """,
    unsafe_allow_html=True,
)


st.title("Explore details of the chosen Stock")
st.markdown(
    """
    Enter the ticker symbol of a company to view all available details from our database.
    """
)

ticker_input = st.text_input("Type in a Stock Ticker (e.g. META)", value="")
ticker = normalize_ticker(ticker_input)

company_details = None
if ticker:
    company_details = load_company_history(ticker)
    if company_details.empty:
        company_details = None
        st.error(f"No data found for ticker '{ticker}'.")
    else:
        st.dataframe(company_details.drop(columns=["Ingested at"], errors="ignore"))
else:
    st.info("Please enter a ticker symbol to view company details.")

has_company = company_details is not None and not company_details.empty

st.markdown("<hr>", unsafe_allow_html=True)


st.header("12-Month Forecast Returns")
st.markdown(
    """
    This boxplot displays the 12-month upside forecasts for S&P 500 companies by showing the highest, median, and lowest
    forecasted percentage increases over the current price. The optimal scenario is when all three forecast metrics are
    above 0% (in the green area), indicating that even the worst-case forecast predicts a price increase.
    This visualization serves as a quick indicator of which sectors are expected to perform positively over the next year.
    """
)

if has_company:
    forecast_percent_cols = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]
    required_cols_percent = ["Date of record"] + forecast_percent_cols
    missing_percent = [col for col in required_cols_percent if col not in company_details.columns]

    if missing_percent:
        st.error(f"Missing columns for forecast percentages: {missing_percent}")
    else:
        df_percent = company_details[required_cols_percent].melt(
            id_vars="Date of record",
            value_vars=forecast_percent_cols,
            var_name="Forecast Type",
            value_name="Value",
        )
        df_percent = df_percent.dropna(subset=["Date of record", "Value"])

        if df_percent.empty:
            st.info("Forecast percentage data is not available for this ticker.")
        else:
            fig_percent = go.Figure()
            for forecast in forecast_percent_cols:
                df_temp = df_percent[df_percent["Forecast Type"] == forecast]
                fig_percent.add_trace(
                    go.Scatter(
                        x=df_temp["Date of record"],
                        y=df_temp["Value"],
                        mode="lines+markers",
                        name=forecast,
                    )
                )

            y_min_data = df_percent["Value"].min()
            y_max_data = df_percent["Value"].max()
            padding = 0.15 * (y_max_data - y_min_data) if y_max_data != y_min_data else 1
            extended_y_min = y_min_data - padding
            extended_y_max = y_max_data + padding

            fig_percent.update_layout(
                yaxis=dict(range=[extended_y_min, extended_y_max]),
                shapes=[
                    dict(
                        type="rect",
                        xref="paper",
                        yref="y",
                        x0=0,
                        x1=1,
                        y0=-5000,
                        y1=0,
                        fillcolor="rgba(255,0,0,0.2)",
                        line_width=0,
                    ),
                    dict(
                        type="rect",
                        xref="paper",
                        yref="y",
                        x0=0,
                        x1=1,
                        y0=0,
                        y1=5000,
                        fillcolor="rgba(0,255,0,0.2)",
                        line_width=0,
                    ),
                ],
                xaxis_title="Date",
                yaxis_title="Forecast (%)",
            )
            st.plotly_chart(fig_percent)
else:
    st.info("Please enter a valid ticker symbol to view forecast percentage trends.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Forecast Price vs. Current Price Trends")
st.markdown(
    """
    This combined line chart shows both the forecasted prices (High, Median, and Low Forecast) and the current
    price of the stock over time. Analysts’ forecast lines provide insight into expected future values, while the
    current price is highlighted with a distinct dashed line and green color. An attractive buying opportunity is suggested
    when the current price is below the lowest forecast, whereas a current price above all forecasted values may
    signal a strong sell recommendation.
    """
)

if has_company:
    forecast_usd_cols = ["High Forecast", "Median Forecast", "Low Forecast"]
    required_cols_usd = ["Date of record", "Price"] + forecast_usd_cols
    missing_usd = [col for col in required_cols_usd if col not in company_details.columns]

    if missing_usd:
        st.error(f"Missing columns for forecast prices: {missing_usd}")
    else:
        df_usd = company_details[["Date of record"] + forecast_usd_cols].melt(
            id_vars="Date of record",
            value_vars=forecast_usd_cols,
            var_name="Forecast Type",
            value_name="Forecast Value",
        )
        df_usd = df_usd.dropna(subset=["Date of record", "Forecast Value"])
        current_price_df = company_details[["Date of record", "Price"]].dropna(subset=["Date of record", "Price"])

        if df_usd.empty or current_price_df.empty:
            st.info("Forecast price data is not available for this ticker.")
        else:
            fig_combined = go.Figure()
            for forecast in forecast_usd_cols:
                df_temp = df_usd[df_usd["Forecast Type"] == forecast]
                fig_combined.add_trace(
                    go.Scatter(
                        x=df_temp["Date of record"],
                        y=df_temp["Forecast Value"],
                        mode="lines+markers",
                        name=forecast,
                    )
                )

            fig_combined.add_trace(
                go.Scatter(
                    x=current_price_df["Date of record"],
                    y=current_price_df["Price"],
                    mode="lines+markers",
                    name="Current Price",
                    line=dict(dash="dash", width=3, color="green"),
                    marker=dict(size=4, color="green"),
                    fill="tozeroy",
                    fillcolor="rgba(0,255,0,0.2)",
                )
            )

            forecast_y_min = df_usd["Forecast Value"].min()
            forecast_y_max = df_usd["Forecast Value"].max()
            current_y_min = current_price_df["Price"].min()
            current_y_max = current_price_df["Price"].max()
            combined_y_min = min(forecast_y_min, current_y_min)
            combined_y_max = max(forecast_y_max, current_y_max)
            padding_combined = 0.15 * (combined_y_max - combined_y_min) if combined_y_max != combined_y_min else 1
            extended_y_min = combined_y_min - padding_combined
            extended_y_max = combined_y_max + padding_combined

            fig_combined.update_layout(
                yaxis=dict(range=[extended_y_min, extended_y_max]),
                xaxis_title="Date",
                yaxis_title="Price (USD)",
            )
            st.plotly_chart(fig_combined)
else:
    st.info("Please enter a valid ticker symbol to view forecast and current price trends.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Dividend Timeline & Yield")

if has_company:
    has_dividend = company_details["Dividend yield"].notna() & (company_details["Dividend yield"] > 0)

    if has_dividend.any():
        div_cols = ["Ex-dividend date", "Dividend pay date", "Dividend yield", "Stock"]
        missing_div_cols = [col for col in div_cols if col not in company_details.columns]

        if missing_div_cols:
            st.error(f"Missing columns for dividend information: {missing_div_cols}")
        else:
            df_div = company_details.loc[has_dividend, div_cols].dropna(
                subset=["Ex-dividend date", "Dividend pay date", "Dividend yield"]
            )

            if df_div.empty:
                st.info("Dividend timeline data is not available for this ticker.")
            else:
                latest_yield = df_div["Dividend yield"].iloc[-1]
                latest_price = company_details["Price"].dropna().iloc[-1]
                latest_dividend_usd = latest_price * (latest_yield / 100)

                col1, col2 = st.columns(2)
                col1.metric("Latest dividend yield", f"{latest_yield:.2f}%")
                col2.metric("Yearly dividend value in USD per share", f"${latest_dividend_usd:.2f}")

                df_div = df_div.copy()
                df_div["Dividend yield"] = df_div["Dividend yield"] / 100

                fig_timeline = px.timeline(
                    df_div,
                    x_start="Ex-dividend date",
                    x_end="Dividend pay date",
                    y="Stock",
                    hover_data={
                        "Stock": True,
                        "Ex-dividend date": "|%Y-%m-%d",
                        "Dividend pay date": "|%Y-%m-%d",
                        "Dividend yield": ":.2%",
                    },
                    color="Stock",
                    title="Timeline: Ex-Dividend and Dividend Pay Dates",
                )

                today = pd.Timestamp.now().floor("D")
                fig_timeline.update_xaxes(
                    tickformat="%Y-%m-%d",
                    range=[today - pd.DateOffset(days=30), today + pd.DateOffset(days=90)],
                    showgrid=True,
                    gridcolor="rgba(128,128,128,0.2)",
                )
                fig_timeline.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
                fig_timeline.add_vline(
                    x=today,
                    line_width=2,
                    line_dash="solid",
                    line_color="rgba(0,0,0,0.8)",
                )
                fig_timeline.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Stock",
                    height=450,
                    dragmode="pan",
                    showlegend=False,
                )

                st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("This company currently does **not** pay a dividend.")
else:
    st.info("Please enter a valid ticker symbol to view dividend information.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Smart Score Trend Over Time")
st.markdown(
    """
    The **Smart Score** (scale **1 – 10**) is a composite rating that blends eight
    fundamental and market-based factors into a single number. The line chart below shows how the score has evolved for the
    selected ticker across all dates available in the database.
    """
)

if has_company:
    if "Smart Score" in company_details.columns:
        df_score = company_details[["Date of record", "Smart Score"]].dropna(subset=["Date of record", "Smart Score"])

        if df_score.empty:
            st.info("Smart Score data not available for this company.")
        else:
            num_sessions = len(df_score)
            avg_smartscore = df_score["Smart Score"].mean()

            col1, col2 = st.columns(2)
            col1.metric("Trading sessions in data set", f"{num_sessions}")
            col2.metric("Average Smart Score", f"{avg_smartscore:.2f}")

            fig_score = go.Figure()
            fig_score.add_trace(
                go.Scatter(
                    x=df_score["Date of record"],
                    y=df_score["Smart Score"],
                    mode="lines+markers",
                    name="Smart Score",
                )
            )
            fig_score.update_layout(
                xaxis_title="Date",
                yaxis_title="Smart Score (1–10)",
                yaxis=dict(range=[0, 10], dtick=1),
            )
            st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.info("Smart Score data not available for this company.")
else:
    st.info("Please enter a valid ticker symbol to view Smart Score trends.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Custom Metric Explorer")
st.markdown(
    """
    Pick any numeric columns to plot their historical trend. P/E ratio is selected by default.
    """
)

if has_company:
    numeric_cols = sorted(
        column for column in company_details.columns if pd.api.types.is_numeric_dtype(company_details[column])
    )
    default_metrics = ["P/E ratio"] if "P/E ratio" in numeric_cols else []

    selected_metrics = st.multiselect(
        "Select metrics to display:",
        options=numeric_cols,
        default=default_metrics,
    )

    if selected_metrics:
        with performance_block("build_custom_metric_chart"):
            df_plot = company_details[["Date of record"] + selected_metrics].dropna(subset=["Date of record"])

            fig_custom = go.Figure()
            for metric in selected_metrics:
                fig_custom.add_trace(
                    go.Scatter(
                        x=df_plot["Date of record"],
                        y=df_plot[metric],
                        mode="lines+markers",
                        name=metric,
                    )
                )

            fig_custom.update_layout(
                xaxis_title="Date",
                yaxis_title="Metric value",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=400,
            )
            st.plotly_chart(fig_custom, use_container_width=True)
    else:
        st.info("Choose at least one metric to draw the chart.")
else:
    st.info("Please enter a valid ticker symbol to explore custom metrics.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("12-Month Price Target Backtest")
st.markdown(
    """
    This section evaluates how often a stock reached analysts' **12-month price targets**.
    For each forecast date, we look for the stock price approximately **1 year later**.
    If there is no session exactly one year later, we match the **nearest available trading session** within a tolerance window
    (preferably the first session **after** the target date, otherwise the closest session **before** it).
    """
)

if has_company:
    col_a, col_b, col_c = st.columns([1, 1, 2])

    tolerance_days = col_a.number_input(
        "Matching tolerance (days)",
        min_value=1,
        max_value=60,
        value=10,
        step=1,
        help="Maximum allowed gap (in days) between the target date (forecast_date + 1 year) and the matched trading session.",
    )
    min_samples = col_b.number_input(
        "Minimum sample size for metrics",
        min_value=3,
        max_value=200,
        value=10,
        step=1,
        help="If the number of evaluated points is below this threshold, a small-sample warning will be shown.",
    )
    show_table = col_c.checkbox(
        "Show matching diagnostics table",
        value=False,
        help="Displays a diagnostic table with the matched session date and the computed forecast errors.",
    )

    required_cols = ["Date of record", "Price", "High Forecast", "Median Forecast", "Low Forecast"]
    missing_cols = [column for column in required_cols if column not in company_details.columns]

    if missing_cols:
        st.error(f"Missing required columns for backtest: {missing_cols}")
    else:
        with performance_block("build_backtest_charts"):
            df_bt = company_details[required_cols].dropna(subset=["Date of record", "Price"]).copy()
            df_bt = df_bt.sort_values("Date of record").drop_duplicates(subset=["Date of record"], keep="last")

            price_series = df_bt[["Date of record", "Price"]].rename(
                columns={"Date of record": "price_date", "Price": "actual_price"}
            )
            pred = df_bt[["Date of record", "Price", "High Forecast", "Median Forecast", "Low Forecast"]].copy()
            pred = pred.dropna(subset=["Median Forecast"])
            pred = pred.rename(columns={"Date of record": "forecast_date", "Price": "price_at_forecast"})

            if pred.empty:
                st.info("No usable forecast records for this ticker (e.g., Median Forecast is missing).")
            else:
                max_date = price_series["price_date"].max()
                pred["target_date"] = pred["forecast_date"] + pd.DateOffset(years=1)
                pred_eval = pred[pred["target_date"] <= max_date].copy()

                if pred_eval.empty:
                    st.info(
                        "There are no forecast points that can be evaluated yet for this ticker "
                        "(the 12M target date falls outside the available price history)."
                    )
                else:
                    pred_eval = pred_eval.sort_values("target_date")
                    tolerance = pd.Timedelta(days=int(tolerance_days))

                    matched_forward = pd.merge_asof(
                        pred_eval,
                        price_series,
                        left_on="target_date",
                        right_on="price_date",
                        direction="forward",
                        tolerance=tolerance,
                    ).rename(columns={"price_date": "matched_date_fwd", "actual_price": "actual_price_fwd"})

                    matched_backward = pd.merge_asof(
                        pred_eval,
                        price_series,
                        left_on="target_date",
                        right_on="price_date",
                        direction="backward",
                        tolerance=tolerance,
                    ).rename(columns={"price_date": "matched_date_bwd", "actual_price": "actual_price_bwd"})

                    merged = matched_forward.copy()
                    merged["matched_date"] = merged["matched_date_fwd"]
                    merged["actual_price_12m"] = merged["actual_price_fwd"]
                    merged["match_direction"] = np.where(merged["actual_price_12m"].notna(), "forward", None)

                    need_backward = merged["actual_price_12m"].isna()
                    merged.loc[need_backward, "matched_date"] = matched_backward.loc[need_backward, "matched_date_bwd"]
                    merged.loc[need_backward, "actual_price_12m"] = matched_backward.loc[
                        need_backward, "actual_price_bwd"
                    ]
                    merged.loc[
                        need_backward & merged["actual_price_12m"].notna(),
                        "match_direction",
                    ] = "backward"

                    merged_ok = merged.dropna(subset=["actual_price_12m", "matched_date"]).copy()

                    total_candidates = len(pred_eval)
                    evaluated = len(merged_ok)
                    coverage = evaluated / total_candidates if total_candidates else 0.0

                    if merged_ok.empty:
                        st.warning(
                            "No sessions could be matched to the 12M target date within the selected tolerance. "
                            "Try increasing the tolerance or check data completeness."
                        )
                    else:
                        merged_ok["hit_low"] = merged_ok["actual_price_12m"] >= merged_ok["Low Forecast"]
                        merged_ok["hit_median"] = merged_ok["actual_price_12m"] >= merged_ok["Median Forecast"]
                        merged_ok["hit_high"] = merged_ok["actual_price_12m"] >= merged_ok["High Forecast"]
                        merged_ok["within_range"] = (
                            (merged_ok["actual_price_12m"] >= merged_ok["Low Forecast"])
                            & (merged_ok["actual_price_12m"] <= merged_ok["High Forecast"])
                        )

                        def pct_err(actual, forecast):
                            return (actual - forecast) / forecast * 100.0

                        for tag, column in [
                            ("low", "Low Forecast"),
                            ("median", "Median Forecast"),
                            ("high", "High Forecast"),
                        ]:
                            merged_ok[f"err_{tag}_pct"] = np.where(
                                merged_ok[column].notna() & (merged_ok[column] != 0),
                                pct_err(merged_ok["actual_price_12m"], merged_ok[column]),
                                np.nan,
                            )

                        mae_median = merged_ok["err_median_pct"].abs().mean()
                        med_err_median = merged_ok["err_median_pct"].median()

                        m1, m2, m3, m4 = st.columns(4)
                        m5, m6, m7 = st.columns(3)

                        m1.metric(
                            "Evaluable records",
                            f"{evaluated}/{total_candidates}",
                            f"{coverage * 100:.1f}% coverage",
                            help=(
                                "How many forecast records can be evaluated with a ~12M outcome. "
                                "Numerator: records for which a trading session was found within the tolerance window. "
                                "Denominator: records whose 12M target date is within your available price history."
                            ),
                        )
                        m2.metric(
                            "Hit-rate: Low target",
                            f"{merged_ok['hit_low'].mean() * 100:.1f}%",
                            help="Share of cases where the ~12M price was >= the Low Forecast target.",
                        )
                        m3.metric(
                            "Hit-rate: Median target",
                            f"{merged_ok['hit_median'].mean() * 100:.1f}%",
                            help="Share of cases where the ~12M price was >= the Median Forecast target.",
                        )
                        m4.metric(
                            "Within [Low, High]",
                            f"{merged_ok['within_range'].mean() * 100:.1f}%",
                            help="Share of cases where the ~12M price fell between Low Forecast and High Forecast (inclusive).",
                        )
                        m5.metric(
                            "Mean |median error|",
                            f"{mae_median:.2f}%",
                            help=(
                                "Mean absolute percentage error for the median target: "
                                "|(Actual - MedianForecast) / MedianForecast| * 100. Lower is better."
                            ),
                        )
                        m6.metric(
                            "Median median-error",
                            f"{med_err_median:.2f}%",
                            help=(
                                "Median of the percentage error for the median target: "
                                "(Actual - MedianForecast) / MedianForecast * 100. "
                                "Positive means the actual price was higher than the forecast."
                            ),
                        )
                        m7.metric(
                            "High target reached",
                            f"{merged_ok['hit_high'].mean() * 100:.1f}%",
                            help="Share of cases where the ~12M price was >= the High Forecast target.",
                        )

                        if evaluated < int(min_samples):
                            st.warning(
                                f"Small sample size ({evaluated} points). Metrics may be noisy. "
                                "Consider increasing tolerance or waiting for more data."
                            )

                        merged_ok = merged_ok.sort_values("forecast_date")

                        fig_bt = go.Figure()
                        fig_bt.add_trace(
                            go.Scatter(
                                x=merged_ok["forecast_date"],
                                y=merged_ok["Low Forecast"],
                                mode="lines+markers",
                                name="Low Forecast (12M target)",
                            )
                        )
                        fig_bt.add_trace(
                            go.Scatter(
                                x=merged_ok["forecast_date"],
                                y=merged_ok["Median Forecast"],
                                mode="lines+markers",
                                name="Median Forecast (12M target)",
                            )
                        )
                        fig_bt.add_trace(
                            go.Scatter(
                                x=merged_ok["forecast_date"],
                                y=merged_ok["High Forecast"],
                                mode="lines+markers",
                                name="High Forecast (12M target)",
                            )
                        )
                        fig_bt.add_trace(
                            go.Scatter(
                                x=merged_ok["forecast_date"],
                                y=merged_ok["actual_price_12m"],
                                mode="lines+markers",
                                name="Actual price after ~12M",
                                line=dict(dash="dash", width=3, color="green"),
                                marker=dict(size=4, color="green"),
                                fill="tozeroy",
                                fillcolor="rgba(0,255,0,0.2)",
                            )
                        )
                        fig_bt.update_layout(
                            xaxis_title="Forecast date",
                            yaxis_title="Price (USD): 12M targets vs actual after ~12M",
                            height=480,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        )
                        st.plotly_chart(fig_bt, use_container_width=True)

                        fig_err = go.Figure()
                        fig_err.add_trace(
                            go.Scatter(
                                x=merged_ok["forecast_date"],
                                y=merged_ok["err_median_pct"],
                                mode="lines+markers",
                                name="Median target error (%)",
                            )
                        )
                        fig_err.update_layout(
                            xaxis_title="Forecast date",
                            yaxis_title="Error (%) = (Actual - Forecast) / Forecast",
                            height=320,
                        )
                        st.plotly_chart(fig_err, use_container_width=True)

                        if show_table:
                            cols_view = [
                                "forecast_date",
                                "target_date",
                                "matched_date",
                                "match_direction",
                                "price_at_forecast",
                                "actual_price_12m",
                                "Low Forecast",
                                "Median Forecast",
                                "High Forecast",
                                "hit_low",
                                "hit_median",
                                "hit_high",
                                "within_range",
                                "err_low_pct",
                                "err_median_pct",
                                "err_high_pct",
                            ]
                            st.dataframe(merged_ok[cols_view])
else:
    st.info("Please enter a valid ticker symbol to run the price-target backtest.")

st.markdown("<hr>", unsafe_allow_html=True)


st.header("Turtle Strategy Signals")
st.markdown(
    """
    This chart applies the classic **Turtle Trading** rules to the selected ticker.

    * **Upper Donchian Channel** – highest high of the past **20** sessions
    * **Lower Donchian Channel** – lowest low of the past **10** sessions

    A **Buy** signal triggers when today’s close breaks **above** yesterday’s 20-day high.
    A **Sell** signal triggers when today’s close breaks **below** yesterday’s 10-day low.
    """
)

if has_company:
    mode = st.selectbox(
        "Signal view:",
        ("Filtered signals (default)", "All signals"),
        index=0,
    )

    with performance_block("build_turtle_chart"):
        df_turtle = company_details[["Date of record", "1-day range", "Price"]].copy()
        df_turtle[["Low", "High"]] = df_turtle["1-day range"].apply(split_range).apply(pd.Series)
        df_turtle = df_turtle.dropna(subset=["Date of record", "Low", "High", "Price"])
        df_turtle = df_turtle.sort_values("Date of record").reset_index(drop=True)

        if df_turtle.empty:
            st.info("Not enough price-range data to compute Turtle signals.")
        else:
            df_turtle["Open"] = df_turtle["Price"].shift(1).fillna(df_turtle["Price"])
            df_turtle["High20"] = df_turtle["High"].rolling(20, min_periods=20).max()
            df_turtle["Low10"] = df_turtle["Low"].rolling(10, min_periods=10).min()

            price = df_turtle["Price"]
            high20_y = df_turtle["High20"].shift(1)
            low10_y = df_turtle["Low10"].shift(1)

            buy_mask = (price > high20_y) & (price.shift(1) <= high20_y)
            sell_mask = (price < low10_y) & (price.shift(1) >= low10_y)

            df_turtle["RawSignal"] = np.select([buy_mask, sell_mask], ["BUY", "SELL"], default=None)

            state = "FLAT"
            filtered = []
            for signal in df_turtle["RawSignal"]:
                if signal == "BUY" and state != "LONG":
                    filtered.append("BUY")
                    state = "LONG"
                elif signal == "SELL" and state == "LONG":
                    filtered.append("SELL")
                    state = "FLAT"
                else:
                    filtered.append(None)

            df_turtle["FiltSignal"] = filtered
            sig_col = "FiltSignal" if "Filtered" in mode else "RawSignal"
            df_turtle["Off"] = (df_turtle["High"] - df_turtle["Low"]) * 0.02

            buys = df_turtle[df_turtle[sig_col] == "BUY"]
            sells = df_turtle[df_turtle[sig_col] == "SELL"]

            fig_turtle = go.Figure()
            fig_turtle.add_trace(
                go.Candlestick(
                    x=df_turtle["Date of record"],
                    open=df_turtle["Open"],
                    high=df_turtle["High"],
                    low=df_turtle["Low"],
                    close=df_turtle["Price"],
                    name="Price",
                    increasing_line_color="green",
                    decreasing_line_color="red",
                    showlegend=False,
                )
            )
            fig_turtle.add_trace(
                go.Scatter(
                    x=df_turtle["Date of record"],
                    y=df_turtle["High20"],
                    mode="lines",
                    name="20-Day High",
                    line=dict(color="royalblue", dash="dot"),
                )
            )
            fig_turtle.add_trace(
                go.Scatter(
                    x=df_turtle["Date of record"],
                    y=df_turtle["Low10"],
                    mode="lines",
                    name="10-Day Low",
                    line=dict(color="orange", dash="dot"),
                )
            )
            fig_turtle.add_trace(
                go.Scatter(
                    x=buys["Date of record"],
                    y=buys["Low"] - buys["Off"],
                    mode="markers",
                    name="BUY",
                    marker=dict(symbol="triangle-up", size=12, color="yellow"),
                )
            )
            fig_turtle.add_trace(
                go.Scatter(
                    x=sells["Date of record"],
                    y=sells["High"] + sells["Off"],
                    mode="markers",
                    name="SELL",
                    marker=dict(symbol="triangle-down", size=12, color="pink"),
                )
            )
            fig_turtle.update_layout(
                xaxis_title="Date",
                yaxis_title="Price (USD) 1D",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=550,
            )
            st.plotly_chart(fig_turtle, use_container_width=True)

            st.subheader("Turtle Signals Log")
            df_signals = (
                pd.concat([buys.assign(Signal="BUY"), sells.assign(Signal="SELL")])
                .loc[:, ["Date of record", "Signal", "Price"]]
                .rename(columns={"Date of record": "Date", "Price": "Close"})
                .sort_values("Date")
                .reset_index(drop=True)
            )
            df_signals["Close"] = df_signals["Close"].map("${:,.2f}".format)

            st.dataframe(df_signals, use_container_width=True)
else:
    st.info("Please enter a valid ticker symbol to compute Turtle signals.")

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    """
    Please note: Investing involves risk and you may lose some or all of your capital.
    This site is provided for informational purposes only and does not constitute financial advice.
    """
)
st.markdown(
    """
    <p style="font-size: 12px; text-align: left; color: gray;">
        © 2025 Michał Ostaszewski<br>
        App source code licensed under the MIT License.<br>
        All data used in this app is licensed under
        <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" style="color: gray;">Creative Commons BY-NC 4.0</a>.<br>
        See the <a href="https://github.com/michael-ostaszewski/stock_scraper_spx" target="_blank" style="color: gray;">GitHub repository</a> for full license details.<br>
        ☕ Support the project:
        <a href="https://buymeacoffee.com/michal.dev" target="_blank" style="color: gray;">buymeacoffee.com/michal.dev</a>
    </p>
    """,
    unsafe_allow_html=True,
)
