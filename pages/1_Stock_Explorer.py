import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

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


@st.cache_data
def load_data():
    # file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
    # data = pd.read_csv(file_path, delimiter=';')
    # return data
    file_url = "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
    data = pd.read_csv(file_url, delimiter=';')
    return data


# Wczytujemy dane
df = load_data()

# Tytuł strony i opis
st.title("Explore details of the chosen Stock")
st.markdown("""
Enter the ticker symbol of a company to view all available details from our database.
""")

# Pole tekstowe do wpisania tickera
ticker = st.text_input("Type in a Stock Ticker (e.g. META)", value="")

# Zainicjujmy company_details jako None, by uniknąć błędów NameError
company_details = None

# Jeżeli użytkownik podał ticker, filtrujemy dane
if ticker:
    filtered_data = df[df["Stock"].str.upper() == ticker.upper()]
    if not filtered_data.empty:
        company_details = filtered_data
        st.dataframe(company_details)
    else:
        st.error(f"No data found for ticker '{ticker}'.")
else:
    st.info("Please enter a ticker symbol to view company details.")

st.markdown("<hr>", unsafe_allow_html=True)

# -------------------------
# Forecast Percentage Trends
# -------------------------

# Zawsze wyświetlamy nagłówek i opis
st.header("12-Month Forecast Returns")
st.markdown("""
This boxplot displays the 12-month upside forecasts for S&P 500 companies by showing the highest, median, and lowest 
forecasted percentage increases over the current price. The optimal scenario is when all three forecast metrics are 
above 0% (in the green area), indicating that even the worst-case forecast predicts a price increase. 
This visualization serves as a quick indicator of which sectors are expected to perform positively over the next year.
""")

# Tworzymy wykres tylko wtedy, gdy company_details istnieje i nie jest puste
if company_details is not None and not company_details.empty:
    forecast_percent_cols = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]
    required_cols_percent = ["Date of record"] + forecast_percent_cols

    # Sprawdzamy czy wszystkie kolumny są obecne
    missing_percent = [col for col in required_cols_percent if col not in company_details.columns]
    if missing_percent:
        st.error(f"Missing columns for forecast percentages: {missing_percent}")
    else:
        df_percent = company_details[required_cols_percent].melt(
            id_vars="Date of record",
            value_vars=forecast_percent_cols,
            var_name="Forecast Type",
            value_name="Value"
        )

        fig_percent = go.Figure()
        # Dodajemy ciągłe linie dla każdej kategorii prognozy
        for forecast in forecast_percent_cols:
            df_temp = df_percent[df_percent["Forecast Type"] == forecast]
            fig_percent.add_trace(go.Scatter(
                x=df_temp["Date of record"],
                y=df_temp["Value"],
                mode="lines+markers",
                name=forecast
            ))

        # Obliczamy zakres danych i dodajemy padding
        y_min_data = df_percent["Value"].min()
        y_max_data = df_percent["Value"].max()
        padding = 0.15 * (y_max_data - y_min_data)
        extended_y_min = y_min_data - padding
        extended_y_max = y_max_data + padding

        fig_percent.update_layout(
            yaxis=dict(range=[extended_y_min, extended_y_max]),
            shapes=[
                dict(
                    type="rect",
                    xref="paper",  # cała szerokość wykresu
                    yref="y",  # odniesienie do osi y
                    x0=0,
                    x1=1,
                    y0=-5000,
                    y1=0,
                    fillcolor="rgba(255,0,0,0.2)",  # czerwony z 20% przezroczystością
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
                    fillcolor="rgba(0,255,0,0.2)",  # zielony z 20% przezroczystością
                    line_width=0,
                )
            ],
            xaxis_title="Date",
            yaxis_title="Forecast (%)"
        )
        st.plotly_chart(fig_percent)
else:
    st.info("Please enter a valid ticker symbol to view forecast percentage trends.")

st.markdown("<hr>", unsafe_allow_html=True)

# ------------------------------
# Forecast Price vs. Current Price
# ------------------------------

# Zawsze wyświetlamy nagłówek i opis
st.header("Forecast Price vs. Current Price Trends")
st.markdown("""
This combined line chart shows both the forecasted prices (High, Median, and Low Forecast) and the current 
price of the stock over time. Analysts’ forecast lines provide insight into expected future values, while the 
current price is highlighted with a distinct dashed line and green color. An attractive buying opportunity is suggested 
when the current price is below the lowest forecast, whereas a current price above all forecasted values may 
signal a strong sell recommendation.
""")

