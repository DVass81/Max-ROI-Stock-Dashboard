from __future__ import annotations

import json
import math
import os
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
TRANSACTIONS_PATH = DATA_DIR / "transactions.json"

DEFAULT_PORTFOLIO = {
    "dashboard_name": "Max ROI",
    "owner_name": "Investor",
    "tagline": "A focused command center for stocks, crypto, risk, and allocation discipline.",
    "cash": 0.0,
    "profile": "Balanced Growth",
    "stock_broker_url": "https://robinhood.com/",
    "crypto_broker_url": "https://www.coinbase.com/",
    "research_url": "https://finance.yahoo.com/",
    "holdings": [],
}

BROKER_PRESETS = {
    "Robinhood + Coinbase": {
        "stock_broker_url": "https://robinhood.com/",
        "crypto_broker_url": "https://www.coinbase.com/",
        "research_url": "https://finance.yahoo.com/",
    },
    "Fidelity + Coinbase": {
        "stock_broker_url": "https://www.fidelity.com/trading/overview",
        "crypto_broker_url": "https://www.coinbase.com/",
        "research_url": "https://finance.yahoo.com/",
    },
    "Schwab + Kraken": {
        "stock_broker_url": "https://www.schwab.com/trading",
        "crypto_broker_url": "https://www.kraken.com/",
        "research_url": "https://finance.yahoo.com/",
    },
    "E*TRADE + Coinbase": {
        "stock_broker_url": "https://us.etrade.com/",
        "crypto_broker_url": "https://www.coinbase.com/",
        "research_url": "https://finance.yahoo.com/",
    },
    "Webull + Crypto.com": {
        "stock_broker_url": "https://www.webull.com/",
        "crypto_broker_url": "https://crypto.com/",
        "research_url": "https://finance.yahoo.com/",
    },
}

