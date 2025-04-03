import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from openai import OpenAI

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


# -----------------------------
# AI COMMENT SECTION (RAG)
# -----------------------------
with st.expander("AI Comment About Selected Stocks"):
    # st.subheader("AI Comment About Selected Stocks")

    # Model selection with tooltips
    model_choice = st.selectbox(
        "Choose the LLM Model",
        ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o", "gpt-o3-mini"],
        help=(
            "Select which large language model(LLM) to use for generating the AI commentary.\n"
            "Note: Response accuracy may vary and should be verified. "
            "Usage is limited to one comment per 3 minutes due to cost constraints.\n\n"
            "Model Characteristics:\n\n"
            "• gpt-3.5-turbo: Intelligence: Low, Speed: Slow\n\n"
            "• gpt-4o-mini: Intelligence: Average, Speed: Fast\n\n"
            "• gpt-4o: Intelligence: High, Speed: Medium\n\n"
            "• o3-mini: Intelligence: Higher, Speed: Medium"
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
        if current_time - st.session_state["last_click_time"] < 180:
            st.warning("Please wait at least 60 seconds before generating another AI comment.")
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