# Tworzymy wykres tylko wtedy, gdy company_details istnieje i nie jest puste
if company_details is not None and not company_details.empty:
    forecast_usd_cols = ["High Forecast", "Median Forecast", "Low Forecast"]
    required_cols_usd = ["Date of record"] + forecast_usd_cols

    missing_usd = [col for col in required_cols_usd if col not in company_details.columns]
    if missing_usd:
        st.error(f"Missing columns for forecast prices: {missing_usd}")
    else:
        df_usd = company_details[required_cols_usd].melt(
            id_vars="Date of record",
            value_vars=forecast_usd_cols,
            var_name="Forecast Type",
            value_name="Forecast Value"
        )

        fig_combined = go.Figure()
        # Dodajemy linie dla prognozowanych cen
        for forecast in forecast_usd_cols:
            df_temp = df_usd[df_usd["Forecast Type"] == forecast]
            fig_combined.add_trace(go.Scatter(
                x=df_temp["Date of record"],
                y=df_temp["Forecast Value"],
                mode="lines+markers",
                name=forecast
            ))

        # Dodajemy linię dla aktualnej ceny
        fig_combined.add_trace(go.Scatter(
            x=company_details["Date of record"],
            y=company_details["Price"],
            mode="lines+markers",
            name="Current Price",
            line=dict(dash="dash", width=3, color="green"),
            marker=dict(size=4, color="green"),
            fill="tozeroy",
            fillcolor="rgba(0,255,0,0.2)"
        ))

        # Ustalanie zakresu osi y
        forecast_y_min = df_usd["Forecast Value"].min()
        forecast_y_max = df_usd["Forecast Value"].max()
        current_y_min = company_details["Price"].min()
        current_y_max = company_details["Price"].max()
        combined_y_min = min(forecast_y_min, current_y_min)
        combined_y_max = max(forecast_y_max, current_y_max)
        padding_combined = 0.15 * (combined_y_max - combined_y_min)
        extended_y_min = combined_y_min - padding_combined
        extended_y_max = combined_y_max + padding_combined

        fig_combined.update_layout(
            yaxis=dict(range=[extended_y_min, extended_y_max]),
            xaxis_title="Date",
            yaxis_title="Price (USD)"
        )

        st.plotly_chart(fig_combined)
else:
    st.info("Please enter a valid ticker symbol to view forecast and current price trends.")

st.markdown("<hr>", unsafe_allow_html=True)

# -------------------------------------------------
# Dividend Timeline & Yield
# -------------------------------------------------

st.header("Dividend Timeline & Yield")

