# Max ROI Stock Dashboard

A professional Streamlit portfolio dashboard for stocks, penny stocks, and crypto.

## Included Universe

- Core and aggressive growth names from the reference layout
- Crypto: `BTC-USD`, `ETH-USD`, `ADA-USD`, `XLM-USD`, `ANKR-USD`
- Penny/speculative names: `LUNR`, `BFGFF`

## Make It Your Own

Open the **Setup** tab inside the app to edit:

- dashboard name, owner name, and cover page tagline
- cash available
- stocks, ETFs, penny stocks, and crypto tickers
- shares, average cost, category, and target allocation
- default stock broker link, crypto exchange link, and research link
- optional asset-specific trade and research links
- watchlist-only assets
- buy-zone, sell-zone, and stop-review alert prices

Use the **Ledger** tab to record buys and sells. Buy/sell entries update shares, average cost, and cash. Use the **Exports** tab to download CSV files or a printable HTML report.

## Analysis Tools

The app includes:

- risk dashboard for concentration, crypto, speculative, and penny-stock exposure
- rebalance assistant showing add/trim gaps versus target allocation
- scenario planner for cash deployment and market-move stress checks
- dividend and crypto staking tracker
- news and custom events calendar
- mobile-first summary view
- user profiles, backup/restore JSON, and holdings CSV import
- theme selector and read-only sharing mode

For Yahoo Finance crypto quotes, use symbols such as `BTC-USD`, `ETH-USD`, `ADA-USD`, `XLM-USD`, and `ANKR-USD`.

The app does not place trades. Trading links open external broker or exchange pages for review and execution.

## Optional Password Protection

In Streamlit Cloud, add this secret to require a password before the dashboard opens:

```toml
DASHBOARD_PASSWORD = "your-password-here"
```

If `DASHBOARD_PASSWORD` is not set, the app opens normally.

## Run Locally

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Deploy To Streamlit Cloud

1. Push this folder to GitHub as its own repository.
2. In Streamlit Cloud, create a new app from that repo.
3. Set the main file path to `app.py`.

The app uses the Yahoo Finance chart endpoint through `requests`. If a quote is temporarily unavailable, it falls back to deterministic sample prices so the dashboard still renders.
