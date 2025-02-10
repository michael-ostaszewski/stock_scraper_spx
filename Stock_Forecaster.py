# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import seaborn as sns
#
# ######### początek kodu CSS - tu jest kod CSS do stylizowania strony - początek ########
# st.markdown(
#     """
#     <style>
#     /* Ten CSS pogrubia wartości w komponentach metric */
#     [data-testid="stMetricValue"] {
#         font-weight: bold;
#     }
#     /* Opcjonalnie: pogrubienie etykiet metryk */
#     [data-testid="stMetricLabel"] {
#         font-weight: bold;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True
# )
# ######### koniec kodu CSS - tu jest kod CSS do stylizowania strony - koniec kodu CSS ########
#
# # Tytuł aplikacji
# st.title("Best stocks S&P500 Index ")
# # st.write("")
# # st.write("")
# # Mniejszy heading z opisem w języku angielskim
# st.markdown("""This site aggregates and averages data from a wide range of financial analysts to identify
#                 the best-performing stocks in the S&P 500 over a one-year horizon. By leveraging diverse insights,
#                 we aim to provide a comprehensive view of market trends and investment opportunities using the latest Data Science techniques.""")
# st.write("")
#
# # Wczytanie danych
# @st.cache_data
# def load_data():
#     file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
#     data = pd.read_csv(file_path, delimiter=';')
#     return data
#
# # Wczytanie danych
# df = load_data()
#
# # Konwersja kolumny daty na format datetime, jeśli taka kolumna istnieje
# if "Date of record" in df.columns:
#     df["Date of record"] = pd.to_datetime(df["Date of record"], errors='coerce')
#
# # Filtr daty
# if "Date of record" in df.columns:
#     # Sortujemy wszystkie dostępne daty
#     unique_dates = sorted(df["Date of record"].dropna().unique())
#     # Domyślnie ustawiamy najnowszą datę
#     max_date = unique_dates[-1] if unique_dates else None
#     selected_date = st.sidebar.date_input("Date selector", value=max_date)
#     filtered_data = df[df["Date of record"] == pd.Timestamp(selected_date)]
# else:
#     filtered_data = df
#     st.sidebar.info("Brak kolumny 'Date of record' - wyświetlane są wszystkie dane.")
#
#
# if filtered_data.empty:
#     st.error("Brak danych dla wybranej daty!")
# else:
#     # Oblicz mediany dla wybranej daty
#     med_low = filtered_data["Low Forecast Percent"].median()
#     med_median = filtered_data["Median Forecast Percent"].median()
#     med_high = filtered_data["High Forecast Percent"].median()
#
#     # Oblicz delta z poprzedniej sesji, jeśli jest dostępna
#     # Znajdujemy poprzednią datę mniejszą od wybranej
#     prev_date = None
#     if "Date of record" in df.columns:
#         earlier_dates = [d for d in unique_dates if d < pd.Timestamp(selected_date)]
#         if earlier_dates:
#             prev_date = earlier_dates[-1]  # najnowsza data przed wybraną
#
#     # Inicjujemy zmienne delty
#     delta_low = delta_median = delta_high = None
#     if prev_date is not None:
#         prev_data = df[df["Date of record"] == prev_date]
#         delta_low = med_low - prev_data["Low Forecast Percent"].median()
#         delta_median = med_median - prev_data["Median Forecast Percent"].median()
#         delta_high = med_high - prev_data["High Forecast Percent"].median()
#
#     st.markdown("### Today's 1-year analyst forecast for the S&P 500 Index")
#
#     col1, col2, col3 = st.columns(3)
#     # Używamy parametru delta w st.metric
#     col1.metric("Median - low forecast", f"{med_low:.2f}%", delta=f"{delta_low:+.2f}%" if delta_low is not None else "N/A")
#     col2.metric("Median - average forecasts", f"{med_median:.2f}%", delta=f"{delta_median:+.2f}%" if delta_median is not None else "N/A")
#     col3.metric("Median - high forecast", f"{med_high:.2f}%", delta=f"{delta_high:+.2f}%" if delta_high is not None else "N/A")
#
#     st.write("")
#     st.write("")
#
#    # -------------------------------------------
#     # Wykres przedstawiający zmiany median w czasie
#     # Grupa danych według daty i obliczenie median dla każdej daty
#     df_time = df.dropna(subset=["Date of record"]).groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]].median().reset_index()
#
#     # st.markdown("### Zmiana median prognoz w czasie")
#     # Możesz użyć wykresu liniowego np. za pomocą Plotly Express
#     fig = px.line(df_time, x="Date of record", y=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
#                   title="Zmiana median prognoz analityków w czasie",
#                   markers=True)
#     st.plotly_chart(fig)
#
#     st.write("")
#
# # -------------------------------------------
#
# # Definicja wymaganych kolumn dla dalszej analizy
# required_columns = [
#     "Stock", "Sector", "Price", "Low Forecast Percent", "Median Forecast Percent",
#     "High Forecast Percent", "Smart Score", "Score", "P/E ratio"
# ]
#
# if all(col in filtered_data.columns for col in required_columns):
#     # Pobieramy unikatowe sektory i tworzymy widget selectbox
#     sectors = sorted(filtered_data["Sector"].unique())
#     sector_options = ["All Sectors"] + sectors
#     selected_sector = st.sidebar.selectbox("Select Sector", options=sector_options, index=0)
#
#     # Przetwarzamy dane według kryteriów
#     scoring = filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
#     scoring = scoring[
#         (scoring["Smart Score"] > 7) &
#         (scoring["Score"] > 2) &
#         (scoring["Low Forecast Percent"] > -5) &
#         (scoring["Score"] < 6)
#         ]
#
#     # Jeśli wybrano konkretny sektor, przefiltruj dane
#     if selected_sector != "All Sectors":
#         scoring = scoring[scoring["Sector"] == selected_sector]
#
#     # Zaokrąglamy wszystkie kolumny numeryczne do dwóch miejsc po przecinku
#     scoring = scoring.round(2)
#     total_stocks = scoring.shape[0]
#
#     if not scoring.empty:
#         max_stocks = st.sidebar.slider(
#             "Select number of stocks to display",
#             min_value=1,
#             max_value=total_stocks,
#             value=10 if total_stocks >= 10 else total_stocks,
#             step=1
#         )
#         # Ograniczamy liczbę spółek do wybranej przez użytkownika
#         scoring = scoring.head(max_stocks)
#
#
#
# # Tytuł i opis wykresu używają stałej total_stocks, a slider ogranicza tylko wyświetlaną liczbę spółek
# st.header("Selected stocks by our AI algorithm")
# st.markdown(
#     f"Our sophisticated algorithm, merging 9 variables, has identified {total_stocks} best stocks for today. "
#     f"You can further refine the list using the slider on the left sidebar to potentially achieve higher returns."
# )
#
# # Obliczamy mediany dla przefiltrowanych spółek
# med_low_scoring = scoring["Low Forecast Percent"].median()
# med_median_scoring = scoring["Median Forecast Percent"].median()
# med_high_scoring = scoring["High Forecast Percent"].median()
#
# # Obliczamy delta dla przefiltrowanych spółek, korzystając z danych z poprzedniej sesji (jeśli dostępne)
# delta_low_scoring = delta_median_scoring = delta_high_scoring = None
# if prev_date is not None:
#     # Pobieramy dane z poprzedniej daty
#     prev_filtered_data = df[df["Date of record"] == prev_date]
#     # Stosujemy te same kryteria, aby otrzymać poprzednią wersję scoringu
#     if all(col in prev_filtered_data.columns for col in required_columns):
#         prev_scoring = prev_filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
#         prev_scoring = prev_scoring[
#             (prev_scoring["Smart Score"] > 7) &
#             (prev_scoring["Score"] > 2) &
#             (prev_scoring["Low Forecast Percent"] > -5) &
#             (prev_scoring["Score"] < 10)
#         ]
#         if selected_sector != "All Sectors":
#             prev_scoring = prev_scoring[prev_scoring["Sector"] == selected_sector]
#         prev_med_low_scoring = prev_scoring["Low Forecast Percent"].median()
#         prev_med_median_scoring = prev_scoring["Median Forecast Percent"].median()
#         prev_med_high_scoring = prev_scoring["High Forecast Percent"].median()
#         delta_low_scoring = med_low_scoring - prev_med_low_scoring
#         delta_median_scoring = med_median_scoring - prev_med_median_scoring
#         delta_high_scoring = med_high_scoring - prev_med_high_scoring
#
#     st.write("")
#     st.markdown("##### Today's 1-year analyst forecast for selected stocks")
#     col4, col5, col6 = st.columns(3)
#     col4.metric("Median - low forecast", f"{med_low_scoring:.2f}%", delta=f"{delta_low_scoring:+.2f}%" if delta_low_scoring is not None else "N/A")
#     col5.metric("Median - average forecast", f"{med_median_scoring:.2f}%", delta=f"{delta_median_scoring:+.2f}%" if delta_median_scoring is not None else "N/A")
#     col6.metric("Median - high forecast", f"{med_high_scoring:.2f}%", delta=f"{delta_high_scoring:+.2f}%" if delta_high_scoring is not None else "N/A")
# else:
#     st.error("Brak wymaganych kolumn w danych.")
#
#
#
# if not scoring.empty:
#     # Ograniczamy wyświetlanie spółek do liczby wybranej na sliderze
#     displayed_stocks = scoring.head(max_stocks)
#     # Ustalamy kolejność spółek na osi X według Score (malejąco)
#     category_order = {"Stock": displayed_stocks.sort_values("Score", ascending=False)["Stock"].tolist()}
#
#     # Tworzymy wykres słupkowy z dodatkowymi danymi (wyświetlanymi przy najechaniu kursorem)
#     fig_bar = px.bar(
#         displayed_stocks,
#         x="Stock",
#         y="Score",
#         color="Sector",
#         title="Use slider on the left sidebar to show more or less stocks in the chart.",
#         category_orders=category_order,
#         hover_data={
#             "Price": True,
#             "Score": True,
#             "P/E ratio": True,
#             "Low Forecast Percent": True,
#             "Median Forecast Percent": True,
#             "High Forecast Percent": True,
#             "Smart Score": True
#         }
#     )
#     st.plotly_chart(fig_bar)
# else:
#     st.info("No data available for the bar chart.")
# # else:
# #     st.error("Missing required columns in the data.")
#
#
#
#
# # 2. Wykres rozrzutu: Cena vs. P/E ratio
# st.header("Median Forecast Percent vs. P/E ratio")
# if not scoring.empty:
#     fig_scatter = px.scatter(scoring, x="Median Forecast Percent", y="P/E ratio", size="Score", color="Sector",
#                              hover_data=["Stock"],
#                              title="Zależność ceny od P/E ratio")
#     st.plotly_chart(fig_scatter)
# else:
#     st.info("Brak danych do wykresu rozrzutu.")
#
#
#
#
# # ----- Dla całego S&P500 -----
# df_time_all = (
#     df.dropna(subset=["Date of record"])
#       .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
#       .median()
#       .reset_index()
# )
#
# # ----- Dla przefiltrowanych spółek (historical scoring) -----
# # Tworzymy kopię danych i stosujemy te same kryteria filtrowania, jakie używamy przy tworzeniu scoring
# df_scoring_all = df.copy()
# df_scoring_all = df_scoring_all[
#     (df_scoring_all["Smart Score"] > 7) &
#     (df_scoring_all["Score"] > 2) &
#     (df_scoring_all["Low Forecast Percent"] > -5) &
#     (df_scoring_all["Score"] < 6)
# ]
#
# # Jeśli użytkownik wybrał konkretny sektor, stosujemy dodatkowy filtr:
# if selected_sector != "All Sectors":
#     df_scoring_all = df_scoring_all[df_scoring_all["Sector"] == selected_sector]
#
# df_time_scoring = (
#     df_scoring_all.dropna(subset=["Date of record"])
#                   .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
#                   .median()
#                   .reset_index()
# )
#
# # ----- Przekształcenie danych do formatu long -----
# # Dla całego S&P500:
# df_all_melt = df_time_all.melt(
#     id_vars=["Date of record"],
#     value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
#     var_name="Forecast Type",
#     value_name="Median Value"
# )
# df_all_melt["Group"] = "All Stocks"
#
# # Dla przefiltrowanych spółek:
# df_scoring_melt = df_time_scoring.melt(
#     id_vars=["Date of record"],
#     value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
#     var_name="Forecast Type",
#     value_name="Median Value"
# )
# df_scoring_melt["Group"] = "Filtered Stocks"
#
# # Łączymy oba zestawy danych:
# df_combined = pd.concat([df_all_melt, df_scoring_melt])
#
# # ----- Nowy selektor do wyboru typu prognozy -----
# forecast_options = ["All forecasts", "High forecasts", "Med forecasts", "Low forecasts"]
# selected_forecast = st.sidebar.selectbox("Select forecast type", options=forecast_options, index=0, key="forecast_select")
#
# # Jeśli użytkownik nie chce wyświetlać wszystkiego, filtrujemy dane:
# if selected_forecast != "All forecasts":
#     if selected_forecast == "High forecasts":
#         df_combined = df_combined[df_combined["Forecast Type"] == "High Forecast Percent"]
#     elif selected_forecast == "Med forecasts":
#         df_combined = df_combined[df_combined["Forecast Type"] == "Median Forecast Percent"]
#     elif selected_forecast == "Low forecasts":
#         df_combined = df_combined[df_combined["Forecast Type"] == "Low Forecast Percent"]
#
# # ----- Tworzenie wykresu -----
# if selected_forecast == "All forecasts":
#     # Jeśli pokazujemy wszystkie prognozy – stosujemy facetowanie
#     fig = px.line(
#         df_combined,
#         x="Date of record",
#         y="Median Value",
#         color="Group",
#         facet_col="Forecast Type",
#         title="Comparison of Median Analyst Forecasts Over Time (All forecasts)",
#         markers=True
#     )
# else:
#     # Jeśli wybrano pojedynczy typ prognozy – wykres bez facetowania
#     fig = px.line(
#         df_combined,
#         x="Date of record",
#         y="Median Value",
#         color="Group",
#         title=f"Comparison of Median Analyst Forecasts Over Time ({selected_forecast.title()})",
#         markers=True
#     )
#
# fig.update_layout(
#     xaxis_title="Date of Record",
#     yaxis_title="Median Forecast (%)",
#     legend_title="Group"
# )
#
# st.plotly_chart(fig)
#
#
#
# # # 2. Wykres rozrzutu: Median Forecast Percent vs. P/E ratio dla wszystkich spółek
# # st.header("Median Forecast Percent vs. P/E ratio (All Stocks)")
# # if not filtered_data.empty:
# #     # Tworzymy kopię danych do wykresu
# #     plot_data = filtered_data.copy()
# #     # Dodajemy nową kolumnę, która zawiera wartość bezwzględną z kolumny "Score"
# #     plot_data["Score_abs"] = plot_data["Score"].abs()
# #
# #     fig_scatter_all = px.scatter(
# #         plot_data,
# #         x="Median Forecast Percent",
# #         y="P/E ratio",
# #         # size="Market cap clear",       # Używamy wartości bezwzględnej, aby nie było wartości ujemnych
# #         color="Sector",
# #         hover_data=["Stock"],
# #         title="Relationship between Median Forecast Percent and P/E ratio (All Stocks, Bubble size = |Score|)"
# #     )
# #     st.plotly_chart(fig_scatter_all)
# # else:
# #     st.info("Brak danych do wykresu rozrzutu.")
#
#
#
#
#
#
#
# #testy poniżej
#
# # # ----- Dodatkowe wizualizacje danych -----
# # st.header("Additional Visualizations")
#
# # # 1. Box Plot – Rozkład P/E Ratio wg Sektora
# # # Ten wykres pokazuje, jak rozkładają się wartości P/E Ratio w poszczególnych sektorach.
# # st.subheader("Distribution of P/E Ratio by Sector")
# # fig_box = px.box(
# #     df,
# #     x="Sector",
# #     y="P/E ratio",
# #     title="Distribution of P/E Ratio by Sector",
# #     points="all"  # pokazuje wszystkie punkty danych
# # )
# # # Obracamy etykiety osi X, aby były bardziej czytelne
# # fig_box.update_layout(xaxis_tickangle=-45)
# # st.plotly_chart(fig_box)
#
# # # 2. Scatter Plot – Price vs. Market Cap (Clear)
# # # Wykres rozrzutu przedstawia zależność między ceną akcji a wielkością rynkową (Market Cap Clear)
# # # Używamy skali logarytmicznej na osi Y, aby lepiej przedstawić duże różnice wartości.
# # st.subheader("Price vs. Market Cap (Clear)")
# # fig_scatter2 = px.scatter(
# #     df,
# #     x="Price",
# #     y="Market cap clear",
# #     color="Sector",
# #     hover_data=["Stock"],
# #     title="Price vs. Market Cap (Clear) (Log scale on Y-axis)"
# # )
# # fig_scatter2.update_yaxes(type="log")
# # st.plotly_chart(fig_scatter2)
#
# # # 3. Heatmap – Macierz korelacji wybranych wskaźników
# # # Ten wykres przedstawia korelacje między kluczowymi zmiennymi finansowymi, takimi jak Price, P/E Ratio, Score, Smart Score oraz prognozy.
# # st.subheader("Correlation Heatmap of Selected Financial Metrics")
# # corr_columns = [
# #     "Price", "P/E ratio", "Score", "Smart Score",
# #     "Median Forecast Percent", "High Forecast Percent", "Low Forecast Percent", "Number of analysts"
# # ]
# # corr_df = df[corr_columns].corr()
# # fig_heat = px.imshow(
# #     corr_df,
# #     text_auto=True,
# #     color_continuous_scale="RdBu_r",
# #     title="Correlation Heatmap of Selected Financial Metrics"
# # )
# # st.plotly_chart(fig_heat)
#
#
#
# # 4. Bar Chart – Top 20 spółek wg liczby analityków (posortowane malejąco)
# st.subheader("Top 20 Stocks by Number of Analysts")
#
# # Upewnij się, że kolumna "Number of analysts" w filtered_data jest liczbowa
# filtered_data["Number of analysts"] = pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")
#
# # Wybieramy tylko te wiersze, które mają niepuste wartości w "Number of analysts"
# filtered_data_notnull = filtered_data.dropna(subset=["Number of analysts"])
#
# # Pobieramy 20 rekordów z najwyższą liczbą analityków
# top_analysts = filtered_data_notnull.nlargest(20, "Number of analysts")
#
# # Sortujemy malejąco po kolumnie "Number of analysts"
# top_analysts_sorted = top_analysts.sort_values(by="Number of analysts", ascending=False)
#
# # Ustawiamy jawnie kolejność kategorii w osi X
# category_order = {"Stock": top_analysts_sorted["Stock"].tolist()}
#
# fig_bar2 = px.bar(
#     top_analysts_sorted,
#     x="Stock",
#     y="Number of analysts",
#     color="Sector",
#     title="Top 20 Stocks by Number of Analysts",
#     category_orders=category_order
# )
#
# st.plotly_chart(fig_bar2)
#
#
#
#
# # 5. Histogram – rozkład liczby analityków dla wszystkich spółek (przefiltrowanych datą)
# st.subheader("Histogram of Number of Analysts (All Filtered Stocks)")
#
# # Upewniamy się, że kolumna 'Number of analysts' jest liczbowa
# filtered_data["Number of analysts"] = pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")
#
# # Wybieramy tylko te wiersze, które mają niepuste wartości w 'Number of analysts'
# filtered_data_notnull = filtered_data.dropna(subset=["Number of analysts"])
#
# if not filtered_data_notnull.empty:
#     # Obliczamy minimalną i maksymalną liczbę analityków
#     min_val = int(filtered_data_notnull["Number of analysts"].min())
#     max_val = int(filtered_data_notnull["Number of analysts"].max())
#
#     # Liczba binów: dla każdej wartości całkowitej mamy jeden bin
#     nbins = max_val - min_val + 1
#
#     # Obliczamy dodatkowe statystyki opisowe
#     mean_val = filtered_data_notnull["Number of analysts"].mean()
#     median_val = filtered_data_notnull["Number of analysts"].median()
#
#     # Tworzymy histogram
#     fig_hist = px.histogram(
#         filtered_data_notnull,
#         x="Number of analysts",
#         nbins=nbins,
#         range_x=[min_val - 0.5, max_val + 0.5],
#         title="Distribution of Number of Analysts"
#     )
#
#     # Przygotowujemy tekst ze statystykami
#     stats_text = f"<b>Stats:</b><br>Mean: {mean_val:.2f}<br>Median: {median_val:.2f}"
#
#     # Dodajemy adnotację w prawym górnym rogu wykresu (używając odniesienia do 'paper')
#     fig_hist.add_annotation(
#         x=1,
#         y=1,
#         xref="paper",
#         yref="paper",
#         text=stats_text,
#         showarrow=False,
#         align="right",
#         bordercolor="black",
#         borderwidth=1,
#         borderpad=4,
#         bgcolor="black",
#         opacity=0.8
#     )
#
#     st.plotly_chart(fig_hist)
# else:
#     st.info("No data available for Number of analysts in the selected date.")
#
# # 5. Line Chart – Średnia wartość Fear & Greed Index w czasie
# # Wykres liniowy przedstawia, jak zmienia się średnia wartość wskaźnika Fear & Greed Index (mierzącego nastroje rynkowe) w czasie.
# st.subheader("Average Fear & Greed Index Over Time")
# df_fgi = df.dropna(subset=["Date of record", "Fear & Greed Index"])\
#            .groupby("Date of record")["Fear & Greed Index"].mean().reset_index()
# fig_line_fgi = px.line(
#     df_fgi,
#     x="Date of record",
#     y="Fear & Greed Index",
#     title="Average Fear & Greed Index Over Time"
# )
# st.plotly_chart(fig_line_fgi)
#
#
#
# # # --- Przygotowanie danych do wykresu skorelowanego ---
# #
# # # 1. Dane dla prognoz – obliczamy mediany prognoz w czasie
# # df_time = (
# #     df.dropna(subset=["Date of record"])
# #       .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
# #       .median()
# #       .reset_index()
# # )
# #
# # # 2. Dane dla Fear & Greed – obliczamy średnią wartość dla każdej daty
# # df_fgi = (
# #     df.dropna(subset=["Date of record", "Fear & Greed Index"])
# #       .groupby("Date of record")["Fear & Greed Index"]
# #       .mean()
# #       .reset_index()
# # )
# #
# # # 3. Łączymy oba zestawy danych po "Date of record"
# # df_merge = pd.merge(df_time, df_fgi, on="Date of record", how="inner")
# #
# # # 4. Normalizacja wskaźnika Fear & Greed do skali median prognoz
# # med_min = df_merge["Median Forecast Percent"].min()
# # med_max = df_merge["Median Forecast Percent"].max()
# # fgi_min = df_merge["Fear & Greed Index"].min()
# # fgi_max = df_merge["Fear & Greed Index"].max()
# #
# # if fgi_max - fgi_min != 0:
# #     df_merge["Normalized_FGI"] = (df_merge["Fear & Greed Index"] - fgi_min) / (fgi_max - fgi_min) * (med_max - med_min) + med_min
# # else:
# #     df_merge["Normalized_FGI"] = df_merge["Fear & Greed Index"]
# #
# # # 5. Obliczenie korelacji między "Median Forecast Percent" a "Fear & Greed Index"
# # corr_val = df_merge["Median Forecast Percent"].corr(df_merge["Fear & Greed Index"])
# # # Jeśli chcesz, by wartość była zawsze dodatnia (liczba od 0 do 1), użyj wartości bezwzględnej:
# # corr_val = abs(corr_val)
# #
# # # --- Tworzenie wykresu łączonego (overlay) ---
# # import plotly.graph_objects as go
# #
# # fig_combined = go.Figure()
# #
# # # Dodajemy wykresy linii dla prognoz
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Low Forecast Percent"],
# #     mode="lines+markers",
# #     name="Low Forecast Percent"
# # ))
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Median Forecast Percent"],
# #     mode="lines+markers",
# #     name="Median Forecast Percent"
# # ))
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["High Forecast Percent"],
# #     mode="lines+markers",
# #     name="High Forecast Percent"
# # ))
# #
# # # Dodajemy wykres linii dla znormalizowanego wskaźnika Fear & Greed (przerywana linia)
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Normalized_FGI"],
# #     mode="lines+markers",
# #     name="Normalized Fear & Greed",
# #     line=dict(dash="dash", color="yellow")
# # ))
# #
# # fig_combined.update_layout(
# #     title="Forecast Medians and Normalized Fear & Greed Index Over Time",
# #     xaxis_title="Date of Record",
# #     yaxis_title="Value",
# # )
# #
# # # Dodajemy adnotację z korelacją w prawym górnym rogu (referencje 'paper')
# # corr_text = f"<b>Correlation (Median Forecast vs. Fear & Greed):</b><br>{corr_val:.2f}"
# # fig_combined.add_annotation(
# #     x=1,
# #     y=1,
# #     xref="paper",
# #     yref="paper",
# #     text=corr_text,
# #     showarrow=False,
# #     align="right",
# #     bordercolor="white",
# #     borderwidth=1,
# #     borderpad=4,
# #     bgcolor="black",
# #     opacity=0.8
# # )
# #
# # st.plotly_chart(fig_combined)
#
#
#
#
#
# # # --- Przygotowanie danych do wykresu bez normalizacji Fear & Greed Index ---
# #
# # # 1. Dane dla prognoz – obliczamy mediany prognoz w czasie
# # df_time = (
# #     df.dropna(subset=["Date of record"])
# #       .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
# #       .median()
# #       .reset_index()
# # )
# #
# # # 2. Dane dla Fear & Greed – obliczamy średnią wartość dla każdej daty
# # df_fgi = (
# #     df.dropna(subset=["Date of record", "Fear & Greed Index"])
# #       .groupby("Date of record")["Fear & Greed Index"]
# #       .mean()
# #       .reset_index()
# # )
# #
# # # 3. Łączymy oba zestawy danych po "Date of record"
# # df_merge = pd.merge(df_time, df_fgi, on="Date of record", how="inner")
# #
# # # 4. Obliczenie korelacji między "Median Forecast Percent" a "Fear & Greed Index"
# # corr_val = df_merge["Median Forecast Percent"].corr(df_merge["Fear & Greed Index"])
# # corr_val = abs(corr_val)  # wartość bezwzględna, aby korelacja była w przedziale [0,1]
# #
# # # --- Tworzenie wykresu łączonego (overlay) przy użyciu Plotly Graph Objects ---
# # import plotly.graph_objects as go
# #
# # fig_combined = go.Figure()
# #
# # # Dodajemy linie dla prognoz
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Low Forecast Percent"],
# #     mode="lines+markers",
# #     name="Low Forecast Percent"
# # ))
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Median Forecast Percent"],
# #     mode="lines+markers",
# #     name="Median Forecast Percent"
# # ))
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["High Forecast Percent"],
# #     mode="lines+markers",
# #     name="High Forecast Percent"
# # ))
# #
# # # Dodajemy linię dla oryginalnego Fear & Greed Index (bez normalizacji)
# # fig_combined.add_trace(go.Scatter(
# #     x=df_merge["Date of record"],
# #     y=df_merge["Fear & Greed Index"],
# #     mode="lines+markers",
# #     name="Fear & Greed Index",
# #     line=dict(dash="dash", color="yellow")
# # ))
# #
# # fig_combined.update_layout(
# #     title="Forecast Medians and Fear & Greed Index Over Time (Without Normalization)",
# #     xaxis_title="Date of Record",
# #     yaxis_title="Value",
# # )
# #
# # # Dodajemy adnotację z wartością korelacji w prawym górnym rogu wykresu
# # # Najpierw zwiększamy dolny margines wykresu, aby zrobić miejsce pod wykresem:
# # fig_combined.update_layout(
# #     margin=dict(b=120)  # zwiększamy margines dolny, np. do 120
# # )
# #
# #
# # st.plotly_chart(fig_combined)