# Build the chart only when a company is selected
if company_details is not None and not company_details.empty:
    # A dividend is considered “paid” when Dividend yield is present and > 0
    has_dividend = company_details["Dividend yield"].notna() & (company_details["Dividend yield"] > 0)

    if has_dividend.any():
        # Ensure the required columns exist
        div_cols = ["Ex-dividend date", "Dividend pay date", "Dividend yield", "Stock"]
        missing_div_cols = [col for col in div_cols if col not in company_details.columns]
        if missing_div_cols:
            st.error(f"Missing columns for dividend information: {missing_div_cols}")
        else:
            df_div = company_details.loc[has_dividend, div_cols].copy()

            # Convert date strings to real datetime objects
            df_div["Ex-dividend date"] = pd.to_datetime(df_div["Ex-dividend date"])
            df_div["Dividend pay date"] = pd.to_datetime(df_div["Dividend pay date"])

            # Show the latest dividend yield as a quick metric
            latest_yield = df_div["Dividend yield"].iloc[-1]
            # st.metric("Latest Dividend Yield", f"{latest_yield:.2f}%")

            # ───── metrics side-by-side ─────────────────────────────────────────
            col1, col2 = st.columns(2)

            # 1) Yield (already calculated)
            col1.metric("Latest dividend yield", f"{latest_yield:.2f}%")

            # 2) Cash amount of the most recent dividend per share
            latest_price = company_details["Price"].iloc[-1]

            # If the yield is stored as “6.37”, turn it into a fraction; if it is already
            # 0.0637 leave it unchanged. (Anything > 1 is assumed to be percent-points.)
            yield_fraction = latest_yield / 100
            latest_dividend_usd = latest_price * yield_fraction

            col2.metric("Yearly dividend value in USD per share", f"${latest_dividend_usd:.2f}")

            df_div["Dividend yield"] = df_div["Dividend yield"] / 100

            # Build a horizontal timeline (one row per dividend period)
            fig_timeline = px.timeline(
                df_div,
                x_start="Ex-dividend date",
                x_end="Dividend pay date",
                y="Stock",
                hover_data={
                    "Stock": True,
                    "Ex-dividend date": "|%Y-%m-%d",
                    "Dividend pay date": "|%Y-%m-%d",
                    "Dividend yield": ":.2%"
                },
                color="Stock",
                title="Timeline: Ex-Dividend and Dividend Pay Dates"
            )


            # Focus the x-axis on ±30 / +90 days around “today”
            today = pd.Timestamp.now().floor("D")
            fig_timeline.update_xaxes(
                tickformat="%Y-%m-%d",
                range=[today - pd.DateOffset(days=30),
                       today + pd.DateOffset(days=90)],
                showgrid=True, gridcolor="rgba(128,128,128,0.2)"
            )
            fig_timeline.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
            fig_timeline.add_vline(
                x=today,
                line_width=2,
                line_dash="solid",
                line_color="rgba(0,0,0,0.8)"
            )
            fig_timeline.update_layout(
                xaxis_title="Date",
                yaxis_title="Stock",
                height=450,
                dragmode="pan",
                showlegend=False
            )

            st.plotly_chart(fig_timeline, use_container_width=True)

    else:
        st.info("This company currently does **not** pay a dividend.")
else:
    st.info("Please enter a valid ticker symbol to view dividend information.")


st.markdown("<hr>", unsafe_allow_html=True)

# -------------------------------------------------
# Smart Score – historical trend
# -------------------------------------------------

st.header("Smart Score Trend Over Time")
st.markdown("""
The **Smart Score** (scale **1 – 10**) is a composite rating that blends eight
fundamental and market-based factors into a single number. The line chart below shows how the score has evolved for the
selected ticker across all dates available in the database.
""")

if company_details is not None and not company_details.empty:
    if "Smart Score" in company_details.columns:
        # Sort by date so the line proceeds chronologically
        df_score = company_details.sort_values("Date of record")

        # ───── summary metrics side-by-side ────────────────────────────────
        num_sessions = len(df_score)
        avg_smartscore = df_score["Smart Score"].mean()

        col1, col2 = st.columns(2)
        col1.metric("Trading sessions in data set", f"{num_sessions}")
        col2.metric("Average Smart Score", f"{avg_smartscore:.2f}")

        #───── summary metrics side-by-side ────────────────────────────────

        fig_score = go.Figure()
        fig_score.add_trace(
            go.Scatter(
                x=df_score["Date of record"],
                y=df_score["Smart Score"],
                mode="lines+markers",
                name="Smart Score"
            )
        )
        fig_score.update_layout(
            xaxis_title="Date",
            yaxis_title="Smart Score (1–10)",
            yaxis=dict(range=[0, 10], dtick=1)
        )
        st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.info("Smart Score data not available for this company.")
else:
    st.info("Please enter a valid ticker symbol to view Smart Score trends.")



st.markdown("<hr>", unsafe_allow_html=True)


# -------------------------------------------------
# Custom Metric Explorer
# -------------------------------------------------

st.header("Custom Metric Explorer")
st.markdown("""
Pick any numeric columns to plot their historical trend. P/E ratio is selected by default.""")

if company_details is not None and not company_details.empty:

    # Identify numeric columns in the DataFrame
    numeric_cols = [
        c for c in company_details.columns
        if pd.api.types.is_numeric_dtype(company_details[c])
    ]

    # Default to P/E ratio if it exists, otherwise start empty
    default_metrics = ["P/E ratio"] if "P/E ratio" in numeric_cols else []

    selected_metrics = st.multiselect(
        "Select metrics to display:",
        options=sorted(numeric_cols),
        default=default_metrics
    )

    if selected_metrics:
        df_plot = company_details.sort_values("Date of record")

        fig_custom = go.Figure()

        # Add a line for each selected metric
        for metric in selected_metrics:
            fig_custom.add_trace(go.Scatter(
                x=df_plot["Date of record"],
                y=df_plot[metric],
                mode="lines+markers",
                name=metric
            ))

        fig_custom.update_layout(
            xaxis_title="Date",
            yaxis_title="Metric value",
            legend=dict(orientation="h", yanchor="bottom",
                        y=1.02, xanchor="right", x=1),
            height=400
        )

        st.plotly_chart(fig_custom, use_container_width=True)
    else:
        st.info("Choose at least one metric to draw the chart.")
