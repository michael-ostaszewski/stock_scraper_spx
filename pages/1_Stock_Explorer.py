import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


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
#
# # -------------------------------------------------
# # Turtle Strategy – Donchian Channels & Signals
# # -------------------------------------------------
#
# st.header("Turtle Strategy Signals")
# st.markdown("""
# This chart applies the classic **Turtle Trading** rules to the selected ticker.
#
# * **Upper Donchian Channel** – highest high of the past **20** sessions
# * **Lower Donchian Channel** – lowest low of the past **10** sessions
#
# A **Buy** signal appears when today’s close breaks above yesterday’s 20-day high.
# A **Sell** signal appears when today’s close falls below yesterday’s 10-day low.
# """)
#
# if company_details is not None and not company_details.empty:
#
#     # ───── 1. Parse 1-day range into Low / High ──────────────────────────
#     def split_range(r):
#         """Return low, high from 'low high' or 'low\\nhigh' strings."""
#         if pd.isna(r):
#             return [None, None]
#         parts = str(r).replace("\n", " ").split()
#         if len(parts) != 2:
#             return [None, None]
#         low, high = map(float, parts)
#         return [min(low, high), max(low, high)]
#
#     lows_highs = company_details["1-day range"].apply(split_range).tolist()
#     company_details[["Low", "High"]] = pd.DataFrame(lows_highs, index=company_details.index)
#
#     # Drop rows where parsing failed
#     company_details = company_details.dropna(subset=["Low", "High", "Price"])
#
#     # ───── 2. Compute Donchian channels ─────────────────────────────────
#     company_details = company_details.sort_values("Date of record")
#
#     company_details["High20"] = (
#         company_details["High"].rolling(window=20, min_periods=20).max()
#     )
#     company_details["Low10"] = (
#         company_details["Low"].rolling(window=10, min_periods=10).min()
#     )
#
#     # ───── 3. Generate Turtle entry / exit signals ──────────────────────
#     price      = company_details["Price"]
#     high20_y   = company_details["High20"].shift(1)   # yesterday’s band
#     low10_y    = company_details["Low10"].shift(1)
#
#     company_details["BuySignal"]  = (price > high20_y) & (price.shift(1) <= high20_y)
#     company_details["SellSignal"] = (price < low10_y) & (price.shift(1) >= low10_y)
#
#     # ───── 4. Build the plot ────────────────────────────────────────────
#     fig_turtle = go.Figure()
#
#     # Closing price
#     fig_turtle.add_trace(go.Scatter(
#         x=company_details["Date of record"],
#         y=price,
#         mode="lines",
#         name="Close",
#         line=dict(color="black")
#     ))
#
#     # Donchian channels
#     fig_turtle.add_trace(go.Scatter(
#         x=company_details["Date of record"],
#         y=company_details["High20"],
#         mode="lines",
#         name="20-Day High",
#         line=dict(color="royalblue", dash="dot")
#     ))
#     fig_turtle.add_trace(go.Scatter(
#         x=company_details["Date of record"],
#         y=company_details["Low10"],
#         mode="lines",
#         name="10-Day Low",
#         line=dict(color="orange", dash="dot")
#     ))
#
#     # Buy markers (green triangles up)
#     buys = company_details[company_details["BuySignal"]]
#     fig_turtle.add_trace(go.Scatter(
#         x=buys["Date of record"],
#         y=buys["Price"],
#         mode="markers",
#         name="BUY",
#         marker=dict(symbol="triangle-up", size=12, color="green")
#     ))
#
#     # Sell markers (red triangles down)
#     sells = company_details[company_details["SellSignal"]]
#     fig_turtle.add_trace(go.Scatter(
#         x=sells["Date of record"],
#         y=sells["Price"],
#         mode="markers",
#         name="SELL",
#         marker=dict(symbol="triangle-down", size=12, color="red")
#     ))
#
#     fig_turtle.update_layout(
#         xaxis_title="Date",
#         yaxis_title="Price (USD)",
#         legend=dict(orientation="h", yanchor="bottom",
#                     y=1.02, xanchor="right", x=1),
#         height=500
#     )
#
#     st.plotly_chart(fig_turtle, use_container_width=True)
#
# else:
#     st.info("Please enter a valid ticker symbol to compute Turtle signals.")


