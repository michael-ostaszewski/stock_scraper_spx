# Poprzedni kod backtestera, bez uwzględnienia rozdziału na realized i unrealized profit.
#
# # ────────────────────────────────────────────────────────────────────────────────
# # Back‑test – dynamic filters + optimisation grid search
# # ────────────────────────────────────────────────────────────────────────────────
# import re, itertools, numpy as np
# import streamlit as st
# import pandas as pd
# import plotly.express as px
# from math import sqrt
#
# # ╭──────────────────────────────────────────╮
# # │ 0. DATA LOADING & CLEANING               │
# # ╰──────────────────────────────────────────╯
# @st.cache_data
# def load_and_clean() -> pd.DataFrame:
#     url = ("https://raw.githubusercontent.com/"
#            "michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv")
#     df = pd.read_csv(url, delimiter=";")
#     df["Date of record"] = pd.to_datetime(df["Date of record"], errors="coerce")
#
#     def fix_num(x):
#         if pd.isna(x): return None
#         x = re.sub(r"[^\d.]", "", str(x).replace(",", ""))
#         if x.count(".") > 1:
#             parts = x.split("."); x = "".join(parts[:-1]) + "." + parts[-1]
#         return x
#
#     num_cols = ["Closing Price","Low Forecast","Smart Score","Score",
#                 "Low Forecast Percent","Number of analysts"]
#     for col in num_cols:
#         df[col] = df[col].apply(fix_num).pipe(pd.to_numeric, errors="coerce")
#
#     return df.dropna(subset=["Closing Price","Low Forecast","Score",
#                              "Smart Score","Low Forecast Percent"])
#
# df = load_and_clean()
#
# # ╭──────────────────────────────────────────╮
# # │ 1. SIDEBAR – COMMON BACK‑TEST PARAMS     │
# # ╰──────────────────────────────────────────╯
# st.sidebar.markdown("### Back‑test parameters")
#
# dates = sorted(df["Date of record"].unique())
# d_start = st.sidebar.date_input("Start date", value=dates[0])
# d_end   = st.sidebar.date_input("End date",   value=dates[-1])
# if d_start > d_end: st.sidebar.error("Start date must precede end date"); st.stop()
#
# daily_budget = st.sidebar.number_input("Daily budget (USD)", 10.0, 100_000.0, 100.0, 100.0)
# top_n = st.sidebar.slider("Top‑N per day", 1, 20, 3)
#
# sector_opts = ["All Sectors"] + sorted(df["Sector"].dropna().unique())
# sector_choice = st.sidebar.selectbox("Sector filter", sector_opts, 0)
#
# commission_pct = st.sidebar.number_input("Commission (%)", 0.0, 5.0, 0.0, 0.05)/100
#
# st.sidebar.markdown("---")
# st.sidebar.markdown("#### Exit rule")
# exit_mult = st.sidebar.slider("Close ≥ Low Forecast ×", 0.5, 1.5, 1.0, 0.01)
#
# st.sidebar.markdown("#### Selection filters")
# min_ss  = st.sidebar.slider("Smart Score ≥",        0.0, 10.0, 7.0, 0.5)
# min_sc  = st.sidebar.slider("Score ≥",             0.0, 10.0, 2.0, 0.5)
# max_sc  = st.sidebar.slider("Score ≤",             2.0, 10.0, 6.0, 0.5)
# min_lfp = st.sidebar.slider("Low Forecast % ≥",    -0.0, 50.0, 0.0, 0.5)
# min_an  = st.sidebar.slider("Number of analysts ≥",   0, 100, 0, 1)
#
# # ╭──────────────────────────────────────────╮
# # │ 1A.  OPTIMISER SECTION                   │
# # ╰──────────────────────────────────────────╯
# st.sidebar.markdown("---")
# opt_section = st.sidebar.checkbox("Run optimisation")
#
# if opt_section:
#     st.sidebar.markdown("##### Search ranges (min / max / step)")
#     rng_exit = st.sidebar.slider("Exit multiplier", 0.8, 1.2, (0.9, 1.1), 0.05)
#     rng_ss   = st.sidebar.slider("Smart Score", 0.0,10.0,(6.0,9.0),0.5)
#     rng_sc   = st.sidebar.slider("Score min/max", 0.0,10.0,(1.0,7.0),0.5)
#     rng_lfp  = st.sidebar.slider("Low F% min", -5.0,30.0, (-2.0,10.0),1.0)
#     rng_an   = st.sidebar.slider("Min analysts", 0,50,(0,20),5)
#     search_btn = st.sidebar.button("Start search")
# else:
#     search_btn = False
#
# run_btn = st.sidebar.button("Run single back‑test ▶")
#
# # ╭──────────────────────────────────────────╮
# # │ 2. PARAMETERISED BACK‑TEST ENGINE        │
# # ╰──────────────────────────────────────────╯
# def run_backtest(params):
#     """params: dict with keys exit_mult, min_ss, min_sc, max_sc, min_lfp, min_an"""
#     mask = df["Date of record"].between(pd.Timestamp(d_start), pd.Timestamp(d_end))
#     data = df[mask]
#     cash, pos, trade, curve = 0.0, [], [], []
#     for day in sorted(data["Date of record"].unique()):
#         day_rows = data[data["Date of record"]==day]
#
#         # EXIT
#         for p in pos[:]:
#             rw = day_rows[day_rows["Stock"]==p["tick"]]
#             if not rw.empty and rw.iloc[0]["Closing Price"] >= rw.iloc[0]["Low Forecast"]*params["exit_mult"]:
#                 proceeds=p["shr"]*rw.iloc[0]["Closing Price"]; fee=proceeds*commission_pct
#                 cash+=proceeds-fee; trade.append([day,"SELL",p["tick"],p["shr"],proceeds-fee]); pos.remove(p)
#
#         # BUY
#         cash+=daily_budget; per_alloc=daily_budget/top_n
#         pick=day_rows.sort_values("Score",ascending=False)
#         pick=pick[
#             (pick["Smart Score"]>=params["min_ss"])&
#             (pick["Score"]>=params["min_sc"])&
#             (pick["Score"]<=params["max_sc"])&
#             (pick["Low Forecast Percent"]>=params["min_lfp"])&
#             (pick["Number of analysts"]>=params["min_an"])
#         ]
#         if sector_choice!="All Sectors": pick=pick[pick["Sector"]==sector_choice]
#         for _,r in pick.head(top_n).iterrows():
#             shares=per_alloc/r["Closing Price"]; fee=per_alloc*commission_pct; cash-=per_alloc+fee
#             pos.append({"tick":r["Stock"],"shr":shares,"cost":r["Closing Price"]})
#             trade.append([day,"BUY",r["Stock"],shares,-(per_alloc+fee)])
#
#         # MTM
#         mkt=sum((day_rows[day_rows["Stock"]==p["tick"]]["Closing Price"].iloc[0]
#                 if not day_rows[day_rows["Stock"]==p["tick"]].empty else p["cost"])*p["shr"] for p in pos)
#         curve.append(cash+mkt)
#
#     invested=daily_budget*len(curve)
#     ret=(curve[-1]-invested)/invested
#     return ret, curve[-1]  # return and final equity
#
# # ╭──────────────────────────────────────────╮
# # │ 3. GRID SEARCH                           │
# # ╰──────────────────────────────────────────╯
# if search_btn:
#     st.header("Optimisation progress")
#     ranges = {
#         "exit_mult": np.arange(rng_exit[0], rng_exit[1]+1e-9, 0.05),
#         "min_ss":    np.arange(rng_ss[0],   rng_ss[1]+1e-9,   0.5),
#         "min_sc":    [rng_sc[0]],
#         "max_sc":    [rng_sc[1]],
#         "min_lfp":   np.arange(rng_lfp[0],  rng_lfp[1]+1e-9,  1.0),
#         "min_an":    np.arange(rng_an[0],   rng_an[1]+1,      5, dtype=int)
#     }
#     grid = list(itertools.product(*ranges.values()))
#     prog = st.progress(0.0, text="Searching...")
#     best_ret=-1e9; best_params=None; results=[]
#     for i,vals in enumerate(grid,1):
#         p=dict(zip(ranges.keys(), vals))
#         ret,_=run_backtest(p)
#         results.append({**p,"Return":ret})
#         if ret>best_ret: best_ret=ret; best_params=p
#         prog.progress(i/len(grid), text=f"{i}/{len(grid)} combinations")
#
#     prog.empty()
#     st.success(f"Best total return: {best_ret*100:.2f}% with parameters:")
#     st.code(best_params)
#
#     res_df=pd.DataFrame(results).sort_values("Return",ascending=False).head(10)
#     st.dataframe(res_df,use_container_width=True)
#
#     st.divider()
#     st.subheader("Running back‑test with best parameters…")
#     exit_mult = best_params["exit_mult"]
#     min_ss, min_sc, max_sc = best_params["min_ss"], best_params["min_sc"], best_params["max_sc"]
#     min_lfp, min_an = best_params["min_lfp"], best_params["min_an"]
#     run_btn=True  # fall through to single BT display
#
# # ╭──────────────────────────────────────────╮
# # │ 4. SINGLE BACK‑TEST DISPLAY              │
# # ╰──────────────────────────────────────────╯
# if run_btn:
#     params=dict(exit_mult=exit_mult,min_ss=min_ss,min_sc=min_sc,
#                 max_sc=max_sc,min_lfp=min_lfp,min_an=min_an)
#     ret,_ = run_backtest(params)
#     st.info(f"Single run total return: **{ret*100:.2f}%** (annualised ~{(1+ret)**(252/((pd.Timestamp(d_end)-pd.Timestamp(d_start)).days+1))-1:.2%})")
# else:
#     st.info("Set parameters and click Run.")