else:
    st.info("Please enter a valid ticker symbol to explore custom metrics.")

st.markdown("<hr>", unsafe_allow_html=True)

# -------------------------------------------------
# 12M Price Target Backtest (Forecast accuracy)
# -------------------------------------------------

st.header("12-Month Price Target Backtest")
st.markdown("""
This section evaluates how often a stock reached analysts' **12-month price targets**.
For each forecast date, we look for the stock price approximately **1 year later**.
If there is no session exactly one year later, we match the **nearest available trading session** within a tolerance window
(preferably the first session **after** the target date, otherwise the closest session **before** it).
""")

if company_details is not None and not company_details.empty:

    # --- user controls ---
    colA, colB, colC = st.columns([1, 1, 2])

    tolerance_days = colA.number_input(
        "Matching tolerance (days)",
        min_value=1,
        max_value=60,
        value=10,
        step=1,
        help="Maximum allowed gap (in days) between the target date (forecast_date + 1 year) and the matched trading session."
    )

    min_samples = colB.number_input(
        "Minimum sample size for metrics",
        min_value=3,
        max_value=200,
        value=10,
        step=1,
        help="If the number of evaluated points is below this threshold, a small-sample warning will be shown."
    )

    show_table = colC.checkbox(
        "Show matching diagnostics table",
        value=False,
        help="Displays a diagnostic table with the matched session date and the computed forecast errors."
    )

    required_cols = ["Date of record", "Price", "High Forecast", "Median Forecast", "Low Forecast"]
    missing_cols = [c for c in required_cols if c not in company_details.columns]

    if missing_cols:
        st.error(f"Missing required columns for backtest: {missing_cols}")
    else:
        df_bt = company_details.copy()

        # --- data types ---
        df_bt["Date of record"] = pd.to_datetime(df_bt["Date of record"], errors="coerce")
        for c in ["Price", "High Forecast", "Median Forecast", "Low Forecast"]:
            df_bt[c] = pd.to_numeric(df_bt[c], errors="coerce")

        df_bt = df_bt.dropna(subset=["Date of record", "Price"]).sort_values("Date of record")

        # If duplicates occur for the same date, keep the latest record
        df_bt = df_bt.drop_duplicates(subset=["Date of record"], keep="last")

        # Price series used for "12 months later" matching
        price_series = df_bt[["Date of record", "Price"]].rename(
            columns={"Date of record": "price_date", "Price": "actual_price"}
        ).sort_values("price_date")

        # Forecast records (require median at minimum)
        pred = df_bt[["Date of record", "Price", "High Forecast", "Median Forecast", "Low Forecast"]].copy()
        pred = pred.dropna(subset=["Median Forecast"])
        pred = pred.rename(columns={"Date of record": "forecast_date", "Price": "price_at_forecast"})
        pred = pred.sort_values("forecast_date")

        if pred.empty:
            st.info("No usable forecast records for this ticker (e.g., Median Forecast is missing).")
        else:
            max_date = price_series["price_date"].max()
            pred["target_date"] = pred["forecast_date"] + pd.DateOffset(years=1)

            # Only evaluate forecasts whose 12M target date fits within available price history
            pred_eval = pred[pred["target_date"] <= max_date].copy()

            if pred_eval.empty:
                st.info(
                    "There are no forecast points that can be evaluated yet for this ticker "
                    "(the 12M target date falls outside the available price history)."
                )
            else:
                pred_eval = pred_eval.sort_values("target_date")
                tol = pd.Timedelta(days=int(tolerance_days))

                # 1) Prefer the first trading session AFTER the target date
                m_fwd = pd.merge_asof(
                    pred_eval,
                    price_series,
                    left_on="target_date",
                    right_on="price_date",
                    direction="forward",
                    tolerance=tol
                ).rename(columns={"price_date": "matched_date_fwd", "actual_price": "actual_price_fwd"})

                # 2) If not found, use the last trading session BEFORE the target date
                m_bwd = pd.merge_asof(
                    pred_eval,
                    price_series,
                    left_on="target_date",
                    right_on="price_date",
                    direction="backward",
                    tolerance=tol
                ).rename(columns={"price_date": "matched_date_bwd", "actual_price": "actual_price_bwd"})

                merged = m_fwd.copy()
                merged["matched_date"] = merged["matched_date_fwd"]
                merged["actual_price_12m"] = merged["actual_price_fwd"]
                merged["match_direction"] = np.where(merged["actual_price_12m"].notna(), "forward", None)

                need_bwd = merged["actual_price_12m"].isna()
                merged.loc[need_bwd, "matched_date"] = m_bwd.loc[need_bwd, "matched_date_bwd"]
                merged.loc[need_bwd, "actual_price_12m"] = m_bwd.loc[need_bwd, "actual_price_bwd"]
                merged.loc[need_bwd & merged["actual_price_12m"].notna(), "match_direction"] = "backward"

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
                    # --- hit rates ---
                    merged_ok["hit_low"] = merged_ok["actual_price_12m"] >= merged_ok["Low Forecast"]
                    merged_ok["hit_median"] = merged_ok["actual_price_12m"] >= merged_ok["Median Forecast"]
                    merged_ok["hit_high"] = merged_ok["actual_price_12m"] >= merged_ok["High Forecast"]

                    merged_ok["within_range"] = (
                        (merged_ok["actual_price_12m"] >= merged_ok["Low Forecast"]) &
                        (merged_ok["actual_price_12m"] <= merged_ok["High Forecast"])
                    )

                    # --- percentage errors (Actual vs Forecast) ---
                    def _pct_err(actual, forecast):
                        return (actual - forecast) / forecast * 100.0

                    # Protect against 0 / NaN forecasts
                    for tag, col in [("low", "Low Forecast"), ("median", "Median Forecast"), ("high", "High Forecast")]:
                        merged_ok[f"err_{tag}_pct"] = np.where(
                            merged_ok[col].notna() & (merged_ok[col] != 0),
                            _pct_err(merged_ok["actual_price_12m"], merged_ok[col]),
                            np.nan
                        )

                    # --- median forecast error aggregates ---
                    mae_median = merged_ok["err_median_pct"].abs().mean()
                    med_err_median = merged_ok["err_median_pct"].median()

                    # --- metrics (above charts) with help definitions ---
                    m1, m2, m3, m4 = st.columns(4)
                    m5, m6, m7 = st.columns(3)

                    m1.metric(
                        "Evaluable records",
                        f"{evaluated}/{total_candidates}",
                        f"{coverage*100:.1f}% coverage",
                        help=(
                            "How many forecast records can be evaluated with a ~12M outcome. "
                            "Numerator: records for which a trading session was found within the tolerance window. "
                            "Denominator: records whose 12M target date is within your available price history."
                        )
                    )
                    m2.metric(
                        "Hit-rate: Low target",
                        f"{merged_ok['hit_low'].mean()*100:.1f}%",
                        help="Share of cases where the ~12M price was >= the Low Forecast target."
                    )
                    m3.metric(
                        "Hit-rate: Median target",
                        f"{merged_ok['hit_median'].mean()*100:.1f}%",
                        help="Share of cases where the ~12M price was >= the Median Forecast target."
                    )
                    m4.metric(
                        "Within [Low, High]",
                        f"{merged_ok['within_range'].mean()*100:.1f}%",
                        help="Share of cases where the ~12M price fell between Low Forecast and High Forecast (inclusive)."
                    )

                    m5.metric(
                        "Mean |median error|",
                        f"{mae_median:.2f}%",
                        help=(
                            "Mean absolute percentage error for the median target: "
                            "|(Actual - MedianForecast) / MedianForecast| * 100. Lower is better."
                        )
                    )
                    m6.metric(
                        "Median median-error",
                        f"{med_err_median:.2f}%",
                        help=(
                            "Median of the percentage error for the median target: "
                            "(Actual - MedianForecast) / MedianForecast * 100. "
                            "Positive means the actual price was higher than the forecast."
                        )
                    )
                    m7.metric(
                        "High target reached",
                        f"{merged_ok['hit_high'].mean()*100:.1f}%",
                        help="Share of cases where the ~12M price was >= the High Forecast target."
                    )

                    if evaluated < int(min_samples):
                        st.warning(
                            f"Small sample size ({evaluated} points). Metrics may be noisy. "
                            "Consider increasing tolerance or waiting for more data."
                        )

                    # --- Chart 1: targets vs ~12M realized price (Actual as line + green fill) ---
                    merged_ok = merged_ok.sort_values("forecast_date")

                    fig_bt = go.Figure()

                    fig_bt.add_trace(go.Scatter(
                        x=merged_ok["forecast_date"],
                        y=merged_ok["Low Forecast"],
                        mode="lines+markers",
                        name="Low Forecast (12M target)"
                    ))
                    fig_bt.add_trace(go.Scatter(
                        x=merged_ok["forecast_date"],
                        y=merged_ok["Median Forecast"],
                        mode="lines+markers",
                        name="Median Forecast (12M target)"
                    ))
                    fig_bt.add_trace(go.Scatter(
                        x=merged_ok["forecast_date"],
                        y=merged_ok["High Forecast"],
                        mode="lines+markers",
                        name="High Forecast (12M target)"
                    ))

                    fig_bt.add_trace(go.Scatter(
                        x=merged_ok["forecast_date"],
                        y=merged_ok["actual_price_12m"],
                        mode="lines+markers",
                        name="Actual price after ~12M",
                        line=dict(dash="dash", width=3, color="green"),
                        marker=dict(size=4, color="green"),
                        fill="tozeroy",
                        fillcolor="rgba(0,255,0,0.2)"
                    ))

                    fig_bt.update_layout(
                        xaxis_title="Forecast date",
                        yaxis_title="Price (USD): 12M targets vs actual after ~12M",
                        height=480,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_bt, use_container_width=True)

                    # --- Chart 2: median target percentage error over time ---
                    fig_err = go.Figure()
                    fig_err.add_trace(go.Scatter(
                        x=merged_ok["forecast_date"],
                        y=merged_ok["err_median_pct"],
                        mode="lines+markers",
                        name="Median target error (%)"
                    ))
                    fig_err.update_layout(
                        xaxis_title="Forecast date",
                        yaxis_title="Error (%) = (Actual - Forecast) / Forecast",
                        height=320
                    )
                    st.plotly_chart(fig_err, use_container_width=True)

                    # --- diagnostics table ---
                    if show_table:
                        cols_view = [
                            "forecast_date", "target_date", "matched_date", "match_direction",
                            "price_at_forecast", "actual_price_12m",
                            "Low Forecast", "Median Forecast", "High Forecast",
                            "hit_low", "hit_median", "hit_high", "within_range",
                            "err_low_pct", "err_median_pct", "err_high_pct"
                        ]
                        st.dataframe(merged_ok[cols_view])

