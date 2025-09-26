import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from openai import OpenAI
import re
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
######### koniec kodu CSS - tu jest kod CSS do stylizowania strony - koniec kodu CSS ########


# --- utils ---------------------------------------------------------------
def clean_numeric(df: pd.DataFrame, columns: list[str]):
    """
    Zamienia wskazane kolumny na float.
    Zwraca krotkę: (oczyszczony_df, dict{kolumna: DataFrame-z-błędami})
    """
    bad_values: dict[str, pd.DataFrame] = {}

    for col in columns:
        # zachowaj oryginał, a potem spróbuj na float
        col_clean = (
            df[col].astype(str)
                  .str.replace(",", ".", regex=False)   # 1,23 → 1.23
                  .str.strip()
        )
        as_num = pd.to_numeric(col_clean, errors="coerce")

        # zapisz w df
        df[col] = as_num

        # zbierz wadliwe wiersze
        mask_bad = as_num.isna() & col_clean.notna()
        if mask_bad.any():
            bad_values[col] = df.loc[mask_bad, ["Stock", col]].copy()

    return df, bad_values
# ------------------------------------------------------------------------


# Title of the application
st.title("Best stocks in S&P500 Index")


# Loading data
@st.cache_data
def load_data():
    # file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
    # data = pd.read_csv(file_path, delimiter=';')
    # return data
    file_url = "https://raw.githubusercontent.com/michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv"
    data = pd.read_csv(file_url, delimiter=';')
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
    "High Forecast Percent", "Smart Score", "Score", "P/E ratio", "Number of analysts"
]
# --- konwersja problematycznych kolumn na liczby ------------------------
numeric_cols = [
    "Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent",
    "Score", "Smart Score", "P/E ratio", "Number of analysts"
]

filtered_data, invalid_vals = clean_numeric(filtered_data, numeric_cols)

# Pokaż, co nie przeszło konwersji
if invalid_vals:                       # jeżeli słownik nie jest pusty
    with st.sidebar.expander("Incorrect values rejected from calculations"):
        for col, bad_df in invalid_vals.items():
            st.write(f"**{col}** – rejected {bad_df.shape[0]} rows:")
            st.dataframe(bad_df, use_container_width=True)

# for col in required_columns:
#     filtered_data[col] = pd.to_numeric(filtered_data[col].astype(str).str.replace(",", "."), errors="coerce")

if all(col in filtered_data.columns for col in required_columns):
    # We create a selectbox for sectors
    sectors = sorted(filtered_data["Sector"].dropna().unique()) #usuwam brakujące waertości przed sortowaniem
    # sectors = sorted(filtered_data["Sector"].unique())
    sector_options = ["All Sectors"] + sectors
    selected_sector = st.sidebar.selectbox("Select Sector",
                                           options=sector_options,
                                           index=0,
                                           help=(
                                               "Use this selector to filter the data by sector. This selector affects some of the charts – feel free to experiment.\n"
                                               "Affected charts:\n"
                                               " - Best stocks in S&P500 Index\n"
                                               " - Selected stocks by our AI algorithm\n"
                                               " - Median Forecast Percent vs. P/E ratio\n"
                                               " - Historical Analyst Forecast Trends"))


    # Filter data according to certain criteria
    scoring = filtered_data[required_columns].sort_values("Score", ascending=False, ignore_index=True)
    scoring = scoring[
        (scoring["Smart Score"] >= 9) &
        (scoring["Score"] > 2) &
        (scoring["Low Forecast Percent"] > -10) &
        (scoring["Score"] < 7) &
        (scoring["Number of analysts"] > 19)
        ]

    if selected_sector != "All Sectors":
        scoring = scoring[scoring["Sector"] == selected_sector]

    # Round numeric columns
    scoring = scoring.round(2)
    total_stocks = scoring.shape[0]

    # if not scoring.empty:
    #     max_stocks = st.sidebar.slider(
    #         "Select number of stocks to display",
    #         min_value=1,
    #         max_value=total_stocks,
    #         value=10 if total_stocks >= 10 else total_stocks,
    #         step=1
    #     )
    #     # We limit the number of displayed stocks to 'max_stocks'
    #     scoring = scoring.head(max_stocks)

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


