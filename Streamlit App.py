import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

######### początek kodu CSS - tu jest kod CSS do stylizowania strony - początek ########
st.markdown(
    """
    <style>
    /* Ten CSS pogrubia wartości w komponentach metric */
    [data-testid="stMetricValue"] {
        font-weight: bold;
    }
    /* Opcjonalnie: pogrubienie etykiet metryk */
    [data-testid="stMetricLabel"] {
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)
######### koniec kodu CSS - tu jest kod CSS do stylizowania strony - koniec kodu CSS ########

# Tytuł aplikacji
st.title("Best stocks S&P500 Index ")
# st.write("")
# st.write("")
# Mniejszy heading z opisem w języku angielskim
st.markdown("""This site aggregates and averages data from a wide range of financial analysts to identify 
                the best-performing stocks in the S&P 500 over a one-year horizon. By leveraging diverse insights,
                we aim to provide a comprehensive view of market trends and investment opportunities using the latest Data Science techniques.""")
st.write("")

# Wczytanie danych
@st.cache_data
def load_data():
    file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
    data = pd.read_csv(file_path, delimiter=';')
    return data

# Wczytanie danych
df = load_data()

# Konwersja kolumny daty na format datetime, jeśli taka kolumna istnieje
if "Date of record" in df.columns:
    df["Date of record"] = pd.to_datetime(df["Date of record"], errors='coerce')

# Filtr daty
if "Date of record" in df.columns:
    # Sortujemy wszystkie dostępne daty
    unique_dates = sorted(df["Date of record"].dropna().unique())
    # Domyślnie ustawiamy najnowszą datę
    max_date = unique_dates[-1] if unique_dates else None
    selected_date = st.sidebar.date_input("Date selector", value=max_date)
    filtered_data = df[df["Date of record"] == pd.Timestamp(selected_date)]
else:
    filtered_data = df
    st.sidebar.info("Brak kolumny 'Date of record' - wyświetlane są wszystkie dane.")


if filtered_data.empty:
    st.error("Brak danych dla wybranej daty!")
else:
    # Oblicz mediany dla wybranej daty
    med_low = filtered_data["Low Forecast Percent"].median()
    med_median = filtered_data["Median Forecast Percent"].median()
    med_high = filtered_data["High Forecast Percent"].median()

    # Oblicz delta z poprzedniej sesji, jeśli jest dostępna
    # Znajdujemy poprzednią datę mniejszą od wybranej
    prev_date = None
    if "Date of record" in df.columns:
        earlier_dates = [d for d in unique_dates if d < pd.Timestamp(selected_date)]
        if earlier_dates:
            prev_date = earlier_dates[-1]  # najnowsza data przed wybraną

    # Inicjujemy zmienne delty
    delta_low = delta_median = delta_high = None
    if prev_date is not None:
        prev_data = df[df["Date of record"] == prev_date]
        delta_low = med_low - prev_data["Low Forecast Percent"].median()
        delta_median = med_median - prev_data["Median Forecast Percent"].median()
        delta_high = med_high - prev_data["High Forecast Percent"].median()

    st.markdown("### Today's 1-year analyst forecast for the S&P 500 Index")

    col1, col2, col3 = st.columns(3)
    # Używamy parametru delta w st.metric
    col1.metric("Median - low forecast", f"{med_low:.2f}%", delta=f"{delta_low:+.2f}%" if delta_low is not None else "N/A")
    col2.metric("Median - average forecasts", f"{med_median:.2f}%", delta=f"{delta_median:+.2f}%" if delta_median is not None else "N/A")
    col3.metric("Median - high forecast", f"{med_high:.2f}%", delta=f"{delta_high:+.2f}%" if delta_high is not None else "N/A")

    st.write("")
    st.write("")

   # -------------------------------------------
    # Wykres przedstawiający zmiany median w czasie
    # Grupa danych według daty i obliczenie median dla każdej daty
    df_time = df.dropna(subset=["Date of record"]).groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]].median().reset_index()

    # st.markdown("### Zmiana median prognoz w czasie")
    # Możesz użyć wykresu liniowego np. za pomocą Plotly Express
    fig = px.line(df_time, x="Date of record", y=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
                  title="Zmiana median prognoz analityków w czasie",
                  markers=True)
    st.plotly_chart(fig)

    st.write("")
    st.write("")
    st.write("")
    st.write("")
# -------------------------------------------

# Definicja wymaganych kolumn dla dalszej analizy
required_columns = [
    "Stock", "Sector", "Price", "Low Forecast Percent", "Median Forecast Percent",
    "High Forecast Percent", "Smart Score", "Score", "P/E ratio"
]

if all(col in filtered_data.columns for col in required_columns):
    # Pobieramy unikatowe sektory i tworzymy widget selectbox
    sectors = sorted(filtered_data["Sector"].unique())
    sector_options = ["All Sectors"] + sectors
    selected_sector = st.sidebar.selectbox("Select Sector", options=sector_options, index=0)

    # Przetwarzamy dane według kryteriów
    scoring = filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
    scoring = scoring[
        (scoring["Smart Score"] > 7) &
        (scoring["Score"] > 2) &
        (scoring["Low Forecast Percent"] > -5) &
        (scoring["Score"] < 10)
        ]

    # Jeśli wybrano konkretny sektor, przefiltruj dane
    if selected_sector != "All Sectors":
        scoring = scoring[scoring["Sector"] == selected_sector]

    # Zaokrąglamy wszystkie kolumny numeryczne do dwóch miejsc po przecinku
    scoring = scoring.round(2)

    st.header("Najlepsze spółki według kryteriów")
    if scoring.empty:
        st.warning("Żadna ze spółek nie spełnia wybranych kryteriów. Spróbuj zmienić filtr sektorów lub kryteria.")
    else:
        st.dataframe(scoring)
else:
    st.error("Brak wymaganych kolumn w danych.")

# Obliczamy mediany dla przefiltrowanych spółek
med_low_scoring = scoring["Low Forecast Percent"].median()
med_median_scoring = scoring["Median Forecast Percent"].median()
med_high_scoring = scoring["High Forecast Percent"].median()

# Obliczamy delta dla przefiltrowanych spółek, korzystając z danych z poprzedniej sesji (jeśli dostępne)
delta_low_scoring = delta_median_scoring = delta_high_scoring = None
if prev_date is not None:
    # Pobieramy dane z poprzedniej daty
    prev_filtered_data = df[df["Date of record"] == prev_date]
    # Stosujemy te same kryteria, aby otrzymać poprzednią wersję scoringu
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

    st.markdown("### Today's 1-year analyst forecast for filtered stocks")
    col4, col5, col6 = st.columns(3)
    col4.metric("Median - low forecast", f"{med_low_scoring:.2f}%", delta=f"{delta_low_scoring:+.2f}%" if delta_low_scoring is not None else "N/A")
    col5.metric("Median - average forecast", f"{med_median_scoring:.2f}%", delta=f"{delta_median_scoring:+.2f}%" if delta_median_scoring is not None else "N/A")
    col6.metric("Median - high forecast", f"{med_high_scoring:.2f}%", delta=f"{delta_high_scoring:+.2f}%" if delta_high_scoring is not None else "N/A")
else:
    st.error("Brak wymaganych kolumn w danych.")


st.write("")
st.write("")
st.write("")
st.write("")

# Dodatkowe statystyki i wizualizacje

# 1. Wykres słupkowy Top 10 spółek wg Score
st.header("Top 10 spółek na dziś")
if not scoring.empty:
    top10 = scoring.head(10)
    # Jawnie ustawiamy kolejność spółek na osi x według wartości 'Score' (malejąco)
    category_order = {
        "Stock": top10.sort_values("Score", ascending=False)["Stock"].tolist()
    }

    fig_bar = px.bar(top10, x="Stock", y="Score", color="Sector",
                     category_orders=category_order)
    st.plotly_chart(fig_bar)
else:
    st.info("Brak danych do wykresu słupkowego.")




# 2. Wykres rozrzutu: Cena vs. P/E ratio
st.header("Median Forecast Percent vs. P/E ratio")
if not scoring.empty:
    fig_scatter = px.scatter(scoring, x="Median Forecast Percent", y="P/E ratio", size="Score", color="Sector",
                             hover_data=["Stock"],
                             title="Zależność ceny od P/E ratio (rozmiar bąbelka = Score)")
    st.plotly_chart(fig_scatter)
else:
    st.info("Brak danych do wykresu rozrzutu.")




# ----- Dla całego S&P500 -----
df_time_all = (
    df.dropna(subset=["Date of record"])
      .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
      .median()
      .reset_index()
)

# ----- Dla przefiltrowanych spółek (historical scoring) -----
# Tworzymy kopię danych i stosujemy te same kryteria filtrowania, jakie używamy przy tworzeniu scoring
df_scoring_all = df.copy()
df_scoring_all = df_scoring_all[
    (df_scoring_all["Smart Score"] > 7) &
    (df_scoring_all["Score"] > 2) &
    (df_scoring_all["Low Forecast Percent"] > -5) &
    (df_scoring_all["Score"] < 10)
]

# Jeśli użytkownik wybrał konkretny sektor, stosujemy dodatkowy filtr:
if selected_sector != "All Sectors":
    df_scoring_all = df_scoring_all[df_scoring_all["Sector"] == selected_sector]

df_time_scoring = (
    df_scoring_all.dropna(subset=["Date of record"])
                  .groupby("Date of record")[["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]]
                  .median()
                  .reset_index()
)

# ----- Przekształcenie danych do formatu long -----
# Dla całego S&P500:
df_all_melt = df_time_all.melt(
    id_vars=["Date of record"],
    value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
    var_name="Forecast Type",
    value_name="Median Value"
)
df_all_melt["Group"] = "All Stocks"

# Dla przefiltrowanych spółek:
df_scoring_melt = df_time_scoring.melt(
    id_vars=["Date of record"],
    value_vars=["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"],
    var_name="Forecast Type",
    value_name="Median Value"
)
df_scoring_melt["Group"] = "Filtered Stocks"

# Łączymy oba zestawy danych:
df_combined = pd.concat([df_all_melt, df_scoring_melt])

# ----- Nowy selektor do wyboru typu prognozy -----
forecast_options = ["All forecasts", "High forecasts", "Med forecasts", "Low forecasts"]
selected_forecast = st.sidebar.selectbox("Select forecast type", options=forecast_options, index=0, key="forecast_select")

# Jeśli użytkownik nie chce wyświetlać wszystkiego, filtrujemy dane:
if selected_forecast != "All forecasts":
    if selected_forecast == "High forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "High Forecast Percent"]
    elif selected_forecast == "Med forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "Median Forecast Percent"]
    elif selected_forecast == "Low forecasts":
        df_combined = df_combined[df_combined["Forecast Type"] == "Low Forecast Percent"]

# ----- Tworzenie wykresu -----
if selected_forecast == "All forecasts":
    # Jeśli pokazujemy wszystkie prognozy – stosujemy facetowanie
    fig = px.line(
        df_combined,
        x="Date of record",
        y="Median Value",
        color="Group",
        facet_col="Forecast Type",
        title="Comparison of Median Analyst Forecasts Over Time (All forecasts)",
        markers=True
    )
else:
    # Jeśli wybrano pojedynczy typ prognozy – wykres bez facetowania
    fig = px.line(
        df_combined,
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

st.plotly_chart(fig)



# 2. Wykres rozrzutu: Median Forecast Percent vs. P/E ratio dla wszystkich spółek
st.header("Median Forecast Percent vs. P/E ratio (All Stocks)")
if not filtered_data.empty:
    # Tworzymy kopię danych do wykresu
    plot_data = filtered_data.copy()
    # Dodajemy nową kolumnę, która zawiera wartość bezwzględną z kolumny "Score"
    plot_data["Score_abs"] = plot_data["Score"].abs()

    fig_scatter_all = px.scatter(
        plot_data,
        x="Median Forecast Percent",
        y="P/E ratio",
        # size="Market cap clear",       # Używamy wartości bezwzględnej, aby nie było wartości ujemnych
        color="Sector",
        hover_data=["Stock"],
        title="Relationship between Median Forecast Percent and P/E ratio (All Stocks, Bubble size = |Score|)"
    )
    st.plotly_chart(fig_scatter_all)
else:
    st.info("Brak danych do wykresu rozrzutu.")







#testy poniżej

# ----- Dodatkowe wizualizacje danych -----
st.header("Additional Visualizations")

# 1. Box Plot – Rozkład P/E Ratio wg Sektora
# Ten wykres pokazuje, jak rozkładają się wartości P/E Ratio w poszczególnych sektorach.
st.subheader("Distribution of P/E Ratio by Sector")
fig_box = px.box(
    df,
    x="Sector",
    y="P/E ratio",
    title="Distribution of P/E Ratio by Sector",
    points="all"  # pokazuje wszystkie punkty danych
)
# Obracamy etykiety osi X, aby były bardziej czytelne
fig_box.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_box)

# 2. Scatter Plot – Price vs. Market Cap (Clear)
# Wykres rozrzutu przedstawia zależność między ceną akcji a wielkością rynkową (Market Cap Clear)
# Używamy skali logarytmicznej na osi Y, aby lepiej przedstawić duże różnice wartości.
st.subheader("Price vs. Market Cap (Clear)")
fig_scatter2 = px.scatter(
    df,
    x="Price",
    y="Market cap clear",
    color="Sector",
    hover_data=["Stock"],
    title="Price vs. Market Cap (Clear) (Log scale on Y-axis)"
)
fig_scatter2.update_yaxes(type="log")
st.plotly_chart(fig_scatter2)

# 3. Heatmap – Macierz korelacji wybranych wskaźników
# Ten wykres przedstawia korelacje między kluczowymi zmiennymi finansowymi, takimi jak Price, P/E Ratio, Score, Smart Score oraz prognozy.
st.subheader("Correlation Heatmap of Selected Financial Metrics")
corr_columns = [
    "Price", "P/E ratio", "Score", "Smart Score",
    "Median Forecast Percent", "High Forecast Percent", "Low Forecast Percent"
]
corr_df = df[corr_columns].corr()
fig_heat = px.imshow(
    corr_df,
    text_auto=True,
    color_continuous_scale="RdBu_r",
    title="Correlation Heatmap of Selected Financial Metrics"
)
st.plotly_chart(fig_heat)

# 4. Bar Chart – Top 10 spółek wg liczby analityków
# Wykres słupkowy przedstawia 10 spółek, które mają największą liczbę analityków, co może świadczyć o dużym zainteresowaniu rynkowym.
st.subheader("Top 10 Stocks by Number of Analysts")
# Upewniamy się, że kolumna "Number of analysts" jest liczbowa
df["Number of analysts"] = pd.to_numeric(df["Number of analysts"], errors="coerce")
top_analysts = df.nlargest(10, "Number of analysts")
fig_bar2 = px.bar(
    top_analysts,
    x="Stock",
    y="Number of analysts",
    color="Sector",
    title="Top 10 Stocks by Number of Analysts"
)
st.plotly_chart(fig_bar2)

# 5. Line Chart – Średnia wartość Fear & Greed Index w czasie
# Wykres liniowy przedstawia, jak zmienia się średnia wartość wskaźnika Fear & Greed Index (mierzącego nastroje rynkowe) w czasie.
st.subheader("Average Fear & Greed Index Over Time")
df_fgi = df.dropna(subset=["Date of record", "Fear & Greed Index"])\
           .groupby("Date of record")["Fear & Greed Index"].mean().reset_index()
fig_line_fgi = px.line(
    df_fgi,
    x="Date of record",
    y="Fear & Greed Index",
    title="Average Fear & Greed Index Over Time"
)
st.plotly_chart(fig_line_fgi)



