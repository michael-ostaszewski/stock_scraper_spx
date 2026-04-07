# Monte Carlo GBM Simulator (Stooq) — Streamlit page
# --------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pandas.tseries.offsets import BDay
from datetime import date, timedelta
from app_auth import require_auth

require_auth("GBM Price Simulator")

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


# ============================
#  GBM Calibration & Out-of-Sample Check (Stooq)
# ============================

st.header("GBM Backtest: Calibrate on a Window and Evaluate to a Target Date")

# ---------- Data loaders (Stooq) ----------
@st.cache_data(show_spinner=False)
def to_stooq_symbol(ticker: str, suffix=".us") -> str:
    """
    Map Yahoo-style ticker (AAPL, BRK.B) to Stooq symbol:
    lower-case, '.' -> '-', + '.us' suffix for US stocks.
    """
    t = ticker.strip().lower().replace(".", "-")
    return f"{t}{suffix}"

@st.cache_data(show_spinner=True)
def load_stooq_ohlcv(ticker: str, start=None, end=None, interval: str = "d") -> pd.DataFrame:
    """
    Fetch OHLCV from Stooq for the given ticker.
    interval: 'd' (daily), 'w' (weekly), 'm' (monthly)
    """
    symbol = to_stooq_symbol(ticker, suffix=".us")
    url = f"https://stooq.com/q/d/l/?s={symbol}&i={interval}"
    df = pd.read_csv(url)
    if df.empty:
        raise ValueError(f"No data from Stooq for symbol: {symbol} (URL: {url})")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").set_index("Date")
    if start:
        df = df[df.index >= pd.to_datetime(start)]
    if end:
        df = df[df.index <= pd.to_datetime(end)]
    return df

@st.cache_data(show_spinner=False)
def load_stooq_close(symbol_stooq: str) -> pd.Series:
    """
    Helper: fetch daily Close by Stooq symbol (e.g., 'qqq.us').
    """
    url = f"https://stooq.com/q/d/l/?s={symbol_stooq}&i=d"
    s = pd.read_csv(url, parse_dates=['Date']).set_index('Date').sort_index()['Close'].dropna()
    return s

# ---------- UI: Inputs ----------
with st.expander("Settings", expanded=True):
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        ticker = st.text_input("Ticker (US)", value="FSLR", help="Any US stock ticker (e.g., NVDA, AAPL, BRK.B)")
    with c2:
        n_sims = st.number_input("Simulations (N)", min_value=1000, max_value=200_000, value=10_000, step=1000)
    with c3:
        seed = st.number_input("Random seed", min_value=0, max_value=2_147_483_647, value=42, step=1)

    c4, c5, c6 = st.columns([1, 1, 1])
    with c4:
        use_capm = st.checkbox("Use CAPM drift (market = QQQ)", value=False,
                               help="Overrides μ with CAPM estimate based on QQQ.")
    with c5:
        interval = st.selectbox("Interval", ["d", "w", "m"], index=0, help="Daily/Weekly/Monthly data from Stooq")
    with c6:
        st.caption("Tip: Keep daily for GBM. Weekly/monthly allowed for experiments.")

# Load once we have a ticker
try:
    df_all = load_stooq_ohlcv(ticker, interval=interval)
except Exception as e:
    st.error(f"Failed to load data for {ticker}: {e}")
    st.stop()

if df_all.empty:
    st.error("No data returned for the selected ticker.")
    st.stop()

min_dt = df_all.index.min().date()
max_dt = df_all.index.max().date()