# -----------------------------
# AI COMMENT SECTION (RAG)
# -----------------------------
with st.expander("AI Comment About Selected Stocks"):
    # st.subheader("AI Comment About Selected Stocks")

    # Model selection with tooltips
    model_choice = st.selectbox(
        "Choose the LLM Model",
        ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o"],
        help=(
            "Select which large language model(LLM) to use for generating the AI commentary.\n"
            "Note: Response accuracy may vary and should be verified. "
            "Usage is limited to one comment per 2 minutes due to cost constraints.\n\n"
            "Model Characteristics:\n\n"
            "• gpt-3.5-turbo: Intelligence: Low, Speed: Slow\n\n"
            "• gpt-4o-mini: Intelligence: Average, Speed: Fast\n\n"
            "• gpt-4o: Intelligence: High, Speed: Medium\n\n"
            # "• o3-mini: Intelligence: Higher, Speed: Medium"
        )
    )

    # Initialize time limit check
    if "last_click_time" not in st.session_state:
        st.session_state["last_click_time"] = 0.0

    # def build_prompt_for_stocks(df_stocks):
    #     """
    #     A simple example of building a RAG-style prompt:
    #     We extract key metrics from the DataFrame and include them in the prompt.
    #     """
    #     prompt = (
    #         "You are a language model providing insights to investors based on "
    #         "statistical data and quantitative analysis.\n"
    #         "Below is a list of stocks with certain metrics. Using this information, "
    #         "generate a short (4-6 sentences) commentary analyzing which stocks seem attractive and why, "
    #         "from a 'quant' perspective (numbers, indicators, outlook). "
    #         "Keep it concise, referencing P/E ratios, potential growth percentages, and 'Score' evaluations. "
    #         "Do not provide actual investment advice – only analysis.\n\n"
    #         "Here are the data for the stocks:\n\n"
    #     )
    #     for _, row in df_stocks.iterrows():
    #         prompt += (
    #             f"- Stock: {row['Stock']} | P/E: {row['P/E ratio']} | HighForecast%: {row['High Forecast Percent']}% "
    #             f"| Score: {row['Score']} | Smart Score: {row['Smart Score']}\n"
    #         )
    #     prompt += ("\n Add also 1-2 sentences of the description about what each company is doing as a bussiness."
    #                "Generate your analysis based on the information above.")
    #
    #     st.write("**Prompt being sent to the LLM**:")
    #     st.code(prompt)
    #
    #     return prompt

    def build_prompt_for_stocks(df_stocks):
        """
        Builds a prompt that first asks:
        "Czym zajmuje się <TICKER>? (1–2 sentences about the business)"
        then references the key metrics, and finally includes a short overall summary.
        """

        # Wprowadzenie do roli modelu i stylu analizy
        prompt = (
            "You are a language model providing insights to investors based on statistical data and quantitative analysis.\n"
            "For each stock listed below, first address the question: \"What <STOCK> company is doing?\" "
            "and write 1-2 sentences describing what the company does. Then analyze the key metrics (P/E ratio, Score, etc.).\n"
            "Finally, provide a short 1-2 sentence summary.\n\n"
        )

        # Dla każdej spółki:
        for _, row in df_stocks.iterrows():
            ticker = row["Stock"]

            # Najpierw pytanie: "Czym zajmuje się <TICKER>? (plus krótki opis biznesu)
            prompt += f"Czym zajmuje się spółka {ticker}?\n"
            prompt += "Please provide 1-2 sentences describing the company's business activities.\n"

            # Potem informacje nt. kluczowych metryk
            prompt += (
                f"Key metrics for {ticker}: P/E ratio={row['P/E ratio']}, "
                f"Median Forecast (in percents)={row['Median Forecast Percent']}%, "
                f"Score={row['Score']}, "
                f"Smart Score={row['Smart Score']}\n\n"
            )

        # Prośba o końcowe podsumowanie
        prompt += (
            "After describing each company's business and metrics, please provide a short (1-2 sentence) overall summary. "
            "Do not provide actual investment advice—only analysis."
        )

        # st.write("**Prompt being sent to the LLM**:") #dzięŻi temu fragmentowi można wyświetlić tekst zbudowanego prompta w aplikacji
        # st.code(prompt)

        return prompt

    def generate_ai_comment(df_stocks, model):
        """
        Creates a prompt and calls Chat Completion using the openai 1.70+ library.
        """
        prompt = build_prompt_for_stocks(df_stocks)

        # Initialize the client with our API key
        client = OpenAI(api_key=st.secrets["openai"]["OPENAI_API_KEY"])

        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1400,
            temperature=0.7
        )

        # Return the generated text
        return completion.choices[0].message.content.strip()

    # Example: we assume best_three = scoring.head(3) from your main code
    # Make sure best_three is not empty before calling generate_ai_comment

    if st.button("Generate AI Comment About Selected Stocks"):
        current_time = time.time()
        # Check if 60 seconds have passed since last invocation
        if current_time - st.session_state["last_click_time"] < 120:
            st.warning("Please wait at least 120 seconds before generating another AI comment.")
        else:
            if best_three.empty:
                st.info("No stocks available in the result – cannot generate commentary.")
            else:
                st.session_state["last_click_time"] = current_time
                with st.spinner("Generating AI commentary..."):
                    ai_comment = generate_ai_comment(best_three, model_choice)
                st.success("Here is your AI commentary:")
                st.write(ai_comment)




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

    # -- załóżmy, że mamy już utworzone 'filtered_data' na podstawie wybranej daty (selected_date)


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
# st.markdown("<hr>", unsafe_allow_html=True)



