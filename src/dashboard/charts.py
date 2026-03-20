"""Reusable Plotly chart builders for the Streamlit dashboard."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


COLORS = {
    "bullish":  "#00c853",
    "bearish":  "#d50000",
    "neutral":  "#90a4ae",
    "extreme":  "#ff6d00",
    "cot_line": "#1565c0",
    "net_bar":  "#5c6bc0",
    "price":    "#37474f",
}


def cot_index_chart(df: pd.DataFrame, cot_col: str, title: str) -> go.Figure:
    """Line chart of COT Index with overbought/oversold zones."""
    fig = go.Figure()

    # Overbought/oversold bands
    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(213,0,0,0.08)", line_width=0,
                  annotation_text="Extreme Long", annotation_position="right")
    fig.add_hrect(y0=0, y1=20, fillcolor="rgba(0,200,83,0.08)", line_width=0,
                  annotation_text="Extreme Short", annotation_position="right")
    fig.add_hline(y=50, line_dash="dot", line_color="gray", line_width=1)

    # COT Index line
    fig.add_trace(go.Scatter(
        x=df["report_date"], y=df[cot_col],
        mode="lines", name="COT Index",
        line=dict(color=COLORS["cot_line"], width=2),
        fill="tozeroy", fillcolor="rgba(21,101,192,0.1)",
    ))

    fig.update_layout(
        title=title,
        yaxis_title="COT Index (0–100)",
        yaxis=dict(range=[0, 100]),
        height=350,
        margin=dict(l=40, r=40, t=50, b=40),
        hovermode="x unified",
        showlegend=False,
    )
    return fig


def net_position_chart(df: pd.DataFrame, net_col: str, title: str) -> go.Figure:
    """Bar chart of net positions with color coding."""
    colors = [COLORS["bullish"] if v >= 0 else COLORS["bearish"]
              for v in df[net_col].fillna(0)]

    fig = go.Figure(go.Bar(
        x=df["report_date"], y=df[net_col],
        marker_color=colors,
        name="Net Position",
    ))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        title=title,
        yaxis_title="Net Contracts",
        height=300,
        margin=dict(l=40, r=40, t=50, b=40),
        showlegend=False,
    )
    return fig


def dual_positioning_chart(
    df: pd.DataFrame,
    col_a: str, label_a: str,
    col_b: str, label_b: str,
    title: str,
) -> go.Figure:
    """Overlay two positioning series to visualize divergence."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=df["report_date"], y=df[col_a],
        name=label_a, line=dict(color="#d50000", width=2),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df["report_date"], y=df[col_b],
        name=label_b, line=dict(color="#1565c0", width=2, dash="dash"),
    ), secondary_y=True)

    fig.add_hline(y=80, line_dash="dot", line_color="#d50000", opacity=0.4, secondary_y=False)
    fig.add_hline(y=20, line_dash="dot", line_color="#d50000", opacity=0.4, secondary_y=False)

    fig.update_layout(
        title=title,
        height=380,
        margin=dict(l=40, r=60, t=50, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.15),
    )
    fig.update_yaxes(title_text=f"{label_a} COT Index", range=[0, 100], secondary_y=False)
    fig.update_yaxes(title_text=f"{label_b} COT Index", range=[0, 100], secondary_y=True)
    return fig


def correlation_heatmap(corr_df: pd.DataFrame) -> go.Figure:
    """Heatmap of cross-market COT Index correlations. Height scales with market count."""
    n = len(corr_df)
    cell_px = 38
    height = max(380, n * cell_px + 120)
    label_margin = max(120, max(len(s) for s in corr_df.columns) * 7)

    # Hide text labels when there are too many cells to avoid clutter
    show_text = n <= 15

    fig = go.Figure(go.Heatmap(
        z=corr_df.values,
        x=corr_df.columns.tolist(),
        y=corr_df.index.tolist(),
        colorscale="RdBu",
        zmid=0,
        zmin=-1, zmax=1,
        text=corr_df.values.round(2) if show_text else None,
        texttemplate="%{text}" if show_text else None,
        colorbar_title="Corr",
        hoverongaps=False,
        hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"COT Index Cross-Market Correlations (52-Week) — {n}×{n}",
        height=height,
        margin=dict(l=label_margin, r=40, t=60, b=label_margin),
    )
    fig.update_xaxes(tickangle=45)
    return fig


def backtest_cumulative_return_chart(backtest_df: pd.DataFrame, market_name: str) -> go.Figure:
    """Cumulative return chart from backtesting results."""
    if backtest_df.empty:
        fig = go.Figure()
        fig.update_layout(title="No backtest data available")
        return fig

    df = backtest_df.sort_values("report_date").copy()
    df["cum_return"] = (1 + df["adj_return"] / 100).cumprod() * 100 - 100

    colors = [COLORS["bullish"] if h else COLORS["bearish"] for h in df["hit"]]

    fig = make_subplots(rows=2, cols=1, row_heights=[0.65, 0.35], shared_xaxes=True)

    fig.add_trace(go.Scatter(
        x=df["report_date"], y=df["cum_return"],
        name="Cumulative Return (%)",
        line=dict(color=COLORS["cot_line"], width=2),
        fill="tozeroy", fillcolor="rgba(21,101,192,0.1)",
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df["report_date"], y=df["adj_return"],
        name="Signal Return (%)",
        marker_color=colors,
    ), row=2, col=1)

    fig.update_layout(
        title=f"Backtest: COT Index Signals — {market_name}",
        height=500,
        margin=dict(l=40, r=40, t=60, b=40),
        showlegend=False,
    )
    fig.update_yaxes(title_text="Cumulative %", row=1)
    fig.update_yaxes(title_text="Return %", row=2)
    return fig


def signal_strength_gauge(strength: float, title: str) -> go.Figure:
    """Gauge chart showing signal strength."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=strength,
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": COLORS["cot_line"]},
            "steps": [
                {"range": [0, 20],  "color": "rgba(0,200,83,0.2)"},
                {"range": [20, 80], "color": "rgba(144,164,174,0.1)"},
                {"range": [80, 100],"color": "rgba(213,0,0,0.2)"},
            ],
            "threshold": {
                "line": {"color": COLORS["extreme"], "width": 3},
                "thickness": 0.8,
                "value": strength,
            },
        },
        number={"suffix": "th pct", "font": {"size": 20}},
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=20))
    return fig
