import itertools
import time
from math import sqrt

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from portfolio_backtester_data import (
    BacktestPreparedData,
    load_available_dates,
    load_backtest_history,
    load_backtester_universe,
    prepare_backtest_market,
)
from stock_forecaster_data import performance_block


EMPTY_TRADES_COLUMNS = ["Date", "Action", "Ticker", "Shares", "Price", "Gross", "Fee", "Net"]
EMPTY_PORTFOLIO_COLUMNS = [
    "Ticker",
    "Shares",
    "Avg cost",
    "Last price",
    "Market value",
    "Unrealised P/L",
]


def fmt_secs(sec: float) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def empty_backtest_result():
    equity = pd.DataFrame(columns=["Cash", "Positions", "Equity"])
    equity.index.name = "Date"
    trades_df = pd.DataFrame(columns=EMPTY_TRADES_COLUMNS)
    portfolio = pd.DataFrame(columns=EMPTY_PORTFOLIO_COLUMNS)
    stats = dict(
        Invested=0.0,
        NetProfit=0.0,
        NetProfitWithUnreal=0.0,
        TotRet=0.0,
        TotRetWithUnreal=0.0,
        Ann=0.0,
        AnnWithUnreal=0.0,
        Sharpe=0.0,
        MaxDD=0.0,
        TradesRaw=0,
        Tickers=0,
        SharesTotal=0.0,
        MaxExposure=0.0,
        CurExposure=0.0,
        CashNow=0.0,
        Unrealised=0.0,
    )
    return equity, trades_df, portfolio, stats


available_dates = load_available_dates()
if not available_dates:
    st.error("No backtester dates available in the database.")
    st.stop()

data_version = available_dates[-1].isoformat()
universe = load_backtester_universe(data_version)

st.sidebar.markdown("### Back-test parameters")

d_start = st.sidebar.date_input(
    "Start date",
    value=available_dates[0],
    min_value=available_dates[0],
    max_value=available_dates[-1],
)
d_end = st.sidebar.date_input(
    "End date",
    value=available_dates[-1],
    min_value=available_dates[0],
    max_value=available_dates[-1],
)
if d_start > d_end:
    st.sidebar.error("Start date must precede end date")
    st.stop()

daily_budget = st.sidebar.number_input("Daily budget (USD)", 10.0, 100_000.0, 100.0, 100.0)
top_n = st.sidebar.slider("Top-N per day", 1, 20, 3)

sector_opts = ["All Sectors"] + universe["sectors"]
sector_choice = st.sidebar.selectbox("Sector filter", sector_opts, 0)

commission_pct = st.sidebar.number_input("Commission (%)", 0.0, 5.0, 0.0, 0.05) / 100

all_tickers = universe["tickers"]
exclude_tickers = st.sidebar.multiselect("Exclude tickers", options=all_tickers, default=[])

st.sidebar.markdown("---")
st.sidebar.markdown("#### Exit rule")
exit_mult = st.sidebar.slider("Close ≥ Low Forecast ×", 0.5, 2.99, 1.0, 0.01)

st.sidebar.markdown("#### Selection filters")
min_ss = st.sidebar.slider("Smart Score ≥", 0.0, 10.0, 7.0, 0.5)
min_sc = st.sidebar.slider("Score ≥", 0.0, 10.0, 2.0, 0.5)
max_sc = st.sidebar.slider("Score ≤", 2.0, 10.0, 6.0, 0.5)
min_lfp = st.sidebar.slider("Low Forecast % ≥", -0.0, 50.0, 0.0, 0.5)
min_an = st.sidebar.slider("Number of analysts ≥", 0, 100, 0, 1)