# -------------------------------------------------
# Turtle Strategy – Donchian Channels, Candles & Signals
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

    # ───── 1. Parse 1-day range into Low / High ──────────────────────────
    def split_range(r):
        """Return low, high from 'low high' or 'low\\nhigh' strings."""
        if pd.isna(r):
            return [None, None]
        parts = str(r).replace("\n", " ").split()
        if len(parts) != 2:
            return [None, None]
        low, high = map(float, parts)
        return [min(low, high), max(low, high)]

    lows_highs = company_details["1-day range"].apply(split_range).tolist()
    company_details[["Low", "High"]] = pd.DataFrame(lows_highs, index=company_details.index)

    # Keep rows where parsing succeeded and price is present
    company_details = company_details.dropna(subset=["Low", "High", "Price"])

    # ───── 2. Build OHLC columns ─────────────────────────────────────────
    company_details = company_details.sort_values("Date of record")

    # Open ≈ previous close.  Replace with true 'Open' if you have it.
    company_details["Open"] = company_details["Price"].shift(1)
    company_details["Open"].iloc[0] = company_details["Price"].iloc[0]

    # ───── 3. Donchian channels ─────────────────────────────────────────
    company_details["High20"] = (
        company_details["High"].rolling(window=20, min_periods=20).max()
    )
    company_details["Low10"] = (
        company_details["Low"].rolling(window=10, min_periods=10).min()
    )

    # ───── 4. Turtle entry / exit signals ───────────────────────────────
    price      = company_details["Price"]
    high20_y   = company_details["High20"].shift(1)   # yesterday’s band
    low10_y    = company_details["Low10"].shift(1)

    company_details["BuySignal"]  = (price > high20_y) & (price.shift(1) <= high20_y)
    company_details["SellSignal"] = (price < low10_y) & (price.shift(1) >= low10_y)

    # ───── 5. Plot: candles + channels + markers ────────────────────────
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

    # Buy markers (green triangles up)
    buys = company_details[company_details["BuySignal"]]
    fig_turtle.add_trace(go.Scatter(
        x=buys["Date of record"],
        y=buys["Price"],
        mode="markers",
        name="BUY",
        marker=dict(symbol="triangle-up", size=12, color="green")
    ))

    # Sell markers (red triangles down)
    sells = company_details[company_details["SellSignal"]]
    fig_turtle.add_trace(go.Scatter(
        x=sells["Date of record"],
        y=sells["Price"],
        mode="markers",
        name="SELL",
        marker=dict(symbol="triangle-down", size=12, color="red")
    ))

    fig_turtle.update_layout(
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        height=550
    )

    st.plotly_chart(fig_turtle, use_container_width=True)

    # ───── 6. Signals table (read-only helper) ─────────────────────────────
    st.subheader("Turtle Signals Log")

    # Gather BUY and SELL rows, tag them, and tidy up the columns
    df_signals = (
        pd.concat(
            [
                buys.assign(Signal="BUY"),
                sells.assign(Signal="SELL")
            ]
        )
        .loc[:, ["Date of record", "Signal", "Price"]]
        .sort_values("Date of record")
        .reset_index(drop=True)
        .rename(columns={"Date of record": "Date", "Price": "Close"})
    )

    # Optional: prettify price column
    df_signals["Close"] = df_signals["Close"].map("${:,.2f}".format)

    # Display as an interactive table
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