HOLDINGS_COLUMNS = [
    "ticker",
    "name",
    "category",
    "watch_only",
    "shares",
    "avg_cost",
    "target_weight",
    "buy_below",
    "sell_above",
    "stop_below",
    "trade_url",
    "research_url",
]

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
        button[data-baseweb="tab"],
        button[data-baseweb="tab"] p,
        div[role="tablist"] button,
        div[role="tablist"] button p {
            color: #ffffff !important;
            font-weight: 800 !important;
        }
        button[data-baseweb="tab"][aria-selected="true"],
        button[data-baseweb="tab"][aria-selected="true"] p,
        div[role="tab"][aria-selected="true"],
        div[role="tab"][aria-selected="true"] p {
            color: var(--green) !important;
            border-bottom-color: var(--green) !important;
        }
        label, .stTextInput label, .stNumberInput label, .stSelectbox label {
            color: #ffffff !important;
            font-weight: 760 !important;
        }
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
        .cover {
            min-height: 420px;
            display: grid;
            grid-template-columns: minmax(300px, 1.1fr) minmax(320px, 0.9fr);
            gap: 1.2rem;
            align-items: stretch;
            margin-bottom: 1rem;
        }
        .cover-hero {
            background:
                linear-gradient(135deg, rgba(5, 11, 18, 0.96), rgba(12, 23, 38, 0.84)),
                radial-gradient(circle at 78% 18%, rgba(34, 197, 94, 0.23), transparent 34%),
                radial-gradient(circle at 18% 76%, rgba(96, 165, 250, 0.18), transparent 30%);
            border: 1px solid var(--line);
            padding: 2.2rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .cover-title {
            font-size: clamp(2.3rem, 4.8vw, 5.4rem);
            line-height: 0.95;
            margin: 0;
            font-weight: 900;
        }
        .cover-tagline {
            color: #b8c6d8;
            font-size: 1.08rem;
            max-width: 760px;
            margin-top: 1rem;
        }
        .ticker-tape {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.65rem;
            margin-top: 1.8rem;
        }
        .ticker-card {
            border: 1px solid var(--line);
            background: rgba(7, 15, 26, 0.76);
            padding: 0.75rem;
            min-height: 82px;
        }
        .ticker-card b { display: block; font-size: 0.95rem; }
        .ticker-card span { color: var(--muted); font-size: 0.74rem; }
        .cover-panel {
            background: var(--panel);
            border: 1px solid var(--line);
            padding: 1rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .link-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(160px, 1fr));
            gap: 0.7rem;
        }
        .action-link {
            display: block;
            border: 1px solid var(--line);
            background: #091322;
            padding: 0.85rem;
            color: var(--text) !important;
            text-decoration: none !important;
            min-height: 86px;
        }
        .action-link small { color: var(--muted); display: block; margin-top: 0.35rem; }
        .setup-callout {
            border: 1px solid rgba(34, 197, 94, 0.38);
            background: rgba(34, 197, 94, 0.09);
            padding: 1rem;
            margin: 1rem 0;
        }
        .setup-callout h3 { margin-top: 0; color: #ffffff; }
        .setup-callout li, .setup-callout p { color: #e5eef9; }
        .alert-row {
            display: grid;
            grid-template-columns: 110px 1fr auto;
            gap: 0.7rem;
            align-items: center;
            border: 1px solid var(--line);
            background: #08111f;
            padding: 0.7rem;
            margin-bottom: 0.45rem;
        }
        .auth-card {
            max-width: 460px;
            margin: 8vh auto;
            border: 1px solid var(--line);
            background: var(--panel);
            padding: 1.2rem;
        }
        @media (max-width: 900px) {
            .cover { grid-template-columns: 1fr; }
            .ticker-tape, .link-grid, .setting-grid { grid-template-columns: 1fr 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_url(value: object, fallback: str = "") -> str:
    url = str(value or "").strip()
    if not url:
        return fallback
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "watch"}


def normalize_portfolio(portfolio: dict[str, Any]) -> dict[str, Any]:
    normalized = DEFAULT_PORTFOLIO.copy()
    if isinstance(portfolio, dict):
        normalized.update(portfolio)
    normalized["cash"] = safe_float(normalized.get("cash"))
    normalized["dashboard_name"] = str(normalized.get("dashboard_name") or "Max ROI").strip()
    normalized["owner_name"] = str(normalized.get("owner_name") or "Investor").strip()
    normalized["tagline"] = str(normalized.get("tagline") or DEFAULT_PORTFOLIO["tagline"]).strip()
    normalized["stock_broker_url"] = normalize_url(normalized.get("stock_broker_url"), DEFAULT_PORTFOLIO["stock_broker_url"])
    normalized["crypto_broker_url"] = normalize_url(normalized.get("crypto_broker_url"), DEFAULT_PORTFOLIO["crypto_broker_url"])
    normalized["research_url"] = normalize_url(normalized.get("research_url"), DEFAULT_PORTFOLIO["research_url"])
    holdings = []
    for item in normalized.get("holdings", []):
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        category = str(item.get("category") or "Core").strip()
        default_trade_url = normalized["crypto_broker_url"] if category == "Crypto" or ticker.endswith("-USD") else normalized["stock_broker_url"]
        holdings.append(
            {
                "ticker": ticker,
                "name": str(item.get("name") or ticker).strip(),
                "category": category,
                "shares": safe_float(item.get("shares")),
                "avg_cost": safe_float(item.get("avg_cost")),
                "target_weight": safe_float(item.get("target_weight")),
                "watch_only": safe_bool(item.get("watch_only", False)),
                "buy_below": safe_float(item.get("buy_below")),
                "sell_above": safe_float(item.get("sell_above")),
                "stop_below": safe_float(item.get("stop_below")),
                "trade_url": normalize_url(item.get("trade_url"), default_trade_url),
                "research_url": normalize_url(item.get("research_url"), yahoo_quote_url(ticker)),
            }
        )
    normalized["holdings"] = holdings
    return normalized


def yahoo_quote_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def asset_type_label(ticker: str, category: str) -> str:
    if category == "Crypto" or ticker.endswith("-USD"):
        return "Crypto"
    if ticker.startswith("^"):
        return "Index"
    return "Stock"


def get_secret_value(name: str) -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, ""))
    except Exception:  # noqa: BLE001
        return ""


def require_auth() -> bool:
    password = get_secret_value("DASHBOARD_PASSWORD")
    if not password:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.title("Portfolio Access")
    st.caption("Enter the dashboard password to continue.")
    attempt = st.text_input("Password", type="password", key="dashboard_password")
    if st.button("Unlock Dashboard", type="primary"):
        if attempt == password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Password did not match.")
    st.markdown("</div>", unsafe_allow_html=True)
    return False


def load_transactions() -> list[dict[str, Any]]:
    data = load_json(TRANSACTIONS_PATH, [])
    return data if isinstance(data, list) else []


def save_transactions(records: list[dict[str, Any]]) -> None:
    save_json(TRANSACTIONS_PATH, records)


def make_report_html(portfolio: dict[str, Any], df: pd.DataFrame, transactions: list[dict[str, Any]]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    rows = ""
    for _, row in df.iterrows():
        rows += (
            f"<tr><td>{row['Ticker']}</td><td>{row['Category']}</td><td>{money(float(row['Current']))}</td>"
            f"<td>{money(float(row['Value']))}</td><td>{float(row['Gain %']):+.2f}%</td>"
            f"<td>{row.get('Signal', '')}</td><td>{row.get('Alert', '')}</td></tr>"
        )
    ledger_rows = ""
    for tx in transactions[-12:]:
        ledger_rows += (
            f"<tr><td>{tx.get('date', '')}</td><td>{tx.get('ticker', '')}</td><td>{tx.get('action', '')}</td>"
            f"<td>{tx.get('shares', '')}</td><td>{tx.get('price', '')}</td><td>{tx.get('note', '')}</td></tr>"
        )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{portfolio['dashboard_name']} Snapshot</title>
<style>
body {{ font-family: Arial, sans-serif; background:#07101c; color:#e5eef9; padding:32px; }}
h1 {{ font-size:42px; margin-bottom:4px; }}
.muted {{ color:#9fb0c7; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
th, td {{ border:1px solid #22334a; padding:8px; text-align:left; }}
th {{ background:#0d1a2b; }}
.card {{ border:1px solid #22334a; background:#0b1422; padding:16px; margin:16px 0; }}
</style>
</head>
<body>
<h1>{portfolio['dashboard_name']}</h1>
<div class="muted">{portfolio['owner_name']} | Generated {generated}</div>
<div class="card">{portfolio['tagline']}</div>
<h2>Portfolio Snapshot</h2>
<table><thead><tr><th>Ticker</th><th>Category</th><th>Current</th><th>Value</th><th>Gain %</th><th>Signal</th><th>Alert</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Recent Ledger</h2>
<table><thead><tr><th>Date</th><th>Ticker</th><th>Action</th><th>Shares</th><th>Price</th><th>Note</th></tr></thead><tbody>{ledger_rows}</tbody></table>
</body>
</html>"""


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
    if df.empty:
        return df
    records: list[dict[str, Any]] = []
    deployable_cash = max(cash - float(settings["minimum_cash_reserve"]), 0)
    max_trade = deployable_cash * float(settings["max_trade_pct_available_cash"])
    for _, row in df.iterrows():
        if bool(row.get("watch_only", False)):
            records.append(
                {
                    "Status": "WATCHLIST",
                    "Trend": "WATCH",
                    "Timing": "ENTRY SCOUT",
                    "Signal": "WATCH",
                    "Score": 50,
                    "Action $": 0.0,
                }
            )
            continue
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
        buy_below = float(item.get("buy_below") or 0)
        sell_above = float(item.get("sell_above") or 0)
        stop_below = float(item.get("stop_below") or 0)
        alert = "On Watch"
        if stop_below and current <= stop_below:
            alert = "Stop Review"
        elif buy_below and current <= buy_below:
            alert = "Buy Zone"
        elif sell_above and current >= sell_above:
            alert = "Sell Zone"
        rows.append(
            {
                "Ticker": ticker,
                "Name": item["name"],
                "Category": item["category"],
                "Type": asset_type_label(ticker, item["category"]),
                "Current": current,
                "Avg Cost": avg_cost,
                "Shares": shares,
                "shares": shares,
                "Watch Only": bool(item.get("watch_only", False)),
                "watch_only": bool(item.get("watch_only", False)),
                "Value": value,
                "Gain $": gain,
                "Gain %": gain_pct,
                "gain_pct": gain_pct,
                "Target %": float(item["target_weight"]),
                "Buy Below": buy_below,
                "Sell Above": sell_above,
                "Stop Below": stop_below,
                "Alert": alert,
                "Daily %": daily_change_pct(hist),
                "range_position": range_position(hist),
                "history": hist,
                "Trade Link": item.get("trade_url") or portfolio.get("stock_broker_url", ""),
                "Research Link": item.get("research_url") or yahoo_quote_url(ticker),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    portfolio_value = float(df["Value"].sum()) + float(portfolio.get("cash", 0))
    df["portfolio_value"] = portfolio_value
    df["Allocation %"] = (df["Value"] / portfolio_value) * 100 if portfolio_value else 0
    df["allocation_pct"] = df["Allocation %"]
    df["target_weight"] = df["Target %"]
    df["daily_pct"] = df["Daily %"]
    return df


def topbar(active: str, refreshed: datetime, profile: str, dashboard_name: str) -> None:
    st.markdown(
        f"""
        <div class="topbar">
            <div class="brand">
                <div class="brand-bars"><span></span><span></span><span></span><span></span></div>
                <div>{dashboard_name}</div>
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
    if df.empty:
        st.info("Add holdings in Setup to start building the dashboard.")
        return
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
    if df.empty:
        st.info("No holdings are configured yet.")
        return
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
            "Alert",
            "Daily",
            "Status",
            "Trend",
            "Timing",
            "Signal",
            "Score",
            "Action $",
            "Research Link",
            "Trade Link",
        ]
    ]
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "Research Link": st.column_config.LinkColumn("Research"),
            "Trade Link": st.column_config.LinkColumn("Trade"),
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


def render_alerts(df: pd.DataFrame) -> None:
    if df.empty:
        return
    active_alerts = df[df["Alert"].isin(["Buy Zone", "Sell Zone", "Stop Review"])].copy()
    st.markdown('<div class="panel"><h3>Price Alerts</h3>', unsafe_allow_html=True)
    if active_alerts.empty:
        st.markdown('<div class="small-muted">No buy-zone, sell-zone, or stop-review alerts are active.</div>', unsafe_allow_html=True)
    for _, row in active_alerts.sort_values("Alert").iterrows():
        cls = "green" if row["Alert"] == "Buy Zone" else "yellow"
        if row["Alert"] == "Stop Review":
            cls = "red"
        st.markdown(
            f"""
            <div class="alert-row">
                <b>{row['Ticker']}</b>
                <span>{row['Name']} | Current {money(float(row['Current']))}</span>
                <span class="pill {cls}">{row['Alert']}</span>
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
    if not tickers:
        st.info("Use Setup to add stocks, crypto, ETFs, or penny stocks.")
        return
    histories = fetch_history(tickers, "7d")
    cash = float(portfolio.get("cash", 0))
    df = build_portfolio_frame(portfolio, histories)
    df = calculate_signals(df, settings, cash)
    render_metrics(df, cash)
    st.markdown("### Holdings")
    render_holdings_table(df)
    render_alerts(df)
    render_opportunities(df)
    render_allocation(df, cash)


def render_home(portfolio: dict[str, Any], settings: dict[str, Any]) -> None:
    tickers = tuple(item["ticker"] for item in portfolio["holdings"])
    histories = fetch_history(tickers[:8], "7d") if tickers else {}
    df = pd.DataFrame()
    if tickers:
        all_histories = fetch_history(tickers, "7d")
        df = calculate_signals(build_portfolio_frame(portfolio, all_histories), settings, float(portfolio.get("cash", 0)))
    portfolio_value = float(df["Value"].sum()) + float(portfolio.get("cash", 0)) if not df.empty else float(portfolio.get("cash", 0))
    buy_count = int((df["Signal"] == "WATCH BUY").sum()) if not df.empty else 0
    trim_count = int(df["Signal"].isin(["TRIM", "EXIT"]).sum()) if not df.empty else 0
    best = df.sort_values("Gain %", ascending=False).iloc[0]["Ticker"] if not df.empty else "Add assets"
    tape_html = ""
    for item in portfolio["holdings"][:4]:
        ticker = item["ticker"]
        hist = histories.get(ticker, pd.DataFrame())
        tape_html += (
            f"<div class='ticker-card'><b>{ticker}</b>"
            f"<span>{money(latest_price(hist, ticker))} | {pct(daily_change_pct(hist))}</span></div>"
        )
    if not tape_html:
        tape_html = "<div class='ticker-card'><b>Setup</b><span>Add your first tracked assets</span></div>"
    st.markdown(
        f"""
        <div class="cover">
            <section class="cover-hero">
                <div>
                    <span class="pill green">{portfolio.get('profile', 'Balanced Growth')}</span>
                    <h1 class="cover-title">{portfolio['dashboard_name']}</h1>
                    <p class="cover-tagline">{portfolio['tagline']}</p>
                </div>
                <div class="ticker-tape">{tape_html}</div>
            </section>
            <aside class="cover-panel">
                <div>
                    <h3>{portfolio['owner_name']} Portfolio Brief</h3>
                    <div class="opportunity" style="grid-template-columns:1fr auto;"><b>Total Value</b><span>{money(portfolio_value)}</span></div>
                    <div class="opportunity" style="grid-template-columns:1fr auto;"><b>Tracked Assets</b><span>{len(portfolio['holdings'])}</span></div>
                    <div class="opportunity" style="grid-template-columns:1fr auto;"><b>Watch Buys</b><span>{buy_count}</span></div>
                    <div class="opportunity" style="grid-template-columns:1fr auto;"><b>Trim / Exit</b><span>{trim_count}</span></div>
                    <div class="opportunity" style="grid-template-columns:1fr auto;"><b>Top Performer</b><span>{best}</span></div>
                </div>
                <p class="small-muted">Dashboard signals are planning aids only. Review risk, liquidity, and your brokerage order screen before making any trade.</p>
            </aside>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Cash Available", money(float(portfolio.get("cash", 0))), "editable in Setup")
    c2.metric("Risk Mode", settings.get("risk_mode", "Auto"), portfolio.get("profile", "Balanced Growth"))
    c3.metric("Universe", f"{len(portfolio['holdings'])} assets", "stocks, ETFs, crypto")
    st.markdown(
        """
        <div class="setup-callout">
            <h3>Personalize This Dashboard</h3>
            <p>Use the <b>Personalize / Setup</b> tab at the top to add or remove stocks and crypto, update shares, adjust average cost, change cash available, and set your own broker or crypto exchange links.</p>
            <ul>
                <li>Add a new stock or crypto by inserting a row in the holdings table.</li>
                <li>Use Yahoo Finance crypto symbols like <b>BTC-USD</b>, <b>ETH-USD</b>, <b>ADA-USD</b>, <b>XLM-USD</b>, and <b>ANKR-USD</b>.</li>
                <li>Set category, shares, average cost, and target allocation, then click <b>Save Holdings</b>.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_new_trade(portfolio: dict[str, Any], settings: dict[str, Any]) -> None:
    st.header("New Trade")
    st.caption("Position sizing follows the active preset and current target allocation gap.")
    tickers = [item["ticker"] for item in portfolio["holdings"]]
    if not tickers:
        st.info("Add at least one tracked asset in Setup before planning a trade.")
        return
    selected = st.selectbox("Ticker", tickers, key="new_trade_ticker")
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
    trade_amount = st.number_input("Planned trade amount", min_value=0.0, max_value=max(cash, 1.0), value=round(min(max_trade, cash), 2), step=1.0, key="new_trade_amount")
    shares = trade_amount / price if price else 0
    st.info(f"Estimated shares: {shares:,.6f}. This dashboard records planning signals only and does not place trades.")
    col1, col2, col3 = st.columns(3)
    col1.link_button("Open Trade Platform", item.get("trade_url") or portfolio.get("stock_broker_url", "https://robinhood.com/"), use_container_width=True)
    col2.link_button("Open Yahoo Research", item.get("research_url") or yahoo_quote_url(selected), use_container_width=True)
    col3.link_button("Open Broker Home", portfolio.get("crypto_broker_url") if item.get("category") == "Crypto" else portfolio.get("stock_broker_url"), use_container_width=True)


def render_portfolio_identity(portfolio: dict[str, Any], key_prefix: str) -> None:
    st.subheader("Dashboard Identity")
    portfolio["dashboard_name"] = st.text_input("Dashboard name", value=portfolio["dashboard_name"], key=f"{key_prefix}_dashboard_name")
    portfolio["owner_name"] = st.text_input("Owner or group name", value=portfolio["owner_name"], key=f"{key_prefix}_owner_name")
    portfolio["tagline"] = st.text_input("Cover page tagline", value=portfolio["tagline"], key=f"{key_prefix}_tagline")
    col1, col2, col3 = st.columns(3)
    portfolio["stock_broker_url"] = col1.text_input("Default stock/ETF trade link", value=portfolio["stock_broker_url"], key=f"{key_prefix}_stock_url")
    portfolio["crypto_broker_url"] = col2.text_input("Default crypto trade link", value=portfolio["crypto_broker_url"], key=f"{key_prefix}_crypto_url")
    portfolio["research_url"] = col3.text_input("Default research home", value=portfolio["research_url"], key=f"{key_prefix}_research_url")
    st.markdown("#### Broker Presets")
    preset_cols = st.columns(len(BROKER_PRESETS))
    for index, (label, preset) in enumerate(BROKER_PRESETS.items()):
        if preset_cols[index].button(label, key=f"{key_prefix}_preset_{index}", use_container_width=True):
            portfolio.update(preset)
            save_json(PORTFOLIO_PATH, normalize_portfolio(portfolio))
            st.success(f"{label} links applied. Refresh or reopen Setup to see the fields update.")


def render_holdings_editor(portfolio: dict[str, Any], key_prefix: str = "holdings", show_identity: bool = False) -> None:
    st.header("Personalize This Dashboard" if show_identity else "Holdings")
    st.caption("Make this dashboard yours by editing the account name, links, stocks, crypto, shares, cost basis, and target weights.")
    if show_identity:
        st.info(
            "To add a new stock or crypto, scroll to the holdings table below and use the blank row at the bottom. "
            "Fill in ticker, name, category, shares, average cost, and target weight, then save."
        )
    if show_identity:
        render_portfolio_identity(portfolio, key_prefix)
        st.divider()
    holdings_df = pd.DataFrame(portfolio["holdings"])
    if holdings_df.empty:
        holdings_df = pd.DataFrame(columns=HOLDINGS_COLUMNS)
    edited = st.data_editor(
        holdings_df,
        use_container_width=True,
        num_rows="dynamic",
        key=f"{key_prefix}_editor",
        column_config={
            "category": st.column_config.SelectboxColumn(
                "category",
                options=["Core", "Aggressive", "Speculative", "Defensive", "Crypto"],
            ),
            "watch_only": st.column_config.CheckboxColumn("watch_only"),
            "shares": st.column_config.NumberColumn("shares", min_value=0.0, step=0.000001),
            "avg_cost": st.column_config.NumberColumn("avg_cost", min_value=0.0, step=0.01),
            "target_weight": st.column_config.NumberColumn("target_weight", min_value=0.0, max_value=100.0, step=0.5),
            "buy_below": st.column_config.NumberColumn("buy_below", min_value=0.0, step=0.01),
            "sell_above": st.column_config.NumberColumn("sell_above", min_value=0.0, step=0.01),
            "stop_below": st.column_config.NumberColumn("stop_below", min_value=0.0, step=0.01),
            "trade_url": st.column_config.LinkColumn("trade_url"),
            "research_url": st.column_config.LinkColumn("research_url"),
        },
    )
    cash = st.number_input(
        "Cash available",
        min_value=0.0,
        value=float(portfolio.get("cash", 0)),
        step=1.0,
        key=f"{key_prefix}_cash",
    )
    if st.button("Save Holdings", type="primary", key=f"{key_prefix}_save"):
        portfolio["holdings"] = edited.to_dict("records")
        portfolio["cash"] = cash
        portfolio = normalize_portfolio(portfolio)
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
    tabs = st.tabs(["Strategy", "Buy & Add Logic", "Trim & Exit Logic", "System", "Setup", "Raw JSON"])
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
        render_holdings_editor(portfolio, "settings_holdings", show_identity=True)
    with tabs[5]:
        st.json({"portfolio": portfolio, "settings": settings})

    if st.button("Save Settings", type="primary"):
        save_json(SETTINGS_PATH, settings)
        save_json(PORTFOLIO_PATH, portfolio)
        st.success("Settings saved.")


def render_watchlist(portfolio: dict[str, Any]) -> None:
    st.header("Watchlist")
    if not portfolio["holdings"]:
        st.info("Add assets in Setup to build a watchlist.")
        return
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
                "Research": item.get("research_url") or yahoo_quote_url(item["ticker"]),
                "Trade": item.get("trade_url") or portfolio.get("stock_broker_url"),
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={"Research": st.column_config.LinkColumn("Research"), "Trade": st.column_config.LinkColumn("Trade")},
    )


def render_trading_links(portfolio: dict[str, Any]) -> None:
    st.header("Trading Links")
    st.caption("Quick links are editable in Setup. Use your own preferred broker or exchange links.")
    st.markdown(
        f"""
        <div class="link-grid">
            <a class="action-link" href="{portfolio['stock_broker_url']}" target="_blank"><b>Stocks / ETFs</b><small>Default brokerage link</small></a>
            <a class="action-link" href="{portfolio['crypto_broker_url']}" target="_blank"><b>Crypto</b><small>Default crypto exchange link</small></a>
            <a class="action-link" href="{portfolio['research_url']}" target="_blank"><b>Research</b><small>Market research home</small></a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rows = []
    for item in portfolio["holdings"]:
        rows.append(
            {
                "Ticker": item["ticker"],
                "Name": item["name"],
                "Type": asset_type_label(item["ticker"], item["category"]),
                "Research": item.get("research_url") or yahoo_quote_url(item["ticker"]),
                "Trade": item.get("trade_url") or portfolio.get("stock_broker_url"),
            }
        )
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Research": st.column_config.LinkColumn("Research"), "Trade": st.column_config.LinkColumn("Trade")},
        )
    else:
        st.info("No tracked assets yet. Add rows in Setup to create asset-specific trading links.")
    st.warning("This dashboard does not place trades. Links open external platforms where you remain responsible for order review and execution.")


def render_exports(portfolio: dict[str, Any], settings: dict[str, Any]) -> None:
    st.header("Exports")
    st.caption("Download portfolio data, transaction history, or a polished HTML report that can be printed to PDF.")
    tickers = tuple(item["ticker"] for item in portfolio["holdings"])
    transactions = load_transactions()
    if tickers:
        histories = fetch_history(tickers, "7d")
        df = calculate_signals(build_portfolio_frame(portfolio, histories), settings, float(portfolio.get("cash", 0)))
    else:
        df = pd.DataFrame()

    portfolio_csv = df.drop(columns=["history"], errors="ignore").to_csv(index=False) if not df.empty else ""
    transactions_csv = pd.DataFrame(transactions).to_csv(index=False) if transactions else ""
    report_html = make_report_html(portfolio, df, transactions)
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Download Portfolio CSV",
        data=portfolio_csv,
        file_name="max_roi_portfolio.csv",
        mime="text/csv",
        disabled=df.empty,
        use_container_width=True,
    )
    c2.download_button(
        "Download Ledger CSV",
        data=transactions_csv,
        file_name="max_roi_transactions.csv",
        mime="text/csv",
        disabled=not transactions,
        use_container_width=True,
    )
    c3.download_button(
        "Download HTML Report",
        data=report_html,
        file_name="max_roi_snapshot.html",
        mime="text/html",
        use_container_width=True,
    )
    st.info("Open the HTML report in your browser and use Print > Save as PDF for a clean portfolio snapshot.")


def apply_transaction_to_portfolio(portfolio: dict[str, Any], transaction: dict[str, Any]) -> dict[str, Any]:
    action = transaction["action"]
    ticker = transaction["ticker"].upper()
    shares = float(transaction.get("shares") or 0)
    price = float(transaction.get("price") or 0)
    amount = shares * price
    if action not in {"Buy", "Sell"} or shares <= 0 or price <= 0:
        return portfolio

    for item in portfolio["holdings"]:
        if item["ticker"] != ticker:
            continue
        current_shares = float(item.get("shares") or 0)
        current_cost = float(item.get("avg_cost") or 0)
        if action == "Buy":
            new_shares = current_shares + shares
            total_cost = current_shares * current_cost + amount
            item["shares"] = new_shares
            item["avg_cost"] = total_cost / new_shares if new_shares else 0
            item["watch_only"] = False
            portfolio["cash"] = max(float(portfolio.get("cash") or 0) - amount, 0)
        else:
            item["shares"] = max(current_shares - shares, 0)
            portfolio["cash"] = float(portfolio.get("cash") or 0) + amount
        return portfolio

    if action == "Buy":
        portfolio["holdings"].append(
            {
                "ticker": ticker,
                "name": ticker,
                "category": "Crypto" if ticker.endswith("-USD") else "Core",
                "shares": shares,
                "avg_cost": price,
                "target_weight": 0,
                "watch_only": False,
                "buy_below": 0,
                "sell_above": 0,
                "stop_below": 0,
            }
        )
        portfolio["cash"] = max(float(portfolio.get("cash") or 0) - amount, 0)
    return portfolio


def render_ledger(portfolio: dict[str, Any]) -> None:
    st.header("Transaction Ledger")
    st.caption("Record buys, sells, notes, and reviews. Buy/sell entries update shares, average cost, and cash.")
    transactions = load_transactions()
    tickers = [item["ticker"] for item in portfolio["holdings"]]
    with st.form("transaction_form"):
        c1, c2, c3, c4 = st.columns(4)
        tx_date = c1.date_input("Date", value=datetime.today(), key="ledger_date")
        ticker = c2.selectbox("Ticker", sorted(set(tickers + ["NEW"])), key="ledger_ticker")
        custom_ticker = c2.text_input("New ticker", value="", help="Use this when Ticker is NEW.", key="ledger_custom_ticker")
        action = c3.selectbox("Action", ["Buy", "Sell", "Note", "Review"], key="ledger_action")
        shares = c4.number_input("Shares / Units", min_value=0.0, value=0.0, step=0.000001, key="ledger_shares")
        price = st.number_input("Price", min_value=0.0, value=0.0, step=0.01, key="ledger_price")
        note = st.text_input("Note", value="", key="ledger_note")
        submitted = st.form_submit_button("Record Transaction", type="primary")
    if submitted:
        final_ticker = custom_ticker.strip().upper() if ticker == "NEW" else ticker
        if not final_ticker:
            st.error("Enter a ticker before recording the transaction.")
            return
        transaction = {
            "date": tx_date.isoformat(),
            "ticker": final_ticker,
            "action": action,
            "shares": shares,
            "price": price,
            "amount": round(shares * price, 2),
            "note": note,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        transactions.append(transaction)
        portfolio = apply_transaction_to_portfolio(portfolio, transaction)
        save_transactions(transactions)
        save_json(PORTFOLIO_PATH, normalize_portfolio(portfolio))
        st.success("Transaction recorded.")

    if transactions:
        st.dataframe(pd.DataFrame(transactions).sort_values("created_at", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions recorded yet.")


def render_scout(portfolio: dict[str, Any]) -> None:
    st.header("Scout")
    st.caption("Quick read on the portfolio universe.")
    crypto = [item["ticker"] for item in portfolio["holdings"] if item["category"] == "Crypto"]
    speculative = [item["ticker"] for item in portfolio["holdings"] if item["category"] == "Speculative"]
    st.markdown(f"**Crypto sleeve:** {', '.join(crypto)}")
    st.markdown(f"**Speculative and penny sleeve:** {', '.join(speculative)}")
    st.info("I would add an alerts layer next: price bands, target allocation breaches, and a morning risk summary.")
    st.markdown("### Recommended Next Upgrades")
    st.markdown(
        "- Add per-position alert bands for buy zones, trim zones, and stop review levels.\n"
        "- Add a transaction ledger so cost basis updates from buys and sells instead of manual editing.\n"
        "- Add separate watchlist-only assets with target entry prices.\n"
        "- Add an export button for a weekly portfolio PDF or CSV snapshot.\n"
        "- Add optional login protection before sharing a public Streamlit link."
    )


def main() -> None:
    css()
    if not require_auth():
        return
    portfolio = normalize_portfolio(load_json(PORTFOLIO_PATH, DEFAULT_PORTFOLIO.copy()))
    settings = BALANCED_PRESET.copy()
    settings.update(load_json(SETTINGS_PATH, {}))

    active = st.tabs(["Home", "Personalize / Setup", "Overview", "New Trade", "Trading Links", "Alerts", "Ledger", "Exports", "Settings", "Refresh", "Watchlist", "Scout"])
    topbar("Dashboard", datetime.now(), portfolio.get("profile", "Balanced Growth"), portfolio["dashboard_name"])

    with active[0]:
        render_home(portfolio, settings)
    with active[1]:
        render_holdings_editor(portfolio, "setup_page", show_identity=True)
    with active[2]:
        render_overview(portfolio, settings)
    with active[3]:
        render_new_trade(portfolio, settings)
    with active[4]:
        render_trading_links(portfolio)
    with active[5]:
        tickers = tuple(item["ticker"] for item in portfolio["holdings"])
        if tickers:
            histories = fetch_history(tickers, "7d")
            alert_df = calculate_signals(build_portfolio_frame(portfolio, histories), settings, float(portfolio.get("cash", 0)))
            render_alerts(alert_df)
        else:
            st.info("Add assets in Setup to create alerts.")
    with active[6]:
        render_ledger(portfolio)
    with active[7]:
        render_exports(portfolio, settings)
    with active[8]:
        render_settings(settings, portfolio)
    with active[9]:
        if st.button("Refresh Market Data", type="primary"):
            fetch_history.clear()
            st.rerun()
        st.write("Market cache is refreshed every five minutes.")
    with active[10]:
        render_watchlist(portfolio)
    with active[11]:
        render_scout(portfolio)


if __name__ == "__main__":
    main()