st.markdown("##### Today's Aggregated Recommendations for the S&P 500")

if not filtered_data.empty:
    # Przekształcenie kolumn na wartości numeryczne (na wypadek gdyby były tekstowe lub puste)
    filtered_data["Number of analysts"] = pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")
    filtered_data["Buy Recommendation"] = pd.to_numeric(filtered_data["Buy Recommendation"], errors="coerce")
    filtered_data["Hold Recommendation"] = pd.to_numeric(filtered_data["Hold Recommendation"], errors="coerce")
    filtered_data["Sell Recommendation"] = pd.to_numeric(filtered_data["Sell Recommendation"], errors="coerce")

    # Usunięcie wierszy, które mają braki w wymaganych kolumnach
    filtered_data = filtered_data.dropna(
        subset=["Number of analysts", "Buy Recommendation", "Hold Recommendation", "Sell Recommendation"]
    )

    if not filtered_data.empty:
        # Obliczamy łączną liczbę analityków na BUY/HOLD/SELL, sumując "Number of analysts" * (udział rekomendacji)
        total_buy = (filtered_data["Number of analysts"] * filtered_data["Buy Recommendation"]).sum()
        total_hold = (filtered_data["Number of analysts"] * filtered_data["Hold Recommendation"]).sum()
        total_sell = (filtered_data["Number of analysts"] * filtered_data["Sell Recommendation"]).sum()

        # Łączna liczba analityków (suma buy + hold + sell)
        total_analysts = total_buy + total_hold + total_sell

        # Dla bezpieczeństwa sprawdzamy, czy total_analysts > 0
        if total_analysts > 0:
            # Wyliczamy procenty
            pct_buy = (total_buy / total_analysts) * 100
            pct_hold = (total_hold / total_analysts) * 100
            pct_sell = (total_sell / total_analysts) * 100

            # Prezentacja w 3 kolumnach
            col1, col2, col3 = st.columns(3)
            col1.metric(
                label="Buy",
                value=f"{pct_buy:.2f}%",
                help=f"{int(round(total_buy, 0))} analysts out of {int(round(total_analysts, 0))}"
            )
            col2.metric(
                label="Hold",
                value=f"{pct_hold:.2f}%",
                help=f"{int(round(total_hold, 0))} analysts out of {int(round(total_analysts, 0))}"
            )
            col3.metric(
                label="Sell",
                value=f"{pct_sell:.2f}%",
                help=f"{int(round(total_sell, 0))} analysts out of {int(round(total_analysts, 0))}"
            )

            # st.markdown("##### Zagregowane rekomendacje dla całego indexu SP 500")

            # Dane w procentach (załóżmy, że masz je policzone: pct_buy, pct_hold, pct_sell)
            # Przykładowe wartości:
            # pct_buy, pct_hold, pct_sell = 45.0, 35.0, 20.0

            fig_bar = go.Figure()

            fig_bar.add_trace(go.Bar(
                x=[pct_buy],
                y=[" "],
                name="Buy",
                orientation='h',
                marker=dict(color="green"),
                # Tekst wewnątrz słupka
                text=[f"Buy {pct_buy:.1f}%"],
                textposition="inside",
                insidetextanchor="middle",

                # Treść dymka hover
                hovertext=[f"Approx. {int(round(total_buy, 0))} analysts out of {int(round(total_analysts, 0))}"],
                hoverinfo="text"
            ))

            fig_bar.add_trace(go.Bar(
                x=[pct_hold],
                y=[" "],
                name="Hold",
                orientation='h',
                marker=dict(color="lightblue"),  # np. jaśniejszy niebieski
                text=[f"Hold {pct_hold:.1f}%"],
                textposition="inside",
                insidetextanchor="middle",

                hovertext=[f"Approx. {int(round(total_hold, 0))} analysts out of {int(round(total_analysts, 0))}"],
                hoverinfo="text"
            ))

            fig_bar.add_trace(go.Bar(
                x=[pct_sell],
                y=[" "],
                name="Sell",
                orientation='h',
                marker=dict(color="red"),
                text=[f"Sell {pct_sell:.1f}%"],
                textposition="inside",
                insidetextanchor="middle",

                hovertext=[f"Approx. {int(round(total_sell, 0))} analysts out of {int(round(total_analysts, 0))}"],
                hoverinfo="text"
            ))

            fig_bar.update_layout(
                barmode="stack",
                showlegend=False,
                height=50,
                margin=dict(l=0, r=120, t=0, b=20),
            )

            fig_bar.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=False, visible=False)
            fig_bar.update_yaxes(showgrid=False, visible=False)

            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No valid analyst data to compute Buy/Hold/Sell percentages.")
    else:
        st.info("No rows with valid numeric data for Number of analysts / Recommendations.")
