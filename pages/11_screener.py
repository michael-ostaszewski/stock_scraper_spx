# 3_Stock_Scanner.py
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from textwrap import dedent

# ---------- CONFIG -----------------------------------------------------------
st.set_page_config(page_title="Stock Scanner")
st.title("Stock Scanner")

######### CSS – spójny z Twoją aplikacją #####################################
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-weight: bold; }
    [data-testid="stMetricLabel"] { font-weight: bold; }

    div.stButton > button {
        width: 100%;
        color: #ffffff;
        background-image: linear-gradient(to right, #034980, #0277bd);
        border: 2px solid #0277bd;
        font-size: 16px;
        font-weight: bold;
        transition: background-image 0.3s ease, transform 0.3s ease;
    }
    .full-width-blue-button > button:hover {
        background-image: linear-gradient(to right, #388e3c, #66bb6a);
        transform: scale(1.02);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("""
Zbuduj własny skaner spółek z codziennych snapshotów metryk (Finviz-like).
Wybierz **datę**, zastosuj **preset** albo dodaj własne filtry. Zapisz wynik do CSV.
""")

# ---------- CACHING & LOAD ---------------------------------------------------
@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    df_ = pd.read_csv(
        path,
        parse_dates=["recorded_at_utc"],
        infer_datetime_format=True,
    )
    # Wyrównanie nazw kolumn (czasem CSVy potrafią mieć spacje niełamliwe)
    df_.columns = [c.replace("\xa0", " ").strip() for c in df_.columns]
    return df_

@st.cache_data(show_spinner=False)
def load_from_upload(file) -> pd.DataFrame:
    df_ = pd.read_csv(
        file,
        parse_dates=["recorded_at_utc"],
        infer_datetime_format=True,
    )
    df_.columns = [c.replace("\xa0", " ").strip() for c in df_.columns]
    return df_

# ---------- DATA SOURCE (fixed path) ----------------------------------------
sb = st.sidebar
sb.header("Ustawienia danych")

DEFAULT_PATH = "/Users/michal/PycharmProjects/Stock Scraper/Stocks fv/finviz_snapshot_clean.csv"

@st.cache_data(show_spinner=False)
def load_data_fixed(path: str) -> pd.DataFrame:
    # używamy wcześniejszego load_csv, żeby zachować parse_dates i czyszczenie nagłówków
    return load_csv(path)

try:
    df_full = load_data_fixed(DEFAULT_PATH)
except Exception as e:
    st.error(f"Nie udało się wczytać CSV z lokalizacji:\n{DEFAULT_PATH}\n\nSzczegóły: {e}")
    st.stop()

if df_full is None or df_full.empty:
    st.error(f"Brak danych w pliku: {DEFAULT_PATH}")
    st.stop()

# sb.caption(f"Źródło danych: `{DEFAULT_PATH}`")

# ---------- DATE SELECTION ---------------------------------------------------
if "recorded_at_utc" not in df_full.columns:
    st.error("Brak kolumny **recorded_at_utc** – nie mogę wybrać sesji.")
    st.stop()

df_full["record_date"] = df_full["recorded_at_utc"].dt.date
dates_available = sorted(df_full["record_date"].dropna().unique())
default_date = dates_available[-1]

chosen_date = sb.date_input(
    "Data sesji",
    value=default_date,
    min_value=dates_available[0],
    max_value=dates_available[-1],
)
df = df_full[df_full["record_date"] == chosen_date].copy()

if df.empty:
    st.error("Brak danych dla wybranej daty.")
    st.stop()

# ---------- HELPERS ----------------------------------------------------------
def is_num_col(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s)

NUM_COLS = [c for c in df.columns if is_num_col(df[c])]
OBJ_COLS = [c for c in df.columns if c not in NUM_COLS]

def qbounds(series: pd.Series, q_low=0.01, q_high=0.99) -> Tuple[float, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return (0.0, 1.0)
    return (float(s.quantile(q_low)), float(s.quantile(q_high)))

def safe_fmt_money(x: Optional[float]) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if abs(x) >= 1e12:
        return f"{x/1e12:,.2f} T"
    if abs(x) >= 1e9:
        return f"{x/1e9:,.2f} B"
    if abs(x) >= 1e6:
        return f"{x/1e6:,.2f} M"
    return f"{x:,.0f}"

# ---------- QUICK UNIVERSE FILTERS ------------------------------------------
sb.header("Szybkie filtry (uniwersum)")

index_cols = {
    "S&P 500": "Index_S&P_500",
    "NASDAQ-100": "Index_NDX",
    "DJIA": "Index_DJIA",
    "Russell 2000": "Index_RUT",
}
index_flags = {}
for lbl, col in index_cols.items():
    if col in df.columns:
        index_flags[col] = sb.checkbox(f"Tylko {lbl}", value=False)

# Market Cap / Price
mc_min, mc_max = (None, None)
if "Market Cap" in df.columns and is_num_col(df["Market Cap"]):
    # lo, hi = qbounds(df["Market Cap"])
    # mc_min, mc_max = sb.slider(
    #     "Market Cap [USD]",
    #     min_value=float(max(0.0, lo)),
    #     max_value=float(max(hi, lo + 1.0)),
    #     value=(float(max(0.0, lo)), float(hi)),
    #     step=float((hi - lo) / 100 if hi > lo else 1.0),
    # )
    mc_series = pd.to_numeric(df["Market Cap"], errors="coerce")
    lo_all, hi_all = float(mc_series.min()), float(mc_series.max())
    lo_q, hi_q = qbounds(mc_series, q_low=0.01, q_high=0.99)  # do wartości domyślnej

    mc_min, mc_max = sb.slider(
        "Market Cap [USD]",
        min_value=lo_all,
        max_value=hi_all,
        value=(lo_q, hi_q),  # domyślnie przycięte, ale można rozszerzyć do pełnego max
        step=max((hi_all - lo_all) / 200, 1.0),
    )

price_min, price_max = (None, None)
if "Price" in df.columns and is_num_col(df["Price"]):
    # lo_p, hi_p = qbounds(df["Price"])
    # price_min, price_max = sb.slider(
    #     "Cena (USD)",
    #     min_value=float(max(0.0, lo_p)),
    #     max_value=float(max(hi_p, lo_p + 0.01)),
    #     value=(float(max(0.0, lo_p)), float(hi_p)),
    #     step=float((hi_p - lo_p) / 200 if hi_p > lo_p else 0.01),
    # )
    pr_series = pd.to_numeric(df["Price"], errors="coerce")
    plo_all, phi_all = float(pr_series.min()), float(pr_series.max())
    plo_q, phi_q = qbounds(pr_series, 0.01, 0.99)

    price_min, price_max = sb.slider(
        "Cena (USD)",
        min_value=plo_all,
        max_value=phi_all,
        value=(plo_q, phi_q),
        step=max((phi_all - plo_all) / 200, 0.01),
    )

only_positive_eps = sb.checkbox("Tylko spółki z dodatnim EPS (ttm)", value=False)

# ---------- PRESETS (3 GOTOWE SKANERY) --------------------------------------
# --- Rule of 40 variant switch (wpływa na preset) ---------------------------
r40_choice = sb.radio(
    "Rule of 40 – wariant",
    ["Op (Sales YoY + Oper. Margin)", "Net (Sales YoY + Profit Margin)"],
    index=0,
    help="Obie definicje są spotykane; wybierz spójnie dla porównań.",
)
RULE40_COL = "Rule40_Op" if r40_choice.startswith("Op") else "Rule40_Net"

sb.header("Presety skanerów")
def get_presets(rule40_col: str) -> dict[str, list[dict]]:
    return {
        # (Twoje dotychczasowe)
        "Growth (quality)": [
            {"col": "EPS next 5Y (%)", "op": ">=", "val": 15},
            {"col": "Sales Y/Y TTM (%)", "op": ">=", "val": 10},
            {"col": "ROE (%)", "op": ">=", "val": 10},
            {"col": "Profit Margin (%)", "op": ">=", "val": 5},
            {"col": "Debt/Eq", "op": "<=", "val": 1.5},
            {"col": "P/E", "op": "between", "val": (5, 50)},
            {"col": "Market Cap", "op": ">=", "val": 2e9},
        ],
        "Dividend (sustainable)": [
            {"col": "Dividend TTM %", "op": ">=", "val": 2},
            {"col": "Payout (%)", "op": "between", "val": (20, 75)},
            {"col": "Dividend Gr. 5Y (%)", "op": ">=", "val": 5},
            {"col": "Profit Margin (%)", "op": ">=", "val": 5},
            {"col": "Debt/Eq", "op": "<=", "val": 2.0},
            {"col": "EPS (ttm)", "op": ">", "val": 0},
            {"col": "Market Cap", "op": ">=", "val": 1e9},
        ],
        "Momentum (12M/5Y)": [
            {"col": "Perf Year (%)", "op": ">=", "val": 20},
            {"col": "Perf 5Y (%)", "op": ">=", "val": 50},
            {"col": "SMA50 (%)", "op": ">", "val": 0},
            {"col": "SMA200 (%)", "op": ">", "val": 0},
            {"col": "RSI (14)", "op": "between", "val": (50, 80)},
            {"col": "Avg Volume", "op": ">=", "val": 250_000},
        ],

        # --- NOWE PRESETY ----------------------------------------------------
        "Q+G+M Leaders": [
            # Płynność / skala
            {"col": "Price", "op": ">=", "val": 10},
            {"col": "Avg Volume", "op": ">=", "val": 1_000_000},
            {"col": "Market Cap", "op": ">=", "val": 10e9},
            # Growth
            {"col": "Sales Y/Y TTM (%)", "op": ">=", "val": 25},
            {"col": "EPS Y/Y TTM (%)", "op": ">=", "val": 25},
            {"col": "EPS next Y (%)", "op": ">=", "val": 20},
            # Jakość
            {"col": "Gross Margin (%)", "op": ">=", "val": 50},
            {"col": "ROIC (%)", "op": ">=", "val": 15},
            {"col": "ROE (%)", "op": ">=", "val": 15},
            {"col": "Profit Margin (%)", "op": ">=", "val": 10},
            {"col": "Debt/Eq", "op": "<=", "val": 1.5},
            # Momentum / technika
            {"col": "Perf Year (%)", "op": ">=", "val": 50},
            {"col": "SMA50 (%)", "op": ">", "val": 0},
            {"col": "SMA200 (%)", "op": ">", "val": 0},
            {"col": "RSI (14)", "op": "between", "val": (50, 80)},
            # Valuation sanity (opcjonalne, usuń jeśli chcesz szerzej)
            {"col": "PEG", "op": "between", "val": (0.5, 2.0)},
        ],

        f"Rule-of-40 + ROIC ({'Op' if rule40_col=='Rule40_Op' else 'Net'})": [
            {"col": rule40_col, "op": ">=", "val": 40},
            {"col": "Gross Margin (%)", "op": ">=", "val": 60},
            {"col": "ROIC (%)", "op": ">=", "val": 10},
            {"col": "Debt/Eq", "op": "<=", "val": 1.0},
            {"col": "SMA50 (%)", "op": ">", "val": 0},
            {"col": "SMA200 (%)", "op": ">", "val": 0},
            {"col": "Perf Year (%)", "op": ">=", "val": 20},
            {"col": "EV/Sales", "op": "<=", "val": 15},
            {"col": "Avg Volume", "op": ">=", "val": 300_000},
            {"col": "Market Cap", "op": ">=", "val": 2e9},
        ],

        "Earnings Shock & Drift (PEAD)": [
            {"col": "EPS Surpr. (%)", "op": ">=", "val": 5},
            {"col": "Sales Surpr. (%)", "op": ">=", "val": 2},
            {"col": "Rel Volume", "op": ">=", "val": 1.5},
            {"col": "Perf Week (%)", "op": "between", "val": (0, 15)},
            {"col": "RSI (14)", "op": "between", "val": (45, 75)},
            {"col": "SMA50 (%)", "op": ">", "val": 0},
            {"col": "SMA200 (%)", "op": ">", "val": 0},
            {"col": "Price", "op": ">=", "val": 5},
            {"col": "Avg Volume", "op": ">=", "val": 500_000},
            # świeżo po wynikach – jeśli days_since_earnings dostępne
            {"col": "days_since_earnings", "op": "between", "val": (1, 10)},
        ],
    }




if "scanner_filters" not in st.session_state:
    st.session_state["scanner_filters"]: List[Dict[str, Any]] = []

PRESETS = get_presets(RULE40_COL)

preset_name = sb.selectbox("Wybierz preset (opcjonalnie)",
                           options=["— brak —"] + list(PRESETS.keys()), index=0)

# preset_name = sb.selectbox(
#     "Wybierz preset (opcjonalnie)",
#     options=["— brak —"] + list(PRESETS.keys()),
#     index=0,
# )
col_preset_btn1, col_preset_btn2 = sb.columns(2)
if col_preset_btn1.button("Załaduj preset", use_container_width=True, disabled=(preset_name == "— brak —")):
    st.session_state["scanner_filters"] = PRESETS.get(preset_name, []).copy()
if col_preset_btn2.button("Wyczyść filtry", use_container_width=True):
    st.session_state["scanner_filters"] = []

# # ---------- ADVANCED FILTER BUILDER ------------------------------------------
# sb.header("Dodaj własny filtr")
#
# # wybór kolumny
# col_to_filter = sb.selectbox("Kolumna", options=NUM_COLS + OBJ_COLS)
# # # operator
# # ops_num = ["≥", "≤", ">", "<", "=", "≠", "between"]
# # ops_obj = ["=", "≠", "contains"]
# # op = sb.selectbox("Operator", options=(ops_num if col_to_filter in NUM_COLS else ops_obj))
#
# # --- 1) W kreatorze: pozwól na oba zapisy -----------------------------
# ops_num = ["≥", "≤", ">=", "<=", ">", "<", "=", "==", "≠", "!=", "between"]
# ops_obj = ["=", "==", "≠", "!=", "contains"]
#
# # --- 2) Helper do normalizacji operatorów -----------------------------
# def _norm_op(op: str) -> str:
#     op = str(op).strip()
#     mapping = {
#         ">=": "≥",
#         "=>": "≥",
#         "<=": "≤",
#         "=<": "≤",
#         "!=": "≠",
#         "<>": "≠",
#         "==": "=",
#     }
#     return mapping.get(op, op)
#
# val: Any = None
# if col_to_filter in NUM_COLS:
#     if op == "between":
#         lo, hi = qbounds(df[col_to_filter])
#         val = sb.slider("Zakres (inclusive)", min_value=float(lo), max_value=float(hi),
#                         value=(float(lo), float(hi)))
#     else:
#         lo, hi = qbounds(df[col_to_filter])
#         val = sb.number_input("Wartość", value=float(lo), step=(hi - lo) / 100 if hi > lo else 1.0)
# else:
#     if op == "contains":
#         val = sb.text_input("Fragment tekstu")
#     else:
#         # porównanie tekstowe
#         candidates = sorted(df[col_to_filter].dropna().astype(str).unique())[:300]
#         val = sb.selectbox("Wybierz wartość", options=["<wpisz ręcznie>"] + candidates)
#         if val == "<wpisz ręcznie>":
#             val = sb.text_input("Wpisz wartość")
#
# if sb.button("Dodaj filtr", use_container_width=True):
#     st.session_state["scanner_filters"].append({"col": col_to_filter, "op": op, "val": val})

# --- 1) W kreatorze: pozwól na oba zapisy -----------------------------
ops_num = ["≥", "≤", ">=", "<=", ">", "<", "=", "==", "≠", "!=", "between"]
ops_obj = ["=", "==", "≠", "!=", "contains"]

# --- 2) Helper do normalizacji operatorów -----------------------------
def _norm_op(op: str) -> str:
    op = str(op).strip()
    mapping = {
        ">=": "≥", "=>": "≥",
        "<=": "≤", "=<": "≤",
        "!=": "≠", "<>": "≠",
        "==": "=",
    }
    return mapping.get(op, op)

# ---------- ADVANCED FILTER BUILDER ------------------------------------------
sb.header("Dodaj własny filtr")

# 1) wybór kolumny
col_to_filter = sb.selectbox("Kolumna", options=NUM_COLS + OBJ_COLS)

# 2) wybór operatora + NATYCHMIASTOWA normalizacja
op_raw = sb.selectbox(
    "Operator",
    options=(ops_num if col_to_filter in NUM_COLS else ops_obj)
)
op = _norm_op(op_raw)  # <— ważne

# 3) wartość(e) do filtra
val: Any = None
if col_to_filter in NUM_COLS:
    lo, hi = qbounds(df[col_to_filter])
    if op == "between":
        val = sb.slider(
            "Zakres (inclusive)",
            min_value=float(lo),
            max_value=float(hi),
            value=(float(lo), float(hi))
        )
    else:
        step = (hi - lo) / 100 if hi > lo else 1.0
        val = sb.number_input("Wartość", value=float(lo), step=step)
else:
    if op == "contains":
        val = sb.text_input("Fragment tekstu")
    else:
        candidates = sorted(df[col_to_filter].dropna().astype(str).unique())[:300]
        choice = sb.selectbox("Wybierz wartość", options=["<wpisz ręcznie>"] + candidates)
        val = sb.text_input("Wpisz wartość") if choice == "<wpisz ręcznie>" else choice

# 4) dodanie filtra (zapisujemy już znormalizowany operator)
if sb.button("Dodaj filtr", use_container_width=True):
    st.session_state["scanner_filters"].append({"col": col_to_filter, "op": op, "val": val})

def _metric_defs() -> dict[str, str]:
    return {
        "EPS next 5Y (%)": "Prognozowane tempo wzrostu zysku na akcję (EPS) średniorocznie na 5 lat.",
        "Sales Y/Y TTM (%)": "Wzrost przychodów r/r za ostatnie 12 miesięcy (TTM).",
        "ROE (%)": "Zwrot na kapitale własnym – efektywność użycia kapitału akcjonariuszy.",
        "ROIC (%)": "Zwrot na zainwestowanym kapitale – jakościowy miernik sprawności operacyjnej.",
        "Gross Margin (%)": "Marża brutto = (przychody − koszt własny sprzedaży) / przychody.",
        "Oper. Margin (%)": "Marża operacyjna (EBIT/przychody) – rentowność działalności podstawowej.",
        "Profit Margin (%)": "Marża netto (zysk netto/przychody) – ostateczna rentowność.",
        "Debt/Eq": "Wskaźnik zadłużenia do kapitału własnego – dźwignia finansowa.",
        "P/E": "Cena/zysk TTM – prosta wycena na bazie zysków z ostatnich 12 miesięcy.",
        "Forward P/E": "Cena/zysk na bazie prognoz przyszłych zysków.",
        "PEG": "P/E skorygowane o tempo wzrostu EPS (niższe ≈ bardziej 'GARP').",
        "EV/Sales": "Enterprise Value / sprzedaż – często używane przy spółkach wzrostowych.",
        "P/FCF": "Cena/FCF – im niżej, tym tańszy wolny przepływ pieniężny.",
        "Avg Volume": "Średni dzienny wolumen – proxy płynności.",
        "Price": "Aktualna cena akcji.",
        "Market Cap": "Kapitalizacja rynkowa – skala spółki.",
        "RSI (14)": "Indeks siły względnej z 14 dni – momentum krótkoterminowe (30–70 neutralny).",
        "SMA50 (%)": "% odchylenie ceny od 50-dniowej średniej kroczącej (powyżej 0 → trend wzrostowy).",
        "SMA200 (%)": "% odchylenie od 200-dniowej średniej – długoterminowy trend.",
        "Perf Week (%)": "Stopa zwrotu za 1 tydzień.",
        "Perf Month (%)": "Stopa zwrotu za 1 miesiąc.",
        "Perf Quarter (%)": "Stopa zwrotu za kwartał.",
        "Perf Half Y (%)": "Stopa zwrotu za pół roku.",
        "Perf Year (%)": "Stopa zwrotu za 12 miesięcy.",
        "Perf 5Y (%)": "Stopa zwrotu za 5 lat.",
        "Perf 10Y (%)": "Stopa zwrotu za 10 lat.",
        "EPS Y/Y TTM (%)": "Wzrost EPS r/r (TTM).",
        "EPS next Y (%)": "Prognozowany wzrost EPS w kolejnym roku.",
        "Dividend TTM %": "Bieżąca stopa dywidendy (za TTM).",
        "Payout (%)": "Wypłata dywidendy jako % zysku – trwałość wypłat.",
        "Dividend Gr. 5Y (%)": "Średnie roczne tempo wzrostu dywidendy (5 lat).",
        "EPS (ttm)": "Zysk na akcję za ostatnie 12 miesięcy.",
        "EV/EBITDA": "EV do EBITDA – wycena względem przepływów operacyjnych (bez D&A).",
        "days_since_earnings": "Liczba dni od publikacji wyników (w absolute value).",
        "Rel Volume": "Względny wolumen vs. średnia – siła reakcji rynku.",
    }

def _knowhow_text(preset: str, rule40_col: str) -> str:
    # krótkie, użytkowe opisy + dlaczego takie progi
    if preset == "Growth (quality)":
        return dedent(f"""
        **Cel:** wyłowić spółki wzrostowe o przyzwoitej jakości i rozsądnej wycenie (GARP).

        **Dlaczego takie progi?**
        - **EPS next 5Y ≥ 15%** i **Sales Y/Y ≥ 10%** – chcemy realnego tempa wzrostu przychodów i zysków.
        - **ROE ≥ 10%**, **Profit Margin ≥ 5%** – filtr jakości (zyskowność nie zjada wzrostu).
        - **Debt/Eq ≤ 1.5** – ograniczamy ryzyko zadłużenia.
        - **P/E 5–50** – unikamy zarówno skrajnie drogich, jak i „value traps”.
        - **Market Cap ≥ 2B** – minimum skali i płynności.

        **Kiedy poluzować?** Gdy chcesz złapać wcześniejszą fazę liderów – obniż progi wzrostu lub usuń górną granicę P/E.
        """)
    if preset == "Dividend (sustainable)":
        return dedent("""
        **Cel:** dywidenda, ale trwała – nie „high yield trap”.

        **Dlaczego takie progi?**
        - **Dividend TTM ≥ 2%** – sensowny poziom bieżącego dochodu.
        - **Payout 20–75%** – zbyt niski bywa sygnałem braku chęci dzielenia się, zbyt wysoki grozi cięciem.
        - **Dividend Gr. 5Y ≥ 5%** – realny wzrost wypłat.
        - **Profit Margin ≥ 5%**, **Debt/Eq ≤ 2.0**, **EPS (ttm) > 0** – filtr zdrowia finansowego.
        - **Market Cap ≥ 1B** – płynność/skalowalność.

        **Kiedy zaostrzyć?** Dla „dividend aristocrats” podnieś growth, obniż maksymalny payout.
        """)
    if preset == "Momentum (12M/5Y)":
        return dedent("""
        **Cel:** gra trendu – łączymy 12-miesięczne momentum z długim tłem 5-letnim.

        **Dlaczego takie progi?**
        - **Perf Year ≥ 20%** i **Perf 5Y ≥ 50%** – szukamy zwycięzców, nie odwróceń.
        - **SMA50 > 0**, **SMA200 > 0** – cena powyżej kluczowych średnich (trend).
        - **RSI 50–80** – dodatnie momentum, bez skrajnego „wygrzania”.
        - **Avg Volume ≥ 250k** – unikamy iluzji momentum na niskiej płynności.

        **Kiedy poluzować?** Przy szerokim rynku byków – obniż Perf Year do 10–15%.
        """)
    if preset == "Q+G+M Leaders":
        return dedent("""
        **Cel:** kandydaci na „liderów cyklu” – miks Quality + Growth + Momentum.

        **Dlaczego takie progi?**
        - **Price ≥ 10**, **Avg Volume ≥ 1M**, **Market Cap ≥ 10B** – handlowalność i skala.
        - **Sales Y/Y ≥ 25%**, **EPS Y/Y ≥ 25%**, **EPS next Y ≥ 20%** – szybki, spójny wzrost.
        - **Gross Margin ≥ 50%**, **ROIC ≥ 15%**, **ROE ≥ 15%**, **Profit Margin ≥ 10%** – przewaga konkurencyjna i jakość.
        - **Perf Year ≥ 50%**, **SMA50 > 0**, **SMA200 > 0**, **RSI 50–80** – potwierdzenie trendu.
        - **PEG 0.5–2.0** – bezpiecznik wyceny dla growth.

        **Kiedy poluzować?** Wcześniejsza faza liderów: obniż Sales/EPS Y/Y do 15–20% i usuń PEG.
        """)
    if preset.startswith("Rule-of-40 + ROIC"):
        variant = "Op (Sales + Oper. Margin)" if "Op" in preset or rule40_col == "Rule40_Op" \
                  else "Net (Sales + Profit Margin)"
        return dedent(f"""
        **Cel:** zdrowy wzrost = tempo przychodów + rentowność **≥ 40%** (Rule of 40, wariant **{variant}**)
        + filtr jakości i sanity check wyceny.

        **Dlaczego takie progi?**
        - **{rule40_col} ≥ 40** – szybkie firmy, które już „dowiozły” marżę.
        - **Gross Margin ≥ 60%**, **ROIC ≥ 10%**, **Debt/Eq ≤ 1.0** – jakość i rozsądna dźwignia.
        - **SMA50 > 0**, **SMA200 > 0**, **Perf Year ≥ 20%** – działający trend.
        - **EV/Sales ≤ 15** – bezpiecznik przed skrajnościami wyceny.
        - **Płynność:** **Avg Volume ≥ 300k**, **Market Cap ≥ 2B**.

        **Uwaga:** Rule of 40 ma różne warianty (Op/Net/EBITDA/FCF). Zachowaj spójność w porównaniach.
        """)
    if preset == "Earnings Shock & Drift (PEAD)":
        return dedent("""
        **Cel:** wykorzystać post-earnings announcement drift – pozytywne zaskoczenia „ciągną” kursy jeszcze tygodniami.

        **Dlaczego takie progi?**
        - **EPS Surpr. ≥ +5%**, **Sales Surpr. ≥ +2%** – istotny sygnał informacyjny.
        - **Rel Volume ≥ 1.5** – rynek naprawdę zareagował.
        - **Perf Week 0–15%**, **RSI 45–75** – momentum tak, ale bez gonienia paraboli.
        - **SMA50 > 0**, **SMA200 > 0** – trend w górę.
        - **days_since_earnings 1–10** – świeży katalizator.
        - **Price ≥ 5**, **Avg Volume ≥ 500k** – handel bez poślizgów.

        **Zarządzanie pozycją:** typowo 1–3 miesiące hold i comiesięczny rebalans.
        """)
    return ""

def _render_filters_table(preset_name: str, presets_dict: dict[str, list[dict]]):
    try:
        rows = presets_dict.get(preset_name, [])
        if not rows:
            return
        tbl = pd.DataFrame(rows)
        tbl = tbl.rename(columns={"col": "Kolumna", "op": "Operator", "val": "Wartość"})
        st.dataframe(tbl, use_container_width=True, height=min(300, 50 + 30*len(tbl)))
    except Exception:
        pass

if preset_name != "— brak —":
    with st.expander(f"📘 Know-how: {preset_name}", expanded=False):
        st.markdown(_knowhow_text(preset_name, RULE40_COL))
        st.markdown("**Filtry w tym presecie (domyślne wartości):**")
        _render_filters_table(preset_name, PRESETS)

        st.caption(
            "Uwaga: progi to punkt startu. Dostosuj je do rynku/branży i własnego horyzontu. "
            "Skaner łączy warunki logicznie jako AND (wszystkie muszą być spełnione)."
        )

# lista aktywnych filtrów z możliwością usuwania
if st.session_state["scanner_filters"]:
    st.markdown("**Aktywne filtry:**")
    to_remove = []
    for i, f in enumerate(st.session_state["scanner_filters"]):
        cols = st.columns([6, 1])
        cols[0].markdown(f"- `{f['col']}` {f['op']} {f['val']}``")
        if cols[1].button("✖", key=f"remove_{i}"):
            to_remove.append(i)
    if to_remove:
        for i in sorted(to_remove, reverse=True):
            st.session_state["scanner_filters"].pop(i)

# ---------- APPLY FILTERS ----------------------------------------------------
# def apply_filters(df_in: pd.DataFrame) -> pd.DataFrame:
#     df_out = df_in.copy()
#
#     # Szybkie filtry z sidebaru
#     for col, checked in index_flags.items():
#         # if checked and col in df_out.columns:
#         #     df_out = df_out[df_out[col] == 1]
#         checked_cols = [col for col, checked in index_flags.items() if checked]
#         if checked_cols:
#             mask = np.zeros(len(df_out), dtype=bool)
#             for col in checked_cols:
#                 if col in df_out.columns:
#                     mask |= (df_out[col] == 1)
#             df_out = df_out[mask]
#
#     if mc_min is not None and mc_max is not None and "Market Cap" in df_out.columns:
#         df_out = df_out[(df_out["Market Cap"] >= mc_min) & (df_out["Market Cap"] <= mc_max)]
#
#     if price_min is not None and price_max is not None and "Price" in df_out.columns:
#         df_out = df_out[(df_out["Price"] >= price_min) & (df_out["Price"] <= price_max)]
#
#     if only_positive_eps and "EPS (ttm)" in df_out.columns:
#         df_out = df_out[df_out["EPS (ttm)"] > 0]
#
#     # Filtry zaawansowane
#     for f in st.session_state["scanner_filters"]:
#         col, op, val = f["col"], f["op"], f["val"]
#         if col not in df_out.columns:
#             continue
#         s = df_out[col]
#
#         if is_num_col(s):
#             s = pd.to_numeric(s, errors="coerce")
#             if op == "≥": df_out = df_out[s >= float(val)]
#             elif op == "≤": df_out = df_out[s <= float(val)]
#             elif op == ">": df_out = df_out[s > float(val)]
#             elif op == "<": df_out = df_out[s < float(val)]
#             elif op == "=": df_out = df_out[s == float(val)]
#             elif op == "≠": df_out = df_out[s != float(val)]
#             elif op == "between":
#                 lo, hi = val
#                 df_out = df_out[s.between(float(lo), float(hi), inclusive="both")]
#         else:
#             s = s.astype(str)
#             if op == "contains" and isinstance(val, str):
#                 df_out = df_out[s.str.contains(val, case=False, na=False)]
#             elif op == "=":
#                 df_out = df_out[s == str(val)]
#             elif op == "≠":
#                 df_out = df_out[s != str(val)]
#
#     return df_out

def apply_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    df_out = df_in.copy()

    # --- Indeksy (uproszczona, jednokrotna aplikacja OR) -----------------
    checked_cols = [col for col, checked in index_flags.items() if checked]
    if checked_cols:
        mask = np.zeros(len(df_out), dtype=bool)
        for col in checked_cols:
            if col in df_out.columns:
                mask |= (pd.to_numeric(df_out[col], errors="coerce").fillna(0).astype(int) == 1)
        df_out = df_out[mask]

    # --- Market Cap / Price / EPS ----------------------------------------
    if mc_min is not None and mc_max is not None and "Market Cap" in df_out.columns:
        df_out = df_out[(df_out["Market Cap"] >= mc_min) & (df_out["Market Cap"] <= mc_max)]

    if price_min is not None and price_max is not None and "Price" in df_out.columns:
        df_out = df_out[(df_out["Price"] >= price_min) & (df_out["Price"] <= price_max)]

    if only_positive_eps and "EPS (ttm)" in df_out.columns:
        df_out = df_out[pd.to_numeric(df_out["EPS (ttm)"], errors="coerce") > 0]

    # --- Filtry z presetów / własne --------------------------------------
    for f in st.session_state["scanner_filters"]:
        col, op, val = f.get("col"), _norm_op(f.get("op", "")), f.get("val")
        if col not in df_out.columns:
            continue
        s = df_out[col]

        if is_num_col(s):
            s = pd.to_numeric(s, errors="coerce")
            if op == "≥":    df_out = df_out[s >= float(val)]
            elif op == "≤":  df_out = df_out[s <= float(val)]
            elif op == ">":  df_out = df_out[s >  float(val)]
            elif op == "<":  df_out = df_out[s <  float(val)]
            elif op == "=":  df_out = df_out[s == float(val)]
            elif op == "≠":  df_out = df_out[s != float(val)]
            elif op == "between":
                lo, hi = val
                df_out = df_out[s.between(float(lo), float(hi), inclusive="both")]
            else:
                st.warning(f"Nieznany operator liczbowy: {op} (filtr: {col})")
        else:
            s = s.astype(str)
            if op in ("=", "=="):   df_out = df_out[s == str(val)]
            elif op in ("≠", "!="): df_out = df_out[s != str(val)]
            elif op == "contains":  df_out = df_out[s.str.contains(str(val), case=False, na=False)]
            else:
                st.warning(f"Nieznany operator tekstowy: {op} (filtr: {col})")

    return df_out

df_scanned = apply_filters(df)


# with st.expander("🔧 Debug filtrów (self-check)", expanded=False):
#     tmp = df.copy()
#     for f in st.session_state["scanner_filters"]:
#         col, op, val = f["col"], _norm_op(f["op"]), f["val"]
#         if col not in tmp.columns:
#             st.write(f"❌ Brak kolumny: {col}")
#             continue
#         s = pd.to_numeric(tmp[col], errors="coerce") if is_num_col(tmp[col]) else tmp[col].astype(str)
#         before = len(tmp)
#         # policz tylko maskę, bez modyfikacji tmp
#         if is_num_col(tmp[col]):
#             if op == "≥": mask = s >= float(val)
#             elif op == "≤": mask = s <= float(val)
#             elif op == ">": mask = s > float(val)
#             elif op == "<": mask = s < float(val)
#             elif op == "=": mask = s == float(val)
#             elif op == "≠": mask = s != float(val)
#             elif op == "between":
#                 lo, hi = val; mask = s.between(float(lo), float(hi), inclusive="both")
#             else: mask = pd.Series(False, index=s.index)
#         else:
#             if op in ("=", "=="): mask = (s == str(val))
#             elif op in ("≠", "!="): mask = (s != str(val))
#             elif op == "contains": mask = s.str.contains(str(val), case=False, na=False)
#             else: mask = pd.Series(False, index=s.index)
#
#         st.write(f"• `{col}` {op} {val}  →  pasuje: {int(mask.sum())} / {before}")


with st.expander("🔧 Debug filtrów (self-check)", expanded=False):
    include_universe = st.checkbox(
        "Uwzględnij szybkie filtry (indeksy / Market Cap / Price / EPS+)",
        value=True
    )

    # --- Etapy do lejka (kumulatywnie) -------------------------------------
    stages: list[tuple[str, int]] = []
    stage_rows = []  # do tabeli
    current = df.copy()
    stages.append(("Start (wszystkie)", len(current)))

    # -- 1) Szybkie filtry (opcjonalnie w lejku)
    if include_universe:
        # Indeksy (OR po zaznaczonych)
        checked_cols = [c for c, on in index_flags.items() if on and c in current.columns]
        if checked_cols:
            mask = np.zeros(len(current), dtype=bool)
            for c in checked_cols:
                mask |= (pd.to_numeric(current[c], errors="coerce").fillna(0).astype(int) == 1)
            before = len(current)
            matched = int(mask.sum())
            current = current[mask]
            after = len(current)
            used_labels = [lbl for lbl, col in index_cols.items() if index_flags.get(col, False)]
            label = f"Indeksy: {', '.join(used_labels)}"
            stages.append((label, after))
            stage_rows.append({"Krok": "Uni", "Filtr": label, "Przed": before, "Pasuje": matched,
                               "Po": after, "Drop-off %": round((1 - after / before) * 100, 2) if before else 0.0})

        # Market Cap
        if mc_min is not None and mc_max is not None and "Market Cap" in current.columns:
            s = pd.to_numeric(current["Market Cap"], errors="coerce")
            before = len(current)
            mask = s.between(float(mc_min), float(mc_max), inclusive="both")
            matched = int(mask.sum())
            current = current[mask]
            after = len(current)
            label = f"Market Cap [{safe_fmt_money(mc_min)} .. {safe_fmt_money(mc_max)}]"
            stages.append((label, after))
            stage_rows.append({"Krok": "Uni", "Filtr": label, "Przed": before, "Pasuje": matched,
                               "Po": after, "Drop-off %": round((1 - after / before) * 100, 2) if before else 0.0})

        # Price
        if price_min is not None and price_max is not None and "Price" in current.columns:
            s = pd.to_numeric(current["Price"], errors="coerce")
            before = len(current)
            mask = s.between(float(price_min), float(price_max), inclusive="both")
            matched = int(mask.sum())
            current = current[mask]
            after = len(current)
            label = f"Cena [{float(price_min):.2f} .. {float(price_max):.2f}]"
            stages.append((label, after))
            stage_rows.append({"Krok": "Uni", "Filtr": label, "Przed": before, "Pasuje": matched,
                               "Po": after, "Drop-off %": round((1 - after / before) * 100, 2) if before else 0.0})

        # EPS dodatni
        if only_positive_eps and "EPS (ttm)" in current.columns:
            s = pd.to_numeric(current["EPS (ttm)"], errors="coerce")
            before = len(current)
            mask = s > 0
            matched = int(mask.sum())
            current = current[mask]
            after = len(current)
            label = "EPS (ttm) > 0"
            stages.append((label, after))
            stage_rows.append({"Krok": "Uni", "Filtr": label, "Przed": before, "Pasuje": matched,
                               "Po": after, "Drop-off %": round((1 - after / before) * 100, 2) if before else 0.0})

    # -- 2) Filtry zaawansowane (kreator)
    tmp_prev = current.copy()
    for i, f in enumerate(st.session_state.get("scanner_filters", []), start=1):
        col, op, val = f["col"], _norm_op(f["op"]), f["val"]
        label_val = (f"{val[0]:g}–{val[1]:g}" if (op == "between" and isinstance(val, (tuple, list)))
                     else (f"{val}" if not isinstance(val, float) else f"{val:g}"))
        label = f"{col} {op} {label_val}"

        if col not in tmp_prev.columns:
            stage_rows.append({"Krok": i, "Filtr": f"❌ {label} (brak kolumny)", "Przed": len(tmp_prev),
                               "Pasuje": 0, "Po": len(tmp_prev), "Drop-off %": 0.0})
            stages.append((f"❌ {label}", len(tmp_prev)))
            continue

        s = tmp_prev[col]
        if is_num_col(s):
            s = pd.to_numeric(s, errors="coerce")
            if op == "≥":       mask = s >= float(val)
            elif op == "≤":     mask = s <= float(val)
            elif op == ">":     mask = s > float(val)
            elif op == "<":     mask = s < float(val)
            elif op == "=":     mask = s == float(val)
            elif op == "≠":     mask = s != float(val)
            elif op == "between":
                lo, hi = val
                mask = s.between(float(lo), float(hi), inclusive="both")
            else:
                mask = pd.Series(False, index=s.index)
        else:
            s = s.astype(str)
            if op in ("=", "=="):       mask = (s == str(val))
            elif op in ("≠", "!="):     mask = (s != str(val))
            elif op == "contains":      mask = s.str.contains(str(val), case=False, na=False)
            else:                       mask = pd.Series(False, index=s.index)

        before  = len(tmp_prev)
        matched = int(mask.sum())
        tmp_prev = tmp_prev[mask]
        after   = len(tmp_prev)
        drop    = round((1 - after / before) * 100, 2) if before else 0.0

        stages.append((label, after))
        stage_rows.append({"Krok": i, "Filtr": label, "Przed": before, "Pasuje": matched, "Po": after, "Drop-off %": drop})

    # --- Wykres lejka --------------------------------------------------------
    if len(stages) > 1:
        labels = [s[0] for s in stages]
        values = [s[1] for s in stages]

        # Tworzymy FIGURĘ z trace typu Funnel
        fig_funnel = go.Figure(
            data=[go.Funnel(
                y=labels,
                x=values,
                textinfo="value+percent previous"
            )]
        )
        fig_funnel.update_layout(
            height=max(620, 38 * len(labels)),
            margin=dict(l=10, r=10, t=20, b=10)
        )
        st.plotly_chart(fig_funnel, use_container_width=True)


# ---------- SORT & COLUMNS PICK ---------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.subheader("Wyniki skanera")

default_display_cols = [
    "Ticker", "Price", "Market Cap", "P/E", "EPS (ttm)",
    "EPS next 5Y (%)", "Sales Y/Y TTM (%)", "ROE (%)", "ROA (%)",
    "Debt/Eq", "P/FCF", "Dividend TTM %", "Payout (%)",
    "Perf YTD (%)", "Perf Year (%)", "Perf 3Y (%)",
    "RSI (14)", "Beta", "SMA50 (%)", "SMA200 (%)",
    "recorded_at_utc"
]
display_cols = [c for c in default_display_cols if c in df_scanned.columns]
cols_pick = st.multiselect(
    "Wybierz kolumny do tabeli",
    options=list(df_scanned.columns),
    default=display_cols,
)

sort_col = st.selectbox(
    "Sortuj po",
    options=cols_pick if cols_pick else list(df_scanned.columns),
    index=(cols_pick.index("Market Cap") if "Market Cap" in cols_pick else 0),
)
sort_asc = st.checkbox("Rosnąco", value=False)

# ---------- METRICS ----------------------------------------------------------
total_matches = int(df_scanned.shape[0])

avg_mcap = float(df_scanned["Market Cap"].mean()) if "Market Cap" in df_scanned.columns else np.nan
median_pe = float(df_scanned["P/E"].median()) if "P/E" in df_scanned.columns else np.nan
avg_div = float(df_scanned["Dividend TTM %"].mean()) if "Dividend TTM %" in df_scanned.columns else np.nan
avg_ytd = float(df_scanned["Perf YTD (%)"].mean()) if "Perf YTD (%)" in df_scanned.columns else np.nan

m1, m2, m3, m4 = st.columns(4)
m1.metric("Liczba spółek", f"{total_matches}")
m2.metric("Śr. Market Cap", safe_fmt_money(avg_mcap))
m3.metric("Mediana P/E", f"{median_pe:,.2f}" if not np.isnan(median_pe) else "—")
m4.metric("Śr. Dywidenda TTM", f"{avg_div:,.2f}%" if not np.isnan(avg_div) else "—")

# ---- Średnie stopy zwrotu dla przefiltrowanych spółek ----------------------
def _fmt_pct(x: float) -> str:
    try:
        return f"{x:+.2f}%"
    except Exception:
        return "—"

perf_cols_map = [
    ("Perf Week (%)",   "Śr. tydzień"),
    ("Perf Month (%)",  "Śr. miesiąc"),
    ("Perf Quarter (%)","Śr. kwartał"),
    ("Perf Half Y (%)", "Śr. półrocze"),
    ("Perf 5Y (%)",     "Śr. 5 lat"),
    ("Perf 10Y (%)",    "Śr. 10 lat"),
]

present = [(col, lab) for col, lab in perf_cols_map if col in df_scanned.columns]

if present:
    st.markdown("**Średnie stopy zwrotu (dla przefiltrowanych spółek):**")
    cols_per_row = 3
    for i in range(0, len(present), cols_per_row):
        row = st.columns(cols_per_row)
        for j, (col, lab) in enumerate(present[i:i+cols_per_row]):
            avg_val = pd.to_numeric(df_scanned[col], errors="coerce").mean()
            row[j].metric(lab, _fmt_pct(avg_val) if pd.notna(avg_val) else "—")

# ---------- RESULTS TABLE & DOWNLOAD ----------------------------------------
if total_matches == 0:
    st.warning("Brak wyników – dopasuj filtry.")
else:
    # sort
    if sort_col in df_scanned.columns:
        df_scanned = df_scanned.sort_values(sort_col, ascending=sort_asc, kind="mergesort")

    st.dataframe(df_scanned[cols_pick], use_container_width=True, height=500)

    # download
    csv_bytes = df_scanned[cols_pick].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Pobierz wyniki jako CSV",
        data=csv_bytes,
        file_name=f"scanner_{chosen_date}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ---------- VISUALS ----------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.subheader("Wizualizacje (opcjonalne)")

viz_choice = st.selectbox(
    "Wybierz wykres",
    options=[
        "— brak —",
        "P/E vs. EPS next 5Y",
        "Dividend % vs. Payout %",
        "Momentum map: Perf Year vs. RSI",
    ],
    index=0,
)

if total_matches > 0 and viz_choice != "— brak —":
    if viz_choice == "P/E vs. EPS next 5Y":
        needed = ["P/E", "EPS next 5Y (%)", "Market Cap", "Ticker"]
        ok = all(col in df_scanned.columns for col in needed)
        if not ok:
            st.info("Brakuje wymaganych kolumn: P/E, EPS next 5Y (%), Market Cap, Ticker.")
        else:
            src = df_scanned.dropna(subset=["P/E", "EPS next 5Y (%)"]).copy()
            src["mc_bubble"] = np.clip(np.sqrt(src["Market Cap"].clip(lower=0)) / 500, 3, 50)
            fig = px.scatter(
                src,
                x="P/E",
                y="EPS next 5Y (%)",
                size="mc_bubble",
                hover_name="Ticker",
                title="Valuation vs. Growth",
            )
            fig.update_layout(height=550)
            st.plotly_chart(fig, use_container_width=True)

    elif viz_choice == "Dividend % vs. Payout %":
        needed = ["Dividend TTM %", "Payout (%)", "Ticker"]
        ok = all(col in df_scanned.columns for col in needed)
        if not ok:
            st.info("Brakuje wymaganych kolumn: Dividend TTM %, Payout (%), Ticker.")
        else:
            src = df_scanned.dropna(subset=["Dividend TTM %", "Payout (%)"]).copy()
            fig = px.scatter(
                src,
                x="Payout (%)",
                y="Dividend TTM %",
                hover_name="Ticker",
                title="Sustainability Check (Yield vs. Payout)",
            )
            fig.add_vline(x=75, line_dash="dash", line_color="red", opacity=0.6)
            fig.add_vline(x=20, line_dash="dash", line_color="green", opacity=0.6)
            fig.update_layout(height=550, xaxis_title="Payout (%)", yaxis_title="Dividend TTM %")
            st.plotly_chart(fig, use_container_width=True)

    elif viz_choice == "Momentum map: Perf Year vs. RSI":
        needed = ["Perf Year (%)", "RSI (14)", "Market Cap", "Ticker"]
        ok = all(col in df_scanned.columns for col in needed)
        if not ok:
            st.info("Brakuje wymaganych kolumn: Perf Year (%), RSI (14), Market Cap, Ticker.")
        else:
            src = df_scanned.dropna(subset=["Perf Year (%)", "RSI (14)"]).copy()
            src["mc_bubble"] = np.clip(np.sqrt(src["Market Cap"].clip(lower=0)) / 500, 3, 50)
            fig = px.scatter(
                src,
                x="RSI (14)",
                y="Perf Year (%)",
                size="mc_bubble",
                hover_name="Ticker",
                title="Momentum Map",
            )
            fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)
            fig.update_layout(height=550, xaxis_title="RSI (14)", yaxis_title="12M Performance (%)")
            st.plotly_chart(fig, use_container_width=True)

# ---------- FOOTER -----------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    """
**Disclaimer:** Inwestowanie wiąże się z ryzykiem; możesz stracić część lub całość kapitału.  
Ta strona ma charakter **informacyjny** i nie stanowi **porady inwestycyjnej**.
"""
)
st.markdown(
    """
<p style="font-size: 12px; text-align: left; color: gray;">
Website made by @Michał Ostaszewski
</p>
""",
    unsafe_allow_html=True,
)