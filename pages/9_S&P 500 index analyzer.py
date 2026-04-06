import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date

RAW_GITHUB_URL = (
    "/Users/michal/PycharmProjects/Stock Scraper/Index data/Clear_index_data/S&P 500 Historical Data from 1980 - with metrics.csv"
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. GLOBAL CSS – kopiuję Twój styl dla metric-ów + przycisków
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        font-weight: bold;
    }
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
    unsafe_allow_html=True,
)

st.title("📈 S&P 500 – historia, korekty i statystyki")

# ─────────────────────────────────────────────────────────────────────────────
# 2. LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Pobieram dane CSV…")
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df

df = load_data(RAW_GITHUB_URL)

# # ─────────────────────────────────────────────────────────────────────────────
# # 3. PODSTAWOWY LINIOWY WYKRES CENY
# # ─────────────────────────────────────────────────────────────────────────────
# fig_price = go.Figure()
# fig_price.add_scatter(
#     x=df["Date"], y=df["Price"],
#     mode="lines", name="Close / Price",
#     line=dict(width=1.7)
# )
# fig_price.add_scatter(
#     x=df["Date"], y=df["ATH_price"],
#     mode="lines", name="ATH (cummax)",
#     line=dict(width=1, dash="dot", color="rgba(200,0,0,.6)")
# )
# fig_price.update_layout(
#     title="S&P 500 od 1979 r.",
#     legend_title_text="Serie",
#     height=450,
#     margin=dict(l=0, r=0, t=50, b=0),
# )
# st.plotly_chart(fig_price, use_container_width=True)
#
# # ─────────────────────────────────────────────────────────────────────────────
# # 4. KLUCZOWE METRYKI
# # ─────────────────────────────────────────────────────────────────────────────
# # 4.1 dni od ostatniego ATH
# days_since_last_ath = int(df["days_since_ATH"].iloc[-1])
#
# # 4.2 średnia długość cyklu ATH (lata 1979-2025)
# ath_indices = df.index[df["days_since_ATH"] == 0].to_list()
# periods = np.diff(ath_indices)          # liczba sesji między kolejnymi ATH
# avg_days_between_ath = int(periods.mean()) if len(periods) else np.nan
#
# # 4.3 helper – funkcja zliczająca korekty większe niż próg
# def count_corrections(threshold_pct: float) -> int:
#     mask = df["pct_from_ATH"] <= -threshold_pct
#     # grupowanie ciągów True→False i zliczanie tylko zakończonych spadków
#     groups = (mask.ne(mask.shift()).cumsum())[mask]
#     return groups.nunique()
#
# corr_5  = count_corrections(5)
# corr_10 = count_corrections(10)
# corr_20 = count_corrections(20)
# corr_30 = count_corrections(30)
#
# col1, col2, col3 = st.columns(3)
# col1.metric("🕒 Dni od ostatniego ATH", f"{days_since_last_ath}")
# col2.metric("📊 Średni czas między ATH", f"{avg_days_between_ath} dni")
# col3.metric("📉 Korekty > 5 %", f"{corr_5}")
#
# col4, col5, col6 = st.columns(3)
# col4.metric("Korekty > 10 %", f"{corr_10}")
# col5.metric("Korekty > 20 %", f"{corr_20}")
# col6.metric("Korekty > 30 %", f"{corr_30}")
#
# st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# 3. WYKRES CENY + ATH
# ─────────────────────────────────────────────────────────────────────────────
fig_price = go.Figure()
fig_price.add_scatter(
    x=df["Date"], y=df["Price"], mode="lines",
    name="Close / Price", line=dict(width=1.7)
)
fig_price.add_scatter(
    x=df["Date"], y=df["ATH_price"], mode="lines",
    name="ATH (cummax)", line=dict(width=1, dash="dot", color="rgba(200,0,0,.6)")
)
fig_price.update_layout(
    title="S&P 500 od 1979 r.",
    legend_title_text="Serie",
    height=450,
    margin=dict(l=0, r=0, t=50, b=0),
)
st.plotly_chart(fig_price, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# 4. KLUCZOWE METRYKI (cały zakres danych)
# ─────────────────────────────────────────────────────────────────────────────
total_days = len(df)              # 1) łączna liczba sesji

# 4.1 dni od ostatniego ATH
days_since_last_ath = int(df["days_since_ATH"].iloc[-1])

# 4.1b dystans ostatniej sesji do ATH (w %)
last_distance_to_ath_pct = max(0.0, -float(df["pct_from_ATH"].iloc[-1]))

# 4.2 średnia długość cyklu ATH
ath_indices = df.index[df["days_since_ATH"] == 0]
periods = np.diff(ath_indices)
avg_days_between_ath = int(periods.mean()) if len(periods) else np.nan

# 4.3 helper – liczba i odsetek dni z draw-downem ≥ threshold
def count_dd(threshold: int) -> tuple[int, float]:
    mask = df["pct_from_ATH"] <= -threshold
    return int(mask.sum()), float(mask.mean() * 100)

def compute_drawdown_outlook(data: pd.DataFrame, tolerance_pp: float = 0.5) -> dict:
    """
    Szacuje, czy bieżąca korekta jest już na swoim maksimum,
    na podstawie domkniętych epizodów ATH -> kolejne ATH.
    """
    current_dd = max(0.0, -float(data["pct_from_ATH"].iloc[-1]))
    if current_dd == 0.0:
        return {
            "status": "no_active_drawdown",
            "current_dd": current_dd,
            "tolerance_pp": tolerance_pp,
        }

    work = data[["pct_from_ATH", "days_since_ATH"]].copy()
    work["drawdown_abs"] = (-work["pct_from_ATH"].astype(float)).clip(lower=0.0)
    work["episode_id"] = (work["days_since_ATH"] == 0).cumsum()

    last_episode_id = int(work["episode_id"].iloc[-1])
    analogs: list[tuple[float, float, float, int]] = []

    for episode_id, seg in work.groupby("episode_id", sort=True):
        if int(episode_id) == last_episode_id:
            # Ostatni epizod może być nadal otwarty -> pomijamy.
            continue

        corr_seg = seg.loc[seg["drawdown_abs"] > 0.0, ["drawdown_abs", "days_since_ATH"]].copy()
        dd_path = corr_seg["drawdown_abs"].to_numpy()
        if dd_path.size == 0:
            continue

        cross_idx = np.where(dd_path >= current_dd)[0]
        if cross_idx.size == 0:
            continue

        first_cross = int(cross_idx[0])
        dd_at_cross = float(dd_path[first_cross])
        future_path = dd_path[first_cross:]
        future_max_dd = float(future_path.max())
        additional_dd = future_max_dd - dd_at_cross
        bottom_rel_idx = int(np.argmax(future_path))
        bottom_idx = first_cross + bottom_rel_idx
        days_ath_to_bottom = int(corr_seg["days_since_ATH"].iloc[bottom_idx])
        analogs.append((dd_at_cross, future_max_dd, additional_dd, days_ath_to_bottom))

    if not analogs:
        return {
            "status": "no_analogs",
            "current_dd": current_dd,
            "tolerance_pp": tolerance_pp,
            "n_analog": 0,
        }

    arr = np.asarray(analogs, dtype=float)
    additional = arr[:, 2]
    is_max_reached = additional <= tolerance_pp

    p_max_reached = float(is_max_reached.mean() * 100.0)
    p_deepen = float(100.0 - p_max_reached)

    result = {
        "status": "ok",
        "current_dd": current_dd,
        "tolerance_pp": tolerance_pp,
        "n_analog": int(arr.shape[0]),
        "p_max_reached": p_max_reached,
        "p_deepen": p_deepen,
    }

    deeper = arr[additional > tolerance_pp]
    result["n_deepen_cases"] = int(deeper.shape[0])

    if deeper.shape[0] == 0:
        result["status"] = "ok_no_deepen_cases"
        return result

    target_depth_p50, target_depth_p75, target_depth_p90 = np.percentile(
        deeper[:, 1], [50, 75, 90]
    )
    additional_p50, additional_p75, additional_p90 = np.percentile(
        deeper[:, 2], [50, 75, 90]
    )
    avg_days_ath_to_bottom = float(np.mean(deeper[:, 3]))
    median_days_ath_to_bottom = float(np.median(deeper[:, 3]))
    p75_days_ath_to_bottom = float(np.percentile(deeper[:, 3], 75))

    result.update(
        {
            "target_depth_p50": float(target_depth_p50),
            "target_depth_p75": float(target_depth_p75),
            "target_depth_p90": float(target_depth_p90),
            "additional_p50": float(additional_p50),
            "additional_p75": float(additional_p75),
            "additional_p90": float(additional_p90),
            "avg_days_ath_to_bottom": avg_days_ath_to_bottom,
            "median_days_ath_to_bottom": median_days_ath_to_bottom,
            "p75_days_ath_to_bottom": p75_days_ath_to_bottom,
        }
    )
    return result

def build_correction_dynamics(data: pd.DataFrame) -> pd.DataFrame:
    """
    Buduje tabelę epizodów korekt:
    - czas od ATH do dołka,
    - głębokość dołka,
    - czas odbicia od dołka do kolejnego ATH (dla epizodów domkniętych).
    """
    work = data[["Date", "days_since_ATH", "pct_from_ATH"]].copy()
    work["drawdown_abs"] = (-work["pct_from_ATH"].astype(float)).clip(lower=0.0)
    work["episode_id"] = (work["days_since_ATH"] == 0).cumsum()

    last_episode_id = int(work["episode_id"].iloc[-1])
    rows: list[dict] = []

    for episode_id, seg in work.groupby("episode_id", sort=True):
        corr_seg = seg.loc[seg["drawdown_abs"] > 0.0, ["Date", "drawdown_abs", "days_since_ATH"]].copy()
        if corr_seg.empty:
            continue

        ath_date = pd.Timestamp(seg["Date"].iloc[0])
        trough_idx = corr_seg["drawdown_abs"].idxmax()
        trough_row = work.loc[trough_idx]
        trough_date = pd.Timestamp(trough_row["Date"])
        days_to_bottom = int(trough_row["days_since_ATH"])
        max_depth = float(trough_row["drawdown_abs"])
        is_closed = int(episode_id) != last_episode_id

        row = {
            "episode_id": int(episode_id),
            "ath_date": ath_date,
            "trough_date": trough_date,
            "max_drawdown_pct": max_depth,
            "days_to_bottom_sessions": days_to_bottom,
            "days_to_bottom_calendar": int((trough_date - ath_date).days),
            "status": "closed" if is_closed else "open",
        }

        if is_closed:
            next_episode = work[work["episode_id"] == int(episode_id) + 1]
            if not next_episode.empty:
                recovery_idx = next_episode.index[0]
                recovery_date = pd.Timestamp(next_episode["Date"].iloc[0])
                days_recovery = int(recovery_idx - trough_idx)
                row.update(
                    {
                        "recovery_date": recovery_date,
                        "days_to_recovery_sessions": days_recovery,
                        "days_to_recovery_calendar": int((recovery_date - trough_date).days),
                        "total_cycle_sessions": int(days_to_bottom + days_recovery),
                    }
                )

        rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

# teraz liczymy też 35 / 40 / 45
dd_stats = {thr: count_dd(thr) for thr in (5, 10, 15, 20, 25, 30, 35, 40, 45)}

# ── wyświetlamy metryki ─────────────────────────────────────────────────────
st.subheader("Metryki ogólne")

row1 = st.columns(4)
row1[0].metric("Liczba sesji (1979-2025)", f"{total_days}")
row1[1].metric("Dni od ostatniego ATH", f"{days_since_last_ath}")
row1[2].metric("Średni dystans ATH→ATH", f"{avg_days_between_ath} dni")
row1[3].metric("Ostatnia sesja do ATH", f"{last_distance_to_ath_pct:,.2f} %")

st.subheader("Ile sesji spędziliśmy w draw-downie?")

row2 = st.columns(3)
row3 = st.columns(3)
row4 = st.columns(3)  # nowy rząd na 35 / 40 / 45

# kolejność: 5,10,15 | 20,25,30 | 35,40,45
for col, thr in zip(row2 + row3 + row4, (5, 10, 15, 20, 25, 30, 35, 40, 45)):
    n, pct = dd_stats[thr]
    col.metric(
        label=f"DD ≥ {thr:>2} %",
        value=f"{n}",
        delta=f"{pct:,.1f} %",
        delta_color="inverse",  # czerwone = dużo draw-downów
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 5. HISTOGRAM GŁĘBOKOŚCI KOREKT
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("Rozkład głębokości korekt (pct_from_ATH)"):
    hist = px.histogram(
        df, x="pct_from_ATH",
        nbins=60, title="Histogram draw-downów od ATH",
        labels={"pct_from_ATH": "% od ATH"},
        opacity=0.75,
    )
    hist.update_layout(
        bargap=0.05, height=350,
        margin=dict(l=0, r=0, t=50, b=0),
    )
    st.plotly_chart(hist, use_container_width=True)

    st.caption("Prawdopodobieństwo dalszego pogłębienia obecnej korekty (na bazie epizodów ATH→ATH).")
    dd_outlook = compute_drawdown_outlook(df, tolerance_pp=0.5)

    if dd_outlook["status"] == "no_active_drawdown":
        st.info("Brak aktywnej korekty (jesteśmy na ATH), więc metryka pogłębienia nie ma zastosowania.")
    elif dd_outlook["status"] == "no_analogs":
        st.info("Brak historycznych analogów dla obecnej głębokości korekty, aby oszacować prawdopodobieństwa.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(
            "P(max już osiągnięty)",
            f"{dd_outlook['p_max_reached']:,.1f} %",
            delta=f"n={dd_outlook['n_analog']} analogów",
            delta_color="off",
        )
        c2.metric(
            "P(dalszego pogłębienia)",
            f"{dd_outlook['p_deepen']:,.1f} %",
        )

        if dd_outlook["status"] == "ok_no_deepen_cases":
            c3.metric("Gdy pogłębia: docelowa głębokość", "brak danych")
            c4.metric("Price target (P50)", "brak danych")
            c5.metric("Śr. czas ATH→dołek", "brak danych")
        else:
            ath_ref_price = float(df["ATH_price"].iloc[-1])
            current_price = float(df["Price"].iloc[-1])

            target_price_p50 = ath_ref_price * (1.0 - dd_outlook["target_depth_p50"] / 100.0)
            target_price_p75 = ath_ref_price * (1.0 - dd_outlook["target_depth_p75"] / 100.0)
            target_price_p90 = ath_ref_price * (1.0 - dd_outlook["target_depth_p90"] / 100.0)
            move_vs_current_p50 = (target_price_p50 / current_price - 1.0) * 100.0

            c3.metric(
                "Gdy pogłębia: docelowa głębokość",
                f"{dd_outlook['target_depth_p50']:,.2f} %",
                delta=f"med. dalsze zejście: +{dd_outlook['additional_p50']:,.2f} pp",
                delta_color="inverse",
                help=(
                    f"P75: {dd_outlook['target_depth_p75']:,.2f} %, "
                    f"P90: {dd_outlook['target_depth_p90']:,.2f} %.\n"
                    f"Dalsze zejście (pp): P75 +{dd_outlook['additional_p75']:,.2f}, "
                    f"P90 +{dd_outlook['additional_p90']:,.2f}."
                ),
            )
            c4.metric(
                "Price target (P50)",
                f"{target_price_p50:,.0f} pkt",
                delta=f"vs dziś: {move_vs_current_p50:,.2f} %",
                help=(
                    f"Przeliczone od ATH: {ath_ref_price:,.2f} pkt.\n"
                    f"Scenariusze głębsze: P75 ≈ {target_price_p75:,.0f} pkt, "
                    f"P90 ≈ {target_price_p90:,.0f} pkt."
                ),
            )
            c5.metric(
                "Śr. czas ATH→dołek",
                f"{dd_outlook['avg_days_ath_to_bottom']:,.0f} sesji",
                delta=f"mediana: {dd_outlook['median_days_ath_to_bottom']:,.0f} sesji",
                help=f"P75: {dd_outlook['p75_days_ath_to_bottom']:,.0f} sesji.",
            )

    st.caption(
        "To statystyka historyczna (empiryczna), nie sygnał inwestycyjny. "
        "Wyniki opierają się na analogach korekt między kolejnymi ATH."
    )

    dynamics_df = build_correction_dynamics(df)
    if not dynamics_df.empty:
        st.markdown("#### Dynamika korekt i odbić")

        closed_dyn = dynamics_df[dynamics_df["status"] == "closed"].copy()
        if not closed_dyn.empty:
            # Jaśniejsza skala: małe korekty/krótsze odbicia startują od jasnego błękitu,
            # dzięki czemu punkty są lepiej widoczne na ciemnym tle.
            recovery_color_scale = [
                [0.0, "#8be9fd"],
                [0.35, "#38bdf8"],
                [0.65, "#22d3ee"],
                [1.0, "#facc15"],
            ]

            fig_dyn = px.scatter(
                closed_dyn,
                x="days_to_bottom_sessions",
                y="max_drawdown_pct",
                color="days_to_recovery_sessions",
                size="total_cycle_sessions",
                hover_data={
                    "episode_id": True,
                    "ath_date": "|%Y-%m-%d",
                    "trough_date": "|%Y-%m-%d",
                    "days_to_bottom_calendar": True,
                    "days_to_recovery_calendar": True,
                    "days_to_bottom_sessions": True,
                    "days_to_recovery_sessions": True,
                    "total_cycle_sessions": True,
                    "max_drawdown_pct": ":.2f",
                },
                labels={
                    "days_to_bottom_sessions": "Czas ATH→dołek (sesje)",
                    "max_drawdown_pct": "Głębokość korekty (%)",
                    "days_to_recovery_sessions": "Czas odbicia do ATH (sesje)",
                    "total_cycle_sessions": "Cały cykl (sesje)",
                },
                title="Korekty S&P 500: czas do dołka vs głębokość (kolor = czas odbicia)",
                color_continuous_scale=recovery_color_scale,
                opacity=0.85,
            )
            fig_dyn.update_traces(
                marker=dict(line=dict(width=0.8, color="rgba(255,255,255,0.85)")),
                selector=dict(type="scatter"),
            )

            # Delikatne, kolorowe tło (green -> yellow -> red),
            # aby wizualnie pokazać przejście od "łagodnych" do "cięższych" korekt.
            x_min = float(closed_dyn["days_to_bottom_sessions"].min())
            x_max = float(closed_dyn["days_to_bottom_sessions"].max())
            y_min = 0.0
            y_max = float(closed_dyn["max_drawdown_pct"].max())
            if x_max > x_min and y_max > y_min:
                x_grid = np.linspace(x_min, x_max, 36)
                y_grid = np.linspace(y_min, y_max, 36)
                xx, yy = np.meshgrid(x_grid, y_grid)

                x_norm = (xx - x_min) / (x_max - x_min)
                y_norm = (yy - y_min) / (y_max - y_min)
                risk_bg = 0.45 * x_norm + 0.55 * y_norm

                bg_heatmap = go.Heatmap(
                    x=x_grid,
                    y=y_grid,
                    z=risk_bg,
                    zsmooth="best",
                    hoverinfo="skip",
                    showscale=False,
                    opacity=0.25,
                    colorscale=[
                        [0.0, "rgb(34,139,34)"],
                        [0.5, "rgb(245,181,35)"],
                        [1.0, "rgb(205,44,36)"],
                    ],
                )
                fig_dyn.add_trace(bg_heatmap)
                fig_dyn.data = (fig_dyn.data[-1],) + fig_dyn.data[:-1]

            open_dyn = dynamics_df[dynamics_df["status"] == "open"].copy()
            if not open_dyn.empty:
                fig_dyn.add_scatter(
                    x=open_dyn["days_to_bottom_sessions"],
                    y=open_dyn["max_drawdown_pct"],
                    mode="markers+text",
                    name="Obecna (otwarta) korekta",
                    text=["obecna"] * len(open_dyn),
                    textposition="top center",
                    marker=dict(symbol="x", size=12, color="red", line=dict(width=1)),
                    hovertemplate=(
                        "Obecna korekta<br>"
                        "ATH→dołek (sesje): %{x}<br>"
                        "Głębokość: %{y:.2f}%<extra></extra>"
                    ),
                )

            fig_dyn.update_layout(
                height=760,
                width=760,
                margin=dict(l=0, r=0, t=60, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_dyn, use_container_width=False)

            st.caption(
                "Każdy punkt to jedna historyczna korekta. "
                "Im bardziej w prawo, tym dłużej trwało schodzenie do dołka; "
                "im wyżej, tym głębsza była korekta; kolor punktu pokazuje czas odbicia do ATH, "
                "a kolor tła orientacyjnie pokazuje \"ciężar\" scenariusza (zielony -> czerwony)."
            )
        else:
            st.info("Brak domkniętych epizodów korekt do narysowania wykresu dynamiki.")
    else:
        st.info("Brak wystarczających danych do zbudowania wykresu dynamiki korekt.")



# ─────────────────────────────────────────────────────────────
# Najdłuższy okres wychodzenia na zero po zakupie na ATH
# ─────────────────────────────────────────────────────────────
st.subheader("Jak długo można było czekać na wyjście na zero po zakupie na szczycie?")

# 1️⃣ Dni z nowym ATH (kupujemy dokładnie na szczycie)
ath_df = df[df["days_since_ATH"] == 0].copy()

breakeven_dates = []
ttb_days = []  # time-to-breakeven w dniach

for idx, row in ath_df.iterrows():
    price0 = row["Price"]
    date0 = row["Date"]

    # kolejne sesje po danym ATH
    later = df.loc[idx + 1 :]
    rec = later[later["Price"] >= price0]

    if not rec.empty:
        be_date = rec["Date"].iloc[0]
        days = (be_date - date0).days
    else:
        be_date = pd.NaT
        days = np.nan

    breakeven_dates.append(be_date)
    ttb_days.append(days)

ath_df["breakeven_date"] = breakeven_dates
ath_df["time_to_breakeven_days"] = ttb_days

# tylko epizody, które faktycznie się domknęły (cena wróciła do poziomu ATH)
realized = ath_df.dropna(subset=["time_to_breakeven_days"])

# helper do ładnego formatu czasu
def _format_days(n: int) -> str:
    years = n // 365
    months = (n % 365) // 30
    days = n - years * 365 - months * 30
    parts = []
    if years:
        parts.append(f"{years} lat" if years > 1 else "1 rok")
    if months:
        parts.append(f"{months} mies.")
    if days and not years:
        parts.append(f"{days} dni")
    return ", ".join(parts) if parts else f"{n} dni"

if realized.empty:
    st.info("Brak wystarczających domkniętych epizodów (ATH → powrót do tego poziomu), aby policzyć statystyki.")
else:
    # 2️⃣ Najdłuższy historyczny czas do wyjścia na zero
    worst = realized.sort_values("time_to_breakeven_days", ascending=False).iloc[0]
    worst_days = int(worst["time_to_breakeven_days"])
    worst_start = worst["Date"].date()
    worst_end = worst["breakeven_date"].date()

    avg_ttb = int(realized["time_to_breakeven_days"].mean())
    median_ttb = int(realized["time_to_breakeven_days"].median())

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Najgorszy czas do wyjścia na zero (po ATH)",
        f"{worst_days} dni",
        help=f"Od {worst_start} do {worst_end} — ok. {_format_days(worst_days)}",
    )
    col2.metric(
        "Średni czas do wyjścia na zero (po ATH)",
        f"{avg_ttb} dni",
        help="Średnia po wszystkich historycznych szczytach, które zostały wybite.",
    )
    col3.metric(
        "Mediana czasu do wyjścia na zero",
        f"{median_ttb} dni",
    )

    # 3️⃣ Czy są ATH-y wciąż „pod wodą” (brak powrotu do poziomu)?
    open_underwater = ath_df[ath_df["breakeven_date"].isna()].copy()
    if not open_underwater.empty:
        last_date = df["Date"].iloc[-1]
        open_underwater["current_underwater_days"] = (last_date - open_underwater["Date"]).dt.days

        current_worst = open_underwater.sort_values(
            "current_underwater_days", ascending=False
        ).iloc[0]
        cur_days = int(current_worst["current_underwater_days"])
        cur_start = current_worst["Date"].date()

        # st.caption(
        #     f"Obecnie najdłużej trwający **niedomknięty** okres po ATH zaczął się "
        #     f"{cur_start} i trwa już około {cur_days} dni (~{_format_days(cur_days)})."
        # )

    # 4️⃣ Wykres słupkowy: czas do wyjścia na zero po każdym ATH
    with st.expander("Rozkład czasów wyjścia na zero po historycznych szczytach"):
        bar = px.bar(
            realized,
            x="Date",
            y="time_to_breakeven_days",
            labels={
                "Date": "Data szczytu (ATH)",
                "time_to_breakeven_days": "Dni do wyjścia na zero",
            },
            title="Czas do wyjścia na zero po zakupie na szczycie (tylko epizody domknięte)",
        )

        # zamiast add_vline (które gryzie się z Timestamp) rysujemy pionową linię scatterem
        max_y = realized["time_to_breakeven_days"].max()
        worst_date = worst["Date"]

        bar.add_scatter(
            x=[worst_date, worst_date],
            y=[0, max_y * 1.05],
            mode="lines",
            name="Najgorszy epizod",
            line=dict(dash="dash", width=2),
        )

        bar.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0))
        st.plotly_chart(bar, use_container_width=True)

    # Wykres „pod wodą” dla najgorszego epizodu
    with st.expander("Najgorszy epizod – ścieżka indeksu od szczytu do wyjścia na zero"):
        mask = (df["Date"] >= worst["Date"]) & (df["Date"] <= worst["breakeven_date"])
        seg = df[mask].copy()
        entry_price = worst["Price"]
        seg["underwater_pct"] = (seg["Price"] / entry_price - 1) * 100

        fig_under = go.Figure()
        fig_under.add_scatter(
            x=seg["Date"],
            y=seg["underwater_pct"],
            mode="lines",
            name="% względem ceny zakupu na ATH",
        )
        fig_under.add_hline(
            y=0,
            line_dash="dash",
            line_width=1,
            annotation_text="poziom wejścia",
        )
        fig_under.update_layout(
            title=f"Najdłuższy okres wychodzenia na zero: {worst_days} dni "
                  f"({worst_start} → {worst_end})",
            yaxis_title="% względem ceny zakupu",
            height=400,
            margin=dict(l=0, r=0, t=50, b=0),
        )
        st.plotly_chart(fig_under, use_container_width=True)





