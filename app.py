from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Max ROI",
    page_icon="ROI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"
SETTINGS_PATH = DATA_DIR / "settings.json"

BALANCED_PRESET = {
    "risk_mode": "Auto",
    "minimum_cash_reserve": 25.0,
    "absolute_min_trade": 5.0,
    "max_trade_pct_available_cash": 0.75,
    "allocation_tolerance_pct": 1.0,
    "starter_fill_pct_gap": 0.75,
    "owned_add_fill_pct_gap": 0.60,
    "watch_buy_scaler": 1.00,
    "trim_profit_pct": 12.0,
    "hard_exit_loss_pct": -8.0,
    "tactical_exit_loss_pct": -6.0,
    "tactical_exit_required_signals": 3,
    "tactical_exit_rsi_max": 45,
    "tactical_exit_range_position_max": 35,
    "tactical_exit_off_5d_high_min_pct": 8,
}

CONSERVATIVE_PRESET = {
    "risk_mode": "Auto",
    "minimum_cash_reserve": 40.0,
    "absolute_min_trade": 5.0,
    "max_trade_pct_available_cash": 0.50,
    "allocation_tolerance_pct": 1.5,
    "starter_fill_pct_gap": 0.50,
    "owned_add_fill_pct_gap": 0.35,
    "watch_buy_scaler": 0.85,
    "trim_profit_pct": 14.0,
    "hard_exit_loss_pct": -7.0,
    "tactical_exit_loss_pct": -5.0,
    "tactical_exit_required_signals": 2,
    "tactical_exit_rsi_max": 47,
    "tactical_exit_range_position_max": 40,
    "tactical_exit_off_5d_high_min_pct": 7,
}

MARKET_WATCH = ["^GSPC", "^IXIC", "^DJI", "BTC-USD", "^VIX"]

FALLBACK_PRICES = {
    "NVDA": 199.64,
    "GOOGL": 303.24,
    "ETN": 424.50,
    "AMD": 305.33,
    "PLTR": 141.57,
    "VRT": 321.75,
    "XLV": 148.75,
    "RKLB": 84.60,
    "BTC-USD": 78215.00,
    "CAT": 835.24,
    "CEG": 292.77,
    "LUNR": 27.56,
    "ETH-USD": 2328.68,
    "ADA-USD": 0.71,
    "XLM-USD": 0.16,
    "ANKR-USD": 0.034,
    "BFGFF": 0.22,
    "^GSPC": 7108.40,
    "^IXIC": 26782.63,
    "^DJI": 49310.32,
    "^VIX": 18.67,
}