#

# ────────────────────────────────────────────────────────────────────────────────
# Back-test – grid search + pełny panel wyników
# ────────────────────────────────────────────────────────────────────────────────
import re, itertools, numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
from math import sqrt
import time

# ╭──────────────────────────────────────────╮
# │ 0. DATA LOADING & CLEANING               │
# ╰──────────────────────────────────────────╯
@st.cache_data
def load_and_clean() -> pd.DataFrame:
    url = ("https://raw.githubusercontent.com/"
           "michael-ostaszewski/stock_scraper_spx/main/stocks/stocks_data.csv")
    df = pd.read_csv(url, delimiter=";")
    df["Date of record"] = pd.to_datetime(df["Date of record"], errors="coerce")

    def fix_num(x):
        if pd.isna(x):
            return None
        x = re.sub(r"[^\d.]", "", str(x).replace(",", ""))
        if x.count(".") > 1:
            p = x.split(".")
            x = "".join(p[:-1]) + "." + p[-1]
        return x

    num_cols = [
        "Closing Price",
        "Low Forecast",
        "Smart Score",
        "Score",
        "Low Forecast Percent",
        "Number of analysts",
    ]
    for col in num_cols:
        df[col] = df[col].apply(fix_num).pipe(pd.to_numeric, errors="coerce")

    return df.dropna(
        subset=[
            "Closing Price",
            "Low Forecast",
            "Score",
            "Smart Score",
            "Low Forecast Percent",
        ]
    )