# ─────────────────────────────────────────────────────────────────────────────
# 6. OPCJONALNIE – rolling Sharpe 252 dni
# ─────────────────────────────────────────────────────────────────────────────



if st.checkbox("🟢 Pokaż rolling Sharpe (1 rok)", value=False):
    with st.expander("ℹ️ Co to jest Rolling Sharpe Ratio?"):
        st.markdown("""
    Wykres przedstawia **rolling Sharpe ratio** (czyli ruchome Sharpe ratio) dla indeksu S&P 500 z kroczącym oknem **252 dni**, co odpowiada mniej więcej jednemu rokowi handlowemu.

    ---

    ### 🔍 Co to jest Sharpe ratio?

    Sharpe ratio mierzy, ile **nadwyżkowego zysku (ponad stopę wolną od ryzyka)** generuje portfel lub indeks **na jednostkę ryzyka (odchylenia standardowego zwrotów)**:

    Wzór:
    """)

        st.latex(r"\text{Sharpe ratio} = \frac{R_p - R_f}{\sigma_p}")

        st.markdown("**Gdzie:**")

        st.latex(r"R_p = \text{średnia stopa zwrotu portfela}")
        st.latex(r"R_f = \text{stopa wolna od ryzyka}")
        st.latex(r"\sigma_p = \text{odchylenie standardowe stóp zwrotu portfela}")

        st.markdown("""
    Wersja *rolling* oznacza, że współczynnik ten liczony jest **w sposób kroczący** – np. każdego dnia liczony jest Sharpe za poprzednie 252 dni.

    ---

    ### 📈 Jak interpretować wykres?

    #### ✅ Wartości dodatnie (> 0):
    - Indeks S&P 500 generował dodatni nadwyżkowy zwrot względem ryzyka.
    - Im wyższy Sharpe ratio, tym lepsza relacja zysku do ryzyka.
    - Typowe poziomy:
      - **0.5–1**: akceptowalne  
      - **1–2**: dobre  
      - **>2**: bardzo dobre (rzadkie)

    #### ❌ Wartości ujemne (< 0):
    - Indeks miał ujemny zwrot skorygowany o ryzyko – **więcej ryzyka niż zysku**.
    - Oznacza to okresy nieopłacalnego inwestowania z punktu widzenia relacji zysk/ryzyko.

    ---

    ### 📉 Przykłady z wykresu:

    - **2002 i 2008–2009**: rolling Sharpe ratio spada poniżej zera — oznacza to słabą jakość rynku w tych okresach (bańka dot-com, kryzys finansowy).
    - **1995, 2013, 2021**: wysokie piki — zyski były wysokie, ryzyko niskie.

    ---

    ### 🔄 Sharpe jako wskaźnik *nastroju rynkowego*

    #### 📊 Wysokie Sharpe ratio (>2):
    - Po silnych wzrostach, niska zmienność.
    - Inwestorzy czują się komfortowo, panuje optymizm.
    - **Uwaga:** rynek często jest blisko szczytu, a przyszła stopa zwrotu może być niska.

    #### 🧨 Niskie lub ujemne Sharpe ratio (<0):
    - Często po spadkach, zmienność wysoka.
    - Strach, pesymizm, kapitulacja.
    - **To często najlepsze momenty do wejścia na rynek.**

    ---

    ### 🧠 Wniosek: Rolling Sharpe jako wskaźnik sentymentu?

    Można potraktować rolling Sharpe ratio jako **„miernik komfortu” inwestorów** — a jak wiadomo:

    > 📉 Najlepsze decyzje inwestycyjne podejmuje się wtedy, gdy jest niewygodnie.

    ---

    ### 📌 Strategia kontrariańska:

    - **Inwestować**, gdy rolling Sharpe jest bardzo **niski lub ujemny**
    - **Być ostrożnym**, gdy rolling Sharpe ratio osiąga **ekstremalnie wysokie poziomy**

    ---

    ### ⚠️ Uwaga

    Rolling Sharpe **nie przewiduje przyszłości**, pokazuje tylko **jakość relacji zysku do ryzyka w przeszłości**.

    - Jego **maksima często pokrywają się z końcówką hossy**
    - Jego **minima — z dołkami bessy**
        """)

    sharpe_fig = px.line(
        df, x="Date", y="roll_sharpe",
        title="Rolling Sharpe – 252 dni",
        labels={"roll_sharpe": "Sharpe"},
    )
    sharpe_fig.update_layout(height=350, margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(sharpe_fig, use_container_width=True)

    # ── statystyki: ile czasu Sharpe był dodatni / ujemny ───────
    valid_sharpe = df["roll_sharpe"].dropna()

    if len(valid_sharpe) == 0:
        st.info("Brak wystarczających danych rolling Sharpe do policzenia statystyk.")
    else:
        pos_mask = valid_sharpe > 0
        neg_mask = valid_sharpe <= 0

        n_total = int(len(valid_sharpe))
        n_pos = int(pos_mask.sum())
        n_neg = int(neg_mask.sum())

        pct_pos = n_pos / n_total * 100
        pct_neg = n_neg / n_total * 100

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Sharpe > 0",
            f"{pct_pos:,.1f} %",
            help=f"{n_pos} z {n_total} dostępnych dni rolling Sharpe",
        )
        c2.metric(
            "Sharpe ≤ 0",
            f"{pct_neg:,.1f} %",
            help=f"{n_neg} z {n_total} dostępnych dni rolling Sharpe",
        )
        c3.metric(
            "Średni rolling Sharpe",
            f"{valid_sharpe.mean():.2f}",
        )

        # ── histogram rozkładu rolling Sharpe ───────────────────
        with st.expander("📊 Rozkład wartości rolling Sharpe (252 dni)"):
            hist = px.histogram(
                valid_sharpe,
                x=valid_sharpe.values,
                nbins=60,
                labels={"x": "Rolling Sharpe (252 dni)"},
                title="Histogram wartości rolling Sharpe",
                opacity=0.8,
            )
            # pionowa linia w 0 (tu już x jest float, więc add_vline jest OK)
            hist.add_vline(
                x=0.0,
                line_dash="dash",
                line_width=1,
                annotation_text="0",
                annotation_position="top left",
            )
            hist.update_layout(
                bargap=0.05,
                height=350,
                margin=dict(l=0, r=0, t=50, b=0),
            )
            st.plotly_chart(hist, use_container_width=True)

