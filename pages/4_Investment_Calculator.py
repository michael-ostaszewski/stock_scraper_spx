import streamlit as st
import yfinance as yf
import datetime
import pandas as pd
import plotly.express as px

from app_auth import require_auth

require_auth("Investment Calculator")

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

def investment_calculator():
    st.title("Investment Calculator")

    st.write(
        "Set your investment parameters and click Calculate Investment to view the results."
    )

    # --- Input Columns for Investment Parameters ---
    col1, col2 = st.columns(2)

    with col1:
        initial_investment = st.number_input(
            "Initial Investment (USD)",
            min_value=0.0,
            value=0.0,
            step=100.0
        )
        investment_years = st.number_input(
            "Number of years",
            min_value=1,
            value=10,
            step=1
        )
        rate_of_return = st.number_input(
            "Estimated annual rate of return (%)",
            min_value=0.0,
            value=5.0,
            step=0.1
        )

    with col2:
        interest_compounding = st.selectbox(
            "Interest compounding",
            ["daily", "monthly", "yearly"]
        )
        additional_deposit_amount = st.number_input(
            "Single additional deposit amount (USD)",
            min_value=0.0,
            value=1.0,
            step=50.0
        )
        deposit_frequency = st.selectbox(
            "Frequency of additional deposits",
            ["daily", "weekly", "monthly", "yearly"]
        )

    # --- Inflation Input ---
    inflation_rate = st.number_input(
        "Annual inflation rate (%)",
        min_value=0.0,
        value=3.0,
        step=0.1,
        help= "The 20-year average inflation rate in USA is around 2.3%."
    )



    # with st.expander("Check average return(CAGR) from key benchmarks over the last 1-20 years", expanded=False):
    #     # st.write(
    #     #     "The data below is fetched dynamically from Yahoo Finance. "
    #     #     "It may change based on current market conditions. Select benchmark period (years):"
    #     # )
    #
    #     # Add slider to dynamically select the number of years (from 1 to 20)
    #     years = st.slider("The data below is fetched dynamically from Yahoo Finance. It may change based on current market conditions. "
    #                       "Select benchmark period (years):",
    #                       min_value=1, max_value=20, value=15, step=1)
    #
    #     # Calculate the date range based on the slider value
    #     end_date = datetime.date.today() - datetime.timedelta(days=1)
    #     start_date = end_date.replace(year=end_date.year - years)
    #
    #     # Define the 3 main benchmarks
    #     benchmarks = {
    #         "S&P 500": "^GSPC",
    #         "Nasdaq Composite": "^IXIC",
    #         "Dow Jones Industrial Average": "^DJI"
    #     }
    #
    #     # Calculate CAGR for each benchmark
    #     cagr_values = {}
    #     for name, symbol in benchmarks.items():
    #         # data = yf.download(symbol, start=start_date, end=end_date, progress=False)
    #         #
    #         # # Access the closing prices using the MultiIndex (e.g., ("Close", symbol))
    #         # start_price = data[("Close", symbol)][1]
    #         # if len(data) > 30:
    #         #     end_price = data[("Close", symbol)][-30]
    #         # else:
    #         #     end_price = data[("Close", symbol)][-1]
    #         data = yf.download(symbol, start=start_date, end=end_date, progress=False)
    #
    #         # Jeżeli nic nie pobrano – przerwij pętlę i pokaż brak danych
    #         if data.empty or ("Close", symbol) not in data.columns or len(data[("Close", symbol)]) < 2:
    #             st.warning(f"Brak danych lub ograniczenie rate‑limit dla {symbol}.")
    #             cagr_values[name] = None
    #             continue  # idź do następnego benchmarku
    #
    #         # bezpieczne pobranie pierwszej i ostatniej ceny
    #         start_price = data[("Close", symbol)].iloc[0]
    #         end_price = data[("Close", symbol)].iloc[-30] if len(data) > 30 else data[("Close", symbol)].iloc[-1]
    #
    #         num_of_years = (data.index[-1] - data.index[0]).days / 365
    #         cagr = (end_price / start_price) ** (1 / num_of_years) - 1
    #         cagr_values[name] = cagr * 100
    #
    #     # Display the benchmark CAGR values in 3 columns as metrics,
    #     # updating the label to reflect the selected period from the slider.
    #     col_bench_1, col_bench_2, col_bench_3 = st.columns(3)
    #
    #     with col_bench_1:
    #         sp500_cagr = cagr_values["S&P 500"]
    #         st.metric(f"S&P 500 ({years}-year CAGR)", f"{sp500_cagr:.2f}%")
    #
    #     with col_bench_2:
    #         nasdaq_cagr = cagr_values["Nasdaq Composite"]
    #         st.metric(f"Nasdaq ({years}-year CAGR)", f"{nasdaq_cagr:.2f}%")
    #
    #     with col_bench_3:
    #         dji_cagr = cagr_values["Dow Jones Industrial Average"]
    #         st.metric(f"Dow Jones ({years}-year CAGR)", f"{dji_cagr:.2f}%")



    # --- Single Button to trigger all calculations ---
    calculate_button = st.button("Calculate Investment")

    if calculate_button:
        # -------------------------------------------------------------------
        # 1) INVESTMENT SIMULATION
        # -------------------------------------------------------------------
        compounding_map = {"daily": 365, "monthly": 12, "yearly": 1}
        deposit_map = {"daily": 365, "weekly": 52, "monthly": 12, "yearly": 1}

        interest_periods = compounding_map[interest_compounding]
        deposit_periods = deposit_map[deposit_frequency]
        total_periods = investment_years * interest_periods

        # How often additional deposits occur
        deposit_step = interest_periods / deposit_periods

        # Effective rates per compounding period
        effective_rate_of_return = (1 + rate_of_return / 100) ** (1 / interest_periods) - 1
        effective_inflation_rate = (1 + inflation_rate / 100) ** (1 / interest_periods) - 1

        # Prepare lists for simulation results
        period_list = []
        nominal_contributions_list = []
        nominal_investment_value_list = []
        real_contributions_list = []
        real_investment_value_list = []

        # Tracking variables
        current_investment_value = initial_investment
        total_nominal_contributions = initial_investment
        total_real_contributions = initial_investment  # Present-value terms

        # Simulation loop
        for period in range(total_periods + 1):
            period_list.append(period)
            nominal_contributions_list.append(total_nominal_contributions)
            nominal_investment_value_list.append(current_investment_value)

            # Real investment value (discounting to period 0)
            real_investment_value = current_investment_value / ((1 + effective_inflation_rate) ** period)
            real_investment_value_list.append(real_investment_value)

            # Real contributed capital
            real_contributions_list.append(total_real_contributions)

            if period < total_periods:
                # Compounding
                current_investment_value *= (1 + effective_rate_of_return)

                # Additional Deposits
                if additional_deposit_amount > 0:
                    if interest_periods >= deposit_map[deposit_frequency]:
                        # Deposit at specific steps
                        if period > 0 and (period % int(deposit_step) == 0):
                            current_investment_value += additional_deposit_amount
                            total_nominal_contributions += additional_deposit_amount
                            total_real_contributions += (
                                additional_deposit_amount
                                / ((1 + effective_inflation_rate) ** (period + 1))
                            )
                    else:
                        # Deposit every period
                        current_investment_value += additional_deposit_amount
                        total_nominal_contributions += additional_deposit_amount
                        total_real_contributions += (
                            additional_deposit_amount
                            / ((1 + effective_inflation_rate) ** (period + 1))
                        )

        # Final nominal calculations
        final_nominal_contributions = total_nominal_contributions
        final_nominal_investment_value = current_investment_value
        nominal_profit = final_nominal_investment_value - final_nominal_contributions
        nominal_profit_percentage = (
            (nominal_profit / final_nominal_contributions) * 100
            if final_nominal_contributions != 0
            else 0
        )

        # Final real calculations
        final_real_investment_value = (
            final_nominal_investment_value
            / ((1 + effective_inflation_rate) ** total_periods)
        )
        final_real_contributions = total_real_contributions
        real_profit = final_real_investment_value - final_real_contributions
        real_profit_percentage = (
            (real_profit / final_real_contributions) * 100
            if final_real_contributions != 0
            else 0
        )

        # Amount eroded by inflation
        # eroded_by_inflation = final_nominal_investment_value - final_real_investment_value

        # Rename sumofinvestment to a more descriptive name
        total_final_value = final_nominal_contributions + nominal_profit

        # Display metrics in two columns
        colA, colB = st.columns(2)

        with colA:
            st.metric(
                label="Nominal Contributed Capital",
                value=f"{final_nominal_contributions:.2f} USD",
                help="Amount that you contributed from your own funds."
            )
            # st.metric(
            #     label="Amount Eroded by Inflation",
            #     value=f"{eroded_by_inflation:.2f} USD",
            #     help="Reduction in investment value due to inflation over time."
            # )
            st.metric(
                label="Nominal Profit (zero inflation)",
                value=f"{nominal_profit:.2f} USD",
                help="Nominal profit computed without taking inflation into account."
            )
            st.metric(
                label="Nominal Profit % (zero inflation)",
                value=f"{nominal_profit_percentage:.2f}%",
                help="Profit percentage calculated without adjusting for the effects of inflation."
            )

        with colB:
            st.metric(
                label="Total Final Investment Value",
                value=f"{total_final_value:.2f} USD",
                help="Sum of your total contributions and the nominal profit."
            )
            st.metric(
                label="Real Profit (net of inflation)",
                value=f"{real_profit:.2f} USD",
                help="Actual profit after adjusting for inflation."
            )
            st.metric(
                label="Real Profit (net of inflation) %",
                value=f"{real_profit_percentage:.2f}%",
                help="Profit percentage reflecting inflation-adjusted growth."
            )

        # Prepare data for the chart
        df = pd.DataFrame({
            "Period": period_list,
            "Nominal Contributed Capital": nominal_contributions_list,
            "Nominal Investment Value": nominal_investment_value_list,
            "Real Contributed Capital": real_contributions_list,
            "Real Investment Value": real_investment_value_list
        })

        # Calculating Real Profit in every period
        df["Real Profit over time (net of inflation)"] = df["Real Investment Value"] - df["Real Contributed Capital"]

        fig = px.line(
            df,
            x="Period",
            y=[
                "Nominal Investment Value",
                "Nominal Contributed Capital",
                "Real Profit over time (net of inflation)"
            ],
            labels={
                "value": "Amount (USD)",
                "variable": "Legend",
            },
            title="Investment Growth Simulation (Nominal & Real Values)"
        )

        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    investment_calculator()