else:
    st.info("No data for the selected date or filtered DataFrame is empty.")


st.markdown("<hr>", unsafe_allow_html=True)
# -------------------------------------------



# Title and description
st.header("Selected stocks by our AI algorithm")
st.markdown(
    f"Our sophisticated algorithm, merging 9 variables, has identified {total_stocks} best stocks for today. "
    f"You can further refine the list using the slider below to potentially achieve higher returns or rebalance your portfolio."
)


# Compute medians for the filtered stocks
# if not scoring.empty:

if not scoring.empty:
    # Tu wstawiamy nowy slider
    max_stocks = st.slider(
        "This slider affects also other charts below - as it creates Selected Stocks list ", #Use the slider to show more or fewer stocks on the chart.
        min_value=1,
        max_value=total_stocks,
        value=10 if total_stocks >= 10 else total_stocks,
        step=1
    )

    # Ograniczamy liczbę spółek dopiero teraz, tuż przed wykresem
    scoring = scoring.head(max_stocks)

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
        # title="Use the slider on the left sidebar to show more or fewer stocks in the chart.",
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

st.header("Historical Analyst Forecast Trends")
st.markdown("""
This section displays the historical evolution of analyst forecast medians over time for both the entire S&P 500 and the top stocks selected by our AI algorithm. The forecasts are categorized as Low forecasts, Median Forecasts, and High Forecasts, allowing you to observe trends in analysts' expectations and compare the performance of filtered stocks against the broader market. Use the forecast type selector to focus on a specific forecast scenario.
""")

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
selected_forecast = st.selectbox("Select forecast type", options=forecast_options, index=0, key="forecast_select")

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
    # title="From entire S&P500 Index",
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


# -------------------------------------------------
# Analyst-Coverage Distribution (selected date)
# -------------------------------------------------

st.subheader("Distribution of Analyst Coverage (Selected Date)")

if filtered_data.empty or "Number of analysts" not in filtered_data.columns:
    st.info("No analyst-coverage data available for the selected date.")
else:
    analysts_num = (
        pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")
        .dropna()
    )

    if analysts_num.empty:
        st.info("All rows for the selected date have missing analyst counts.")
    else:
        fig_analyst_hist = px.histogram(
            analysts_num,
            nbins=80,                                # adjust if you prefer finer / coarser bins
            labels={"value": "Number of Analysts", "count": "Number of Stocks"},
            # title="Histogram of Analyst Coverage (Selected Date)",
        )

        fig_analyst_hist.update_layout(
            xaxis_title="Number of Analysts covering stock",
            yaxis_title="Number of Stocks",
            bargap=0.05
        )

        st.plotly_chart(fig_analyst_hist, use_container_width=True)


st.markdown("<hr>", unsafe_allow_html=True)



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




# --- Dividend Yield Chart (using filtered_data) ---
st.subheader("Dividend Yield of Stocks (Filtered by Sector)")

# Make sure the "Dividend yield" column is valid and numeric
div_data = filtered_data.dropna(subset=["Dividend yield"]).copy()
div_data["Dividend yield"] = (
    div_data["Dividend yield"]
    .astype(str)
    .str.replace(",", ".")
    .astype(float, errors="ignore")
)

# Create a list of sectors
sector_options = ["All Sectors"] + sorted(div_data["Sector"].dropna().unique().tolist())

# Create two columns side by side
col1, col2 = st.columns(2)

# Selector in the first column
with col1:
    selected_sector = st.selectbox("Select a sector for the dividend yield chart:", options=sector_options)

# Preset options for the number of stocks in the second column
limit_options = ["10", "20", "50", "100", "All"]
with col2:
    selected_limit = st.selectbox("Select how many top stocks to display:", limit_options, index=1)  # default "20"

# Filtering by the selected sector
if selected_sector != "All Sectors":
    div_data = div_data[div_data["Sector"] == selected_sector]

# Sorting by "Dividend yield" in descending order
div_data_sorted = div_data.sort_values("Dividend yield", ascending=False)