st.sidebar.markdown("---")
opt_on = st.sidebar.checkbox("Run optimisation")
if opt_on:
    st.sidebar.markdown("##### Search ranges")
    rng_exit = st.sidebar.slider("Exit multiplier", 0.8, 1.8, (0.9, 1.1), 0.05)
    rng_ss = st.sidebar.slider("Smart Score", 0.0, 10.0, (6.0, 9.0), 0.5)
    rng_sc = st.sidebar.slider("Score min / max", 0.0, 10.0, (1.0, 7.0), 0.5)
    rng_lfp = st.sidebar.slider("Low F% min", -5.0, 30.0, (-2.0, 10.0), 1.0)
    rng_an = st.sidebar.slider("Min analysts", 0, 50, (0, 20), 5)
    search_btn = st.sidebar.button("Start search")
else:
    search_btn = False

run_btn = st.sidebar.button("Run single back-test ▶")


def run_backtest(
    prepared_market: BacktestPreparedData,
    params: dict[str, float],
    daily_budget_value: float,
    top_n_value: int,
    commission_pct_value: float,
):
    if prepared_market.is_empty:
        return empty_backtest_result()

    cash = 0.0
    positions: dict[str, dict[str, float]] = {}
    trades: list[list[object]] = []
    curve: list[list[object]] = []

    for day in prepared_market.days:
        quotes = prepared_market.day_quotes.get(day, {})

        for ticker, position in list(positions.items()):
            quote = quotes.get(ticker)
            if quote is None:
                continue

            closing_price, low_forecast = quote
            if closing_price >= low_forecast * params["exit_mult"]:
                proceeds = position["shr"] * closing_price
                fee = proceeds * commission_pct_value
                cash += proceeds - fee
                trades.append(
                    [
                        day,
                        "SELL",
                        ticker,
                        position["shr"],
                        closing_price,
                        proceeds,
                        fee,
                        proceeds - fee,
                    ]
                )
                positions.pop(ticker, None)

        cash += daily_budget_value
        alloc = daily_budget_value / top_n_value

        pick = prepared_market.day_candidates.get(day)
        if pick is not None and not pick.empty:
            sel = (
                (pick["Smart Score"] >= params["min_ss"])
                & (pick["Score"] >= params["min_sc"])
                & (pick["Score"] <= params["max_sc"])
                & (pick["Low Forecast Percent"] >= params["min_lfp"])
                & (pick["Number of analysts"] >= params["min_an"])
            )
            buy_rows = pick.loc[sel].head(top_n_value)

            for row in buy_rows.to_dict("records"):
                if row["Closing Price"] <= 0:
                    continue
                shares = alloc / row["Closing Price"]
                fee = alloc * commission_pct_value
                cash -= alloc + fee
                position = positions.setdefault(row["Stock"], {"shr": 0.0, "cost": 0.0})
                position["shr"] += shares
                position["cost"] += shares * row["Closing Price"]
                trades.append(
                    [
                        day,
                        "BUY",
                        row["Stock"],
                        shares,
                        row["Closing Price"],
                        alloc,
                        fee,
                        -(alloc + fee),
                    ]
                )

        mkt_val = 0.0
        for ticker, position in positions.items():
            quote = quotes.get(ticker)
            if quote is not None:
                closing_price = quote[0]
            else:
                closing_price = position["cost"] / position["shr"] if position["shr"] else 0.0
            mkt_val += closing_price * position["shr"]

        curve.append([day, cash, mkt_val, cash + mkt_val])

    equity = pd.DataFrame(curve, columns=["Date", "Cash", "Positions", "Equity"]).set_index("Date")
    trades_df = pd.DataFrame(trades, columns=EMPTY_TRADES_COLUMNS)

    rows = []
    for ticker, position in positions.items():
        avg_cost = position["cost"] / position["shr"] if position["shr"] else 0.0
        last_price = prepared_market.last_day_quotes.get(ticker, avg_cost)
        market_value = position["shr"] * last_price
        unrealised = position["shr"] * (last_price - avg_cost)
        rows.append([ticker, position["shr"], avg_cost, last_price, market_value, unrealised])

    portfolio = pd.DataFrame(rows, columns=EMPTY_PORTFOLIO_COLUMNS)

    invested = daily_budget_value * len(equity)
    unrealised_sum = portfolio["Unrealised P/L"].sum() if not portfolio.empty else 0.0
    net_profit_incl = equity["Equity"].iloc[-1] - invested if not equity.empty else 0.0
    net_profit_real = net_profit_incl - unrealised_sum

    if invested > 0 and not equity.empty:
        tot_ret_real = net_profit_real / invested
        tot_ret_incl = net_profit_incl / invested
        ann_real = (1 + tot_ret_real) ** (252 / len(equity)) - 1
        ann_incl = (1 + tot_ret_incl) ** (252 / len(equity)) - 1
    else:
        tot_ret_real = 0.0
        tot_ret_incl = 0.0
        ann_real = 0.0
        ann_incl = 0.0

    if equity.empty:
        sharpe = 0.0
        mdd = 0.0
    else:
        rets = equity["Equity"].pct_change().fillna(0.0)
        sharpe = (rets.mean() / rets.std()) * sqrt(252) if rets.std() else 0.0
        drawdown_base = equity["Equity"].cummax().replace(0, np.nan)
        mdd = (1 - equity["Equity"] / drawdown_base).fillna(0.0).max()

    stats = dict(
        Invested=invested,
        NetProfit=net_profit_real,
        NetProfitWithUnreal=net_profit_incl,
        TotRet=tot_ret_real,
        TotRetWithUnreal=tot_ret_incl,
        Ann=ann_real,
        AnnWithUnreal=ann_incl,
        Sharpe=sharpe,
        MaxDD=mdd,
        TradesRaw=len(trades_df.groupby(["Date", "Action", "Ticker"])) if not trades_df.empty else 0,
        Tickers=len(portfolio),
        SharesTotal=portfolio["Shares"].sum() if not portfolio.empty else 0.0,
        MaxExposure=equity["Positions"].max() if not equity.empty else 0.0,
        CurExposure=equity["Positions"].iloc[-1] if not equity.empty else 0.0,
        CashNow=equity["Cash"].iloc[-1] if not equity.empty else 0.0,
        Unrealised=unrealised_sum,
    )
    return equity, trades_df, portfolio, stats