# # ─────────────────────────────────────────────────────────────────────────────
# # 7. BONUS – tabela z ostatnimi 10 sesjami (rozwiń, gdy potrzebne)
# # ─────────────────────────────────────────────────────────────────────────────
# with st.expander("📄 Zobacz ostatnie 10 wierszy danych"):
#     st.dataframe(
#         df.tail(10).style.format(precision=2),
#         use_container_width=True,
#         height=250,
#     )






# # ───────────────────────────────────────────────────────────
# # 1. Dane & cache
# # ───────────────────────────────────────────────────────────
# @st.cache_data(show_spinner="Pobieram dane…")
# def load_data(url: str) -> pd.DataFrame:
#     df = pd.read_csv(url, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
#     return df
#
# df = load_data(RAW_GITHUB_URL)

# ───────────────────────────────────────────────────────────
# 2. Sidebar – parametry backtestu
# ───────────────────────────────────────────────────────────
st.sidebar.header("🎛️ Parametry backtestu")
start_date = st.sidebar.date_input(
    "Data początkowa",
    value=df["Date"].iloc[0].date(),
    min_value=df["Date"].iloc[0].date(),
    max_value=df["Date"].iloc[-2].date(),
)
n_trades = st.sidebar.slider("Liczba transakcji", 10, 500, 100, step=10)
invest_usd = st.sidebar.slider("Kwota jednej transakcji [$]", 10, 1000, 100, step=10)
drawdown_pct = st.sidebar.selectbox(
    "Próg spadku od ATH (%)",
    options=[5, 10, 15, 20, 25, 30],
    index=1,
)

# ───────────────────────────────────────────────────────────
# 3. Funkcje pomocnicze
# ───────────────────────────────────────────────────────────
def buy_and_hold(dates: np.ndarray, amount_per_trade: float) -> float:
    """
    Kupujemy w zadane dni za stałą kwotę.
    Zwraca końcową wartość portfela przy sprzedaży w ostatniej dostępnej sesji.
    """
    prices = df.loc[dates, "Price"].values
    shares = amount_per_trade / prices               # ile „udziałów” kupiliśmy
    final_price = df["Price"].iloc[-1]
    return shares.sum() * final_price

# ───────────────────────────────────────────────────────────
# ZASTĄP STARĄ  pick_drawdown_days()  TYM NOWYM KODEM
# ───────────────────────────────────────────────────────────
def sample_drawdown_days(threshold: float, n: int) -> np.ndarray:
    """
    Losuje dni zakupów TYLKO z okresów, gdy draw-down ≤ –threshold.
    • Każdy ciąg spadkowy dostaje ≥1 transakcję (o ile pulę na to stać).
    • Reszta transakcji rozkłada się losowo z równym prawdopodobieństwem
      na wszystkie ciągi (sampling 'segment-balanced').
    """
    mask = df["pct_from_ATH"] <= -threshold
    mask &= df["Date"] >= pd.Timestamp(start_date)   # ograniczenie zakresu backtestu

    # 1️⃣ identyfikujemy kolejne ciągi spadkowe
    seg_id = (mask != mask.shift()).cumsum()
    segments = {
        k: grp.index.to_numpy()
        for k, grp in df[mask].groupby(seg_id[mask])
    }

    rng = np.random.default_rng(seed=42)
    picked: list[int] = []

    # 2️⃣ najpierw po 1 losowym dniu z każdego ciągu
    for idxs in segments.values():
        picked.append(rng.choice(idxs))

    if len(picked) >= n:      # mamy już dość transakcji
        return np.array(rng.choice(picked, size=n, replace=False))

    # 3️⃣ uzupełniamy brakujące losując segment → dzień aż dopełnimy n
    all_eligible = np.concatenate(list(segments.values()))
    while len(picked) < n and len(picked) < len(all_eligible):
        day = rng.choice(all_eligible)
        if day not in picked:          # gwarancja unikalności
            picked.append(day)

    return np.array(sorted(picked))