# # 4_Investment_Calculator.py
# import streamlit as st
# import yfinance as yf
# import datetime
# import pandas as pd
# import plotly.express as px
#
# # ---------- STYLE ----------
# st.markdown(
#     """
#     <style>
#     /* Pogubne metryk */
#     [data-testid="stMetricValue"],
#     [data-testid="stMetricLabel"] {
#         font-weight: bold;
#     }
#     /* Przycisk */
#     div.stButton > button {
#         width: 100%;
#         color: #ffffff;
#         background-image: linear-gradient(to right, #034980, #0277bd);
#         border: 2px solid #0277bd;
#         font-size: 16px;
#         font-weight: bold;
#         transition: background-image 0.3s ease, transform 0.3s ease;
#     }
#     div.stButton > button:hover {
#         background-image: linear-gradient(to right, #388e3c, #66bb6a);
#         transform: scale(1.02);
#     }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )
#
# # ---------- HELPER ----------
# def safe_metric(value: float | None) -> str:
#     """Ładne formatowanie wartości metric. Zwraca 'N/A', gdy brak danych."""
#     return "N/A" if value is None else f"{value:.2f}%"
#
#
# # ---------- MAIN ----------
# def investment_calculator() -> None:
#     st.title("Investment Calculator")
#     st.write("Set your investment parameters and click **Calculate Investment** to view the results.")
#
#     # --- INPUTS -----------------------------------------------------------
#     col1, col2 = st.columns(2)
#
#     with col1:
#         initial_investment = st.number_input("Initial Investment (USD)", min_value=0.0, value=0.0, step=100.0)
#         investment_years   = st.number_input("Number of years", min_value=1, value=10, step=1)
#         rate_of_return     = st.number_input("Estimated annual rate of return (%)", min_value=0.0, value=5.0, step=0.1)
#
#     with col2:
#         interest_compounding      = st.selectbox("Interest compounding", ["daily", "monthly", "yearly"])
#         additional_deposit_amount = st.number_input("Single additional deposit amount (USD)", min_value=0.0, value=1.0, step=50.0)
#         deposit_frequency         = st.selectbox("Frequency of additional deposits", ["daily", "weekly", "monthly", "yearly"])
#
#     inflation_rate = st.number_input(
#         "Annual inflation rate (%)",
#         min_value=0.0,
#         value=3.0,
#         step=0.1,
#         help="The 20‑year average inflation rate in USA is around 2.3%.",
#     )
#
#     # --- BENCHMARK CAGR ---------------------------------------------------
#     with st.expander("Check average return (CAGR) from key benchmarks over the last 1‑20 years"):
#         years = st.slider(
#             "The data below is fetched dynamically from Yahoo Finance. "
#             "It may change based on current market conditions. Select benchmark period (years):",
#             min_value=1,
#             max_value=20,
#             value=15,
#             step=1,
#         )
#
#         end_date   = datetime.date.today() - datetime.timedelta(days=1)
#         start_date = end_date.replace(year=end_date.year - years)
#
#         benchmarks = {
#             "S&P 500": "^GSPC",
#             "Nasdaq Composite": "^IXIC",
#             "Dow Jones Industrial Average": "^DJI",
#         }
#
#         cagr_values: dict[str, float | None] = {}
#
#         for name, symbol in benchmarks.items():
#             data = yf.download(symbol, start=start_date, end=end_date, progress=False)
#
#             # brak lub zbyt mało danych
#             if data.empty or "Close" not in data.columns or len(data["Close"]) < 2:
#                 st.warning(f"Brak danych lub ograniczenie rate‑limit dla {symbol}.")
#                 cagr_values[name] = None
#                 continue
#
#             close = data["Close"]
#             start_price = close.iloc[0]
#             end_price   = close.iloc[-1]       # ostatnie notowanie
#             num_years   = (close.index[-1] - close.index[0]).days / 365.25
#             cagr_values[name] = ((end_price / start_price) ** (1 / num_years) - 1) * 100
#
#         # --- METRICS ------------------------------------------------------
#         col_bench_1, col_bench_2, col_bench_3 = st.columns(3)
#         with col_bench_1:
#             st.metric(f"S&P 500 ({years}-year CAGR)", safe_metric(cagr_values["S&P 500"]))
#         with col_bench_2:
#             st.metric(f"Nasdaq ({years}-year CAGR)", safe_metric(cagr_values["Nasdaq Composite"]))
#         with col_bench_3:
#             st.metric(f"Dow Jones ({years}-year CAGR)", safe_metric(cagr_values["Dow Jones Industrial Average"]))
#
#     # --- CALCULATE BUTTON -------------------------------------------------
#     if st.button("Calculate Investment"):
#         # --- CONSTANTS ----------------------------------------------------
#         compounding_map = {"daily": 365, "monthly": 12, "yearly": 1}
#         deposit_map     = {"daily": 365, "weekly": 52, "monthly": 12, "yearly": 1}
#
#         interest_periods = compounding_map[interest_compounding]
#         deposit_periods  = deposit_map[deposit_frequency]
#         total_periods    = int(investment_years * interest_periods)
#
#         deposit_step = interest_periods / deposit_periods
#         effective_rate_of_return = (1 + rate_of_return / 100) ** (1 / interest_periods) - 1
#         effective_inflation_rate = (1 + inflation_rate / 100) ** (1 / interest_periods) - 1
#
#         # --- SIMULATION ARRAYS -------------------------------------------
#         period_list, nominal_contributions_list, nominal_investment_value_list = [], [], []
#         real_contributions_list, real_investment_value_list = [], []
#
#         current_investment_value = initial_investment
#         total_nominal_contrib    = initial_investment
#         total_real_contrib       = initial_investment
#
#         for period in range(total_periods + 1):
#             # zapisz bieżący stan
#             period_list.append(period)
#             nominal_contributions_list.append(total_nominal_contrib)
#             nominal_investment_value_list.append(current_investment_value)
#
#             real_value = current_investment_value / ((1 + effective_inflation_rate) ** period)
#             real_investment_value_list.append(real_value)
#             real_contributions_list.append(total_real_contrib)
#
#             if period < total_periods:
#                 # wzrost kapitału
#                 current_investment_value *= (1 + effective_rate_of_return)
#
#                 # ewentualna wpłata
#                 if additional_deposit_amount > 0:
#                     should_deposit = (
#                         interest_periods >= deposit_periods
#                         and period > 0
#                         and (period % int(deposit_step) == 0)
#                     ) or (interest_periods < deposit_periods)
#
#                     if should_deposit:
#                         current_investment_value += additional_deposit_amount
#                         total_nominal_contrib    += additional_deposit_amount
#                         total_real_contrib       += additional_deposit_amount / (
#                             (1 + effective_inflation_rate) ** (period + 1)
#                         )
#
#         # --- PODSUMOWANIE -------------------------------------------------
#         final_nominal_contrib   = total_nominal_contrib
#         final_nominal_value     = current_investment_value
#         nominal_profit          = final_nominal_value - final_nominal_contrib
#         nominal_profit_pct      = (nominal_profit / final_nominal_contrib * 100) if final_nominal_contrib else 0
#         final_real_value        = final_nominal_value / ((1 + effective_inflation_rate) ** total_periods)
#         real_profit             = final_real_value - total_real_contrib
#         real_profit_pct         = (real_profit / total_real_contrib * 100) if total_real_contrib else 0
#         total_final_value       = final_nominal_value  # = contrib + nominal profit
#
#         # --- METRICS ------------------------------------------------------
#         colA, colB = st.columns(2)
#         with colA:
#             st.metric("Nominal Contributed Capital", f"{final_nominal_contrib:,.2f} USD")
#             st.metric("Nominal Profit (zero inflation)", f"{nominal_profit:,.2f} USD")
#             st.metric("Nominal Profit % (zero inflation)", f"{nominal_profit_pct:.2f}%")
#         with colB:
#             st.metric("Total Final Investment Value", f"{total_final_value:,.2f} USD")
#             st.metric("Real Profit (net of inflation)", f"{real_profit:,.2f} USD")
#             st.metric("Real Profit (net of inflation) %", f"{real_profit_pct:.2f}%")
#
#         # --- WYKRES -------------------------------------------------------
#         df = pd.DataFrame(
#             {
#                 "Period": period_list,
#                 "Nominal Contributed Capital": nominal_contributions_list,
#                 "Nominal Investment Value": nominal_investment_value_list,
#                 "Real Contributed Capital": real_contributions_list,
#                 "Real Investment Value": real_investment_value_list,
#             }
#         )
#         df["Real Profit over time (net of inflation)"] = (
#             df["Real Investment Value"] - df["Real Contributed Capital"]
#         )
#
#         fig = px.line(
#             df,
#             x="Period",
#             y=[
#                 "Nominal Investment Value",
#                 "Nominal Contributed Capital",
#                 "Real Profit over time (net of inflation)",
#             ],
#             labels={"value": "Amount (USD)", "variable": "Legend"},
#             title="Investment Growth Simulation (Nominal & Real Values)",
#         )
#         st.plotly_chart(fig, use_container_width=True)
#
#
# # -------------------------------------------------------------------------
# if __name__ == "__main__":
#     investment_calculator()