import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

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
    """,
    unsafe_allow_html=True
)
######### koniec kodu CSS - tu jest kod CSS do stylizowania strony - koniec kodu CSS ########

# Title of the application
st.title("Best stocks in S&P500 Index")

# # Subheader / short English heading
# st.markdown("""This site aggregates and averages data from a wide range of financial analysts to identify
#                 the best-performing stocks in the S&P 500 over a one-year horizon. By leveraging diverse insights,
#                 we aim to provide a comprehensive view of market trends and investment opportunities using the latest Data Science techniques.""")
# st.write("")

# Loading data
@st.cache_data
def load_data():
    file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
    data = pd.read_csv(file_path, delimiter=';')
    return data

# Read the data
df = load_data()


# Convert the date column if it exists
if "Date of record" in df.columns:
    df["Date of record"] = pd.to_datetime(df["Date of record"], errors='coerce')

# Date filter
if "Date of record" in df.columns:
    unique_dates = sorted(df["Date of record"].dropna().unique())
    max_date = unique_dates[-1] if unique_dates else None
    selected_date = st.sidebar.date_input("Date selector", value=max_date)
    filtered_data = df[df["Date of record"] == pd.Timestamp(selected_date)]
else:
    filtered_data = df
    st.sidebar.info("No 'Date of record' column - displaying all data.")