def pick_random_days(n: int) -> np.ndarray:
    eligible = df[df["Date"] >= pd.Timestamp(start_date)].index
    return np.random.default_rng(seed=42).choice(eligible, size=n, replace=False)

# ───────────────────────────────────────────────────────────
# 4. Symulacja dwóch strategii
# ───────────────────────────────────────────────────────────
drawdown_days = sample_drawdown_days(drawdown_pct, n_trades)
random_days    = pick_random_days(n_trades)

port_drawdown = buy_and_hold(drawdown_days, invest_usd)
port_random   = buy_and_hold(random_days,   invest_usd)

total_invested = n_trades * invest_usd
ret_drawdown = (port_drawdown / total_invested - 1) * 100
ret_random   = (port_random   / total_invested - 1) * 100

# ── BUY-AND-HOLD OD DATY START ────────────────────────────────────────────
start_idx = df.index[df["Date"] >= pd.Timestamp(start_date)][0]
start_price = df.at[start_idx, "Price"]
bh_return = (df["Price"].iloc[-1] / start_price - 1) * 100

# ───────────────────────────────────────────────────────────
# 5. Wyniki – metrici + wykres dat zakupów
# ───────────────────────────────────────────────────────────
st.title("Back-test: kupowanie po korektach vs. losowe zakupy")

c1, c2, c3 = st.columns(3)
c1.metric("Łączna inwestycja", f"${total_invested:,.0f}")
c2.metric(f"Stopa zwrotu (DD ≥ {drawdown_pct} %)", f"{ret_drawdown:,.2f} %")
c3.metric("Stopa zwrotu (losowo)", f"{ret_random:,.2f} %")
c4, _ = st.columns(2)   # wolna kolumna + dystans
c4.metric("Buy-and-Hold od daty start", f"{bh_return:,.2f} %")


st.write("#### Daty transakcji")
fig = go.Figure()
fig.add_scatter(
    x=df["Date"], y=df["Price"],
    mode="lines", name="Cena indeksu", line=dict(width=1.3)
)
fig.add_scatter(
    x=df.loc[drawdown_days, "Date"], y=df.loc[drawdown_days, "Price"],
    mode="markers", name=f"Zakupy przy DD ≥ {drawdown_pct} %",
    marker=dict(size=7, symbol="triangle-down", color="red")
)
fig.add_scatter(
    x=df.loc[random_days, "Date"], y=df.loc[random_days, "Price"],
    mode="markers", name="Zakupy losowe",
    marker=dict(size=7, symbol="circle", color="green", opacity=0.55)
)
fig.update_layout(
    height=450, legend_title_text="Serie",
    margin=dict(l=0, r=0, t=40, b=0),
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    """
    **Założenia**  
    • Każdy zakup to kwota stała (_equal-dollar cost_).  
    • Brak kosztów prowizji i podatków.  
    • Wszystkie pozycje trzymamy do _dziś_ (ostatni wiersz danych).  
    • Wariant „draw-down” kupuje **tylko pierwsze** N sesji, w których spadek od ATH ≥ wybrany próg.  
      Jeśli takich sesji jest mniej niż N, kupujemy tyle, ile się da.  
    • Wariant losowy losuje N odrębnych sesji (z ziarnem 42 dla powtarzalności).
    """
)


# ──────────────────────────────────────────────────────────────────────────
# GRID-SEARCH: threshold × n_trades  (kwota=100 USD)
# ──────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────
# GRID-SEARCH: bardziej elastyczny wybór progów DD
# ──────────────────────────────────────────────────────────
st.header("🔎 Grid search strategii «Kupuj po korekcie»")

with st.form("grid_form"):
    # ① zakres progów (slider)
    thr_min, thr_max = st.slider(
        "Zakres progów spadku od ATH (%)",
        min_value=1,  max_value=50,
        value=(5, 20), step=1,
        help="Przesuń uchwyty, aby wybrać minimalny i maksymalny procent spadku."
    )
    drawdown_pct_list = list(range(thr_min, thr_max + 1))  # [5,6,7,…,20]

    # ② zakres liczby transakcji (jak wcześniej)
    n_trade_min, n_trade_max = st.slider(
        "Zakres liczby transakcji",
        10, 500, (50, 200), step=10
    )

    submitted = st.form_submit_button("Uruchom grid-search")

if submitted:
    results = []
    n_values = range(n_trade_min, n_trade_max + 1, 10)
    progress = st.progress(0.0, text="Liczenie…")
    total_iter = len(drawdown_pct_list) * len(n_values)
    k = 0

    for thr in drawdown_pct_list:
        for n in n_values:
            drawdown_days = sample_drawdown_days(thr, n)
            random_days   = pick_random_days(n)

            port_dd = buy_and_hold(drawdown_days, 100)
            port_rn = buy_and_hold(random_days,   100)
            total   = 100 * n

            results.append({
                "threshold_pct": thr,
                "n_trades": n,
                "ret_drawdown_%": (port_dd / total - 1) * 100,
                "ret_random_%":   (port_rn / total - 1) * 100,
                "edge_%":         (port_dd / total - port_rn / total) * 100,
            })
            k += 1
            progress.progress(k / total_iter)

        #     # ──────────────────────────────────────────────────────────
        #     # 8. Analiza korelacji: które zmienne ↔ zwrot?
        #     # ──────────────────────────────────────────────────────────
        #     st.subheader("📈 Korelacja parametrów z wynikiem strategii")
        #
        #     corr_df = gs_df[["threshold_pct", "n_trades", "ret_drawdown_%", "edge_%"]]
        #     corr = corr_df.corr(method="pearson").round(3)
        #
        #     fig_corr = px.imshow(
        #         corr,
        #         text_auto=True,
        #         color_continuous_scale="RdBu",
        #         zmin=-1, zmax=1,
        #         labels=dict(x="", y="", color="ρ"),
        #         title="Macierz korelacji (Pearson)"
        #     )
        #     fig_corr.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0))
        #     st.plotly_chart(fig_corr, use_container_width=True)
        #
        #     rank = (
        #         corr["ret_drawdown_%"]
        #         .drop("ret_drawdown_%")  # pomijamy autokorelację 1.00
        #         .abs()
        #         .sort_values(ascending=False)
        #         .to_frame("abs ρ")
        #     )
        #     st.write("##### Najmocniejsze zależności z `ret_drawdown_%`")
        #     st.dataframe(rank.style.format(precision=3), height=150)
        #
        # else:
        #     st.info("➡️ Uruchom grid-search, aby zobaczyć macierz korelacji parametrów.")

    gs_df = pd.DataFrame(results)
    best_row = gs_df.loc[gs_df["ret_drawdown_%"].idxmax()]

    # ----------------  analiza korelacji  -----------------
    st.subheader("📈 Korelacja parametrów z wynikiem strategii")

    corr_df = gs_df[["threshold_pct", "n_trades",
                     "ret_drawdown_%", "edge_%"]]
    corr = corr_df.corr(method="pearson").round(3)

    fig_corr = px.imshow(
        corr, text_auto=True, color_continuous_scale="RdBu",
        zmin=-1, zmax=1, labels=dict(x="", y="", color="ρ"),
        title="Macierz korelacji (Pearson)"
    )
    fig_corr.update_layout(height=400,
                           margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig_corr, use_container_width=True)

    rank = (
        corr["ret_drawdown_%"]
        .drop("ret_drawdown_%")
        .abs()
        .sort_values(ascending=False)
        .to_frame("abs ρ")
    )
    st.write("##### Najmocniejsze zależności z `ret_drawdown_%`")
    st.dataframe(rank.style.format(precision=3), height=150)

    st.success(
        f"🏆 **Najlepszy wynik:** "
        f"DD ≥ {best_row['threshold_pct']} %, "
        f"{best_row['n_trades']} transakcji ⇒ "
        f"{best_row['ret_drawdown_%']:,.2f} % zwrotu"
    )

    st.dataframe(
        gs_df.sort_values("ret_drawdown_%", ascending=False)
             .reset_index(drop=True)
             .style.format(precision=2),
        use_container_width=True,
        height=400,
    )

    # (opcjonalnie) Heat-mapa
    heat = gs_df.pivot_table(
        index="threshold_pct",
        columns="n_trades",
        values="ret_drawdown_%",
        aggfunc="mean"  # lub np. "max"
    )
    fig_heat = px.imshow(
        heat,
        text_auto=".1f",
        color_continuous_scale="Blues",
        aspect="auto",
        labels=dict(x="n trades", y="threshold [%]", color="Zwrot %")
    )
    fig_heat.update_layout(height=450, margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig_heat, use_container_width=True)




    # 1️⃣ Pivot -> macierz przewagi (edge)
    edge_heat = gs_df.pivot_table(
        index="threshold_pct",
        columns="n_trades",
        values="edge_%",
        aggfunc="mean"          # gdybyś testował kilka razy te same parametry
    )

    # 2️⃣ Zamieniamy ujemne wartości na NaN, żeby nie zaśmiecały koloru
    edge_pos = edge_heat.where(edge_heat > 0)

    # 3️⃣ Heat-mapa
    fig_edge = px.imshow(
        edge_pos,
        text_auto=".1f",
        color_continuous_scale="Greens",     # zielony = lepiej niż losowo
        aspect="auto",
        labels=dict(x="n trades",
                    y="threshold [%]",
                    color="Przewaga\nnad\nrandom %"),
    )

    fig_edge.update_layout(
        title="Heat-mapa: kombinacje lepsze od losowego zakupu",
        height=450,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    st.plotly_chart(fig_edge, use_container_width=True)



# # ──────────────────────────────────────────────────────────
# # 8. Analiza korelacji: które zmienne ↔ zwrot?
# # ──────────────────────────────────────────────────────────
# st.subheader("📈 Korelacja parametrów z wynikiem strategii")
#
# # 1️⃣ wybieramy tylko kolumny numeryczne
# corr_df = gs_df[["threshold_pct", "n_trades", "ret_drawdown_%", "edge_%"]]
# corr = corr_df.corr(method="pearson").round(3)
#
# # 2️⃣ heat-mapa
# fig_corr = px.imshow(
#     corr,
#     text_auto=True,
#     color_continuous_scale="RdBu",
#     zmin=-1, zmax=1,
#     labels=dict(x="", y="", color="ρ"),
#     title="Macierz korelacji (Pearson)"
# )
# fig_corr.update_layout(height=400, margin=dict(l=0, r=0, t=50, b=0))
# st.plotly_chart(fig_corr, use_container_width=True)
#
# # 3️⃣ ranking bezwzględnych korelacji względem zwrotu strategii
# rank = (
#     corr["ret_drawdown_%"]
#     .drop("ret_drawdown_%")          # pomijamy autokorelację 1.00
#     .abs()
#     .sort_values(ascending=False)
#     .to_frame("abs ρ")
# )
# st.write("##### Najmocniejsze zależności z `ret_drawdown_%`")
# st.dataframe(rank.style.format(precision=3), height=150)




# ─────────────────────────────────────────────────────────────
# 9. MIESIĘCZNE ZWROTY – HEAT-MAPA + ROZSZERZONE STATYSTYKI
# ─────────────────────────────────────────────────────────────
st.header("📆 Miesięczne zwroty S&P 500")

# 1️⃣ zwroty m/m (w %)
df_m = (
    df.set_index("Date")["Price"]
      .resample("M").last()
      .pct_change()
      .mul(100)                     # → procenty
      .dropna()
)
df_m.index = df_m.index.to_period("M")   # 2024-03 …

# 2️⃣ lata – dropdowny
years = sorted(df_m.index.year.unique())
c_start, c_end = st.columns(2)
start_year = c_start.selectbox("Pokaż od roku :", years, index=0)
end_year   = c_end.selectbox("Do roku :", years, index=len(years)-1)

if start_year > end_year:
    st.warning("⚠️ Rok początkowy nie może być > końcowego.")
    st.stop()

# 3️⃣ wycinek i pivot Year × Month
sel = df_m[(df_m.index.year >= start_year) & (df_m.index.year <= end_year)]

df_month = sel.to_frame("ret")
df_month["Year"]  = df_month.index.year
df_month["Month"] = df_month.index.month

pivot = (
    df_month.pivot(index="Year", columns="Month", values="ret")
            .round(2)
)

month_map = dict(enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun",
     "Jul","Aug","Sep","Oct","Nov","Dec"], start=1))
