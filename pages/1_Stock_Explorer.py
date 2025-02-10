import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    file_path = '/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv'
    data = pd.read_csv(file_path, delimiter=';')
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

if ticker:
    # Filtrujemy dane - ignorujemy wielkość liter
    company_details = df[df["Stock"].str.upper() == ticker.upper()]
    if not company_details.empty:
        st.dataframe(company_details)
    else:
        st.error(f"No data found for ticker '{ticker}'.")
else:
    st.info("Please enter a ticker symbol to view company details.")


st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)
