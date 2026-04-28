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

For Yahoo Finance crypto quotes, use symbols such as `BTC-USD`, `ETH-USD`, `ADA-USD`, `XLM-USD`, and `ANKR-USD`.

The app does not place trades. Trading links open external broker or exchange pages for review and execution.

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