pivot = (pivot.rename(columns=month_map)
               .reindex(columns=list(month_map.values())))

# kolumna Total – roczny CAGR z miesięcy
pivot["Total"] = ((1 + pivot/100).prod(axis=1) - 1).mul(100).round(2)

# 4️⃣ heat-mapa
vals = pivot.drop(columns="Total").values.flatten()
rng  = np.nanmax(np.abs(vals))

fig_month = px.imshow(
    pivot.drop(columns="Total"),
    text_auto=".2f",
    # color_continuous_scale="RdBu_r",
    color_continuous_scale="RdYlGn",   # ⟵ zamiast "RdBu_r"
    aspect="auto",
    labels=dict(x="", y="", color="% m/m"),
)
fig_month.update_coloraxes(cmin=-rng, cmax=rng, cmid=0)
fig_month.update_layout(
    title=f"Monthly returns {start_year} – {end_year}",
    height=450, margin=dict(l=0, r=0, t=50, b=0)
)
st.plotly_chart(fig_month, use_container_width=True)

# 5️⃣ rozbudowane statystyki: mean, median, min, max, σ, Sharpe
stats = pivot.drop(columns="Total")

agg = stats.agg(["mean", "median", "min", "max", "std"]).T
agg = agg.rename(columns={"std": "vol_%"})
agg["Sharpe"] = (agg["mean"] / agg["vol_%"]).replace(np.inf, np.nan) * np.sqrt(12)
agg = agg.round(2).rename_axis("Month").reset_index()

with st.expander("Statystyki miesięczne"):
    st.dataframe(
        agg.style.format(precision=2),
        use_container_width=True,
        height=480
    )







#


# ───────────────────────────────────────────────────────────
# ❶ Sidebar – parametry strategii „Kupuj przy niskim Sharpe”
# ───────────────────────────────────────────────────────────
st.sidebar.header("🎛️ Sharpe-based backtest")

start_date_sh = st.sidebar.date_input(
    "Data początkowa (Sharpe)",
    value=df["Date"].iloc[0].date(),
    min_value=df["Date"].iloc[0].date(),
    max_value=df["Date"].iloc[-2].date(),
    key="date_sharpe",          # ← unikalny identyfikator
)

n_trades_sh = st.sidebar.slider(
    "Liczba transakcji", 10, 500, 100, step=10, key="n_trades_sh"
)
invest_usd_sh = st.sidebar.slider(
    "Kwota jednej transakcji [$]", 10, 1000, 100, step=10, key="usd_sh"
)
sh_thr = st.sidebar.slider(
    "Górna granica rolling Sharpe (252 dni)",
    -3.0, 3.0, value=-0.5, step=0.1,
    key="thr_sh",
    help="Kupuj tylko w dni, gdy rolling Sharpe ≤ ten próg",
)

# ───────────────────────────────────────────────────────────
# ❷ Funkcje pomocnicze (przyjmują start_date jako arg.)
# ───────────────────────────────────────────────────────────
def buy_and_hold(dates: np.ndarray, amount_per_trade: float) -> float:
    prices = df.loc[dates, "Price"].values
    shares = amount_per_trade / prices
    return shares.sum() * df["Price"].iloc[-1]

def sample_sharpe_days(threshold: float, n: int, start_date) -> np.ndarray:
    """Losuje dni z okresów, w których roll_sharpe ≤ threshold."""
    mask = (df["roll_sharpe"] <= threshold) & (df["Date"] >= pd.Timestamp(start_date))
    seg_id = (mask != mask.shift()).cumsum()
    segments = {k: g.index.to_numpy() for k, g in df[mask].groupby(seg_id[mask])}

    rng, picked = np.random.default_rng(42), []
    for arr in segments.values():                # ≥1 dzień z każdego ciągu
        picked.append(rng.choice(arr))

    if len(picked) >= n:
        return np.sort(rng.choice(picked, n, replace=False))

    all_eligible = np.concatenate(list(segments.values()))
    while len(picked) < min(n, len(all_eligible)):
        d = rng.choice(all_eligible)
        if d not in picked:
            picked.append(d)
    return np.array(sorted(picked))

def pick_random_days(n: int, start_date) -> np.ndarray:
    elig = df[df["Date"] >= pd.Timestamp(start_date)].index
    return np.random.default_rng(42).choice(elig, size=n, replace=False)

# ───────────────────────────────────────────────────────────
# ❸ Symulacja strategii
# ───────────────────────────────────────────────────────────
sharpe_days = sample_sharpe_days(sh_thr, n_trades_sh, start_date_sh)
rand_days   = pick_random_days(n_trades_sh, start_date_sh)

port_sharpe = buy_and_hold(sharpe_days, invest_usd_sh)
port_rand   = buy_and_hold(rand_days,   invest_usd_sh)
total_inv   = n_trades_sh * invest_usd_sh

ret_sharpe  = (port_sharpe / total_inv - 1) * 100
ret_random  = (port_rand   / total_inv - 1) * 100

bh_start = df.loc[df["Date"] >= pd.Timestamp(start_date_sh), "Price"].iloc[0]
bh_ret   = (df["Price"].iloc[-1] / bh_start - 1) * 100

# ───────────────────────────────────────────────────────────
# ❹ Metryki + wykres
# ───────────────────────────────────────────────────────────
st.title("📊 Back-test: kupuj przy niskim Rolling Sharpe")

c1, c2, c3 = st.columns(3)
c1.metric("Łączna inwestycja", f"${total_inv:,.0f}")
c2.metric(f"Zwrot (Sharpe ≤ {sh_thr})", f"{ret_sharpe:,.2f} %")
c3.metric("Zwrot (losowo)",            f"{ret_random:,.2f} %")
st.metric("Buy-and-Hold", f"{bh_ret:,.2f} %")

st.write("#### Daty transakcji vs. rolling Sharpe")
fig = go.Figure()
fig.add_scatter(x=df["Date"], y=df["Price"], mode="lines",
                name="Cena", line=dict(width=1.2))
fig.add_scatter(x=df["Date"], y=df["ATH_price"], mode="lines",
                name="ATH", line=dict(width=0.8, dash="dot", color="gray"))

fig.add_scatter(x=df.loc[sharpe_days, "Date"], y=df.loc[sharpe_days, "Price"],
                mode="markers", name="Zakupy (Sharpe)", marker_symbol="triangle-down",
                marker_size=8, marker_color="red")
fig.add_scatter(x=df.loc[rand_days, "Date"], y=df.loc[rand_days, "Price"],
                mode="markers", name="Zakupy losowe",  marker_symbol="circle",
                marker_size=8, marker_color="green", opacity=0.5)

fig.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=0))
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"""
    **Założenia**  
    • {n_trades_sh} transakcji × ${invest_usd_sh} każda.  
    • Kupujemy, gdy rolling Sharpe (252 d) ≤ **{sh_thr}**.  
    • Po zakupie trzymamy do dziś (brak sprzedaży po sygnałach).  
    • Brak prowizji/podatków.  
    • Porównanie z losowym wyborem {n_trades_sh} sesji i buy-and-hold od {start_date_sh:%Y-%m-%d}.
    """
)





#
# # ───────────────────────────────────────────────────────────
# # 10. MARKOV + „k-down buy” back-test
# # ───────────────────────────────────────────────────────────
# st.header("🔄 Markov chain & k-down strategy")
#
# # 1️⃣ przygotowanie kolumn ‘return’ i ‘state’
# df["daily_ret"] = df["Price"].pct_change()
# df["state"] = np.where(df["daily_ret"] > 0, "up", "down")
#
# # 2️⃣ macierz przejść (rzędu 1)
# tt = pd.crosstab(df["state"].shift(), df["state"], normalize="index").round(3)
# st.subheader("Macierz przejść 1-rzędu")
# st.dataframe(tt.style.format("{:.3f}"), height=120, use_container_width=True)
#
# # 3️⃣ ile razy po k „down” przychodzi „up”  (k = 1…max_k)
# max_k = st.slider("Maks. długość sekwencji down", 1, 10, 5, key="k_max")
# rows = []
# for k in range(1, max_k + 1):
#     cond = (df["state"].shift(1).rolling(k).apply(lambda x: all(x=="down"))) == 1
#     # wystąpienia z pełnymi k spadkami (liczymy na świecy t)
#     idx = cond[cond].index
#     # sprawdzamy świecę t (ostatni ‘down’) oraz t+1 (czy up?)
#     up_next = (df.loc[idx + 1, "state"] == "up").sum()
#     total   = len(idx)
#     prob_up = up_next / total if total else np.nan
#     rows.append({"k_down": k, "occurences": total, "prob_next_up": round(prob_up, 3)})
#
# prob_df = pd.DataFrame(rows).set_index("k_down")
# st.subheader("Prawdopodobieństwo wzrostu po k spadkach")
# st.dataframe(prob_df, use_container_width=True, height=200)
#
# # ───────────────────────────────────────────────────────────
# # 4️⃣ back-test strategii „kup po k down”
# # ───────────────────────────────────────────────────────────
# st.sidebar.header("🎛️ k-down back-test")
#
# start_date_k = st.sidebar.date_input(
#     "Data początkowa (k-down)",
#     value=df["Date"].iloc[0].date(),
#     min_value=df["Date"].iloc[0].date(),
#     max_value=df["Date"].iloc[-2].date(),
#     key="date_kdown",
# )
# k_sel = st.sidebar.slider(
#     "Ile spadków z rzędu (k)", 1, max_k, 3, key="k_sel"
# )
# n_trades_k = st.sidebar.slider(
#     "Liczba transakcji", 10, 500, 100, 10, key="n_trades_k"
# )
# usd_k = st.sidebar.slider(
#     "Kwota jednej transakcji [$]", 10, 1000, 100, 10, key="usd_k"
# )
#
# # funkcje pomocnicze
# def get_kdown_buy_days(k, start_date):
#     cond = (df["state"].shift(1).rolling(k).apply(lambda x: all(x=="down"))) == 1
#     elig = cond[(df["Date"] >= pd.Timestamp(start_date))].index + 1  # kupujemy dzień po sekwencji
#     return elig[elig < len(df)]   # usuń przekroczenie końca
#
# def pick_random_days_k(n, start_date):
#     elig = df[df["Date"] >= pd.Timestamp(start_date)].index
#     return np.random.default_rng(123).choice(elig, size=n, replace=False)
#
# # wyznaczamy dni zakupów
# buy_candidates = get_kdown_buy_days(k_sel, start_date_k)
# if len(buy_candidates) == 0:
#     st.warning("Brak sekwencji spełniających warunek w wybranym okresie.")
#     st.stop()
#
# rng = np.random.default_rng(42)
# buy_days_k = np.sort(rng.choice(buy_candidates, size=min(n_trades_k, len(buy_candidates)), replace=False))
# rand_days_k = pick_random_days_k(len(buy_days_k), start_date_k)
#
# # wyniki
# port_k   = buy_and_hold(buy_days_k, usd_k)
# port_rnd = buy_and_hold(rand_days_k, usd_k)
# total_k  = len(buy_days_k) * usd_k
# ret_k    = (port_k / total_k - 1) * 100
# ret_rnd  = (port_rnd / total_k - 1) * 100
#
# bh_price0 = df.loc[df["Date"] >= pd.Timestamp(start_date_k), "Price"].iloc[0]
# bh_k      = (df["Price"].iloc[-1] / bh_price0 - 1) * 100
#
# # metryki
# st.subheader(f"📈 Back-test: k = {k_sel} down z rzędu")
# c1, c2, c3 = st.columns(3)
# c1.metric("Transakcji", f"{len(buy_days_k)}")
# c2.metric("Zwrot (k-down)", f"{ret_k:,.2f} %")
# c3.metric("Zwrot (losowo)", f"{ret_rnd:,.2f} %")
# st.metric("Buy-and-Hold", f"{bh_k:,.2f} %")
#
# # wykres
# fig_k = go.Figure()
# fig_k.add_scatter(x=df["Date"], y=df["Price"], mode="lines", name="Cena", line=dict(width=1.2))
# fig_k.add_scatter(x=df.loc[buy_days_k, "Date"], y=df.loc[buy_days_k, "Price"],
#                   mode="markers", name=f"Zakupy k={k_sel}", marker_symbol="triangle-down", marker_color="red", marker_size=8)
# fig_k.add_scatter(x=df.loc[rand_days_k, "Date"], y=df.loc[rand_days_k, "Price"],
#                   mode="markers", name="Losowe", marker_symbol="circle", marker_color="green", opacity=0.5, marker_size=8)
# fig_k.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=0))
# st.plotly_chart(fig_k, use_container_width=True)