# ---------------

# Required columns for further analysis
required_columns = [
    "Stock", "Sector", "Price", "Low Forecast Percent", "Median Forecast Percent",
    "High Forecast Percent", "Smart Score", "Score", "P/E ratio"
]

if all(col in filtered_data.columns for col in required_columns):
    # We create a selectbox for sectors
    sectors = sorted(filtered_data["Sector"].unique())
    sector_options = ["All Sectors"] + sectors
    selected_sector = st.sidebar.selectbox("Select Sector", options=sector_options, index=0)

    # Filter data according to certain criteria
    scoring = filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
    scoring = scoring[
        (scoring["Smart Score"] > 7) &
        (scoring["Score"] > 2) &
        (scoring["Low Forecast Percent"] > -5) &
        (scoring["Score"] < 6)
        ]

    if selected_sector != "All Sectors":
        scoring = scoring[scoring["Sector"] == selected_sector]

    # Round numeric columns
    scoring = scoring.round(2)
    total_stocks = scoring.shape[0]

    if not scoring.empty:
        max_stocks = st.sidebar.slider(
            "Select number of stocks to display",
            min_value=1,
            max_value=total_stocks,
            value=10 if total_stocks >= 10 else total_stocks,
            step=1
        )
        # We limit the number of displayed stocks to 'max_stocks'
        scoring = scoring.head(max_stocks)