# Limiting the number of stocks (if the user did not select "All")
if selected_limit != "All":
    max_stocks = int(selected_limit)
    div_data_sorted = div_data_sorted.head(max_stocks)

# Creating the bar chart – X-axis: Stock, Y-axis: Dividend Yield
fig_div = px.bar(
    div_data_sorted,
    x="Stock",
    y="Dividend yield",
    color="Sector",
    # title="Dividend Yield of Stocks (Filtered by Date)",
    labels={"Dividend yield": "Dividend Yield (%)", "Stock": "Stock"},
)

# If we have only one sector in the data, disable the legend
if len(div_data_sorted["Sector"].unique()) == 1:
    fig_div.update_layout(showlegend=False)

# Set the order of categories on the X-axis (descending)
fig_div.update_layout(xaxis={"categoryorder": "total descending"})

# Optionally add the "%" symbol on the Y-axis
fig_div.update_yaxes(ticksuffix="%")

# Display the chart
st.plotly_chart(fig_div, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)



# --- Market cap chart ---
# st.subheader("Total Market Cap (S&P 500)")

# Copy data from filtered_data to avoid modifying it elsewhere
df_pie = filtered_data.copy()

# Ensure the 'Market cap clear' column is numeric
df_pie["Market cap clear"] = pd.to_numeric(df_pie["Market cap clear"], errors="coerce")

# Group data by sector and calculate the total market cap and company count
df_pie_agg = (
    df_pie.groupby("Sector", dropna=True)
          .agg({
              "Stock": "count",
              "Market cap clear": "sum"
          })
          .reset_index()
          .rename(columns={"Stock": "CompanyCount", "Market cap clear": "TotalMarketCap"})
)

# Calculate the total market cap (across sectors) in billions of USD
total_sp500_marketcap = df_pie_agg["TotalMarketCap"].sum()
total_sp500_in_billion = total_sp500_marketcap / 1e9

# Display a full-width metric
st.metric(
    label="Total Market Cap (S&P 500)",
    value=f"{total_sp500_in_billion:,.2f} B USD"
)


# --- Chart 1: Market cap share by sector ---
fig_cap = px.pie(
    df_pie_agg,
    names="Sector",
    values="TotalMarketCap",
    # title="Sector Share in Total Market Cap",
    hover_data=["CompanyCount"],
    labels={"CompanyCount": "Number of companies", "TotalMarketCap": "Market Cap"}  # <-- here we change the label
)

fig_cap.update_layout(
    width=650,   # chart width in pixels
    height=650,  # chart height in pixels
    showlegend=False
)
st.plotly_chart(fig_cap)

st.markdown("<hr>", unsafe_allow_html=True)


# -------------------------------------------------
# Average Smart Score – metric & trend line
# -------------------------------------------------

st.header("Average Smart Score (All S&P 500 Stocks)")

# ── 1 ▸ TODAY’S AVERAGE SMART SCORE ─────────────────────────────────────
if filtered_data.empty or "Smart Score" not in filtered_data.columns:
    st.info("No Smart Score data available for the selected date.")
else:
    # Ensure numeric dtype
    filtered_data["Smart Score"] = pd.to_numeric(
        filtered_data["Smart Score"], errors="coerce"
    )

    avg_today = filtered_data["Smart Score"].mean()

    # Delta vs. previous trading day (optional)
    delta_avg = None
    if prev_date is not None:
        prev_day_data = df[df["Date of record"] == prev_date]
        prev_avg = pd.to_numeric(
            prev_day_data["Smart Score"], errors="coerce"
        ).mean()
        if pd.notna(prev_avg):
            delta_avg = avg_today - prev_avg

    # Metric card (single column so it spans the page width nicely)
    st.metric(
        label="Average Smart Score (today)",
        value=f"{avg_today:.2f}",
        delta=f"{delta_avg:+.2f}" if delta_avg is not None else "N/A",
        help="Simple arithmetic mean of Smart Scores for all stocks on the selected date."
    )

# ── 2 ▸ TREND LINE OVER TIME ────────────────────────────────────────────
# Calculate daily mean across the entire dataset
if "Smart Score" in df.columns and "Date of record" in df.columns:
    df_smart_trend = (
        df.dropna(subset=["Date of record"])
          .assign(**{"Smart Score": pd.to_numeric(df["Smart Score"], errors="coerce")})
          .groupby("Date of record")["Smart Score"]
          .mean()
          .reset_index()
    )

    fig_smart_trend = px.line(
        df_smart_trend.round(2),
        x="Date of record",
        y="Smart Score",
        # title="Average Smart Score Over Time (All S&P 500 Stocks)",
        markers=True,
        labels={"Smart Score": "Average Smart Score"}
    )

    fig_smart_trend.update_layout(
        xaxis_title="Date",
        yaxis_title="Average Smart Score (1 – 10)",
        yaxis=dict(range=[0, 10], dtick=1)
    )

    st.plotly_chart(fig_smart_trend, use_container_width=True)
