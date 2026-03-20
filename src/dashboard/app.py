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

market_options = {v: k for k, v in WATCHED_MARKETS.items()}  # name → code
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
            "COT Index":    round(idx, 1),
            "Net Position": int(net) if net is not None else None,
            "Chg 1W":       int(chg1w) if chg1w is not None else None,
            "Streak (wks)": int(streak),
            "Sentiment":    sentiment,
            "Report Date":  str(row.get("report_date", ""))[:10],
        })

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows).sort_values("COT Index", ascending=False)
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "COT Index": st.column_config.ProgressColumn(
                    "COT Index", min_value=0, max_value=100, format="%.1f"
                ),
            },
        )

        # Quick bar chart
        import plotly.express as px
        bar_colors = ["#d50000" if v >= 80 else "#ff6d00" if v >= 65
                      else "#00c853" if v <= 20 else "#1565c0" if v <= 35
                      else "#90a4ae"
                      for v in summary_df["COT Index"]]
        fig = px.bar(
            summary_df, x="Market", y="COT Index",
            color="COT Index",
            color_continuous_scale=["#00c853", "#90a4ae", "#d50000"],
            range_color=[0, 100],
            title="Non-Commercial COT Index by Market",
        )
        fig.add_hline(y=80, line_dash="dash", line_color="#d50000", annotation_text="Extreme Long (80)")
        fig.add_hline(y=20, line_dash="dash", line_color="#00c853", annotation_text="Extreme Short (20)")
        fig.update_layout(height=420, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        no_data_warning("overview")


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
        # Filter controls
        col1, col2, col3 = st.columns(3)
        with col1:
            dir_filter = st.multiselect("Direction", ["bullish", "bearish", "neutral"],
                                        default=["bullish", "bearish"])
        with col2:
            type_filter = st.multiselect(
                "Signal Type",
                sigs_df["signal_type"].unique().tolist(),
                default=sigs_df["signal_type"].unique().tolist(),
            )
        with col3:
            min_strength = st.slider("Min Strength", 0, 100, 70)

        filtered = sigs_df[
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
            filtered[["", "report_date", "market_name", "signal_type", "direction",
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
        with st.spinner("Building correlation matrix..."):
            panel = build_cot_index_panel()

        if panel.empty:
            no_data_warning("correlation matrix")
        else:
            corr = correlation_matrix(panel)
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