# # ───────────────────────────────────────────────────────────
# # 10. MARKOV chains (1…K-rząd) + strategia „k-down buy”
# # ───────────────────────────────────────────────────────────
# st.header("🔄 Markov chain & k-down strategy")
#
# # 1️⃣ kolumna 'state'  (up / down)
# df["daily_ret"] = df["Price"].pct_change()
# df["state"] = np.where(df["daily_ret"] > 0, "up", "down")
#
# # ───────────────────────────────────────────────────────────
# # MARKOV rzędu 1…K
# # ───────────────────────────────────────────────────────────
# K_max = st.slider("Najwyższy rząd Markowa do analizy", 1, 7, 3, key="markov_K")
#
# from collections import Counter, defaultdict
# seq = df["state"].to_list()          # lista str: 'up' / 'down'
#
# # liczymy przejścia dla każdego rzędu 1…K_max
# markov_tables = {}
# for k in range(1, K_max + 1):
#     trans = Counter()
#     prev_counts = Counter()
#     for i in range(k, len(seq)):
#         prev = tuple(seq[i-k:i])     # sekwencja długości k
#         cur  = seq[i]                # stan następujący
#         trans[(prev, cur)] += 1
#         prev_counts[prev] += 1
#
#     # budujemy macierz prawdopodobieństw (DataFrame)
#     rows = []
#     for prev in prev_counts:
#         up_prob   = trans.get((prev, "up"),   0) / prev_counts[prev]
#         down_prob = trans.get((prev, "down"), 0) / prev_counts[prev]
#         rows.append({"prev_seq": " ".join(prev),
#                      "P→up": round(up_prob, 3),
#                      "P→down": round(down_prob, 3),
#                      "n_occur": prev_counts[prev]})
#     markov_tables[k] = pd.DataFrame(rows).set_index("prev_seq")
#
# # pokazujemy tabele
# with st.expander("📋 Macierze przejść"):
#     for k, tbl in markov_tables.items():
#         st.subheader(f"Rząd {k}")
#         st.dataframe(tbl, use_container_width=True, height=min(300, 30*len(tbl)))
#
# # ───────────────────────────────────────────────────────────
# # 2️⃣ Prawdopodobieństwo wzrostu po k kolejnych spadkach
# #    (to szczególny wiersz macierzy, gdzie prev = 'down'×k)
# # ───────────────────────────────────────────────────────────
# rows=[]
# for k in range(1, K_max + 1):
#     prev = ("down",)*k
#     total = markov_tables[k].loc[" ".join(prev),"n_occur"] if " ".join(prev) in markov_tables[k].index else 0
#     p_up  = markov_tables[k].loc[" ".join(prev),"P→up"]    if total else np.nan
#     rows.append({"k_down": k, "occurences": int(total), "prob_next_up": p_up})
# prob_df = pd.DataFrame(rows).set_index("k_down")
#
# st.subheader("🔑 P(wzrost | k spadków z rzędu)")
# st.dataframe(prob_df, height=200, use_container_width=True)


# # ───────────────────────────────────────────────────────────
# # 10. MARKOV chains (1…K-rząd) + strategia „k-down buy”
# # ───────────────────────────────────────────────────────────
# st.header("🔄 Markov chain & k-down strategy")
#
# # 0️⃣ zakres czasowy analizy
# start_date_mkv = st.date_input(
#     "Data początkowa (Markov)",
#     value=df["Date"].iloc[0].date(),
#     min_value=df["Date"].iloc[0].date(),
#     max_value=df["Date"].iloc[-2].date(),
#     key="date_markov",
# )
#
# # filtr danych
# df_mkv = df[df["Date"] >= pd.Timestamp(start_date_mkv)].copy()
# if len(df_mkv) < 50:
#     st.warning("Za mało danych po wybranej dacie – wybierz wcześniejszą.")
#     st.stop()
#
# # 1️⃣ kolumna ‘state’ (up / down) – tylko w wycinku
# df_mkv["daily_ret"] = df_mkv["Price"].pct_change()
# df_mkv["state"] = np.where(df_mkv["daily_ret"] > 0, "up", "down")
#
# # 2️⃣ rząd Markowa
# K_max = st.slider("Najwyższy rząd Markowa do analizy", 1, 7, 3, key="markov_K")
#
# from collections import Counter
# seq = df_mkv["state"].to_list()
#
# markov_tables = {}
# for k in range(1, K_max + 1):
#     trans, prev_counts = Counter(), Counter()
#     for i in range(k, len(seq)):
#         prev = tuple(seq[i - k : i])     # sekwencja długości k
#         cur  = seq[i]
#         trans[(prev, cur)] += 1
#         prev_counts[prev]  += 1
#
#     rows = []
#     for prev in prev_counts:
#         up_prob   = trans.get((prev, "up"),   0) / prev_counts[prev]
#         down_prob = trans.get((prev, "down"), 0) / prev_counts[prev]
#         rows.append({
#             "prev_seq": " ".join(prev),
#             "P→up":     round(up_prob, 3),
#             "P→down":   round(down_prob, 3),
#             "n_occur":  prev_counts[prev],
#         })
#     markov_tables[k] = pd.DataFrame(rows).set_index("prev_seq")
#
# # 3️⃣ wyświetlenie macierzy
# with st.expander(f"📋 Macierze przejść od {start_date_mkv:%Y-%m-%d}"):
#     for k, tbl in markov_tables.items():
#         st.subheader(f"Rząd {k}")
#         st.dataframe(tbl, use_container_width=True, height=min(300, 30*len(tbl)))
#
# # 4️⃣ P(wzrost | k spadków)   (prev = 'down'×k)
# rows = []
# for k in range(1, K_max + 1):
#     prev = ("down",) * k
#     key  = " ".join(prev)
#     total = markov_tables[k].loc[key, "n_occur"] if key in markov_tables[k].index else 0
#     p_up  = markov_tables[k].loc[key, "P→up"]    if total else np.nan
#     rows.append({"k_down": k, "occurences": int(total), "prob_next_up": p_up})
#
# prob_df = pd.DataFrame(rows).set_index("k_down")
# st.subheader("🔑 P(wzrost | k spadków z rzędu)")
# st.dataframe(prob_df, height=300, use_container_width=True)





# ───────────────────────────────────────────────────────────
# 10. MARKOV chains (1…K-rząd) + strategia „k-down buy”
# ───────────────────────────────────────────────────────────
st.header("🔄 Markov chain & k-down strategy")

# 0️⃣ zakres czasowy analizy
start_date_mkv = st.date_input(
    "Data początkowa (Markov)",
    value=df["Date"].iloc[0].date(),
    min_value=df["Date"].iloc[0].date(),
    max_value=df["Date"].iloc[-2].date(),
    key="date_markov",
)

# # filtr danych
# df_mkv = df[df["Date"] >= pd.Timestamp(start_date_mkv)].copy()
# if len(df_mkv) < 50:
#     st.warning("Za mało danych po wybranej dacie – wybierz wcześniejszą.")
#     st.stop()
#
# # 1️⃣ kolumna ‘state’ (up / down) – tylko w wycinku
# df_mkv["daily_ret"] = df_mkv["Price"].pct_change()
# df_mkv["state"] = np.where(df_mkv["daily_ret"] > 0, "up", "down")
#
# # 2️⃣ rząd Markowa
# K_max = st.slider("Najwyższy rząd Markowa do analizy", 1, 7, 3, key="markov_K")
#
# from collections import Counter
# seq = df_mkv["state"].to_list()
#
# markov_tables = {}
# for k in range(1, K_max + 1):
#     trans, prev_counts = Counter(), Counter()
#     for i in range(k, len(seq)):
#         prev = tuple(seq[i - k : i])     # sekwencja długości k
#         cur  = seq[i]
#         trans[(prev, cur)] += 1
#         prev_counts[prev]  += 1
#
#     rows = []
#     for prev in prev_counts:
#         up_prob   = trans.get((prev, "up"),   0) / prev_counts[prev]
#         down_prob = trans.get((prev, "down"), 0) / prev_counts[prev]
#         rows.append({
#             "prev_seq": " ".join(prev),
#             "P→up":     round(up_prob, 3),
#             "P→down":   round(down_prob, 3),
#             "n_occur":  prev_counts[prev],
#         })
#     markov_tables[k] = pd.DataFrame(rows).set_index("prev_seq")
#
# # 3️⃣ wyświetlenie macierzy
# with st.expander(f"📋 Macierze przejść od {start_date_mkv:%Y-%m-%d}"):
#     for k, tbl in markov_tables.items():
#         st.subheader(f"Rząd {k}")
#         st.dataframe(tbl, use_container_width=True, height=min(300, 30*len(tbl)))
#
# # # 4️⃣ P(wzrost | k spadków)   (prev = 'down'×k)
# # rows = []
# # for k in range(1, K_max + 1):
# #     prev = ("down",) * k
# #     key  = " ".join(prev)
# #     total = markov_tables[k].loc[key, "n_occur"] if key in markov_tables[k].index else 0
# #     p_up  = markov_tables[k].loc[key, "P→up"]    if total else np.nan
# #     rows.append({"k_down": k, "occurences": int(total), "prob_next_up": p_up})
# #
# # prob_df = pd.DataFrame(rows).set_index("k_down")
# # st.subheader("🔑 P(wzrost | k spadków z rzędu)")
# # st.dataframe(prob_df, height=300, use_container_width=True)
#
# # 4️⃣ Statystyka kolejnej świecy po k spadkach z rzędu
# # ───────────────────────────────────────────────────────────
# down_vec = (df_mkv["state"] == "down").astype(int)   # 1 = down
#
# rows = []
# for k in range(1, K_max + 1):
#     # indeksy, w których poprzednie k dni = down (patrzymy na dzień t)
#     prev_down = down_vec.shift(1).rolling(k, min_periods=k).sum() == k
#     idx       = prev_down[prev_down].index + 1                     # dzień PO sekwencji
#     idx       = idx[idx < df_mkv.index[-1]]                        # nie wychodzimy poza zakres
#
#     n_total = len(idx)
#     if n_total == 0:
#         rows.append({"k_down": k, "occurences": 0,
#                      "prob_next_up": np.nan, "prob_next_down": np.nan,
#                      "avg_up_ret_%": np.nan, "avg_down_ret_%": np.nan})
#         continue
#
#     ret_next = df_mkv["daily_ret"].iloc[idx] * 100   # procenty
#     up_mask  = ret_next > 0
#
#     n_up   = int(up_mask.sum())
#     n_down = n_total - n_up
#
#     rows.append({
#         "k_down":         k,
#         "occurences":     n_total,
#         "prob_next_up":   round(n_up   / n_total, 3),
#         "prob_next_down": round(n_down / n_total, 3),
#         "avg_up_ret_%":   round(ret_next[up_mask].mean(), 3)  if n_up   else np.nan,
#         "avg_down_ret_%": round(ret_next[~up_mask].mean(), 3) if n_down else np.nan,
#     })
#
# prob_df = (
#     pd.DataFrame(rows)
#       .set_index("k_down")
#       .rename_axis("k (kolejne spadki)")
# )
#
# st.subheader(f"🔑 Statystyka kolejnej świecy (od {start_date_mkv:%Y-%m-%d})")
# st.dataframe(prob_df, height=300, use_container_width=True)

# ───────────────────────────────────────────────────────────
# 0️⃣ filtr danych + reset_index  ➜ indeks = 0…N-1
# ───────────────────────────────────────────────────────────
df_mkv = (
    df[df["Date"] >= pd.Timestamp(start_date_mkv)]
      .copy()
      .reset_index(drop=True)          # <–– KLUCZOWE
)
if len(df_mkv) < 50:
    st.warning("Za mało danych po wybranej dacie – wybierz wcześniejszą.")
    st.stop()