else:
    st.info("Smart Score or date column missing – cannot draw historical trend.")

st.markdown("<hr>", unsafe_allow_html=True)


# -------------------------------------------------
# Smart Score distribution (histogram) – selected date
# -------------------------------------------------

st.subheader("Smart Score Distribution (Selected Date)")

if filtered_data.empty or "Smart Score" not in filtered_data.columns:
    st.info("No Smart Score data available for the selected date.")
else:
    # ── 1 ▸ przygotuj dane ──────────────────────────────────────────────
    scores_int = (
        pd.to_numeric(filtered_data["Smart Score"], errors="coerce")
        .dropna()
        .round(0)
        .astype(int)
    )

    counts = (
        scores_int.value_counts()
                  .reindex(range(1, 11), fill_value=0)   # wymuś brakujące koszyki
                  .sort_index()
    )

    df_hist = counts.reset_index()
    df_hist.columns = ["Smart Score", "Count"]           # ← kluczowa poprawka

    # ── 2 ▸ wykres ──────────────────────────────────────────────────────
    fig_hist = px.bar(
        df_hist,
        x="Smart Score",
        y="Count",
        # title="Distribution of Smart Scores (Selected Date)",
        labels={"Count": "Number of Stocks"},
        category_orders={"Smart Score": list(range(1, 11))},
        text="Count"
    )

    fig_hist.update_traces(texttemplate="%{text}", textposition="outside")
    fig_hist.update_layout(
        xaxis_title="Smart Score (1 – 10)",
        yaxis_title="Number of Stocks",
        uniformtext_minsize=8,
        uniformtext_mode="hide"
    )

    st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)


# -------------------------------------------------
# Stocks by Smart Score (picker)
# -------------------------------------------------

st.subheader("Stocks with Selected Smart Score")

needed_cols = [
    "Smart Score", "Sector", "Stock",
    "Number of analysts",
    "Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"
]

if filtered_data.empty or not all(c in filtered_data.columns for c in needed_cols):
    st.info("Required columns are missing or no data for the selected date.")
else:
    # Ensure numeric types
    filtered_data["Smart Score"]          = pd.to_numeric(filtered_data["Smart Score"], errors="coerce")
    filtered_data["Number of analysts"]   = pd.to_numeric(filtered_data["Number of analysts"], errors="coerce")
    for col in ["Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"]:
        filtered_data[col] = pd.to_numeric(filtered_data[col], errors="coerce")

    # # Integer bucket 1-10
    # filtered_data["SmartScoreInt"] = filtered_data["Smart Score"].round().astype(int)

    # --- na to:
    scores_clean = (
        pd.to_numeric(filtered_data["Smart Score"], errors="coerce")  # NaN dla nieparsowalnych
        .replace([np.inf, -np.inf], np.nan)  # usuń ±Inf
    )

    filtered_data["SmartScoreInt"] = scores_clean.round().astype("Int64")  # 'Int64' toleruje NA

    # Multiselect - default 10
    score_choice = st.multiselect(
        "Choose Smart Score value(s):",
        options=list(range(1, 11)),
        default=[10]
    )

    subset = filtered_data[filtered_data["SmartScoreInt"].isin(score_choice)]

    if subset.empty:
        st.warning("No stocks match the selected Smart Score value(s).")
    else:
        out_cols = [
            "Stock", "Sector", "SmartScoreInt",
            "Number of analysts",
            "Low Forecast Percent", "Median Forecast Percent", "High Forecast Percent"
        ]
        out = (
            subset[out_cols]
            .rename(columns={"SmartScoreInt": "Smart Score"})
            .sort_values(["Smart Score", "Stock"], ascending=[False, True])
            .reset_index(drop=True)
            .round(2)
        )
        st.dataframe(out, use_container_width=True)


st.markdown("<hr>", unsafe_allow_html=True)




