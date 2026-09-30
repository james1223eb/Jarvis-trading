# JARVIS Trading V1

Responsive Python/Flask trading website prototype.

## Included
- iPad-friendly dark UI
- $100,000 virtual paper account
- Buy/sell paper trades
- Portfolio and P/L
- Market quotes
- Jarvis V1 assistant placeholder
- Trading Academy
- Community posts
- SQLite database

## Run
Install Python 3.11+, then:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python app.py

Open the local address shown by Flask.

## Important
This is a prototype. It is not ready for public internet use as-is.
Before deployment, add production authentication, HTTPS, secure secrets,
a production database, rate limiting, validation, and a proper market-data
provider. Real-money broker integration should be added only as a separate,
explicit feature.