# 1️⃣ kolumny pomocnicze
df_mkv["daily_ret"] = df_mkv["Price"].pct_change()
df_mkv["state"]     = np.where(df_mkv["daily_ret"] > 0, "up", "down")
down_vec            = (df_mkv["state"] == "down").astype(int)  # 1=down,0=up

# 2️⃣ rząd Markowa
K_max = st.slider("Najwyższy rząd Markowa do analizy", 1, 7, 3, key="markov_K")

# ----------  MACIERZE PRZEJŚĆ  ----------
from collections import Counter
seq = df_mkv["state"].to_list()

markov_tables = {}
for k in range(1, K_max + 1):
    trans, prev_counts = Counter(), Counter()
    for i in range(k, len(seq)):
        prev = tuple(seq[i - k : i])
        cur  = seq[i]
        trans[(prev, cur)] += 1
        prev_counts[prev]  += 1

    rows = []
    for prev in prev_counts:
        up_prob   = trans.get((prev, "up"),   0) / prev_counts[prev]
        down_prob = trans.get((prev, "down"), 0) / prev_counts[prev]
        rows.append({
            "prev_seq": " ".join(prev),
            "P→up":     round(up_prob, 3),
            "P→down":   round(down_prob, 3),
            "n_occur":  prev_counts[prev],
        })
    markov_tables[k] = pd.DataFrame(rows).set_index("prev_seq")

with st.expander(f"📋 Macierze przejść od {start_date_mkv:%Y-%m-%d}"):
    for k, tbl in markov_tables.items():
        st.subheader(f"Rząd {k}")
        st.dataframe(tbl, use_container_width=True,
                     height=min(300, 30*len(tbl)))

# ----------  STATYSTYKA NASTĘPNEJ ŚWIECY  ----------
rows = []
for k in range(1, K_max + 1):

    # dzień t: poprzednie k sesji (t-k … t-1) były „down”
    streak = down_vec.shift(1).rolling(k, min_periods=k).sum() == k
    idx    = streak[streak].index                 # ⟵ bez +1  (dzień bezpośrednio po sekwencji)

    n_total = len(idx)
    if n_total == 0:
        rows.append({"k_down": k, "occurences": 0,
                     "prob_next_up": np.nan, "prob_next_down": np.nan,
                     "avg_up_ret_%": np.nan, "avg_down_ret_%": np.nan})
        continue

    ret_next = df_mkv["daily_ret"].iloc[idx] * 100
    up_mask  = ret_next > 0

    n_up   = int(up_mask.sum())
    n_down = n_total - n_up

    rows.append({
        "k_down":         k,
        "occurences":     n_total,
        "prob_next_up":   round(n_up   / n_total, 3),
        "prob_next_down": round(n_down / n_total, 3),
        "avg_up_ret_%":   round(ret_next[up_mask].mean(), 3)  if n_up   else np.nan,
        "avg_down_ret_%": round(ret_next[~up_mask].mean(), 3) if n_down else np.nan,
    })

prob_df = (
    pd.DataFrame(rows)
      .set_index("k_down")
      .rename_axis("k (kolejne spadki)")
)

st.subheader(f"Statystyka kolejnej świecy (od {start_date_mkv:%Y-%m-%d})")
st.dataframe(prob_df, height=300, use_container_width=True)






# ───────────────────────────────────────────────────────────
# 3️⃣ back-test strategii „kup po k-down”
# ───────────────────────────────────────────────────────────
st.header("🎛️ k-down back-test")

start_date_k = st.date_input(
    "Data początkowa (k-down)",
    value=df["Date"].iloc[0].date(),
    min_value=df["Date"].iloc[0].date(),
    max_value=df["Date"].iloc[-2].date(),
    key="date_kdown",
)

k_sel       = st.slider("k (liczba kolejnych spadków)", 1, K_max, 3, key="k_sel")
n_trades_k  = st.slider("Liczba transakcji", 10, 500, 100, 10, key="n_k")
usd_k       = st.slider("Kwota jednej transakcji [$]", 10, 1000, 100, 10, key="usd_k")

# ── 1. wycinek danych od daty start  ───────────────────────
df_k = df[df["Date"] >= pd.Timestamp(start_date_k)].copy()
if df_k.empty:
    st.warning("W wybranym okresie brak danych.")
    st.stop()

df_k["daily_ret"] = df_k["Price"].pct_change()
df_k["state"]     = np.where(df_k["daily_ret"] > 0, "up", "down")

down_vec = (df_k["state"] == "down").astype(int)   # 1 = down, 0 = up

def kdown_signal(k: int) -> np.ndarray:
    """Indeksy sesji, w których poprzednie k dni = down (kup dzień *po* sekwencji)."""
    streak = down_vec.shift(1).rolling(k).sum()   # ile 'down' w oknie kończącym się w t-1
    cond   = streak == k
    idx    = cond[cond].index + 1                 # następny dzień po sekwencji
    return idx[idx < df_k.index[-1]]              # nie wychodzimy poza zakres

def random_days(n: int) -> np.ndarray:
    elig = df_k.index
    return np.random.default_rng(123).choice(elig, size=n, replace=False)

candidates = kdown_signal(k_sel)
if len(candidates) == 0:
    st.warning("Brak sekwencji spełniających warunek w wybranym okresie.")
    st.stop()

rng = np.random.default_rng(42)
buy_days_k  = np.sort(rng.choice(candidates, size=min(n_trades_k, len(candidates)), replace=False))
rand_days_k = random_days(len(buy_days_k))

def buy_and_hold(dates, amount):
    prices = df_k.loc[dates, "Price"].values
    shares = amount / prices
    return shares.sum() * df_k["Price"].iloc[-1]

# ── 2. wycena portfeli  ───────────────────────────────────
port_k   = buy_and_hold(buy_days_k,  usd_k)
port_rnd = buy_and_hold(rand_days_k, usd_k)
total_k  = len(buy_days_k) * usd_k

ret_k   = (port_k  / total_k - 1) * 100
ret_rnd = (port_rnd / total_k - 1) * 100
bh_ret  = (df_k["Price"].iloc[-1] / df_k["Price"].iloc[0] - 1) * 100

# ── 3. metryki  ────────────────────────────────────────────
st.subheader(f"Backtest: k = {k_sel} spadków z rzędu")
c1, c2, c3 = st.columns(3)
c1.metric("Transakcji", f"{len(buy_days_k)}")
c2.metric("Zwrot (k-down)", f"{ret_k:,.2f} %")
c3.metric("Zwrot (losowo)", f"{ret_rnd:,.2f} %")
st.metric("Buy-and-Hold", f"{bh_ret:,.2f} %")

# ── 4. wykres świecowy z markerami  ───────────────────────
fig_k = go.Figure()

fig_k.add_trace(
    go.Candlestick(
        x=df_k["Date"], open=df_k["Open"], high=df_k["High"],
        low=df_k["Low"], close=df_k["Price"],
        increasing_line_color="#2ca02c",
        decreasing_line_color="#d62728",
        name="Świece", showlegend=False,
    )
)

fig_k.add_scatter(
    x=df_k.loc[buy_days_k, "Date"],  y=df_k.loc[buy_days_k, "Price"],
    mode="markers", name=f"Zakupy k={k_sel}",
    marker_symbol="triangle-down", marker_color="yellow", marker_size=9,
)

fig_k.add_scatter(
    x=df_k.loc[rand_days_k, "Date"], y=df_k.loc[rand_days_k, "Price"],
    mode="markers", name="Losowe",
    marker_symbol="circle", marker_color="white", marker_size=9, opacity=0.6,
)

fig_k.update_layout(
    height=500, margin=dict(l=0, r=0, t=40, b=0),
    xaxis_rangeslider_visible=False, legend_title_text="Serie",
)
st.plotly_chart(fig_k, use_container_width=True)

# # ───────────────────────────────────────────────────────────
# # 3️⃣ back-test strategii „kup po k-down”
# # ───────────────────────────────────────────────────────────
# st.sidebar.header("🎛️ k-down back-test")
#
# start_date_k = st.sidebar.date_input(
#     "Data początkowa (k-down)",
#     value=df["Date"].iloc[0].date(),
#     min_value=df["Date"].iloc[0].date(),
#     max_value=df["Date"].iloc[-2].date(),
#     key="date_kdown",
# )
# k_sel = st.sidebar.slider("k (liczba spadków)", 1, K_max, 3, key="k_sel")
# n_trades_k = st.sidebar.slider("Liczba transakcji", 10, 500, 100, 10, key="n_k")
# usd_k = st.sidebar.slider("Kwota jednej transakcji [$]", 10, 1000, 100, 10, key="usd_k")
#
# # pomocnicze: wektor 1 gdy down, 0 gdy up
# down_vec = (df["state"] == "down").astype(int)
#
# def kdown_signal(k, start_dt):
#     """Zwraca indeksy sesji, w których poprzednie k dni to down (kup następnego dnia)."""
#     streak = down_vec.shift(1).rolling(k).sum()   # ile 'down' w oknie
#     cond   = (streak == k) & (df["Date"] >= pd.Timestamp(start_dt))
#     idx    = cond[cond].index + 1                 # sesja następna po sekwencji
#     return idx[idx < len(df)]
#
# def random_days(n, start_dt):
#     elig = df[df["Date"] >= pd.Timestamp(start_dt)].index
#     return np.random.default_rng(123).choice(elig, size=n, replace=False)
#
# candidates = kdown_signal(k_sel, start_date_k)
# if len(candidates) == 0:
#     st.warning("Brak sekwencji spełniających warunek w wybranym okresie.")
#     st.stop()
#
# rng = np.random.default_rng(42)
# buy_days_k = np.sort(rng.choice(candidates, size=min(n_trades_k, len(candidates)), replace=False))
# rand_days_k = random_days(len(buy_days_k), start_date_k)
#
# def buy_and_hold(dates, amt):
#     prices = df.loc[dates, "Price"].values
#     shares = amt / prices
#     return shares.sum() * df["Price"].iloc[-1]
#
# port_k   = buy_and_hold(buy_days_k, usd_k)
# port_rnd = buy_and_hold(rand_days_k, usd_k)
# total_k  = len(buy_days_k) * usd_k
#
# ret_k   = (port_k / total_k - 1) * 100
# ret_rnd = (port_rnd / total_k - 1) * 100
# bh_ret  = (df["Price"].iloc[-1] / df.loc[df["Date"] >= pd.Timestamp(start_date_k),"Price"].iloc[0] - 1)*100
#
# # wyniki
# st.subheader(f"📈 Back-test k={k_sel} down z rzędu")
# c1,c2,c3 = st.columns(3)
# c1.metric("Transakcji", f"{len(buy_days_k)}")
# c2.metric("Zwrot (k-down)", f"{ret_k:,.2f} %")
# c3.metric("Zwrot (losowo)", f"{ret_rnd:,.2f} %")
# st.metric("Buy-and-Hold", f"{bh_ret:,.2f} %")
#
# # # wykres
# # fig_k = go.Figure()
# # fig_k.add_scatter(x=df["Date"], y=df["Price"], mode="lines", name="Cena", line=dict(width=1.2))
# # fig_k.add_scatter(x=df.loc[buy_days_k, "Date"], y=df.loc[buy_days_k, "Price"],
# #                   mode="markers", name=f"Zakupy k={k_sel}", marker_symbol="triangle-down",
# #                   marker_color="red", marker_size=8)
# # fig_k.add_scatter(x=df.loc[rand_days_k, "Date"], y=df.loc[rand_days_k, "Price"],
# #                   mode="markers", name="Losowe", marker_symbol="circle",
# #                   marker_color="green", opacity=0.5, marker_size=8)
# # fig_k.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=0))
# # st.plotly_chart(fig_k, use_container_width=True)
#
# # ───────────────────────────────────────────────────────────
# # wykres świecowy + markery zakupów
# # ───────────────────────────────────────────────────────────
# fig_k = go.Figure()
#
# # 1️⃣ świece 1-dniowe
# fig_k.add_trace(
#     go.Candlestick(
#         x=df["Date"],
#         open=df["Open"],
#         high=df["High"],
#         low=df["Low"],
#         close=df["Price"],            # Price = Close
#         name="Świece",
#         increasing_line_color="#2ca02c",
#         decreasing_line_color="#d62728",
#         showlegend=False,
#     )
# )
#
# # 2️⃣ markery strategii k-down
# fig_k.add_scatter(
#     x=df.loc[buy_days_k,  "Date"],
#     y=df.loc[buy_days_k,  "Price"],
#     mode="markers",
#     name=f"Zakupy k={k_sel}",
#     marker_symbol="triangle-down",
#     marker_color="yellow",
#     marker_size=9,
# )
#
# # 3️⃣ markery losowe
# fig_k.add_scatter(
#     x=df.loc[rand_days_k, "Date"],
#     y=df.loc[rand_days_k, "Price"],
#     mode="markers",
#     name="Zakupy losowe",
#     marker_symbol="circle",
#     marker_color="white",
#     marker_size=9,
#     opacity=0.6,
# )
#
# fig_k.update_layout(
#     height=500,
#     margin=dict(l=0, r=0, t=40, b=0),
#     xaxis_rangeslider_visible=False,        # bez rangeslidera
#     legend_title_text="Serie",
# )
# st.plotly_chart(fig_k, use_container_width=True)