def show_dashboard(eq: pd.DataFrame, trades_df: pd.DataFrame, port: pd.DataFrame, stats: dict[str, float]):
    st.markdown("## Back-test results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invested", f"${stats['Invested']:,.0f}")
    c2.metric("Net profit (real.)", f"${stats['NetProfit']:,.0f}")
    c3.metric("Total return", f"{stats['TotRet'] * 100:,.2f}%")
    c4.metric("Annual return", f"{stats['Ann'] * 100:,.2f}%")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Sharpe", f"{stats['Sharpe']:.2f}")
    d2.metric("Max DD", f"{stats['MaxDD'] * 100:,.2f}%")
    d3.metric("Max in stocks", f"${stats['MaxExposure']:,.0f}")
    d4.metric("Now in stocks", f"${stats['CurExposure']:,.0f}")

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Cash now", f"${stats['CashNow']:,.0f}")
    e2.metric("Tickers held", stats["Tickers"])
    e3.metric("Shares", f"{stats['SharesTotal']:,.2f}")
    e4.metric("Trades", stats["TradesRaw"])

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Unrealised P/L", f"${stats['Unrealised']:,.0f}")
    f2.metric("Total return w/ unreal.", f"{stats['TotRetWithUnreal'] * 100:,.2f}%")
    f3.metric("Annual return w/ unreal.", f"{stats['AnnWithUnreal'] * 100:,.2f}%")
    f4.empty()

    expo = (
        eq.reset_index()
        .melt(id_vars="Date", value_vars=["Cash", "Positions"], var_name="Component", value_name="USD")
    )
    fig = px.area(expo, x="Date", y="USD", color="Component", title="Cash vs. Positions value")
    fig.update_traces(stackgroup="one")
    fig.add_scatter(
        x=eq.index,
        y=daily_budget * np.arange(1, len(eq) + 1),
        mode="lines",
        name="Invested capital",
        line=dict(dash="dash"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Current portfolio (grouped)")
    st.dataframe(port.round(2), use_container_width=True)

    trades_agg = (
        trades_df.groupby(["Date", "Action", "Ticker"], as_index=False)
        .agg({"Shares": "sum", "Gross": "sum", "Fee": "sum", "Net": "sum"})
    )
    trades_agg["Price"] = trades_agg["Gross"] / trades_agg["Shares"]
    trades_agg["Profit"] = trades_agg["Net"]

    st.subheader("Trade log (grouped)")
    st.dataframe(
        trades_agg[["Date", "Action", "Ticker", "Shares", "Price", "Gross", "Fee", "Profit"]].round(4),
        use_container_width=True,
    )


should_run = run_btn or search_btn
prepared_market = None

if should_run:
    history_df = load_backtest_history(d_start, d_end, data_version)
    if history_df.empty:
        st.warning("No historical market data found for the selected date range.")
    else:
        prepared_market = prepare_backtest_market(history_df, sector_choice, exclude_tickers)
        if prepared_market.is_empty:
            st.warning("No historical market data left after applying the current sector and ticker exclusions.")


if search_btn:
    if prepared_market is None or prepared_market.is_empty:
        st.info("Adjust the date range, sector filter, or excluded tickers and try again.")
    else:
        st.header("Optimisation progress")
        rngs = {
            "exit_mult": np.arange(rng_exit[0], rng_exit[1] + 1e-9, 0.05),
            "min_ss": np.arange(rng_ss[0], rng_ss[1] + 1e-9, 0.5),
            "min_sc": [rng_sc[0]],
            "max_sc": [rng_sc[1]],
            "min_lfp": np.arange(rng_lfp[0], rng_lfp[1] + 1e-9, 1.0),
            "min_an": np.arange(rng_an[0], rng_an[1] + 1, 5, dtype=int),
        }
        grid = list(itertools.product(*rngs.values()))
        n_runs = len(grid)

        prog_bar = st.progress(0.0, text="Starting…")
        time_box = st.empty()
        best_ret, best_p = -1e9, None
        results = []
        start_ts = time.perf_counter()

        with performance_block("run_backtest_grid"):
            for i, vals in enumerate(grid, 1):
                params = dict(zip(rngs.keys(), vals))
                eq, tr, port, stats = run_backtest(
                    prepared_market,
                    params,
                    daily_budget,
                    top_n,
                    commission_pct,
                )
                ret = stats["TotRet"]
                results.append({**params, "Return": ret})
                if ret > best_ret:
                    best_ret, best_p = ret, params

                elapsed = time.perf_counter() - start_ts
                eta = elapsed / i * n_runs - elapsed
                time_box.markdown(
                    f"⏱ **Elapsed:** {fmt_secs(elapsed)} &nbsp;|&nbsp; **ETA:** {fmt_secs(eta)}"
                )
                prog_bar.progress(i / n_runs, text=f"{i}/{n_runs} configs")

        prog_bar.empty()
        time_box.markdown(f"✅ **Finished in {fmt_secs(time.perf_counter() - start_ts)}**")

        st.success(f"Best return {best_ret * 100:.2f}%")
        st.code(best_p)
        st.dataframe(pd.DataFrame(results).sort_values("Return", ascending=False), use_container_width=True)

        st.divider()
        st.subheader("Back-test with best parameters")
        eq, tr, port, stats = run_backtest(
            prepared_market,
            best_p,
            daily_budget,
            top_n,
            commission_pct,
        )
        show_dashboard(eq, tr, port, stats)


if run_btn:
    if prepared_market is None or prepared_market.is_empty:
        st.info("Adjust the date range, sector filter, or excluded tickers and try again.")
    else:
        params = dict(
            exit_mult=exit_mult,
            min_ss=min_ss,
            min_sc=min_sc,
            max_sc=max_sc,
            min_lfp=min_lfp,
            min_an=min_an,
        )
        with performance_block("run_backtest_single"):
            eq, tr, port, stats = run_backtest(
                prepared_market,
                params,
                daily_budget,
                top_n,
                commission_pct,
            )
        show_dashboard(eq, tr, port, stats)
elif not search_btn:
    st.info("Set parameters and click a button to run.")