else:
    # Dodajemy obsługę błędu w przypadku braku wymaganych kolumn
    st.error("Missing required columns in the data.")

# ---------

# Display 3 best companies as large tickers (if there are at least 3 stocks)
if not scoring.empty and scoring.shape[0] >= 3:
    best_three = scoring.head(3)
    col1, col2, col3 = st.columns(3)

    col1.metric(
        label=f"Top pick for today:",
        value=best_three.iloc[0]["Stock"]
        # delta=f"Score: {best_three.iloc[0]['Score']}"
    )
    col2.metric(
        label=f"2nd top pick for today:",
        value=best_three.iloc[1]["Stock"],
        # delta=f"Score: {best_three.iloc[1]['Score']}"
    )
    col3.metric(
        label=f"3rd top pick for today:",
        value=best_three.iloc[2]["Stock"],
        # delta=f"Score: {best_three.iloc[2]['Score']}"
    )
else:
    st.info("Not enough stocks in the filtered set to display top 3 tickers.")


# Subheader / short English heading
# st.markdown("""This site aggregates and averages data from a wide range of financial analysts to identify
#                 the best-performing stocks in the S&P 500 over a one-year horizon. By leveraging diverse insights,
#                 we aim to provide a comprehensive view of market trends and investment opportunities using the latest
#                 Data Science techniques. Go further to dive deep into the details and understand better our top picks.
#                 Data on the page is updated everyday morning around 8 AM UTC. Remember that investing is connected with
#                 risk and you can lose your money. Our site is not financial advice.""")
st.markdown("""\
Welcome to our website, where we aggregate and analyze data from a wide range of financial analysts to identify the 
best-performing stocks in the S&P 500 over a one-year horizon. By leveraging diverse insights and the latest 
data science techniques, our platform offers a comprehensive view of market trends and investment opportunities. 
Explore the details to gain a deeper understanding of our top picks. Data is updated every morning around 8 AM UTC.
""")