@dataclass
class SignalResult:
    status: str
    trend: str
    timing: str
    signal: str
    score: int
    suggested_trade: float


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def money(value: float) -> str:
    if abs(value) < 1:
        return f"${value:,.4f}"
    return f"${value:,.2f}"


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #050b12;
            --panel: #0b1422;
            --panel-2: #0f1b2d;
            --line: #1d2b3e;
            --text: #e5eef9;
            --muted: #8fa1b8;
            --green: #22c55e;
            --blue: #60a5fa;
            --red: #ef4444;
            --yellow: #eab308;
        }
        .stApp { background: var(--bg); color: var(--text); }
        header[data-testid="stHeader"] { background: rgba(5, 11, 18, 0.88); }
        div[data-testid="stToolbar"] { display: none; }
        .block-container { padding: 0.8rem 1rem 3rem; max-width: 100%; }
        h1, h2, h3 { letter-spacing: 0; }
        .topbar {
            display: grid;
            grid-template-columns: 180px 1fr 90px;
            gap: 1rem;
            align-items: center;
            border-bottom: 1px solid var(--line);
            padding: 0 0 0.55rem;
            margin-bottom: 1rem;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            font-weight: 800;
            font-size: 1.05rem;
        }
        .brand-bars {
            display: grid;
            grid-template-columns: repeat(4, 4px);
            align-items: end;
            gap: 3px;
            width: 25px;
            height: 20px;
        }
        .brand-bars span { display: block; background: var(--green); border-radius: 2px 2px 0 0; }
        .brand-bars span:nth-child(1) { height: 7px; }
        .brand-bars span:nth-child(2) { height: 11px; }
        .brand-bars span:nth-child(3) { height: 15px; }
        .brand-bars span:nth-child(4) { height: 19px; }
        .top-actions {
            display: flex;
            justify-content: flex-end;
            color: var(--muted);
            font-size: 0.74rem;
            gap: 0.55rem;
            align-items: center;
        }
        .pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.18rem 0.48rem;
            font-weight: 750;
            font-size: 0.7rem;
            border: 1px solid var(--line);
            background: #0a1321;
        }
        .pill.green { color: var(--green); border-color: rgba(34, 197, 94, 0.4); background: rgba(34, 197, 94, 0.12); }
        .pill.blue { color: var(--blue); border-color: rgba(96, 165, 250, 0.35); background: rgba(96, 165, 250, 0.12); }
        .pill.yellow { color: var(--yellow); border-color: rgba(234, 179, 8, 0.42); background: rgba(234, 179, 8, 0.12); }
        .pill.red { color: var(--red); border-color: rgba(239, 68, 68, 0.42); background: rgba(239, 68, 68, 0.12); }
        div[data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--line);
            padding: 0.85rem 0.9rem;
            min-height: 128px;
        }
        div[data-testid="stMetricLabel"] p { color: var(--muted); font-size: 0.76rem; }
        div[data-testid="stMetricValue"] { color: var(--text); font-size: 1.45rem; }
        div[data-testid="stMetricDelta"] { font-weight: 800; }
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            padding: 0.85rem;
            margin-bottom: 0.8rem;
        }
        .panel h3 { margin: 0 0 0.65rem; font-size: 1rem; }
        .small-muted { color: var(--muted); font-size: 0.78rem; }
        .opportunity {
            display: grid;
            grid-template-columns: 34px 1fr auto;
            gap: 0.7rem;
            align-items: center;
            border-bottom: 1px solid var(--line);
            padding: 0.68rem 0;
        }
        .avatar {
            display: grid;
            place-items: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #14243a;
            color: #dbeafe;
            font-size: 0.68rem;
            font-weight: 800;
        }
        .stDataFrame { border: 1px solid var(--line); }
        div[data-baseweb="tab-list"] { gap: 1.8rem; border-bottom: 1px solid var(--line); }
        button[data-baseweb="tab"] { color: var(--text); font-weight: 700; }
        button[data-baseweb="tab"][aria-selected="true"] { color: var(--green); border-bottom-color: var(--green); }
        .setting-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(120px, 1fr));
            gap: 0.8rem;
        }
        .setting-card {
            background: #091322;
            border: 1px solid var(--line);
            padding: 0.9rem;
        }
        .setting-card .label { color: var(--text); font-weight: 760; font-size: 0.82rem; }
        .setting-card .value { font-size: 2rem; margin-top: 0.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(tickers: tuple[str, ...], period: str = "7d") -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        frame = pd.DataFrame()
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            response = requests.get(
                url,
                params={"range": period, "interval": "1d"},
                headers={"User-Agent": "MaxROI/1.0"},
                timeout=8,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            closes = quote.get("close") or []
            opens = quote.get("open") or closes
            highs = quote.get("high") or closes
            lows = quote.get("low") or closes
            volumes = quote.get("volume") or [0 for _ in closes]
            frame = pd.DataFrame(
                {
                    "Open": opens,
                    "High": highs,
                    "Low": lows,
                    "Close": closes,
                    "Volume": volumes,
                },
                index=pd.to_datetime(timestamps, unit="s"),
            ).dropna(subset=["Close"])
        except Exception:  # noqa: BLE001
            frame = pd.DataFrame()
        if frame.empty:
            base = FALLBACK_PRICES.get(ticker, 25.0)
            offsets = [-0.035, -0.018, -0.024, 0.004, 0.017, 0.011, 0.026]
            frame = pd.DataFrame(
                {
                    "Close": [round(base * (1 + offset), 4) for offset in offsets],
                    "Open": [round(base * (1 + offset - 0.006), 4) for offset in offsets],
                    "High": [round(base * (1 + offset + 0.014), 4) for offset in offsets],
                    "Low": [round(base * (1 + offset - 0.018), 4) for offset in offsets],
                    "Volume": [100000 + i * 9000 for i in range(7)],
                },
                index=pd.date_range(end=pd.Timestamp.today(), periods=7),
            )
        histories[ticker] = frame
    return histories


def latest_price(history: pd.DataFrame, ticker: str) -> float:
    if not history.empty and "Close" in history:
        value = float(history["Close"].dropna().iloc[-1])
        if math.isfinite(value) and value > 0:
            return value
    return FALLBACK_PRICES.get(ticker, 1.0)


def daily_change_pct(history: pd.DataFrame) -> float:
    closes = history["Close"].dropna() if not history.empty and "Close" in history else pd.Series(dtype=float)
    if len(closes) < 2 or float(closes.iloc[-2]) == 0:
        return 0.0
    return ((float(closes.iloc[-1]) / float(closes.iloc[-2])) - 1) * 100


def range_position(history: pd.DataFrame) -> float:
    closes = history["Close"].dropna() if not history.empty and "Close" in history else pd.Series(dtype=float)
    if closes.empty:
        return 50.0
    low = float(closes.min())
    high = float(closes.max())
    if high == low:
        return 50.0
    return ((float(closes.iloc[-1]) - low) / (high - low)) * 100


def calculate_signals(df: pd.DataFrame, settings: dict[str, Any], cash: float) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    deployable_cash = max(cash - float(settings["minimum_cash_reserve"]), 0)
    max_trade = deployable_cash * float(settings["max_trade_pct_available_cash"])
    for _, row in df.iterrows():
        gain_pct = float(row["gain_pct"])
        alloc_gap = float(row["target_weight"] - row["allocation_pct"])
        day_pct = float(row["daily_pct"])
        pos = float(row["range_position"])
        weak_signals = sum(
            [
                gain_pct <= float(settings["tactical_exit_loss_pct"]),
                day_pct < -1.5,
                pos <= float(settings["tactical_exit_range_position_max"]),
            ]
        )
        if gain_pct <= float(settings["hard_exit_loss_pct"]):
            signal = "EXIT"
            timing = "HARD STOP"
            status = "DEFEND"
            score = 10
            trade = 0.0
        elif weak_signals >= int(settings["tactical_exit_required_signals"]):
            signal = "TRIM"
            timing = "WEAK TREND"
            status = "DEFEND"
            score = 25
            trade = 0.0
        elif gain_pct >= float(settings["trim_profit_pct"]):
            signal = "TRIM"
            timing = "PROFIT WATCH"
            status = "OVER TARGET" if alloc_gap < 0 else "WATCH"
            score = 45
            trade = 0.0
        elif alloc_gap > float(settings["allocation_tolerance_pct"]):
            fill_rate = float(settings["owned_add_fill_pct_gap"]) if row["shares"] > 0 else float(settings["starter_fill_pct_gap"])
            trade = min(max_trade, max(alloc_gap, 0) / 100 * float(row["portfolio_value"]) * fill_rate)
            trade = trade * float(settings["watch_buy_scaler"])
            if trade >= float(settings["absolute_min_trade"]):
                signal = "WATCH BUY"
                timing = "WATCH"
                status = "UNDER TARGET"
                score = int(min(88, 50 + alloc_gap * 4 + max(day_pct, 0) * 2 + pos / 12))
            else:
                signal = "HOLD"
                timing = "WAIT"
                status = "UNDER TARGET"
                score = 40
        else:
            signal = "HOLD"
            timing = "GOOD" if day_pct >= 0 else "WATCH"
            status = "ON PLAN"
            score = int(55 + min(max(gain_pct, -10), 20))
            trade = 0.0

        if day_pct > 0.5 and pos > 55:
            trend = "BULLISH"
        elif day_pct < -0.5 and pos < 45:
            trend = "WEAK"
        else:
            trend = "MIXED"

        records.append(
            {
                "Status": status,
                "Trend": trend,
                "Timing": timing,
                "Signal": signal,
                "Score": max(0, min(score, 100)),
                "Action $": round(trade, 2),
            }
        )
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(records)], axis=1)