df = load_and_clean()

def fmt_secs(sec: float) -> str:
    """Zamienia liczbę sekund na HH:MM:SS albo MM:SS."""
    h, rem = divmod(int(sec), 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ╭──────────────────────────────────────────╮
# │ 1. SIDEBAR – wspólne parametry           │
# ╰──────────────────────────────────────────╯
st.sidebar.markdown("### Backtest parameters")
dates = sorted(df["Date of record"].unique())
d_start = st.sidebar.date_input("Start date", value=dates[0])
d_end = st.sidebar.date_input("End date", value=dates[-1])
if d_start > d_end:
    st.sidebar.error("Start date must precede end date")
    st.stop()

daily_budget = st.sidebar.number_input("Daily budget (USD)", 10.0, 100_000.0, 100.0, 100.0)
top_n = st.sidebar.slider("Top-N per day", 1, 20, 3)
sector_opts = ["All Sectors"] + sorted(df["Sector"].dropna().unique())
sector_choice = st.sidebar.selectbox("Sector filter", sector_opts, 0)
commission_pct = st.sidebar.number_input("Commission (%)", 0.0, 5.0, 0.0, 0.05) / 100

st.sidebar.markdown("---")
st.sidebar.markdown("#### Exit rule")
exit_mult = st.sidebar.slider("Close ≥ Low Forecast ×", 0.5, 1.8, 1.0, 0.01)

st.sidebar.markdown("#### Selection filters")
min_ss = st.sidebar.slider("Smart Score ≥", 0.0, 10.0, 7.0, 0.5)
min_sc = st.sidebar.slider("Score ≥", 0.0, 10.0, 2.0, 0.5)
max_sc = st.sidebar.slider("Score ≤", 2.0, 10.0, 6.0, 0.5)
min_lfp = st.sidebar.slider("Low Forecast % ≥", -0.0, 50.0, 0.0, 0.5)
min_an = st.sidebar.slider("Number of analysts ≥", 0, 100, 0, 1)

# ----- optimiser controls -----
st.sidebar.markdown("---")
opt_on = st.sidebar.checkbox("Run optimisation")
if opt_on:
    st.sidebar.markdown("##### Search ranges")
    rng_exit = st.sidebar.slider("Exit multiplier", 0.8, 1.8, (0.9, 1.1), 0.05)
    rng_ss = st.sidebar.slider("Smart Score", 0.0, 10.0, (6.0, 9.0), 0.5)
    rng_sc = st.sidebar.slider("Score min/max", 0.0, 10.0, (1.0, 7.0), 0.5)
    rng_lfp = st.sidebar.slider("Low F% min", -5.0, 30.0, (-2.0, 10.0), 1.0)
    rng_an = st.sidebar.slider("Min analysts", 0, 50, (0, 20), 5)
    search_btn = st.sidebar.button("Start search")
else:
    search_btn = False

run_btn = st.sidebar.button("Run single backtest ▶")

# ╭──────────────────────────────────────────╮
# │ 2. PARAMETRYZOWANY BACK-TEST             │
# ╰──────────────────────────────────────────╯
def run_backtest(p):
    """Zwraca equity_df, trades_df, portfolio_df, stats"""
    mask = df["Date of record"].between(pd.Timestamp(d_start), pd.Timestamp(d_end))
    data = df[mask]

    cash, positions, trades, curve = 0.0, [], [], []

    for day in sorted(data["Date of record"].unique()):
        day_rows = data[data["Date of record"] == day]

        # EXIT
        for pos in positions[:]:
            row = day_rows[day_rows["Stock"] == pos["tick"]]
            if not row.empty and row.iloc[0]["Closing Price"] >= row.iloc[0]["Low Forecast"] * p["exit_mult"]:
                proceeds = pos["shr"] * row.iloc[0]["Closing Price"]
                fee = proceeds * commission_pct
                cash += proceeds - fee
                trades.append(
                    [day, "SELL", pos["tick"], pos["shr"], row.iloc[0]["Closing Price"], proceeds, fee, proceeds - fee]
                )
                positions.remove(pos)

        # BUY
        cash += daily_budget
        alloc = daily_budget / top_n

        pick = day_rows.sort_values("Score", ascending=False)
        pick = pick[
            (pick["Smart Score"] >= p["min_ss"])
            & (pick["Score"] >= p["min_sc"])
            & (pick["Score"] <= p["max_sc"])
            & (pick["Low Forecast Percent"] >= p["min_lfp"])
            & (pick["Number of analysts"] >= p["min_an"])
        ]
        if sector_choice != "All Sectors":
            pick = pick[pick["Sector"] == sector_choice]

        for _, r in pick.head(top_n).iterrows():
            shares = alloc / r["Closing Price"]
            fee = alloc * commission_pct
            cash -= alloc + fee
            positions.append({"tick": r["Stock"], "shr": shares, "cost": r["Closing Price"]})
            trades.append([day, "BUY", r["Stock"], shares, r["Closing Price"], alloc, fee, -(alloc + fee)])

        # MTM
        mkt = sum(
            (
                day_rows[day_rows["Stock"] == p0["tick"]]["Closing Price"].iloc[0]
                if not day_rows[day_rows["Stock"] == p0["tick"]].empty
                else p0["cost"]
            )
            * p0["shr"]
            for p0 in positions
        )
        curve.append([day, cash, mkt, cash + mkt])

    equity = pd.DataFrame(curve, columns=["Date", "Cash", "Positions", "Equity"]).set_index("Date")
    trades_df = pd.DataFrame(
        trades, columns=["Date", "Action", "Ticker", "Shares", "Price", "Gross", "Fee", "Net"]
    )

    # portfolio snapshot
    port_map = {}
    for pos in positions:
        d = port_map.setdefault(pos["tick"], {"shr": 0.0, "cost": 0.0})
        d["shr"] += pos["shr"]
        d["cost"] += pos["shr"] * pos["cost"]
    rows = []
    if port_map:
        last_px = data[data["Date of record"] == equity.index[-1]].set_index("Stock")["Closing Price"]
        for t, v in port_map.items():
            avg = v["cost"] / v["shr"]
            px = last_px.get(t, avg)
            mv = v["shr"] * px
            un = v["shr"] * (px - avg)
            rows.append([t, v["shr"], avg, px, mv, un])
    portfolio = pd.DataFrame(
        rows, columns=["Ticker", "Shares", "Avg cost", "Last price", "Market value", "Unrealised P/L"]
    )

    invested = daily_budget * len(equity)
    # ------------------------------------------------------------------
    # NET PROFIT & RETURNS – realised vs. realised+unrealised
    # ------------------------------------------------------------------
    net_profit_incl_unreal = equity["Equity"].iloc[-1] - invested
    unrealised_sum = portfolio["Unrealised P/L"].sum() if not portfolio.empty else 0.0
    net_profit_realised = net_profit_incl_unreal - unrealised_sum

    tot_ret_realised = net_profit_realised / invested
    tot_ret_with_unreal = net_profit_incl_unreal / invested

    ann_realised = (1 + tot_ret_realised) ** (252 / len(equity)) - 1
    ann_with_unreal = (1 + tot_ret_with_unreal) ** (252 / len(equity)) - 1

    rets = equity["Equity"].pct_change().fillna(0)
    sharpe = (rets.mean() / rets.std()) * sqrt(252) if rets.std() else 0
    mdd = (1 - equity["Equity"] / equity["Equity"].cummax()).max()

    stats = dict(
        Invested=invested,
        NetProfit=net_profit_realised,  # Tylko zrealizowany zysk/strata
        NetProfitWithUnreal=net_profit_incl_unreal,
        TotRet=tot_ret_realised,
        TotRetWithUnreal=tot_ret_with_unreal,
        Ann=ann_realised,
        AnnWithUnreal=ann_with_unreal,
        Sharpe=sharpe,
        MaxDD=mdd,
        TradesRaw=len(trades_df),
        Tickers=len(portfolio),
        SharesTotal=portfolio["Shares"].sum() if not portfolio.empty else 0,
        MaxExposure=equity["Positions"].max(),
        CurExposure=equity["Positions"].iloc[-1],
        CashNow=equity["Cash"].iloc[-1],
        Unrealised=unrealised_sum,
    )

    # ten fragment agreguje zliczanie transakcji (jeżeli sprzedaję całość pozycji za jednym razem to jedna transakcja)
    TradesAgg = len(trades_df.groupby(["Date", "Action", "Ticker"]))
    stats["TradesRaw"] = TradesAgg

    return equity, trades_df, portfolio, stats


# ╭──────────────────────────────────────────╮
# │ 3. WYŚWIETLANIE DASHBOARDU               │
# ╰──────────────────────────────────────────╯
def show_dashboard(eq, trades_df, port, stats):
    st.markdown("## Backtest results")

    # ------------------------------ KPI rows ------------------------------
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
    e3.metric("Shares", f"{stats['SharesTotal']:.2f}")
    e4.metric("Trades", stats["TradesRaw"])

    # ------------------- NEW: Unrealised & full-return row -------------------
    f1, f2, f3, f4 = st.columns(4)  # ← mamy 4 kolumny

    f1.metric("Unrealised P/L", f"${stats['Unrealised']:,.0f}")
    f2.metric("Total return w/ unreal.", f"{stats['TotRetWithUnreal'] * 100:,.2f}%")
    f3.metric("Annual return w/ unreal.", f"{stats['AnnWithUnreal'] * 100:,.2f}%")

    # pusta kolumna – placeholder na przyszłość
    f4.metric("#Place Holder", "—")  # albo np. f4.empty()

    # ---------------------- Cash vs. positions plot ----------------------
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

    # Portfolio + trades
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


# # ╭──────────────────────────────────────────╮
# # │ 4. GRID SEARCH                           │
# # ╰──────────────────────────────────────────╯
# if search_btn:
#     st.header("Optimisation progress")
#     rngs = {
#         "exit_mult": np.arange(rng_exit[0], rng_exit[1] + 1e-9, 0.05),
#         "min_ss": np.arange(rng_ss[0], rng_ss[1] + 1e-9, 0.5),
#         "min_sc": [rng_sc[0]],
#         "max_sc": [rng_sc[1]],
#         "min_lfp": np.arange(rng_lfp[0], rng_lfp[1] + 1e-9, 1.0),
#         "min_an": np.arange(rng_an[0], rng_an[1] + 1, 5, dtype=int),
#     }
#     grid = list(itertools.product(*rngs.values()))
#     prog = st.progress(0.0, text="Searching…")
#     best_ret = -1e9
#     best_p = None
#     results = []
#
#     for i, vals in enumerate(grid, 1):
#         p = dict(zip(rngs.keys(), vals))
#
#         eq, tr, port, stats = run_backtest(p)
#
#         #  metryka używana do oceny: tu bierzemy zwrot ZREALIZOWANY
#         ret = stats["TotRet"]  # można podmienić np. na stats["Ann"], stats["Sharpe"] …
#
#         results.append({**p, "Return": ret})
#
#         if ret > best_ret:
#             best_ret, best_p = ret, p
#
#         prog.progress(i / len(grid), text=f"{i}/{len(grid)}")
#     prog.empty()
#
#     st.success(f"Best return {best_ret*100:.2f}%")
#     st.code(best_p)
#     st.dataframe(pd.DataFrame(results).sort_values("Return", ascending=False), use_container_width=True)
#
#     st.divider()
#     st.subheader("Backtest with best parameters")
#     eq, tr, port, stats = run_backtest(best_p)
#     show_dashboard(eq, tr, port, stats)

# ╭──────────────────────────────────────────╮
# │ 4. GRID SEARCH                           │
# ╰──────────────────────────────────────────╯
if search_btn:
    st.header("Optimisation progress")

    rngs = {
        "exit_mult": np.arange(rng_exit[0], rng_exit[1] + 1e-9, 0.05),
        "min_ss":    np.arange(rng_ss[0],  rng_ss[1]  + 1e-9, 0.5),
        "min_sc":   [rng_sc[0]],
        "max_sc":   [rng_sc[1]],
        "min_lfp":   np.arange(rng_lfp[0], rng_lfp[1] + 1e-9, 1.0),
        "min_an":    np.arange(rng_an[0],  rng_an[1]  + 1,     5, dtype=int),
    }
    grid = list(itertools.product(*rngs.values()))
    n_runs = len(grid)

    # ▶ widżety postępu
    prog_bar   = st.progress(0.0, text="Starting…")
    time_box   = st.empty()                # dynamiczny napis z czasem
    best_ret   = -1e9
    best_p     = None
    results    = []

    start_ts   = time.perf_counter()       # znacznik „start”

    for i, vals in enumerate(grid, 1):
        p = dict(zip(rngs.keys(), vals))

        eq, tr, port, stats = run_backtest(p)
        ret                 = stats["TotRet"]    # miara jakości

        results.append({**p, "Return": ret})
        if ret > best_ret:
            best_ret, best_p = ret, p

        # -------------- TIMER & ETA --------------
        elapsed   = time.perf_counter() - start_ts
        total_est = elapsed / i * n_runs           # prosta estymacja ~ liniowa
        eta       = max(0.0, total_est - elapsed)

        time_box.markdown(
            f"⏱ **Elapsed:** {fmt_secs(elapsed)} &nbsp;|&nbsp; "
            f"**ETA:** {fmt_secs(eta)}"
        )

        prog_bar.progress(
            i / n_runs,
            text = f"{i}/{n_runs} configs"
        )

    # --------------------------------------------
    prog_bar.empty()
    time_box.markdown(f"✅ **Finished in {fmt_secs(time.perf_counter()-start_ts)}**")

    st.success(f"Best return {best_ret*100:.2f}%")
    st.code(best_p)
    st.dataframe(pd.DataFrame(results).sort_values("Return", ascending=False),
                 use_container_width=True)

    st.divider()
    st.subheader("Backtest with best parameters")
    eq, tr, port, stats = run_backtest(best_p)
    show_dashboard(eq, tr, port, stats)

# ╭──────────────────────────────────────────╮
# │ 5. SINGLE BACK-TEST                      │
# ╰──────────────────────────────────────────╯
if run_btn:
    params = dict(
        exit_mult=exit_mult,
        min_ss=min_ss,
        min_sc=min_sc,
        max_sc=max_sc,
        min_lfp=min_lfp,
        min_an=min_an,
    )
    eq, tr, port, stats = run_backtest(params)
    show_dashboard(eq, tr, port, stats)
elif not search_btn:
    st.info("Set parameters and click a button to run.")