st.markdown("<hr>", unsafe_allow_html=True)
# st.write("")


# if not scoring.empty:
#     import plotly.express as px
#     fig_treemap = px.treemap(
#         scoring,
#         path=["Sector", "Stock"],  # hierarchia: najpierw sektor, potem ticker
#         values="Median Forecast Percent",            # wielkość prostokąta zależy od Score
#         color="Median Forecast Percent",             # kolor również określany jest przez Score
#         color_continuous_scale="Greens",  # możesz wybrać inną skalę kolorów
#         title="Treemap of Selected Stocks (Size by Score)"
#     )
#     st.plotly_chart(fig_treemap)
# else:
#     st.info("No data available for the treemap.")
#



if filtered_data.empty:
    st.error("No data for the selected date!")
else:
    # Compute medians for the chosen date
    med_low = filtered_data["Low Forecast Percent"].median()
    med_median = filtered_data["Median Forecast Percent"].median()
    med_high = filtered_data["High Forecast Percent"].median()


    # Compute deltas if previous date is available
    prev_date = None
    if "Date of record" in df.columns:
        earlier_dates = [d for d in unique_dates if d < pd.Timestamp(selected_date)]
        if earlier_dates:
            prev_date = earlier_dates[-1]

    delta_low = delta_median = delta_high = None
    if prev_date is not None:
        prev_data = df[df["Date of record"] == prev_date]
        delta_low = med_low - prev_data["Low Forecast Percent"].median()
        delta_median = med_median - prev_data["Median Forecast Percent"].median()
        delta_high = med_high - prev_data["High Forecast Percent"].median()

    st.markdown("### Today's 1-year analyst forecast for the S&P 500 Index")
    col1, col2, col3 = st.columns(3)
    col1.metric("Median - low forecast", f"{med_low:.2f}%", delta=f"{delta_low:+.2f}%" if delta_low is not None else "N/A")
    col2.metric("Median - average forecasts", f"{med_median:.2f}%", delta=f"{delta_median:+.2f}%" if delta_median is not None else "N/A")
    col3.metric("Median - high forecast", f"{med_high:.2f}%", delta=f"{delta_high:+.2f}%" if delta_high is not None else "N/A")

    # st.write("")
    # st.write("")


    # -------------------------------------------
    # Line chart showing median forecasts over time (all S&P500)
    df_time = (
        df.dropna(subset=["Date of record"])
          .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
          .median()
          .round(2)
          .reset_index()
    )

    fig = px.line(
        df_time,
        x="Date of record",
        y=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
        title="Median Analyst Forecasts Over Time (S&P500)",
        markers=True
    )
    st.plotly_chart(fig)
    # st.write("")
    st.markdown("<hr>", unsafe_allow_html=True)