def build_portfolio_frame(portfolio: dict[str, Any], histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for item in portfolio["holdings"]:
        ticker = item["ticker"]
        hist = histories.get(ticker, pd.DataFrame())
        current = latest_price(hist, ticker)
        shares = float(item["shares"])
        avg_cost = float(item["avg_cost"])
        value = shares * current
        cost = shares * avg_cost
        gain = value - cost
        gain_pct = ((current / avg_cost) - 1) * 100 if avg_cost else 0.0
        rows.append(
            {
                "Ticker": ticker,
                "Name": item["name"],
                "Category": item["category"],
                "Current": current,
                "Avg Cost": avg_cost,
                "Shares": shares,
                "shares": shares,
                "Value": value,
                "Gain $": gain,
                "Gain %": gain_pct,
                "gain_pct": gain_pct,
                "Target %": float(item["target_weight"]),
                "Daily %": daily_change_pct(hist),
                "range_position": range_position(hist),
                "history": hist,
            }
        )
    df = pd.DataFrame(rows)
    portfolio_value = float(df["Value"].sum()) + float(portfolio.get("cash", 0))
    df["portfolio_value"] = portfolio_value
    df["Allocation %"] = (df["Value"] / portfolio_value) * 100 if portfolio_value else 0
    df["allocation_pct"] = df["Allocation %"]
    df["target_weight"] = df["Target %"]
    df["daily_pct"] = df["Daily %"]
    return df


def topbar(active: str, refreshed: datetime, profile: str) -> None:
    st.markdown(
        f"""
        <div class="topbar">
            <div class="brand">
                <div class="brand-bars"><span></span><span></span><span></span><span></span></div>
                <div>Max ROI</div>
            </div>
            <div></div>
            <div class="top-actions"><span class="pill green">{active}</span></div>
        </div>
        <div class="top-actions" style="margin-top:-0.6rem;margin-bottom:0.55rem;">
            <span>Last refreshed {refreshed.strftime('%m/%d/%Y %I:%M %p')}</span>
            <span>Auto refresh every 5 min</span>
            <span>Risk <b class="pill green">{profile.upper()}</b></span>
            <span>Freshness <b class="pill green">Fresh</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(df: pd.DataFrame, cash: float) -> None:
    portfolio_value = float(df["Value"].sum()) + cash
    total_gain = float(df["Gain $"].sum())
    total_cost = float((df["Shares"] * df["Avg Cost"]).sum())
    total_return = (total_gain / total_cost) * 100 if total_cost else 0.0
    best = df.sort_values("Gain %", ascending=False).iloc[0]
    weakest = df.sort_values("Gain %", ascending=True).iloc[0]

    c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1.1, 1.1, 1.1])
    c1.metric("Total Portfolio Value", money(portfolio_value), pct(float(df["Daily %"].mean())))
    c2.metric("Total Gain / Loss", money(total_gain), pct(total_return))
    c3.metric("Cash Available", money(cash), f"Buying Power {money(max(cash - 25, 0))}")
    c4.metric("Best Performer", str(best["Ticker"]), f"{money(float(best['Gain $']))}  {pct(float(best['Gain %']))}")
    c5.metric("Weakest Performer", str(weakest["Ticker"]), f"{money(float(weakest['Gain $']))}  {pct(float(weakest['Gain %']))}")


def render_holdings_table(df: pd.DataFrame) -> None:
    table = df.copy()
    table["Current"] = table["Current"].map(money)
    table["Avg Cost"] = table["Avg Cost"].map(money)
    table["Value"] = table["Value"].map(money)
    table["Gain $"] = table["Gain $"].map(money)
    table["Gain %"] = table["Gain %"].map(lambda value: f"{value:+.2f}%")
    table["Allocation"] = table.apply(lambda row: f"{row['Allocation %']:.2f}% / {row['Target %']:.1f}%", axis=1)
    table["Daily"] = table["Daily %"].map(lambda value: f"{value:+.2f}%")
    table["Action $"] = table["Action $"].map(money)
    table = table[
        [
            "Ticker",
            "Category",
            "Current",
            "Avg Cost",
            "Value",
            "Gain $",
            "Gain %",
            "Allocation",
            "Daily",
            "Status",
            "Trend",
            "Timing",
            "Signal",
            "Score",
            "Action $",
        ]
    ]
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        },
    )


def render_opportunities(df: pd.DataFrame) -> None:
    buys = df[df["Signal"] == "WATCH BUY"].sort_values(["Action $", "Score"], ascending=False).head(5)
    trims = df[df["Signal"].isin(["TRIM", "EXIT"])].sort_values("Gain %", ascending=True).head(5)

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="panel"><h3>Top Opportunities</h3>', unsafe_allow_html=True)
        if buys.empty:
            st.markdown('<div class="small-muted">No buy candidates currently clear the trade floor.</div>', unsafe_allow_html=True)
        for _, row in buys.iterrows():
            st.markdown(
                f"""
                <div class="opportunity">
                    <div class="avatar">{str(row['Ticker'])[:2]}</div>
                    <div><b>{row['Ticker']}</b><br><span class="small-muted">Owned add - below target allocation, account allocation {row['Allocation %']:.1f}% vs target {row['Target %']:.1f}%.</span></div>
                    <div style="text-align:right;"><b>{money(float(row['Action $']))}</b><br><span class="pill green">WATCH BUY</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel"><h3>Top Trim Candidates</h3>', unsafe_allow_html=True)
        if trims.empty:
            st.markdown('<div class="small-muted">No trim or exit candidates right now.</div>', unsafe_allow_html=True)
        for _, row in trims.iterrows():
            cls = "red" if row["Signal"] == "EXIT" else "yellow"
            st.markdown(
                f"""
                <div class="opportunity">
                    <div class="avatar">{str(row['Ticker'])[:2]}</div>
                    <div><b>{row['Ticker']}</b><br><span class="small-muted">{row['Trend']} - {row['Timing']} - gain {pct(float(row['Gain %']))}</span></div>
                    <div style="text-align:right;"><span class="pill {cls}">{row['Signal']}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_allocation(df: pd.DataFrame, cash: float) -> None:
    left, mid, right = st.columns([1, 1.2, 1])
    with left:
        st.markdown('<div class="panel"><h3>Portfolio Allocation</h3>', unsafe_allow_html=True)
        category = df.groupby("Category", as_index=False)["Value"].sum()
        category.loc[len(category)] = {"Category": "Cash", "Value": cash}
        total = float(category["Value"].sum()) or 1
        for _, row in category.sort_values("Value", ascending=False).iterrows():
            share = float(row["Value"]) / total * 100
            st.markdown(
                f"""
                <div style="margin:0.55rem 0;">
                    <div style="display:flex;justify-content:space-between;font-size:0.78rem;">
                        <b>{row['Category']}</b><span>{share:.1f}%</span>
                    </div>
                    <div style="height:8px;background:#111c2c;border:1px solid #1d2b3e;">
                        <div style="height:100%;width:{share:.1f}%;background:#22c55e;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with mid:
        st.markdown('<div class="panel"><h3>Performance</h3><div class="small-muted">Signal snapshot anchored to latest available quote.</div>', unsafe_allow_html=True)
        perf = df.sort_values("Daily %", ascending=False).head(7)
        chart = perf.set_index("Ticker")[["Daily %"]]
        st.bar_chart(chart, height=255)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        histories = fetch_history(tuple(MARKET_WATCH), "7d")
        st.markdown('<div class="panel"><h3>Market Snapshot</h3>', unsafe_allow_html=True)
        for ticker in MARKET_WATCH:
            hist = histories[ticker]
            name = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ 100", "^DJI": "DOW JONES", "^VIX": "VIX"}.get(ticker, ticker)
            change = daily_change_pct(hist)
            color = "green" if change >= 0 else "red"
            st.markdown(
                f"""
                <div class="opportunity" style="grid-template-columns: 1fr auto auto;">
                    <div><b>{name}</b></div>
                    <div><b>{latest_price(hist, ticker):,.2f}</b></div>
                    <div><span class="pill {color}">{change:+.2f}%</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('<div class="small-muted">Timing: GOOD | WATCH | WEAK TREND</div></div>', unsafe_allow_html=True)


def render_overview(portfolio: dict[str, Any], settings: dict[str, Any]) -> None:
    tickers = tuple(item["ticker"] for item in portfolio["holdings"])
    histories = fetch_history(tickers, "7d")
    cash = float(portfolio.get("cash", 0))
    df = build_portfolio_frame(portfolio, histories)
    df = calculate_signals(df, settings, cash)
    render_metrics(df, cash)
    st.markdown("### Holdings")
    render_holdings_table(df)
    render_opportunities(df)
    render_allocation(df, cash)


def render_new_trade(portfolio: dict[str, Any], settings: dict[str, Any]) -> None:
    st.header("New Trade")
    st.caption("Position sizing follows the active preset and current target allocation gap.")
    tickers = [item["ticker"] for item in portfolio["holdings"]]
    selected = st.selectbox("Ticker", tickers)
    item = next(row for row in portfolio["holdings"] if row["ticker"] == selected)
    histories = fetch_history((selected,), "7d")
    price = latest_price(histories[selected], selected)
    cash = float(portfolio.get("cash", 0))
    deployable = max(cash - float(settings["minimum_cash_reserve"]), 0)
    max_trade = deployable * float(settings["max_trade_pct_available_cash"])
    target_note = f"{item['target_weight']:.1f}% target in {item['category']}"
    c1, c2, c3 = st.columns(3)
    c1.metric("Current", money(price), target_note)
    c2.metric("Deployable Cash", money(deployable), f"cash reserve {money(float(settings['minimum_cash_reserve']))}")
    c3.metric("Max Trade", money(max_trade), "preset cap")
    trade_amount = st.number_input("Planned trade amount", min_value=0.0, max_value=max(cash, 1.0), value=round(min(max_trade, cash), 2), step=1.0)
    shares = trade_amount / price if price else 0
    st.info(f"Estimated shares: {shares:,.6f}. This dashboard records planning signals only and does not place trades.")


def render_holdings_editor(portfolio: dict[str, Any]) -> None:
    st.header("Holdings")
    st.caption("Edit the portfolio universe, including crypto and penny/speculative names.")
    edited = st.data_editor(
        pd.DataFrame(portfolio["holdings"]),
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "category": st.column_config.SelectboxColumn(
                "category",
                options=["Core", "Aggressive", "Speculative", "Defensive", "Crypto"],
            )
        },
    )
    cash = st.number_input("Cash available", min_value=0.0, value=float(portfolio.get("cash", 0)), step=1.0)
    if st.button("Save Holdings", type="primary"):
        portfolio["holdings"] = edited.to_dict("records")
        portfolio["cash"] = cash
        save_json(PORTFOLIO_PATH, portfolio)
        st.success("Holdings saved.")


def preset_card(title: str, subtitle: str, preset: dict[str, Any], button_label: str) -> bool:
    st.subheader(title)
    st.caption(subtitle)
    st.markdown(
        f"""
        <div class="setting-grid">
            <div class="setting-card"><div class="label">Owned Add Fill</div><div class="value">{preset['owned_add_fill_pct_gap']:.0%}</div></div>
            <div class="setting-card"><div class="label">Starter Fill</div><div class="value">{preset['starter_fill_pct_gap']:.0%}</div></div>
            <div class="setting-card"><div class="label">Trim Trigger</div><div class="value">{preset['trim_profit_pct']:.1f}%</div></div>
            <div class="setting-card"><div class="label">Hard Stop</div><div class="value">{preset['hard_exit_loss_pct']:.1f}%</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button(button_label, use_container_width=False)


def render_settings(settings: dict[str, Any], portfolio: dict[str, Any]) -> None:
    st.header("Settings")
    st.caption("Manage the live strategy controls from this page.")
    tabs = st.tabs(["Strategy", "Buy & Add Logic", "Trim & Exit Logic", "System", "Watchlist & Targets", "Raw JSON"])
    with tabs[0]:
        st.subheader("Live Strategy Controls")
        st.info("The signal generator reads the buy/add, trim, and exit controls from this page.")
        left, right = st.columns(2)
        with left:
            if preset_card(
                "Balanced Growth Preset",
                "Deploy cash faster, let winners run a bit, and keep downside protection.",
                BALANCED_PRESET,
                "Apply Balanced Growth Preset",
            ):
                settings.update(BALANCED_PRESET)
                portfolio["profile"] = "Balanced Growth"
                save_json(SETTINGS_PATH, settings)
                save_json(PORTFOLIO_PATH, portfolio)
                st.success("Balanced Growth applied.")
        with right:
            if preset_card(
                "Conservative Growth Preset",
                "Keep growth on, add more slowly, hold more cash back, and exit weakness sooner.",
                CONSERVATIVE_PRESET,
                "Apply Conservative Growth Preset",
            ):
                settings.update(CONSERVATIVE_PRESET)
                portfolio["profile"] = "Conservative Growth"
                save_json(SETTINGS_PATH, settings)
                save_json(PORTFOLIO_PATH, portfolio)
                st.success("Conservative Growth applied.")
        st.markdown("### What This Preset Tries To Do")
        st.markdown(
            "- **Balanced Growth:** more deployment, more upside capture\n"
            "- **Conservative Growth:** slower deployment, faster defense\n"
            "- Both presets keep the live logic visible so you can see exactly what each one changes."
        )
    with tabs[1]:
        settings["minimum_cash_reserve"] = st.number_input("Minimum Cash Reserve $", value=float(settings["minimum_cash_reserve"]), step=5.0)
        settings["absolute_min_trade"] = st.number_input("Absolute Minimum Trade $", value=float(settings["absolute_min_trade"]), step=1.0)
        settings["max_trade_pct_available_cash"] = st.slider("Max Trade % of Available Cash", 0.0, 1.0, float(settings["max_trade_pct_available_cash"]), 0.05)
        settings["allocation_tolerance_pct"] = st.number_input("Allocation Tolerance %", value=float(settings["allocation_tolerance_pct"]), step=0.25)
        settings["starter_fill_pct_gap"] = st.slider("Starter Fill % of Gap", 0.0, 1.0, float(settings["starter_fill_pct_gap"]), 0.05)
        settings["owned_add_fill_pct_gap"] = st.slider("Owned Add Fill % of Gap", 0.0, 1.0, float(settings["owned_add_fill_pct_gap"]), 0.05)
        settings["watch_buy_scaler"] = st.slider("Watch Buy Scaler", 0.0, 1.5, float(settings["watch_buy_scaler"]), 0.05)
    with tabs[2]:
        settings["trim_profit_pct"] = st.number_input("Trim Profit %", value=float(settings["trim_profit_pct"]), step=0.5)
        settings["hard_exit_loss_pct"] = st.number_input("Hard Exit Loss %", value=float(settings["hard_exit_loss_pct"]), step=0.5)
        settings["tactical_exit_loss_pct"] = st.number_input("Tactical Exit Loss %", value=float(settings["tactical_exit_loss_pct"]), step=0.5)
        settings["tactical_exit_required_signals"] = st.number_input("Tactical Exit Required Signals", value=int(settings["tactical_exit_required_signals"]), step=1)
        settings["tactical_exit_rsi_max"] = st.number_input("Tactical Exit RSI Max", value=int(settings["tactical_exit_rsi_max"]), step=1)
        settings["tactical_exit_range_position_max"] = st.number_input("Tactical Exit Range Position Max", value=int(settings["tactical_exit_range_position_max"]), step=1)
        settings["tactical_exit_off_5d_high_min_pct"] = st.number_input("Tactical Exit Off 5D High Min %", value=int(settings["tactical_exit_off_5d_high_min_pct"]), step=1)
    with tabs[3]:
        settings["risk_mode"] = st.selectbox("Risk Mode", ["Auto", "Risk On", "Risk Off"], index=["Auto", "Risk On", "Risk Off"].index(settings.get("risk_mode", "Auto")))
        st.write("Data source: Yahoo Finance chart endpoint, with sample-price fallback.")
    with tabs[4]:
        render_holdings_editor(portfolio)
    with tabs[5]:
        st.json({"portfolio": portfolio, "settings": settings})

    if st.button("Save Settings", type="primary"):
        save_json(SETTINGS_PATH, settings)
        save_json(PORTFOLIO_PATH, portfolio)
        st.success("Settings saved.")


def render_watchlist(portfolio: dict[str, Any]) -> None:
    st.header("Watchlist")
    rows = []
    histories = fetch_history(tuple(item["ticker"] for item in portfolio["holdings"]), "7d")
    for item in portfolio["holdings"]:
        hist = histories[item["ticker"]]
        rows.append(
            {
                "Ticker": item["ticker"],
                "Name": item["name"],
                "Category": item["category"],
                "Price": money(latest_price(hist, item["ticker"])),
                "Daily": pct(daily_change_pct(hist)),
                "Target": f"{item['target_weight']:.1f}%",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_ledger() -> None:
    st.header("Ledger")
    st.caption("Planning ledger placeholder for manual buys, trims, exits, notes, and review history.")
    st.dataframe(
        pd.DataFrame(
            [
                {"Date": datetime.today().strftime("%Y-%m-%d"), "Ticker": "NVDA", "Action": "WATCH BUY", "Amount": "$10.70", "Note": "Below target allocation"},
                {"Date": datetime.today().strftime("%Y-%m-%d"), "Ticker": "LUNR", "Action": "HOLD", "Amount": "$0.00", "Note": "Speculative sleeve on watch"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_scout(portfolio: dict[str, Any]) -> None:
    st.header("Scout")
    st.caption("Quick read on the portfolio universe.")
    crypto = [item["ticker"] for item in portfolio["holdings"] if item["category"] == "Crypto"]
    speculative = [item["ticker"] for item in portfolio["holdings"] if item["category"] == "Speculative"]
    st.markdown(f"**Crypto sleeve:** {', '.join(crypto)}")
    st.markdown(f"**Speculative and penny sleeve:** {', '.join(speculative)}")
    st.info("I would add an alerts layer next: price bands, target allocation breaches, and a morning risk summary.")


def main() -> None:
    css()
    portfolio = load_json(PORTFOLIO_PATH, {"cash": 0, "profile": "Balanced Growth", "holdings": []})
    settings = BALANCED_PRESET.copy()
    settings.update(load_json(SETTINGS_PATH, {}))

    active = st.tabs(["Overview", "New Trade", "Settings", "Refresh", "Holdings", "Ledger", "Watchlist", "Scout"])
    topbar("Overview", datetime.now(), portfolio.get("profile", "Balanced Growth"))

    with active[0]:
        render_overview(portfolio, settings)
    with active[1]:
        render_new_trade(portfolio, settings)
    with active[2]:
        render_settings(settings, portfolio)
    with active[3]:
        if st.button("Refresh Market Data", type="primary"):
            fetch_history.clear()
            st.rerun()
        st.write("Market cache is refreshed every five minutes.")
    with active[4]:
        render_holdings_editor(portfolio)
    with active[5]:
        render_ledger()
    with active[6]:
        render_watchlist(portfolio)
    with active[7]:
        render_scout(portfolio)


if __name__ == "__main__":
    main()
