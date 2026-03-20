"""
CFTC COT Monitor — Streamlit Dashboard

Run with:  streamlit run src/dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd
import numpy as np

from src.storage.db import (
    init_db,
    get_legacy_df,
    get_disaggregated_df,
    get_financial_df,
    get_latest_signals,
)
from src.config import WATCHED_MARKETS, PRICE_TICKERS, COT_INDEX_LOOKBACK

# ── Sector grouping (mirrors WATCHED_MARKETS order) ───────────────────────────
SECTOR_GROUPS: dict[str, list[str]] = {
    "Grains":    ["002602", "001602", "0006KW", "001612", "005602",
                  "007601", "026603", "004603", "039601"],
    "Softs":     ["033661", "083731", "080732", "073732", "040701"],
    "Livestock": ["057642", "061642", "054642", "052641"],
    "Energy":    ["067651", "06765T", "023651", "022651", "111659"],
    "Metals":    ["088691", "084691", "085692", "076651", "075651"],
    "Equities":  ["13874A", "209742", "12460+", "239742", "1170E1"],
    "Rates":     ["020601", "043602", "044601", "042601", "045601", "132741"],
    "FX":        ["099741", "097741", "096742", "092741", "090741",
                  "232741", "095741", "112741", "102741", "089741"],
    "Crypto":    ["133741", "146021", "133742"],
}

def _code_to_sector(code: str) -> str:
    for sector, codes in SECTOR_GROUPS.items():
        if code in codes:
            return sector
    return "Other"
from src.analyzer.positioning import compute_legacy_metrics, compute_disagg_metrics, compute_financial_metrics
from src.analyzer.sentiment import add_sentiment
from src.analyzer.multi_asset import build_cot_index_panel, correlation_matrix, risk_on_off_indicator
from src.dashboard.charts import (
    cot_index_chart,
    net_position_chart,
    dual_positioning_chart,
    correlation_heatmap,
    backtest_cumulative_return_chart,
    signal_strength_gauge,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CFTC COT Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Init DB
init_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("CFTC COT Monitor")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Market Overview", "Positioning Analysis", "Signals & Alerts",
     "Backtesting", "Multi-Asset Analysis"],
)

sector_choice = st.sidebar.selectbox(
    "Sector", ["All"] + list(SECTOR_GROUPS.keys()), index=0
)
if sector_choice == "All":
    filtered_markets = WATCHED_MARKETS
else:
    sector_codes = SECTOR_GROUPS.get(sector_choice, [])
    filtered_markets = {k: v for k, v in WATCHED_MARKETS.items() if k in sector_codes}

market_options = {v: k for k, v in filtered_markets.items()}  # name → code
selected_market_name = st.sidebar.selectbox(
    "Market", list(market_options.keys()), index=0
)
selected_code = market_options[selected_market_name]

lookback_options = {
    "1 Year (52w)": 52,
    "2 Years (104w)": 104,
    "3 Years (156w)": 156,
}
lookback_label = st.sidebar.selectbox("COT Index Lookback", list(lookback_options.keys()), index=2)
lookback = lookback_options[lookback_label]

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data from CFTC"):
    with st.spinner("Fetching latest COT data..."):
        try:
            from src.fetcher.cot_fetcher import fetch_latest_legacy, fetch_latest_disaggregated, fetch_latest_financial
            from src.parser.cot_parser import parse_legacy_rows, parse_disaggregated_rows, parse_financial_rows
            from src.storage.db import upsert_legacy, upsert_disaggregated, upsert_financial

            n1 = upsert_legacy(parse_legacy_rows(fetch_latest_legacy(weeks=8)))
            n2 = upsert_disaggregated(parse_disaggregated_rows(fetch_latest_disaggregated(weeks=8)))
            n3 = upsert_financial(parse_financial_rows(fetch_latest_financial(weeks=8)))
            st.sidebar.success(f"Updated: +{n1} legacy, +{n2} disagg, +{n3} TFF rows")
        except Exception as e:
            st.sidebar.error(f"Fetch failed: {e}")

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_legacy(code: str, limit: int = 600) -> pd.DataFrame:
    df = get_legacy_df(code, limit)
    if df.empty:
        return df
    return compute_legacy_metrics(df, lookback=lookback)


@st.cache_data(ttl=3600)
def load_disagg(code: str, limit: int = 600) -> pd.DataFrame:
    df = get_disaggregated_df(code, limit)
    if df.empty:
        return df
    return compute_disagg_metrics(df, lookback=lookback)


@st.cache_data(ttl=3600)
def load_financial(code: str, limit: int = 600) -> pd.DataFrame:
    df = get_financial_df(code, limit)
    if df.empty:
        return df
    return compute_financial_metrics(df, lookback=lookback)


def no_data_warning(report_type: str = ""):
    st.warning(
        f"No data available{' for ' + report_type if report_type else ''}. "
        "Use the **Refresh Data** button in the sidebar to download COT data from CFTC, "
        "or run `python main.py backfill` to load historical data."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Market Overview
# ═══════════════════════════════════════════════════════════════════════════════

if page == "Market Overview":
    st.title("Market Overview — COT Positioning Snapshot")
    st.caption("Non-commercial (speculator) positioning percentile across all watched markets")

    # Build full summary once
    summary_rows = []
    for code, name in WATCHED_MARKETS.items():
        df = get_legacy_df(code, limit=COT_INDEX_LOOKBACK + 20)
        if df.empty or len(df) < 26:
            continue
        df = compute_legacy_metrics(df, lookback=lookback)
        if df.empty:
            continue
        row = df.iloc[-1]
        idx    = row.get("noncomm_cot_index")
        net    = row.get("noncomm_net")
        chg1w  = row.get("noncomm_net_chg1w")
        streak = row.get("noncomm_momentum_streak", 0)
        if idx is None or (isinstance(idx, float) and np.isnan(idx)):
            continue
        if idx >= 80:
            sentiment = "🔴 Extreme Long"
        elif idx >= 65:
            sentiment = "🟠 Crowded Long"
        elif idx <= 20:
            sentiment = "🟢 Extreme Short"
        elif idx <= 35:
            sentiment = "🔵 Crowded Short"
        else:
            sentiment = "⚪ Neutral"
        summary_rows.append({
            "Market":       name,
            "Code":         code,
            "Sector":       _code_to_sector(code),
            "COT Index":    round(idx, 1),
            "Net Position": int(net) if net is not None else None,
            "Chg 1W":       int(chg1w) if chg1w is not None else None,
            "Streak (wks)": int(streak),
            "Sentiment":    sentiment,
            "Report Date":  str(row.get("report_date", ""))[:10],
        })

    if not summary_rows:
        no_data_warning("overview")
    else:
        import plotly.express as px
        summary_df = pd.DataFrame(summary_rows)

        # ── Top: extreme signals callout ──────────────────────────────────────
        extremes = summary_df[
            (summary_df["COT Index"] >= 80) | (summary_df["COT Index"] <= 20)
        ].sort_values("COT Index", ascending=False)
        if not extremes.empty:
            st.markdown(f"**{len(extremes)} extreme signals detected:**")
            cols = st.columns(min(len(extremes), 4))
            for i, (_, r) in enumerate(extremes.iterrows()):
                with cols[i % 4]:
                    delta_color = "inverse" if r["COT Index"] >= 80 else "normal"
                    st.metric(
                        r["Market"],
                        f"{r['COT Index']:.0f}th pct",
                        delta=r["Sentiment"],
                        delta_color="off",
                    )
            st.markdown("---")

        # ── Sector tabs ───────────────────────────────────────────────────────
        sector_names = list(SECTOR_GROUPS.keys())
        tabs = st.tabs(["All"] + sector_names)

        def _render_sector_view(df_sect: pd.DataFrame):
            df_sect = df_sect.sort_values("COT Index", ascending=False)
            # Table
            st.dataframe(
                df_sect.drop(columns=["Code", "Sector"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "COT Index": st.column_config.ProgressColumn(
                        "COT Index", min_value=0, max_value=100, format="%.1f"
                    ),
                },
            )
            # Bar chart – horizontal so long market names don't overlap
            fig = px.bar(
                df_sect,
                x="COT Index", y="Market",
                orientation="h",
                color="COT Index",
                color_continuous_scale=["#00c853", "#90a4ae", "#d50000"],
                range_color=[0, 100],
                title="COT Index by Market",
            )
            fig.add_vline(x=80, line_dash="dash", line_color="#d50000",
                          annotation_text="80", annotation_position="top")
            fig.add_vline(x=20, line_dash="dash", line_color="#00c853",
                          annotation_text="20", annotation_position="top")
            fig.update_layout(
                height=max(300, len(df_sect) * 30 + 80),
                showlegend=False,
                margin=dict(l=10, r=40, t=50, b=30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with tabs[0]:  # All
            _render_sector_view(summary_df)

        for i, sector in enumerate(sector_names):
            with tabs[i + 1]:
                sect_df = summary_df[summary_df["Sector"] == sector]
                if sect_df.empty:
                    st.info(f"No data for {sector}")
                else:
                    _render_sector_view(sect_df)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Positioning Analysis
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Positioning Analysis":
    st.title(f"Positioning Analysis — {selected_market_name}")

    tab1, tab2, tab3 = st.tabs(["Legacy COT", "Disaggregated COT", "Financial (TFF)"])

    # Legacy
    with tab1:
        df = load_legacy(selected_code)
        if df.empty:
            no_data_warning("Legacy COT")
        else:
            df["report_date"] = pd.to_datetime(df["report_date"])

            col1, col2, col3 = st.columns(3)
            latest = df.iloc[-1]
            with col1:
                st.metric("COT Index", f"{latest.get('noncomm_cot_index', 0):.1f}th pct",
                          delta=f"{latest.get('noncomm_net_chg1w', 0):+,.0f} net chg")
            with col2:
                st.metric("Net Position", f"{latest.get('noncomm_net', 0):,}")
            with col3:
                streak = int(latest.get("noncomm_momentum_streak", 0))
                st.metric("Momentum Streak", f"{streak:+d} weeks",
                          delta_color="normal" if streak >= 0 else "inverse")

            st.plotly_chart(
                cot_index_chart(df, "noncomm_cot_index", f"{selected_market_name} — Non-Commercial COT Index"),
                use_container_width=True,
            )
            st.plotly_chart(
                net_position_chart(df, "noncomm_net", f"{selected_market_name} — Net Position (Non-Commercial)"),
                use_container_width=True,
            )

            with st.expander("Raw Data (last 52 rows)"):
                st.dataframe(df.tail(52)[["report_date","open_interest","noncomm_net","comm_net",
                                           "noncomm_cot_index","noncomm_net_pct","noncomm_momentum_streak"]]
                             .sort_values("report_date", ascending=False),
                             hide_index=True)

    # Disaggregated
    with tab2:
        df = load_disagg(selected_code)
        if df.empty:
            no_data_warning("Disaggregated COT")
        else:
            df["report_date"] = pd.to_datetime(df["report_date"])
            latest = df.iloc[-1]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Managed Money COT Index", f"{latest.get('mmoney_cot_index', 0):.1f}th pct")
            with col2:
                st.metric("Producer COT Index", f"{latest.get('prod_cot_index', 0):.1f}th pct")
            with col3:
                mm = latest.get("mmoney_cot_index", 50)
                pr = latest.get("prod_cot_index", 50)
                divergence = abs((mm or 50) - (pr or 50))
                st.metric("Divergence Score", f"{divergence:.0f}/100",
                          help="Higher = stronger signal when extremes are opposite")

            st.plotly_chart(
                dual_positioning_chart(
                    df,
                    "mmoney_cot_index", "Managed Money",
                    "prod_cot_index",   "Producer/Merchant",
                    f"{selected_market_name} — Smart Money vs Speculator Divergence",
                ),
                use_container_width=True,
            )
            st.plotly_chart(
                net_position_chart(df, "mmoney_net", f"{selected_market_name} — Managed Money Net Position"),
                use_container_width=True,
            )

    # Financial TFF
    with tab3:
        df = load_financial(selected_code)
        if df.empty:
            no_data_warning("TFF (Financial)")
        else:
            df["report_date"] = pd.to_datetime(df["report_date"])
            latest = df.iloc[-1]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Leveraged Money COT Index", f"{latest.get('levmoney_cot_index', 0):.1f}th pct")
            with col2:
                st.metric("Asset Manager COT Index", f"{latest.get('assetmgr_cot_index', 0):.1f}th pct")

            st.plotly_chart(
                dual_positioning_chart(
                    df,
                    "levmoney_cot_index", "Leveraged Money (Hedge Funds)",
                    "assetmgr_cot_index", "Asset Managers",
                    f"{selected_market_name} — TFF Positioning",
                ),
                use_container_width=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Signals & Alerts
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Signals & Alerts":
    st.title("Active COT Signals")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Generate Signals Now"):
            with st.spinner("Generating signals..."):
                from src.analyzer.signals import generate_all_signals
                sigs = generate_all_signals(save=True)
                st.success(f"Generated {len(sigs)} signals")

    sigs_df = get_latest_signals(limit=200)
    if sigs_df.empty:
        st.info("No signals yet. Generate signals or fetch data first.")
    else:
        # Enrich signals with sector
        code_to_sector = {code: _code_to_sector(code) for code in WATCHED_MARKETS}
        sigs_df["sector"] = sigs_df["market_code"].map(code_to_sector).fillna("Other")

        # Filter controls
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sector_filter = st.multiselect(
                "Sector",
                list(SECTOR_GROUPS.keys()),
                default=list(SECTOR_GROUPS.keys()),
            )
        with col2:
            dir_filter = st.multiselect("Direction", ["bullish", "bearish", "neutral"],
                                        default=["bullish", "bearish"])
        with col3:
            type_filter = st.multiselect(
                "Signal Type",
                sigs_df["signal_type"].unique().tolist(),
                default=sigs_df["signal_type"].unique().tolist(),
            )
        with col4:
            min_strength = st.slider("Min Strength", 0, 100, 70)

        filtered = sigs_df[
            sigs_df["sector"].isin(sector_filter) &
            sigs_df["direction"].isin(dir_filter) &
            sigs_df["signal_type"].isin(type_filter) &
            (sigs_df["strength"] >= min_strength)
        ].sort_values(["report_date", "strength"], ascending=[False, False])

        st.markdown(f"**{len(filtered)} signals** matching filters")

        def direction_icon(d: str) -> str:
            return {"bullish": "🟢", "bearish": "🔴", "bullish_lean": "🟡",
                    "bearish_lean": "🟠", "neutral": "⚪"}.get(d, "")

        filtered[""] = filtered["direction"].apply(direction_icon)

        st.dataframe(
            filtered[["", "sector", "report_date", "market_name", "signal_type", "direction",
                       "strength", "cot_index", "net_position", "description"]].head(100),
            use_container_width=True,
            hide_index=True,
            column_config={
                "strength": st.column_config.ProgressColumn("Strength", min_value=0, max_value=100),
                "description": st.column_config.TextColumn("Description", width="large"),
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Backtesting
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Backtesting":
    st.title(f"Backtesting — {selected_market_name}")
    st.caption("Historical performance of COT Index signals vs actual price returns")

    col1, col2, col3 = st.columns(3)
    with col1:
        long_thresh  = st.slider("Extreme Long Threshold", 60, 95, 80)
    with col2:
        short_thresh = st.slider("Extreme Short Threshold", 5, 40, 20)
    with col3:
        fwd_weeks = st.selectbox("Forward Return Period", [4, 8, 12, 26], index=2)

    if st.button("Run Backtest"):
        ticker = PRICE_TICKERS.get(selected_code)
        if not ticker:
            st.warning(f"No price ticker configured for {selected_market_name}")
        else:
            with st.spinner(f"Running backtest for {selected_market_name}..."):
                from src.analyzer.backtesting import run_full_backtest
                bt_df, summary = run_full_backtest(
                    selected_code, ticker,
                    forward_weeks=fwd_weeks,
                    long_threshold=long_thresh,
                    short_threshold=short_thresh,
                )

            if bt_df.empty:
                st.warning("Not enough data for backtest. Ensure historical data is loaded.")
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Hit Rate", f"{summary.get('hit_rate_pct', 0):.1f}%")
                with col2:
                    st.metric("Avg Return", f"{summary.get('avg_return_pct', 0):+.2f}%")
                with col3:
                    st.metric("Total Signals", summary.get("total_signals", 0))
                with col4:
                    sharpe = summary.get("sharpe_approx")
                    st.metric("Approx Sharpe", f"{sharpe:.2f}" if sharpe else "N/A")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Long Hit Rate",  f"{summary.get('long_hit_rate', 0):.1f}%")
                with col2:
                    st.metric("Short Hit Rate", f"{summary.get('short_hit_rate', 0):.1f}%")

                st.plotly_chart(
                    backtest_cumulative_return_chart(bt_df, selected_market_name),
                    use_container_width=True,
                )

                with st.expander("Backtest Raw Results"):
                    st.dataframe(bt_df, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Multi-Asset Analysis
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Multi-Asset Analysis":
    st.title("Multi-Asset COT Analysis")

    tab1, tab2, tab3 = st.tabs(["Risk-On/Off Indicator", "Correlation Matrix", "Confluence Signals"])

    with tab1:
        st.subheader("Risk-On / Risk-Off Positioning Indicator")
        with st.spinner("Computing..."):
            roo = risk_on_off_indicator()

        if roo.get("status") == "insufficient_data":
            st.warning("Need S&P 500 and 10-Year T-Note COT data. Fetch data first.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("S&P 500 COT Index", f"{roo['sp500_cot_index']:.1f}th pct")
            with col2:
                st.metric("10Y Bond COT Index", f"{roo['bond_cot_index']:.1f}th pct")
            with col3:
                st.metric("Risk-On Score", f"{roo['risk_on_score']:.1f}/100")

            regime_colors = {
                "risk_on_crowded":  "#d50000",
                "risk_on_lean":     "#ff6d00",
                "neutral":          "#90a4ae",
                "risk_off_lean":    "#1565c0",
                "risk_off_crowded": "#00c853",
            }
            color = regime_colors.get(roo["regime"], "#90a4ae")
            st.markdown(
                f'<div style="background:{color}22;border-left:4px solid {color};'
                f'padding:12px;border-radius:4px">'
                f'<b>{roo["regime"].replace("_", " ").title()}</b><br>{roo["outlook"]}</div>',
                unsafe_allow_html=True,
            )

    with tab2:
        st.subheader("Cross-Market COT Index Correlation (52-Week)")

        corr_col1, corr_col2 = st.columns([2, 1])
        with corr_col1:
            selected_sectors_corr = st.multiselect(
                "Sectors to include",
                list(SECTOR_GROUPS.keys()),
                default=["Metals", "Energy", "Equities", "Rates", "FX"],
                key="corr_sectors",
            )
        with corr_col2:
            st.caption("Tip: start with 2–3 sectors for a readable heatmap.")

        # Resolve selected codes from chosen sectors
        corr_codes = [
            code for sector in selected_sectors_corr
            for code in SECTOR_GROUPS.get(sector, [])
            if code in WATCHED_MARKETS
        ]

        with st.spinner("Building correlation matrix..."):
            panel = build_cot_index_panel()

        if panel.empty:
            no_data_warning("correlation matrix")
        else:
            # Filter panel columns to selected markets
            available = [c for c in corr_codes if c in panel.columns]
            if len(available) < 2:
                st.warning("Select at least 2 sectors with available data.")
            else:
                # Rename columns from code to name for readability
                panel_sub = panel[available].rename(
                    columns={c: WATCHED_MARKETS[c] for c in available}
                )
                corr = correlation_matrix(panel_sub)
                if not corr.empty:
                    st.plotly_chart(correlation_heatmap(corr), use_container_width=True)
                    st.caption(
                        "Correlation of COT Index (speculator positioning percentile) across markets. "
                        "Strong negative correlation between pairs like EUR and Gold reflects USD as common driver."
                    )

    with tab3:
        st.subheader("Multi-Asset Confluence Signals")
        with st.spinner("Scanning for confluences..."):
            from src.analyzer.multi_asset import multi_asset_confluence_signals
            confluences = multi_asset_confluence_signals()

        if not confluences:
            st.info("No high-conviction multi-asset confluence signals at this time.")
        else:
            for sig in confluences:
                direction = sig.get("direction", "neutral")
                icon = "🔴" if "bearish" in direction else "🟢"
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{icon} {sig['market_name']}** — {sig['signal_type'].replace('_',' ').title()}")
                        st.caption(sig["description"])
                    with col2:
                        st.metric("Direction", direction.upper())
                    with col3:
                        st.metric("Alignment", f"{sig.get('alignment_score', 0):.0f}%")