#old code:
# import streamlit as st
# import pandas as pd
# import plotly.graph_objects as go
#
# @st.cache_data
# def load_data():
#     # file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
#     # data = pd.read_csv(file_path, delimiter=';')
#     # return data
#     file_url = "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
#     data = pd.read_csv(file_url, delimiter=';')
#     return data
#
# # Wczytujemy dane
# df = load_data()
#
# # Tytuł strony i opis
# st.title("Explore details of the chosen Stock")
# st.markdown("""
# Enter the ticker symbol of a company to view all available details from our database.
# """)
#
# # Pole tekstowe do wpisania tickera
# ticker = st.text_input("Type in a Stock Ticker (e.g. META)", value="")
#
# if ticker:
#     # Filtrujemy dane - ignorujemy wielkość liter
#     company_details = df[df["Stock"].str.upper() == ticker.upper()]
#     if not company_details.empty:
#         st.dataframe(company_details)
#     else:
#         st.error(f"No data found for ticker '{ticker}'.")
# else:
#     st.info("Please enter a ticker symbol to view company details.")
#
# st.markdown("<hr>", unsafe_allow_html=True)
#
# # ---- Forecast Percentage Trends ----
#
# forecast_percent_cols = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]
# required_cols_percent = ["Date of record"] + forecast_percent_cols
# missing_percent = [col for col in required_cols_percent if col not in company_details.columns]
# if missing_percent:
#     st.error(f"Missing columns for forecast percentages: {missing_percent}")
# else:
#     df_percent = company_details[required_cols_percent].melt(
#         id_vars="Date of record",
#         value_vars=forecast_percent_cols,
#         var_name="Forecast Type",
#         value_name="Value"
#     )
#
#     st.header("12-Month Forecast Returns")
#     st.markdown("""
#     This boxplot displays the 12-month upside forecasts for S&P 500 companies by showing the highest, median, and lowest
#     forecasted percentage increases over the current price. The optimal scenario is when all three forecast metrics are
#     above 0% (in the green area), indicating that even the worst-case forecast predicts a price increase.
#     This visualization serves as a quick indicator of which sectors are expected to perform positively over the next year.""")
#
#     fig_percent = go.Figure()
#     # Dodajemy ciągłe linie dla każdej kategorii prognozy
#     for forecast in forecast_percent_cols:
#         df_temp = df_percent[df_percent["Forecast Type"] == forecast]
#         fig_percent.add_trace(go.Scatter(
#             x=df_temp["Date of record"],
#             y=df_temp["Value"],
#             mode="lines+markers",
#             name=forecast
#         ))
#
#     # Obliczamy zakres danych i dodajemy padding, aby kolorowe pola pokrywały cały wykres
#     y_min_data = df_percent["Value"].min()
#     y_max_data = df_percent["Value"].max()
#     padding = 0.15 * (y_max_data - y_min_data)
#     extended_y_min = y_min_data - padding
#     extended_y_max = y_max_data + padding
#
#     fig_percent.update_layout(
#         yaxis=dict(range=[extended_y_min, extended_y_max]),
#         shapes=[
#             dict(
#                 type="rect",
#                 xref="paper",  # cała szerokość wykresu
#                 yref="y",  # odniesienie do osi y
#                 x0=0,
#                 x1=1,
#                 y0=-5000,
#                 y1=0,
#                 fillcolor="rgba(255,0,0,0.2)",  # czerwony z 50% przezroczystością
#                 line_width=0,
#             ),
#             dict(
#                 type="rect",
#                 xref="paper",
#                 yref="y",
#                 x0=0,
#                 x1=1,
#                 y0=0,
#                 y1=5000,
#                 fillcolor="rgba(0,255,0,0.2)",  # zielony z 50% przezroczystością
#                 line_width=0,
#             )
#         ],
#         # title=f"Forecast Percentage Trends Over Time for {ticker.upper()}",
#         xaxis_title="Date",
#         yaxis_title="Forecast (%)"
#     )
#     st.plotly_chart(fig_percent)
#
#
# st.markdown("<hr>", unsafe_allow_html=True)
#
# if ticker and not company_details.empty:
#     # st.subheader(f"Forecast and Current Price Trends Over Time for {ticker.upper()}")
#
#
#
#     # ---- Forecast Price Trends (USD) ----
#     forecast_usd_cols = ["High Forecast", "Median Forecast", "Low Forecast"]
#     required_cols_usd = ["Date of record"] + forecast_usd_cols
#     missing_usd = [col for col in required_cols_usd if col not in company_details.columns]
#     if missing_usd:
#         st.error(f"Missing columns for forecast prices: {missing_usd}")
#     else:
#         df_usd = company_details[required_cols_usd].melt(
#             id_vars="Date of record",
#             value_vars=forecast_usd_cols,
#             var_name="Forecast Type",
#             value_name="Forecast Value"
#         )
#
#         st.header("Forecast Price vs. Current Price Trends")
#         st.markdown("""
#         This combined line chart shows both the forecasted prices (High, Median, and Low Forecast) and the current
#         price of the stock over time. Analysts’ forecast lines provide insight into expected future values, while the
#         current price is highlighted with a distinct dashed line and green color. An attractive buying opportunity is suggested
#         when the current price is below the lowest forecast, whereas a current price above all forecasted values may
#         signal a strong sell recommendation.""")
#
#         fig_combined = go.Figure()
#         # Dodajemy linie dla prognozowanych cen
#         for forecast in forecast_usd_cols:
#             df_temp = df_usd[df_usd["Forecast Type"] == forecast]
#             fig_combined.add_trace(go.Scatter(
#                 x=df_temp["Date of record"],
#                 y=df_temp["Forecast Value"],
#                 mode="lines+markers",
#                 name=forecast
#             ))
#
#         # Dodajemy linię dla aktualnej ceny (wyróżniona stylizacją i wypełnieniem)
#         fig_combined.add_trace(go.Scatter(
#             x=company_details["Date of record"],
#             y=company_details["Price"],
#             mode="lines+markers",
#             name="Current Price",
#             line=dict(dash="dash", width=3, color="green"),
#             marker=dict(size=4, color="green"),
#             fill="tozeroy",  # wypełnienie obszaru poniżej linii do osi y=0
#             fillcolor="rgba(0,255,0,0.2)"  # półprzezroczysty niebieski kolor
#         ))
#
#         # Ustalanie znormalizowanego zakresu osi y
#         forecast_y_min = df_usd["Forecast Value"].min()
#         forecast_y_max = df_usd["Forecast Value"].max()
#         current_y_min = company_details["Price"].min()
#         current_y_max = company_details["Price"].max()
#         combined_y_min = min(forecast_y_min, current_y_min)
#         combined_y_max = max(forecast_y_max, current_y_max)
#         padding_combined = 0.15 * (combined_y_max - combined_y_min)
#         extended_y_min = combined_y_min - padding_combined
#         extended_y_max = combined_y_max + padding_combined
#
#         fig_combined.update_layout(
#             yaxis=dict(range=[extended_y_min, extended_y_max]),
#             # title=f"Forecast Price and Current Price Trends Over Time for {ticker.upper()}",
#             xaxis_title="Date",
#             yaxis_title="Price (USD)"
#         )
#
#         st.plotly_chart(fig_combined)
# else:
#     st.info("Please enter a ticker symbol to view forecast and current price trends over time.")
#
# st.markdown("<hr>", unsafe_allow_html=True)
#
# st.markdown("""
#     <p style="font-size: 12px; text-align: left; color: gray;">
#         Website made by @Michał Ostaszewski
#     </p>
# """, unsafe_allow_html=True)