# # -------------------------------------------------
# # Donchian-Turtle Signals ─ All Stocks, Selected Date   -  all signals
# # -------------------------------------------------
#
# st.header("Turtle Strategy Signals – Entire S&P 500 (Selected Date)")
#
# if "1-day range" not in df.columns or filtered_data.empty:
#     st.info("Cannot compute signals – missing price-range data or no rows for the selected date.")
# else:
#
#     # ── 1 ▸ helper: split 'low high' text into floats ───────────────────
#     def split_range(r: str):
#         """
#         Convert 'low high' (or with newline) to two floats [low, high].
#         Handles thousands separators like '7,866.87'.
#         """
#         if pd.isna(r):
#             return [None, None]
#         parts = str(r).replace("\n", " ").strip().split()
#         if len(parts) != 2:
#             return [None, None]
#
#         nums = []
#         for p in parts:
#             num_str = re.sub(r"[^\d\.\-]", "", p)  # drop commas, $, etc.
#             try:
#                 nums.append(float(num_str))
#             except ValueError:
#                 return [None, None]
#
#         low, high = nums
#         return [min(low, high), max(low, high)]
#
#     # ── 2 ▸ working copy with Low / High columns ────────────────────────
#     df_all = df.copy()
#
#     df_all[["Low", "High"]] = (
#         df_all["1-day range"].apply(split_range).apply(pd.Series)
#     )
#
#     df_all = df_all.dropna(subset=["Low", "High", "Price", "Date of record"])
#
#     # ── 3 ▸ rolling Donchian channels per ticker ────────────────────────
#     df_all["Date of record"] = pd.to_datetime(df_all["Date of record"])
#     df_all = df_all.sort_values(["Stock", "Date of record"])
#
#     df_all["High20"] = (
#         df_all.groupby("Stock")["High"]
#               .transform(lambda s: s.rolling(20, min_periods=20).max())
#     )
#     df_all["Low10"] = (
#         df_all.groupby("Stock")["Low"]
#               .transform(lambda s: s.rolling(10, min_periods=10).min())
#     )
#
#     df_all["High20_y"] = df_all.groupby("Stock")["High20"].shift(1)
#     df_all["Low10_y"]  = df_all.groupby("Stock")["Low10"].shift(1)
#     df_all["Close_y"]  = df_all.groupby("Stock")["Price"].shift(1)
#
#     # ── 4 ▸ BUY / SELL masks ───────────────────────────────────────────
#     df_all["Buy"]  = (df_all["Price"] > df_all["High20_y"]) & (df_all["Close_y"] <= df_all["High20_y"])
#     df_all["Sell"] = (df_all["Price"] < df_all["Low10_y"])  & (df_all["Close_y"] >= df_all["Low10_y"])
#
#     # ── 5 ▸ keep only rows for selected date ───────────────────────────
#     today = pd.Timestamp(selected_date)
#     today_df = df_all[df_all["Date of record"] == today]
#
#     buy_df  = today_df[today_df["Buy"] ].copy()
#     sell_df = today_df[today_df["Sell"]].copy()
#
#     # ── 6 ▸ headline metrics ───────────────────────────────────────────
#     col_b, col_s = st.columns(2)
#     col_b.metric("BUY signals today",  len(buy_df))
#     col_s.metric("SELL signals today", len(sell_df))
#
#     # ── 7 ▸ helper to show tables ──────────────────────────────────────
#     def show_table(df_sig, sig_type: str):
#         if df_sig.empty:
#             st.info(f"No {sig_type} signals for the selected date.")
#             return
#
#         use_cols = ["Stock", "Sector", "Price",
#                     "High20_y" if sig_type == "BUY" else "Low10_y"]
#         renamed = {
#             "Price": "Close",
#             "High20_y": "Y-day 20-day High",
#             "Low10_y": "Y-day 10-day Low"
#         }
#
#         out = (df_sig[use_cols]
#                .rename(columns=renamed)
#                .sort_values("Stock")
#                .round(2)
#                .reset_index(drop=True))
#
#         st.subheader(f"{sig_type} signals")
#         st.dataframe(out, use_container_width=True)
#
#     show_table(buy_df,  "BUY")
#     show_table(sell_df, "SELL")



# -------------------------------------------------
# Donchian-Turtle Signals ─ All Stocks, Selected Date
# -------------------------------------------------

st.header("Turtle Strategy Signals – Entire S&P 500 (Selected Date)")

if "1-day range" not in df.columns or filtered_data.empty:
    st.info("Cannot compute signals – missing price-range data or no rows for the selected date.")