# -------------------------------------------



# Title and description
st.header("Selected stocks by our AI algorithm")
st.markdown(
    f"Our sophisticated algorithm, merging 9 variables, has identified {total_stocks} best stocks for today. "
    f"You can further refine the list using the slider on the left sidebar to potentially achieve higher returns."
)

# Compute medians for the filtered stocks
if not scoring.empty:
    med_low_scoring = scoring["Low Forecast Percent"].median()
    med_median_scoring = scoring["Median Forecast Percent"].median()
    med_high_scoring = scoring["High Forecast Percent"].median()

    # Compute deltas for these filtered stocks (if previous date is available)
    delta_low_scoring = delta_median_scoring = delta_high_scoring = None
    if prev_date is not None:
        prev_filtered_data = df[df["Date of record"] == prev_date]
        if all(col in prev_filtered_data.columns for col in required_columns):
            prev_scoring = prev_filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
            prev_scoring = prev_scoring[
                (prev_scoring["Smart Score"] > 7) &
                (prev_scoring["Score"] > 2) &
                (prev_scoring["Low Forecast Percent"] > -5) &
                (prev_scoring["Score"] < 10)
            ]
            if selected_sector != "All Sectors":
                prev_scoring = prev_scoring[prev_scoring["Sector"] == selected_sector]
            prev_med_low_scoring = prev_scoring["Low Forecast Percent"].median()
            prev_med_median_scoring = prev_scoring["Median Forecast Percent"].median()
            prev_med_high_scoring = prev_scoring["High Forecast Percent"].median()

            delta_low_scoring = med_low_scoring - prev_med_low_scoring
            delta_median_scoring = med_median_scoring - prev_med_median_scoring
            delta_high_scoring = med_high_scoring - prev_med_high_scoring

    st.write("")
    st.markdown("##### Today's 1-year analyst forecast for selected stocks")
    col4, col5, col6 = st.columns(3)
    col4.metric("Median - low forecast", f"{med_low_scoring:.2f}%", delta=f"{delta_low_scoring:+.2f}%" if delta_low_scoring is not None else "N/A")
    col5.metric("Median - median forecast", f"{med_median_scoring:.2f}%", delta=f"{delta_median_scoring:+.2f}%" if delta_median_scoring is not None else "N/A")
    col6.metric("Median - high forecast", f"{med_high_scoring:.2f}%", delta=f"{delta_high_scoring:+.2f}%" if delta_high_scoring is not None else "N/A")

    # Bar chart for these selected stocks
    displayed_stocks = scoring  # we already have the top N in 'scoring'
    category_order = {"Stock": displayed_stocks.sort_values("Score", ascending=False)["Stock"].tolist()}

    fig_bar = px.bar(
        displayed_stocks,
        x="Stock",
        y="Score",
        color="Sector",
        title="Use the slider on the left sidebar to show more or fewer stocks in the chart.",
        category_orders=category_order,
        hover_data={
            "Price": True,
            "Score": True,
            "P/E ratio": True,
            "Low Forecast Percent": True,
            "Median Forecast Percent": True,
            "High Forecast Percent": True,
            "Smart Score": True
        }
    )
    st.plotly_chart(fig_bar)
else:
    st.info("No data available for the bar chart.")

# st.write("")
st.markdown("<hr>", unsafe_allow_html=True)






st.header("Median Forecast Percent vs. P/E ratio")

st.markdown("""
The Price-to-Earnings (P/E) ratio compares a company's current share price to its earnings per share, 
providing insight into market valuation and growth expectations. A lower P/E may indicate that a company 
is undervalued and has potential for future growth, whereas a higher P/E suggests overvaluation. In this scatter 
plot, the bubble size is correlated with the score feature (valid only for "Selected Stocks", as Score could also 
achieve negative values).
""")

