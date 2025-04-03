import streamlit as st
import pandas as pd
import plotly.graph_objects as go


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