else:

    # ── 1 ▸ helper – parse 'low high' text into floats ──────────────────
    def split_range(r: str):
        if pd.isna(r):
            return [None, None]
        parts = str(r).replace("\n", " ").strip().split()
        if len(parts) != 2:
            return [None, None]
        nums = []
        for p in parts:
            p_clean = re.sub(r"[^\d\.\-]", "", p)   # drop commas, $, etc.
            try:
                nums.append(float(p_clean))
            except ValueError:
                return [None, None]
        low, high = nums
        return [min(low, high), max(low, high)]

    # ── 2 ▸ working copy + Low/High columns ────────────────────────────
    df_all = df.copy()
    df_all[["Low", "High"]] = (
        df_all["1-day range"].apply(split_range).apply(pd.Series)
    )
    df_all = df_all.dropna(subset=["Low", "High", "Price", "Date of record"])

    df_all["Date of record"] = pd.to_datetime(df_all["Date of record"])
    df_all = df_all.sort_values(["Stock", "Date of record"])

    # ── 3 ▸ rolling Donchian channels per ticker ────────────────────────
    df_all["High20"] = (
        df_all.groupby("Stock")["High"]
              .transform(lambda s: s.rolling(20, min_periods=20).max())
    )
    df_all["Low10"] = (
        df_all.groupby("Stock")["Low"]
              .transform(lambda s: s.rolling(10, min_periods=10).min())
    )

    df_all["High20_y"] = df_all.groupby("Stock")["High20"].shift(1)
    df_all["Low10_y"]  = df_all.groupby("Stock")["Low10"].shift(1)
    df_all["Close_y"]  = df_all.groupby("Stock")["Price"].shift(1)

    # ── 4 ▸ RAW BUY / SELL flags ───────────────────────────────────────
    df_all["RawSignal"] = np.select(
        [
            (df_all["Price"] > df_all["High20_y"]) & (df_all["Close_y"] <= df_all["High20_y"]),
            (df_all["Price"] < df_all["Low10_y"])  & (df_all["Close_y"] >= df_all["Low10_y"]),
        ],
        ["BUY", "SELL"],
        default=None
    )

    # ── 5 ▸ Filtered swing signals  (first BUY / first SELL) ────────────
    def swing_filter(series):
        out, state = [], "FLAT"
        for sig in series:
            if sig == "BUY" and state != "LONG":
                out.append("BUY");  state = "LONG"
            elif sig == "SELL" and state == "LONG":
                out.append("SELL"); state = "FLAT"
            else:
                out.append(None)
        return out

    df_all["FiltSignal"] = (
        df_all.groupby("Stock")["RawSignal"].transform(swing_filter)
    )

    # ── 6 ▸ user selector (default = Filtered) ──────────────────────────
    mode = st.selectbox(
        "Signal view:",
        ("Filtered signals (default)", "All signals"),
        index=0
    )
    sig_col = "FiltSignal" if "Filtered" in mode else "RawSignal"

    # ── 7 ▸ keep only selected-date rows with a signal ──────────────────
    today = pd.Timestamp(selected_date)
    today_df = df_all[(df_all["Date of record"] == today) & df_all[sig_col].notna()]

    buy_df  = today_df[today_df[sig_col] == "BUY"].copy()
    sell_df = today_df[today_df[sig_col] == "SELL"].copy()

    # ── 8 ▸ headline counters ───────────────────────────────────────────
    col_b, col_s = st.columns(2)
    col_b.metric("BUY signals today",  len(buy_df))
    col_s.metric("SELL signals today", len(sell_df))

    # ── 9 ▸ helper to print tables ──────────────────────────────────────
    def show_table(df_sig, sig_type):
        if df_sig.empty:
            st.info(f"No {sig_type} signals for the selected date.")
            return
        cols = ["Stock", "Sector", "Price",
                "High20_y" if sig_type == "BUY" else "Low10_y"]
        rename = {
            "Price": "Close",
            "High20_y": "Y-day 20-day High",
            "Low10_y":  "Y-day 10-day Low"
        }
        out = (df_sig[cols]
               .rename(columns=rename)
               .sort_values("Stock")
               .round(2)
               .reset_index(drop=True))
        st.subheader(f"{sig_type} signals")
        st.dataframe(out, use_container_width=True)

    show_table(buy_df,  "BUY")
    show_table(sell_df, "SELL")

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""\
Please note: Investing involves risk and you may lose some or all of your capital.
This site is provided for informational purposes only and does not constitute financial advice.
""")

# st.markdown("""
#     <p style="font-size: 12px; text-align: left; color: gray;">
#         Website made by @Michał Ostaszewski
#     </p>
# """, unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        © 2025 App made by Michał Ostaszewski<br>
        App source code licensed under the MIT License.<br>
        All data used in this app is licensed under 
        <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" style="color: gray;">Creative Commons BY-NC 4.0</a>.<br>
        See the <a href="https://github.com/michael-ostaszewski/stock_scraper_spx" target="_blank" style="color: gray;">GitHub repository</a> for full license details.<br>
        ☕ Support the project(available soon, now enjoy the app for free) <a href="https://buymeacoffee.com/michal.dev" target="_blank" style="color: gray;">buymeacoffee.com/michal.dev</a>
    </p>
""", unsafe_allow_html=True)