if not scoring.empty:
    # 1. Usuwamy wiersze z NaN/ujemnym Score z filtered_data, jeśli chcemy użyć size="Score"
    #    Zakomentowane, aby uniknąć błędu. Możesz to włączyć, jeśli chcesz dodać dynamiczny rozmiar także w 'Filtered Data'.
    # filtered_data_nonneg = filtered_data.dropna(subset=["Score"]).copy()
    # filtered_data_nonneg = filtered_data_nonneg[filtered_data_nonneg["Score"] >= 0]

    # --- Wykres PX dla scoring (rozmiar bąbelków = Score) ---
    fig_scoring_px = px.scatter(
        scoring,
        x="Median Forecast Percent",
        y="P/E ratio",
        color="Sector",
        size="Score",  # dynamiczny rozmiar bazujący na Score
        hover_data=["Stock", "Price", "Score", "Smart Score"],
        title="Median Forecast Percent vs. P/E ratio (Selected Stocks)"
    )

    # --- Wykres PX dla filtered_data (bez size="Score" lub z wykomentowanym size) ---
    fig_filtered_px = px.scatter(
        filtered_data,
        x="Median Forecast Percent",
        y="P/E ratio",
        color="Sector",
        # size="Score", # zakomentowane, aby uniknąć błędu przy ujemnym Score
        hover_data=["Stock", "Price", "Score", "Smart Score"],
        title="Median Forecast Percent vs. P/E ratio (All S&P500 Stocks)"
    )

    # 2. Konwertujemy oba wykresy na go.Figure i łączymy je
    fig_combined = go.Figure(data=fig_scoring_px.data + fig_filtered_px.data)

    # Liczba trace'ów w każdym wykresie (każdy sektor to osobny trace)
    scoring_traces = len(fig_scoring_px.data)
    filtered_traces = len(fig_filtered_px.data)

    # Domyślnie: widoczne scoring, ukryte filtered_data
    for i in range(scoring_traces):
        fig_combined.data[i].visible = True
    for i in range(scoring_traces, scoring_traces + filtered_traces):
        fig_combined.data[i].visible = False

    # 3. Definicja przycisków (update menus)
    fig_combined.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.5,
                y=1.15,
                xanchor="center",
                yanchor="top",
                # Ustawienia wyglądu całej grupy przycisków
                bgcolor="Orange",      # zielone tło
                bordercolor="black",
                borderwidth=2,
                font=dict(color="black"),  # czarny kolor tekstu w przyciskach
                active=0,                  # domyślnie aktywny pierwszy przycisk
                buttons=[
                    dict(
                        label="Selected Stocks",
                        method="update",
                        args=[
                            {"visible": [True] * scoring_traces + [False] * filtered_traces},
                            {"title": "Median Forecast Percent vs. P/E ratio (Scoring)"}
                        ],
                    ),
                    dict(
                        label="All S&P500 Stocks",
                        method="update",
                        args=[
                            {"visible": [False] * scoring_traces + [True] * filtered_traces},
                            {"title": "Median Forecast Percent vs. P/E ratio (Filtered Data)"}
                        ],
                    ),
                ],
            )
        ],
        # Parametry osi, legendy, itp.
        xaxis_title="Median Forecast Percent",
        yaxis_title="P/E ratio",
        legend_title="Sector",
        # Zwiększamy czytelność legendy
        legend=dict(
            itemsizing="constant",
            itemwidth=40,
            y = 0.5,
            yanchor = "middle",
            tracegroupgap=0
        )
    )

    # (Opcjonalnie) można powiększyć markery w całym wykresie, co również wpływa na legendę:
    # fig_combined.update_traces(marker=dict(size=12), selector={"mode": "markers"})

    st.plotly_chart(fig_combined)
else:
    st.info("No data available for the scatter plot.")



st.markdown("<hr>", unsafe_allow_html=True)


# ----- NEW: Historical lines for the top N selected stocks -----

# 1. Identify the selected stocks from the final 'scoring'
#    (these are top N chosen by the user)
if not scoring.empty:
    selected_stocks = scoring["Stock"].unique()
else:
    selected_stocks = []

# 2. For the "All S&P 500" baseline, we already have df_time_all (median of all stocks)
df_time_all = (
    df.dropna(subset=["Date of record"])
      .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
      .median()
      .reset_index()
)

# 3. For the "Filtered Stocks" (top N), we retrieve all historical data for the same tickers
df_scoring_all = df[df["Stock"].isin(selected_stocks)].copy()
df_scoring_all = df_scoring_all[
    (df_scoring_all["Smart Score"] > 7) &
    (df_scoring_all["Score"] > 2) &
    (df_scoring_all["Low Forecast Percent"] > -5) &
    (df_scoring_all["Score"] < 6)
]

df_time_scoring = (
    df_scoring_all.dropna(subset=["Date of record"])
                  .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
                  .median()
                  .reset_index()
)

# ----- Reshape data to "long" format -----
# For ALL S&P500:
df_all_melt = df_time_all.melt(
    id_vars=["Date of record"],
    value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
    var_name="Forecast Type",
    value_name="Median Value"
)
df_all_melt["Group"] = "All Stocks"

# For the top N filtered stocks:
df_scoring_melt = df_time_scoring.melt(
    id_vars=["Date of record"],
    value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
    var_name="Forecast Type",
    value_name="Median Value"
)
df_scoring_melt["Group"] = "Filtered Stocks"

# Combine both sets
df_combined = pd.concat([df_all_melt, df_scoring_melt])

# New forecast-type selector
forecast_options = ["All forecasts", "High forecasts", "Med forecasts", "Low forecasts"]
selected_forecast = st.sidebar.selectbox("Select forecast type", options=forecast_options, index=0, key="forecast_select")

# Filter data if user doesn't want all forecasts
if selected_forecast != "All forecasts":
    if selected_forecast == "High forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "High Forecast Percent"]
    elif selected_forecast == "Med forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "Median Forecast Percent"]
    elif selected_forecast == "Low forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "Low Forecast Percent"]

# Create the line chart
if selected_forecast == "All forecasts":
    # If showing all forecasts, we facet them
    fig = px.line(
        round(df_combined,2),
        x="Date of record",
        y="Median Value",
        color="Group",
        facet_col="Forecast Type",
        # title="Comparison of Median Analyst Forecasts Over Time (All forecasts)",
        markers=True
    )
else:
    # Single forecast type
    fig = px.line(
        round(df_combined,2),
        x="Date of record",
        y="Median Value",
        color="Group",
        title=f"Comparison of Median Analyst Forecasts Over Time ({selected_forecast.title()})",
        markers=True
    )