else:
    st.info("Please enter a valid ticker symbol to run the price-target backtest.")

st.markdown("<hr>", unsafe_allow_html=True)


# -------------------------------------------------
# Turtle Strategy – Donchian Channels & Signals
# -------------------------------------------------

st.header("Turtle Strategy Signals")
st.markdown("""
This chart applies the classic **Turtle Trading** rules to the selected ticker.

* **Upper Donchian Channel** – highest high of the past **20** sessions
* **Lower Donchian Channel** – lowest low of the past **10** sessions

A **Buy** signal triggers when today’s close breaks **above** yesterday’s 20-day high.
A **Sell** signal triggers when today’s close breaks **below** yesterday’s 10-day low.
""")

if company_details is not None and not company_details.empty:

    # ───── 1 ▸ Parse '1-day range' into Low / High ──────────────────────
    def split_range(r: str):
        """Return [low, high] from 'low high' or 'low\\nhigh' string."""
        if pd.isna(r):
            return [None, None]
        parts = str(r).replace("\n", " ").split()
        if len(parts) != 2:
            return [None, None]
        low, high = map(float, parts)
        return [min(low, high), max(low, high)]

    company_details[["Low", "High"]] = (
        company_details["1-day range"]
        .apply(split_range)
        .apply(pd.Series)
    )

    company_details = company_details.dropna(subset=["Low", "High", "Price"])

    # ───── 2 ▸ Build OHLC – Open ≈ previous Close ───────────────────────
    company_details = company_details.sort_values("Date of record")
    company_details["Open"] = (
        company_details["Price"].shift(1).fillna(company_details["Price"])
    )

    # ───── 3 ▸ Donchian channels ────────────────────────────────────────
    company_details["High20"] = (
        company_details["High"].rolling(20, min_periods=20).max()
    )
    company_details["Low10"] = (
        company_details["Low"].rolling(10, min_periods=10).min()
    )

    # ───── 4 ▸ Raw BUY / SELL masks (object-safe) ───────────────────────
    price    = company_details["Price"]
    high20_y = company_details["High20"].shift(1)
    low10_y  = company_details["Low10"].shift(1)

    buy_mask  = (price > high20_y) & (price.shift(1) <= high20_y)
    sell_mask = (price < low10_y)  & (price.shift(1) >= low10_y)

    company_details["RawSignal"] = np.select(
        [buy_mask, sell_mask],
        ["BUY", "SELL"],
        default=None
    )

    # ───── 5 ▸ Filtered signals (first BUY / first SELL) ────────────────
    state, filtered = "FLAT", []
    for sig in company_details["RawSignal"]:
        if sig == "BUY" and state != "LONG":
            filtered.append("BUY");  state = "LONG"
        elif sig == "SELL" and state == "LONG":
            filtered.append("SELL"); state = "FLAT"
        else:
            filtered.append(None)

    company_details["FiltSignal"] = filtered

    # ───── 6 ▸ Selector (default = filtered)  ───────────────────────────
    mode = st.selectbox(
        "Signal view:",
        ("Filtered signals (default)", "All signals"),
        index=0
    )

    sig_col = "FiltSignal" if "Filtered" in mode else "RawSignal"

    # ───── 7 ▸ Prepare DataFrames for markers & log  ────────────────────
    company_details["Off"] = (company_details["High"] - company_details["Low"]) * 0.02

    buys  = company_details[company_details[sig_col] == "BUY"]
    sells = company_details[company_details[sig_col] == "SELL"]

    # ───── 8 ▸ Plot – candles, channels, markers  ───────────────────────
    fig_turtle = go.Figure()

    # Candlesticks
    fig_turtle.add_trace(go.Candlestick(
        x     = company_details["Date of record"],
        open  = company_details["Open"],
        high  = company_details["High"],
        low   = company_details["Low"],
        close = company_details["Price"],
        name  = "Price",
        increasing_line_color="green",
        decreasing_line_color="red",
        showlegend=False
    ))

    # Donchian channels
    fig_turtle.add_trace(go.Scatter(
        x=company_details["Date of record"],
        y=company_details["High20"],
        mode="lines",
        name="20-Day High",
        line=dict(color="royalblue", dash="dot")
    ))
    fig_turtle.add_trace(go.Scatter(
        x=company_details["Date of record"],
        y=company_details["Low10"],
        mode="lines",
        name="10-Day Low",
        line=dict(color="orange", dash="dot")
    ))

    # BUY ▴ (below candle)
    fig_turtle.add_trace(go.Scatter(
        x=buys["Date of record"],
        y=buys["Low"] - buys["Off"],
        mode="markers",
        name="BUY",
        marker=dict(symbol="triangle-up", size=12, color="yellow")
    ))

    # SELL ▾ (above candle)
    fig_turtle.add_trace(go.Scatter(
        x=sells["Date of record"],
        y=sells["High"] + sells["Off"],
        mode="markers",
        name="SELL",
        marker=dict(symbol="triangle-down", size=12, color="pink")
    ))

    fig_turtle.update_layout(
        xaxis_title="Date",
        yaxis_title="Price (USD) 1D",
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        height=550
    )

    st.plotly_chart(fig_turtle, use_container_width=True)

    # ───── 9 ▸ Signals table  ───────────────────────────────────────────
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

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        © 2025 Michał Ostaszewski<br>
        App source code licensed under the MIT License.<br>
        All data used in this app is licensed under 
        <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" style="color: gray;">Creative Commons BY-NC 4.0</a>.<br>
        See the <a href="https://github.com/TwojeRepozytorium" target="_blank" style="color: gray;">GitHub repository</a> for full license details.<br>
        ☕ Support the project: <a href="https://buymeacoffee.com/michal.dev" target="_blank" style="color: gray;">buymeacoffee.com/michal.dev</a>
    </p>
""", unsafe_allow_html=True)




