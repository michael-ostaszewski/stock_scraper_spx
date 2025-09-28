# Monte Carlo GBM Simulator (Stooq) — Streamlit page
# --------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pandas.tseries.offsets import BDay

# ---------- Styling (keeps your app look & feel) ----------
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { font-weight: bold; }
    div.stButton > button {
        width: 100%;
        color: #ffffff;
        background-image: linear-gradient(to right, #034980, #0277bd);
        border: 2px solid #0277bd;
        font-size: 16px;
        font-weight: bold;
        transition: background-image 0.3s ease, transform 0.3s ease;
    }
    div.stButton > button:hover {
        background-image: linear-gradient(to right, #388e3c, #66bb6a);
        transform: scale(1.02);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.header("Monte Carlo Simulator (GBM) for US Stocks")

# ---------- Data loaders ----------
@st.cache_data(show_spinner=False)
def load_stooq_ohlc(symbol_stooq: str, interval: str = "d") -> pd.DataFrame:
    """
    Downloads OHLCV from Stooq. Interval: 'd' (daily), 'w' (weekly), 'm' (monthly).
    Returns DF indexed by Date with columns: Open, High, Low, Close, Volume
    """
    url = f"https://stooq.com/q/d/l/?s={symbol_stooq}&i={interval}"
    df = pd.read_csv(url)
    if df.empty or "Date" not in df.columns:
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return df

@st.cache_data(show_spinner=False)
def load_stooq_close(symbol_stooq: str) -> pd.Series:
    """Close-only helper for market (e.g., 'qqq.us')."""
    url = f"https://stooq.com/q/d/l/?s={symbol_stooq}&i=d"
    df = pd.read_csv(url)
    if df.empty or "Date" not in df.columns or "Close" not in df.columns:
        return pd.Series(dtype=float)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").set_index("Date")
    return df["Close"]

# ---------- Sidebar / inputs ----------
with st.sidebar:
    st.subheader("Simulation settings")
    ticker = st.text_input("Ticker (US)", value="NVDA", help="US stock symbol, e.g., AAPL, MSFT, NVDA")
    start_date = st.date_input("Start date for estimation window", value=pd.Timestamp("2010-01-01").date())
    interval = st.selectbox("Price interval (Stooq)", options=["Daily (d)", "Weekly (w)", "Monthly (m)"], index=0)
    horizon_days = st.slider("Horizon (trading days)", min_value=21, max_value=756, value=252, step=21)
    n_sims = st.slider("Number of simulations", min_value=1000, max_value=50_000, value=10_000, step=1000)
    seed = st.number_input("Random seed", value=42, step=1)
    use_capm = st.checkbox("Use CAPM-adjusted drift (market = QQQ)", value=False)
    rf_annual = st.number_input("Risk-free rate (annual, e.g. 0.04 = 4%)", value=0.04, step=0.01, format="%.4f",
                                help="Used only if CAPM is enabled.")

# Map interval label to Stooq code
interval_code = {"Daily (d)": "d", "Weekly (w)": "w", "Monthly (m)": "m"}[interval]

# ---------- Load data ----------
symbol_stooq = f"{ticker.lower()}.us"
prices = load_stooq_ohlc(symbol_stooq, interval=interval_code)

if prices.empty:
    st.error("No data downloaded from Stooq. Check the ticker (US exchange only) or try Daily interval.")
    st.stop()

# Trim by start date & pick Close
close = prices.loc[prices.index >= pd.to_datetime(start_date), "Close"].dropna().copy()
if close.empty:
    st.error("No data after the selected start date. Pick an earlier date.")
    st.stop()

# ---------- Parameter estimation ----------
np.random.seed(int(seed))
S0 = float(close.iloc[-1])
log_ret = np.log(close).diff().dropna()
if log_ret.empty:
    st.error("Not enough data to estimate returns. Try a different start date or interval.")
    st.stop()

mu_daily = float(log_ret.mean())
sigma_daily = float(log_ret.std())
mu_annual = mu_daily * 252.0
sigma_annual = sigma_daily * np.sqrt(252.0)

# Optional CAPM: estimate beta vs QQQ and replace mu_annual with CAPM drift
if use_capm:
    mkt = load_stooq_close("qqq.us")
    both = pd.concat([close, mkt], axis=1, join="inner").dropna()
    both.columns = ["ASSET", "MKT"]
    r_a = np.log(both["ASSET"]).diff().dropna()
    r_m = np.log(both["MKT"]).diff().dropna()
    if r_a.empty or r_m.empty:
        st.warning("Not enough overlapping data to estimate CAPM. Falling back to historical μ.")
    else:
        beta = np.cov(r_a, r_m)[0, 1] / np.var(r_m)
        mkt_return_annual = float(r_m.mean() * 252.0)
        mu_annual = float(rf_annual + beta * (mkt_return_annual - rf_annual))

# ---------- GBM simulation ----------
dt = 1.0 / 252.0
steps = int(horizon_days)
drift = (mu_annual - 0.5 * sigma_annual**2) * dt
diffusion = sigma_annual * np.sqrt(dt)

Z = np.random.standard_normal((steps, n_sims))
increments = drift + diffusion * Z
log_paths = np.cumsum(increments, axis=0)
price_paths = S0 * np.exp(log_paths)  # shape: [steps, n_sims]

terminal = price_paths[-1, :]
p05, p50, p95 = np.percentile(terminal, [5, 50, 95])
exp_mean = float(terminal.mean())

last_date = close.index[-1]
forecast_end_date = (last_date + BDay(horizon_days)).date()
pct_upside = (exp_mean / S0 - 1.0) * 100 if S0 else float("nan")


# st.markdown("<hr>", unsafe_allow_html=True)

# ---------- Headline metrics ----------
# st.markdown("### Summary")

# Row 1 — three metrics
c1, c2, c3 = st.columns(3)
c1.metric("Last price", f"{S0:,.2f} USD")
c2.metric("μ (annualized)", f"{mu_annual:.4f}")
c3.metric("σ (annualized)", f"{sigma_annual:.4f}")

# Row 2 — three metrics
c4, c5, c6 = st.columns(3)
c4.metric("Forecast date", str(forecast_end_date))
c5.metric("P5 (downside)", f"{p05:,.2f} USD")
c6.metric("Median", f"{p50:,.2f} USD")

# Optional: add a third row if you still want P95 and Mean visible
c7, c8, c9 = st.columns(3)
c7.metric("P95 (upside)", f"{p95:,.2f} USD")
c8.metric("Mean (expected)", f"{exp_mean:,.2f} USD")
c9.metric("Upside vs. spot", f"{pct_upside:+.2f}%")

st.caption(
    "GBM path formula: S(t+Δt) = S(t) · exp[(μ − 0.5·σ²)·Δt + σ·√Δt·Z). "
    "Parameters estimated from historical log returns (daily → annualized).")

# ---------- Paths plot (first N for readability) ----------
st.subheader(f"Sample price paths for {ticker.upper()} (first 50 of {n_sims:,} simulations)")
n_show = min(50, n_sims)
df_paths = pd.DataFrame(price_paths[:, :n_show])
df_paths["Step"] = np.arange(1, steps + 1)

fig_paths = px.line(
    df_paths,
    x="Step",
    y=[c for c in df_paths.columns if c != "Step"],
    labels={"value": "Price [USD]", "Step": "Trading day"},
)
fig_paths.update_layout(margin=dict(t=10, r=10, b=10, l=10), height=520, showlegend=False)
st.plotly_chart(fig_paths, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ---------- Terminal distribution ----------
st.subheader("Terminal price distribution")
hist_df = pd.DataFrame({"TerminalPrice": terminal})
fig_hist = px.histogram(hist_df, x="TerminalPrice", nbins=80, opacity=0.85)
fig_hist.add_vline(x=p05, line_dash="dash", annotation_text="P5", annotation_position="top")
fig_hist.add_vline(x=p50, line_dash="dash", annotation_text="P50", annotation_position="top")
fig_hist.add_vline(x=p95, line_dash="dash", annotation_text="P95", annotation_position="top")
fig_hist.update_layout(
    xaxis_title=f"Price after {horizon_days} trading days [USD]",
    yaxis_title="Simulations",
    margin=dict(t=10, r=10, b=10, l=10),
)
st.plotly_chart(fig_hist, use_container_width=True)

# # ---------- Extras ----------
# colA, colB = st.columns(2)
# with colA:
#     st.download_button(
#         "Download terminal distribution (CSV)",
#         data=hist_df.to_csv(index=False).encode(),
#         file_name=f"{ticker.upper()}_mc_terminal_{horizon_days}d_{n_sims}sim.csv",
#         mime="text/csv",
#         use_container_width=True,
#     )
# with colB:
#     st.download_button(
#         "Download sample paths (first 50) as CSV",
#         data=df_paths.to_csv(index=False).encode(),
#         file_name=f"{ticker.upper()}_mc_paths_sample.csv",
#         mime="text/csv",
#         use_container_width=True,
#     )

st.markdown("<hr>", unsafe_allow_html=True)
st.caption(
    "Note: This is a simple GBM model based on historical volatility and drift (or CAPM drift if enabled). "
    "It ignores jumps, stochastic volatility, dividends, splits alignment, and other market microstructure effects. "
    "Use for educational purposes; this is not investment advice."
)