with st.expander("Calibration & Evaluation Window", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        train_start = st.date_input("Training start", value=date(2010, 1, 1),
                                    min_value=min_dt, max_value=max_dt)
    with c2:
        # by default: use the penultimate trading day as train_end (if available)
        default_train_end = max_dt
        # ensure train_end ≥ train_start
        if default_train_end < train_start:
            default_train_end = train_start
        train_end = st.date_input("Training end", value=default_train_end,
                                  min_value=train_start, max_value=max_dt)
    with c3:
        # default eval_end = latest available trading day
        default_eval_end = max_dt
        eval_end = st.date_input("Evaluation end (target date)",
                                 value=default_eval_end,
                                 min_value=train_end, max_value=max_dt,
                                 help="Backtest to this real market date (last trading day by default).")

run = st.button("Run GBM backtest", type="primary", use_container_width=True)

if not run:
    st.stop()

# ---------- Guardrails ----------
if train_start > train_end:
    st.error("Training start must be ≤ training end.")
    st.stop()

# ---------- Prepare series ----------
df = df_all.copy()
train_close = df.loc[(df.index >= pd.to_datetime(train_start)) &
                     (df.index <= pd.to_datetime(train_end)), "Close"].dropna().copy()
if train_close.empty:
    st.error("No data inside the selected training window.")
    st.stop()

S0_date = train_close.index[-1]
S0 = float(train_close.iloc[-1])

future_segment = df.loc[(df.index > S0_date) & (df.index <= pd.to_datetime(eval_end)), "Close"].copy()
steps = len(future_segment)
if steps <= 0:
    st.error("No trading sessions between training end and evaluation end. Choose a later evaluation date.")
    st.stop()

S_T_real = float(df.loc[:pd.to_datetime(eval_end), "Close"].iloc[-1])
T_end_date = df.loc[:pd.to_datetime(eval_end)].index[-1]

# ---------- Parameter estimation (μ, σ) ----------
np.random.seed(int(seed))
log_ret = np.log(train_close).diff().dropna()
if log_ret.empty:
    st.error("Not enough observations in the training window to estimate log-returns.")
    st.stop()

mu_daily     = float(log_ret.mean())
sigma_daily  = float(log_ret.std())
# annualize
scale = 252.0 if interval == "d" else (52.0 if interval == "w" else 12.0)
mu_annual    = mu_daily * scale
sigma_annual = sigma_daily * np.sqrt(scale)

# Optional CAPM μ
if use_capm:
    try:
        mkt = load_stooq_close("qqq.us")
        both = pd.concat([train_close, mkt], axis=1, join="inner").dropna()
        both.columns = ["ASSET", "MKT"]
        r_a = np.log(both["ASSET"]).diff().dropna()
        r_m = np.log(both["MKT"]).diff().dropna()
        beta = np.cov(r_a, r_m)[0, 1] / np.var(r_m)
        rf_annual = 0.04
        mkt_return_annual = float(r_m.mean() * 252.0)
        mu_annual = float(rf_annual + beta * (mkt_return_annual - rf_annual))
    except Exception as e:
        st.warning(f"CAPM override failed ({e}). Falling back to historical μ.")
        # keep mu_annual as estimated above

# ---------- GBM simulation over the exact number of sessions ----------
dt = 1.0 / 252.0  # use trading-day granularity for GBM
drift = (mu_annual - 0.5 * sigma_annual**2) * dt
diffusion = sigma_annual * np.sqrt(dt)

Z = np.random.standard_normal((steps, int(n_sims)))
increments = drift + diffusion * Z
log_paths = np.cumsum(increments, axis=0)
price_paths = S0 * np.exp(log_paths)  # shape [steps, n_sims]

terminal = price_paths[-1, :]
p05, p50, p95 = np.percentile(terminal, [5, 50, 95])
mean_pred = float(terminal.mean())

# ---------- Accuracy metrics ----------
abs_err_med  = abs(p50 - S_T_real)
mape_med     = abs_err_med / S_T_real
abs_err_mean = abs(mean_pred - S_T_real)
mape_mean    = abs_err_mean / S_T_real
coverage90   = (p05 <= S_T_real <= p95)
perc_rank    = float((terminal <= S_T_real).mean())  # e.g. 0.73 → 73rd percentile

# CRPS (empirical)
CRPS = np.mean(np.abs(terminal - S_T_real)) - 0.5 * np.mean(np.abs(terminal[:, None] - terminal[None, :]))

# Log-score under GBM lognormal (closed-form density)
from math import log as _log, sqrt as _sqrt, pi as _pi, exp as _exp
mu_log  = np.log(S0) + (mu_annual - 0.5 * sigma_annual**2) * (steps * dt)
var_log = (sigma_annual**2) * (steps * dt)
pdf = (1.0 / (S_T_real * _sqrt(2*_pi*var_log))) * _exp(-(_log(S_T_real) - mu_log)**2 / (2*var_log))
log_score = -np.log(max(pdf, 1e-300))   # smaller = better

# ---------- Summary ----------
st.markdown("### Summary")

r1c1, r1c2, r1c3 = st.columns(3)
r1c1.metric("S₀ (as of train end)", f"{S0:,.2f} USD", help=str(S0_date.date()))
r1c2.metric("S_T (real)", f"{S_T_real:,.2f} USD", help=str(T_end_date.date()))
r1c3.metric("Trading steps", f"{steps}")

r2c1, r2c2, r2c3 = st.columns(3)
r2c1.metric("μ (annualized)", f"{mu_annual:.4f}")
r2c2.metric("σ (annualized)", f"{sigma_annual:.4f}")
r2c3.metric("Real price percentile in MC", f"{perc_rank*100:.1f}th")

r3c1, r3c2, r3c3 = st.columns(3)
r3c1.metric("P5 (downside)",  f"{p05:,.2f} USD")
r3c2.metric("Median (P50)",   f"{p50:,.2f} USD")
r3c3.metric("P95 (upside)",   f"{p95:,.2f} USD")

r4c1, r4c2, r4c3 = st.columns(3)
r4c1.metric("Mean (expected)", f"{mean_pred:,.2f} USD")
r4c2.metric("MAE vs median",   f"{abs_err_med:,.2f}", delta=f"{mape_med*100:+.2f}%")
r4c3.metric("90% PI coverage", "Yes" if coverage90 else "No")

st.caption(
    "GBM path:  S(t+Δt) = S(t) · exp[(μ − 0.5·σ²)·Δt + σ·√Δt·Z]. "
    "Parameters estimated from historical log-returns in the training window (annualized)."
)

# ---------- Chart 1: Percentile fan vs. real price ----------
q_lo, q_med, q_hi = np.percentile(price_paths, [5, 50, 95], axis=1)
fan_dates = future_segment.index  # real trading dates for x-axis

fig_fan = go.Figure()
fig_fan.add_trace(go.Scatter(
    x=fan_dates, y=q_hi, line=dict(width=0), showlegend=False, hoverinfo="skip"
))
fig_fan.add_trace(go.Scatter(
    x=fan_dates, y=q_lo, fill="tonexty", name="5–95% MC interval", opacity=0.3,
    hovertemplate="Date: %{x}<br>5–95%% band: [%{y:.2f}, %{customdata:.2f}]<extra></extra>",
    customdata=q_hi
))
fig_fan.add_trace(go.Scatter(
    x=fan_dates, y=q_med, name="MC median", mode="lines",
    hovertemplate="Date: %{x}<br>MC median: %{y:.2f}<extra></extra>"
))
fig_fan.add_trace(go.Scatter(
    x=fan_dates, y=future_segment.values, name="Real price", mode="lines",
    hovertemplate="Date: %{x}<br>Real: %{y:.2f}<extra></extra>"
))
fig_fan.update_layout(
    title=f"{ticker.upper()}: GBM forecast from {S0_date.date()} to {T_end_date.date()}",
    xaxis_title="Date",
    yaxis_title="Price [USD]",
    legend_title="Series",
    margin=dict(t=50, r=20, b=40, l=50),
    height=420
)
st.plotly_chart(fig_fan, use_container_width=True)

# ---------- Chart 2: Terminal distribution ----------
fig_hist = px.histogram(
    terminal, nbins=80, opacity=0.85,
    labels={"value": "Terminal price", "count": "Simulations"},
    title="Terminal Price Distribution (Monte Carlo)"
)
for v, name in [(p05, "P5"), (p50, "P50"), (p95, "P95"), (S_T_real, "Real")]:
    fig_hist.add_vline(x=v, line_dash="dash", annotation_text=name, annotation_position="top")

fig_hist.update_layout(
    xaxis_title="Price at evaluation date",
    yaxis_title="Count",
    margin=dict(t=50, r=20, b=40, l=50),
    height=420,
    showlegend=False
)
st.plotly_chart(fig_hist, use_container_width=True)

# ---------- Extra diagnostics ----------
st.markdown("#### Diagnostics")
st.write(
    f"- **CRPS**: `{CRPS:.4f}`  ·  **Log-score**: `{log_score:.3f}`  "
    f"·  **MAPE (median)**: `{mape_med:.2%}`  ·  **MAPE (mean)**: `{mape_mean:.2%}`"
)
st.caption("Lower log-score and CRPS indicate better probabilistic calibration.")

st.markdown("<hr>", unsafe_allow_html=True)

st.caption(
    "Note: This is a simple GBM model based on historical volatility and drift (or CAPM drift if enabled). "
    "It ignores jumps, stochastic volatility, dividends, splits alignment, and other market microstructure effects. "
    "Use for educational purposes; this is not investment advice."
)