fig.update_layout(
    xaxis_title="Date of Record",
    yaxis_title="Median Forecast (%)",
    legend_title="Group"
)

if selected_forecast == "All forecasts":
    # If showing all forecasts, we facet them
    fig = px.line(
        round(df_combined,2),
        x="Date of record",
        y="Median Value",
        color="Group",
        facet_col="Forecast Type",
        markers=True,
        title=f"Comparison of Median Analyst Forecasts Over Time ({selected_forecast.title()})",
        labels={"Forecast Type": ""}
    )


    # Update facet labels to show only the desired text
    def update_facet_label(annotation):
        txt = annotation.text
        if "Low Forecast Percent" in txt:
            new_txt = "Low Forecasts"
        elif "Median Forecast Percent" in txt:
            new_txt = "Median Forecasts"
        elif "High Forecast Percent" in txt:
            new_txt = "High Forecasts"
        else:
            new_txt = txt
        annotation.update(text=new_txt)


    fig.for_each_annotation(update_facet_label)
else:
    # Single forecast type
    fig = px.line(
        df_combined,
        x="Date of record",
        y="Median Value",
        color="Group",
        title=f"Comparison of Median Analyst Forecasts Over Time ({selected_forecast.title()})",
        markers=True
    )

st.header("Historical Analyst Forecast Trends")
st.markdown("""
This section displays the historical evolution of analyst forecast medians over time for both the entire S&P 500 and the top stocks selected by our AI algorithm. The forecasts are categorized as Low forecasts, Median Forecasts, and High Forecasts, allowing you to observe trends in analysts' expectations and compare the performance of filtered stocks against the broader market. Use the forecast type selector to focus on a specific forecast scenario.
""")


st.plotly_chart(fig)

st.markdown("<hr>", unsafe_allow_html=True)
# st.write("")


# 4. Bar Chart – Top 20 stocks by number of analysts (sorted descending)
st.header("Top 20 Stocks by Number of Analysts ")
st.markdown("""
This bar chart displays the top 20 stocks with the highest analyst coverage within the S&P 500 index. 
Analyst coverage is a critical indicator of market interest and confidence, as a larger number of analysts 
typically leads to more robust and reliable forecasts. In general, the greater the analyst coverage, 
the more likely it is that our forecasts for that stock are accurate.
""")


# Ensure "Number of analysts" is numeric
filtered_data["Number of analysts"] = pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")

filtered_data_notnull = filtered_data.dropna(subset=["Number of analysts"])
top_analysts = filtered_data_notnull.nlargest(20, "Number of analysts")
top_analysts_sorted = top_analysts.sort_values(by="Number of analysts", ascending=False)
category_order = {"Stock": top_analysts_sorted["Stock"].tolist()}

fig_bar2 = px.bar(
    top_analysts_sorted,
    x="Stock",
    y="Number of analysts",
    color="Sector",
    title="From entire S&P500 Index",
    category_orders=category_order
)

# Calculate statistics for annotation
mean_val = filtered_data_notnull["Number of analysts"].mean()
median_val = filtered_data_notnull["Number of analysts"].median()

stats_text = f"<b>Mean number of analysts in S&P500: {mean_val:.2f}</b>"
fig_bar2.add_annotation(
    x=1,
    y=1,
    xref="paper",
    yref="paper",
    text=stats_text,
    showarrow=False,
    align="right",
    bordercolor="black",
    borderwidth=1,
    borderpad=4,
    bgcolor="black",
    opacity=0.8
)

st.plotly_chart(fig_bar2)

st.markdown("<hr>", unsafe_allow_html=True)
# st.write("")




# 6. Line Chart – Average Fear & Greed Index Over Time
st.header("Average Fear & Greed Index Over Time")
st.markdown(""" This line chart displays the average Fear & Greed Index over time, a key market sentiment indicator. 
The Fear & Greed Index quantifies investor emotions—high values suggest excessive optimism (greed), 
while low values indicate heightened fear. Monitoring these trends can help identify shifts in market sentiment, 
potentially signaling upcoming changes in market behavior.""")

df_fgi = (
    df.dropna(subset=["Date of record", "Fear & Greed Index"])
      .groupby("Date of record")["Fear & Greed Index"]
      .mean()
      .reset_index()
)
fig_line_fgi = px.line(
    df_fgi,
    x="Date of record",
    y="Fear & Greed Index"
    # title="Average Fear & Greed Index Over Time"
)
st.plotly_chart(fig_line_fgi)
st.markdown("<hr>", unsafe_allow_html=True)



st.header("Average Forecast 1y Returns by Sector")
st.markdown(""" This boxplot displays the average forecast returns for companies in the S&P 500, grouped by sector. 
By presenting the low, median, and high forecasted returns for each sector, the chart offers a snapshot of 
market expectations and potential performance across different industries. Investors can use this visualization 
as a quick indicator of which sectors might offer the most promising opportunities—especially for investments 
like sector-specific ETFs (inside S&P 500 companies).""")

if filtered_data.empty:
    st.error("No data available for the selected date!")
else:
    needed_cols = ["Sector", "Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]
    missing_cols = [col for col in needed_cols if col not in filtered_data.columns]
    if missing_cols:
        st.error(f"Missing columns: {missing_cols}")
    else:
        # Grupujemy dane po sektorze z danych dla wybranej daty
        sectormeanforecast = filtered_data.groupby("Sector")[
            ["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]
        ].mean().reset_index().round(2)

        # Sortujemy według średniej wartości "Median Forecast Percent" (od najmniejszej do największej)
        sectormeanforecast = sectormeanforecast.sort_values("Median Forecast Percent", ascending=True)

        # Przekształcamy dane do formatu long (melt)
        df_long = sectormeanforecast.melt(
            id_vars="Sector",
            value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
            var_name="Forecast Type",
            value_name="Forecast Percent"
        )

        # Ustalamy kolejność sektorów zgodnie z posortowanymi danymi
        category_order = {"Sector": sectormeanforecast["Sector"].tolist()}

        # Rysujemy wykres pudełkowy za pomocą Plotly Express
        fig = px.box(
            df_long,
            x="Sector",
            y="Forecast Percent",
            # title="Average analyst forecasts by sector (S&P 500)",
            category_orders=category_order
        )

        fig.update_layout(
            xaxis_title="Sector",
            yaxis_title="Forecast (%)"
        )

        st.plotly_chart(fig)


st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""\
Please note: Investing involves risk and you may lose some or all of your capital. 
This site is provided for informational purposes only and does not constitute financial advice.
""")
st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)