# ───────────────────────────────────────────────────────────
# 🤖 ML: Predykcja kierunku następnego dnia (UP/DOWN)
# ───────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    roc_auc_score, confusion_matrix, roc_curve
)

st.header("🤖 Predykcja D+1: czy jutro indeks wzrośnie?")

with st.expander("🧱 Założenia & jak to liczymy", expanded=False):
    st.markdown("""
    - **Etykieta**: `target_up = 1` jeśli `Price_{t+1} > Price_t`, inaczej `0`.
    - **Uwaga na czas**: **bez tasowania**, rozdział trening/test po dacie.
    - **Brak wycieku**: cechy liczone wyłącznie z danych dostępnych do dnia *t*.
    - **Modele**: Regresja logistyczna (skalowanie) lub Random Forest (bez skalowania).
    """)

# 1) Inżynieria etykiety i cech
df_ml = df.copy()

# etykieta: wzrost jutro?
df_ml["target_up"] = (df_ml["Price"].shift(-1) > df_ml["Price"]).astype(int)

# pomocnicze zwroty (do ewaluacji strategii na teście)
df_ml["ret_next"] = df_ml["Price"].shift(-1) / df_ml["Price"] - 1  # zwrot od t do t+1

# zbiór cech – dopasowany do Twojej tabeli (bierze tylko kolumny, które istnieją)
preferred_features = [
    "daily_return_pct",     # dzisiejszy % zwrot
    "vol_30d_ann",
    "return_1y_pct",
    "pct_from_ATH",
    "drawdown_pct",
    "ulcer_252d",
    "roll_sharpe",
    "roll_sortino",
    "dist_from_SMA_50_pct",
    "dist_from_SMA_100_pct",
    "dist_from_SMA_200_pct",
    # możesz dodać "EMA_50", "EMA_100", "EMA_200" itd., ale unikam 'Price' by nie wprowadzać trendu nominalnego
]
available = [c for c in preferred_features if c in df_ml.columns]

st.subheader("🎛️ Ustawienia modelu")
colA, colB = st.columns(2)
features_chosen = colA.multiselect(
    "Wybierz cechy wejściowe",
    options=available,
    default=available,
    help="Zalecane jest zostawienie domyślnego zestawu."
)

model_name = colB.selectbox(
    "Model",
    ["Logistic Regression (L2)", "Random Forest"],
)

colC, colD = st.columns(2)
# rozdział po dacie: test = [test_start, ...]
min_d, max_d = df_ml["Date"].iloc[0].date(), df_ml["Date"].iloc[-2].date()
test_start = colC.date_input(
    "Data startu zbioru testowego",
    value=max_d.replace(year=max_d.year-5) if (max_d.year - min_d.year) > 6 else max_d,  # ~5 lat testu gdy się da
    min_value=min_d, max_value=max_d
)

threshold = colD.slider(
    "Próg decyzyjny (P(up) ≥ próg ⇒ kup)",
    min_value=0.05, max_value=0.95, value=0.50, step=0.05
)

# parametry modeli
if model_name == "Logistic Regression (L2)":
    C_val = st.slider("C (siła regularizacji, wyższe = słabsza)", 0.01, 5.0, 1.0, 0.01)
    use_balanced = st.checkbox("class_weight='balanced' (gdy klasy nierówne)", value=True)
else:
    n_estimators = st.slider("RandomForest: liczba drzew", 100, 1000, 400, 50)
    max_depth    = st.slider("RandomForest: max_depth (None = brak)", 2, 20, 8, 1)
    use_balanced = st.checkbox("class_weight='balanced_subsample'", value=True)

# 2) Filtr zakresu czasu i czyszczenie
mask_train = df_ml["Date"] < pd.Timestamp(test_start)
mask_test  = df_ml["Date"] >= pd.Timestamp(test_start)

X = df_ml[features_chosen].replace([np.inf, -np.inf], np.nan)
y = df_ml["target_up"]

# usuwamy wiersze z NaN w cechach (na początku okresy SMA/EMA bywają puste)
valid = X.notna().all(axis=1) & y.notna()
X, y = X[valid], y[valid]
dates = df_ml.loc[valid, "Date"]
ret_next = df_ml.loc[valid, "ret_next"]

train_idx = dates < pd.Timestamp(test_start)
test_idx  = dates >= pd.Timestamp(test_start)

if train_idx.sum() < 200 or test_idx.sum() < 50:
    st.warning("⚠️ Za mało danych po wybranej dacie. Przesuń `Data startu zbioru testowego`.")
    st.stop()

X_train, y_train = X[train_idx], y[train_idx]
X_test,  y_test  = X[test_idx],  y[test_idx]
ret_next_test    = ret_next[test_idx]
dates_test       = dates[test_idx]

# 3) Pipeline (skalowanie tylko dla regresji logistycznej)
if model_name == "Logistic Regression (L2)":
    pre = ColumnTransformer([("num", StandardScaler(), features_chosen)], remainder="drop")
    clf = LogisticRegression(
        max_iter=2000,
        C=C_val,
        class_weight=("balanced" if use_balanced else None),
        n_jobs=None,
        solver="lbfgs"
    )
    pipe = Pipeline([("prep", pre), ("model", clf)])
else:
    # RF nie wymaga skalowania
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=None if max_depth is None else max_depth,
        class_weight=("balanced_subsample" if use_balanced else None),
        random_state=42,
        n_jobs=-1
    )
    pipe = Pipeline([("model", clf)])

# 4) Prosty TimeSeries CV (opcjonalny pogląd stabilności)
with st.expander("🧪 Walidacja szeregowa (TimeSeriesSplit)", expanded=False):
    splits = st.slider("Liczba podziałów (k)", 3, 8, 5)
    tscv = TimeSeriesSplit(n_splits=splits)
    accs = []
    for fold, (tr, va) in enumerate(tscv.split(X_train), 1):
        pipe.fit(X_train.iloc[tr], y_train.iloc[tr])
        p = pipe.predict_proba(X_train.iloc[va])[:, 1] if hasattr(pipe[-1], "predict_proba") else pipe.predict(X_train.iloc[va])
        y_hat = (p >= 0.5).astype(int) if p.ndim == 1 or p.max() <= 1 else (p >= 0.5).astype(int)
        accs.append(accuracy_score(y_train.iloc[va], y_hat))
    st.write(f"Średnia accuracy (CV): **{np.mean(accs):.3f} ± {np.std(accs):.3f}**")

# 5) Trening na pełnym train i ewaluacja na teście
pipe.fit(X_train, y_train)

# predykcja proba → klasy wg progu
proba_test = pipe.predict_proba(X_test)[:, 1] if hasattr(pipe[-1], "predict_proba") else pipe.predict(X_test)
y_pred = (proba_test >= threshold).astype(int)

acc = accuracy_score(y_test, y_pred)
prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary", zero_division=0)
try:
    auc = roc_auc_score(y_test, proba_test)
except Exception:
    auc = float("nan")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Accuracy", f"{acc:.3f}")
c2.metric("Precision", f"{prec:.3f}")
c3.metric("Recall", f"{rec:.3f}")
c4.metric("F1", f"{f1:.3f}")
c5.metric("ROC-AUC", f"{auc:.3f}" if not np.isnan(auc) else "–")

# balans klas na teście
up_rate = y_test.mean()
st.caption(f"Balans klas (test): UP = **{up_rate:.1%}**, DOWN = **{1-up_rate:.1%}**  |  Test od: **{pd.Timestamp(test_start).date()}**")

# 6) Macierz pomyłek
cm = confusion_matrix(y_test, y_pred, labels=[0,1])
fig_cm = px.imshow(
    cm, text_auto=True, aspect="auto",
    labels=dict(x="Prognoza", y="Rzeczywistość", color="Liczba"),
    x=["DOWN","UP"], y=["DOWN","UP"], title="Macierz pomyłek (test)"
)
fig_cm.update_layout(margin=dict(l=0,r=0,t=40,b=0), height=350)
st.plotly_chart(fig_cm, use_container_width=True)

# 7) ROC
if not np.isnan(auc):
    fpr, tpr, _ = roc_curve(y_test, proba_test)
    fig_roc = go.Figure()
    fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines", name=f"ROC (AUC={auc:.3f})"))
    fig_roc.add_trace(go.Scatter(x=[0,1], y=[0,1], mode="lines", name="losowo", line=dict(dash="dash")))
    fig_roc.update_layout(title="Krzywa ROC (test)", xaxis_title="FPR", yaxis_title="TPR",
                          height=350, margin=dict(l=0,r=0,t=40,b=0))
    st.plotly_chart(fig_roc, use_container_width=True)

# 8) Wgląd w „ważność” cech
with st.expander("🔎 Wpływ cech / współczynniki", expanded=False):
    if model_name == "Logistic Regression (L2)":
        # wyciągamy współczynniki po skalowaniu
        lr = pipe[-1]
        scaler = pipe[0].named_transformers_["num"]
        coefs = pd.Series(lr.coef_[0], index=features_chosen)
        coef_df = coefs.sort_values(key=lambda s: s.abs(), ascending=False).to_frame("coef")
        st.dataframe(coef_df.style.format("{:.3f}"), use_container_width=True, height=260)
        st.caption("Współczynniki >0 zwiększają P(UP), <0 zmniejszają – po standaryzacji cech.")
    else:
        rf = pipe[-1]
        imp_df = pd.Series(rf.feature_importances_, index=features_chosen).sort_values(ascending=False).to_frame("importance")
        st.dataframe(imp_df.style.format("{:.3f}"), use_container_width=True, height=260)

# 9) Prosta strategia kierunkowa na teście (kup = 1 gdy P(up)≥próg)
strat_ret = (y_pred * ret_next_test).fillna(0.0)
bh_ret    = ret_next_test.fillna(0.0)  # buy&hold 1x

eq_model = (1 + strat_ret).cumprod()
eq_bh    = (1 + bh_ret).cumprod()

fig_eq = go.Figure()
fig_eq.add_scatter(x=dates_test, y=eq_bh,    mode="lines", name="Buy&Hold (1x)")
fig_eq.add_scatter(x=dates_test, y=eq_model, mode="lines", name=f"Model (próg={threshold:.2f})")
fig_eq.update_layout(title="Krzywa kapitału – test", height=420,
                     margin=dict(l=0,r=0,t=50,b=0), legend_title_text="")
st.plotly_chart(fig_eq, use_container_width=True)

cA, cB = st.columns(2)
cA.metric("CAGR (model, test)", f"{(eq_model.iloc[-1]**(252/len(eq_model)) - 1)*100:,.2f} %")
cB.metric("CAGR (B&H, test)",   f"{(eq_bh.iloc[-1]**(252/len(eq_bh)) - 1)*100:,.2f} %")

st.caption("""
To **nie** jest porada inwestycyjna. Model uczy się na danych historycznych i może przeuczać się lub
dawać złudnie dobre wyniki w określonych okresach. Rozważ **walk-forward** i regularną re-walidację.
""")
