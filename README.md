# FinSight

Personal finance dashboard for recording transactions, importing CSV data, and viewing spending analysis.

## Run

From the project folder, install dependencies once:

```powershell
pip install -r backend/requirements.txt
```

Then start the app:

```powershell
python server.py
```

The terminal prints the local URL and opens the app in your browser. It uses port 8000 by default and selects another free port (up to 8010) if needed. Add `/docs` to the printed URL for API documentation. Stop the server with Ctrl+C.

Optional AI summaries need a valid `OPENAI_API_KEY`: copy `.env.example` to `.env`, replace the placeholder with your key, then restart `server.py`. Keep `.env` private and never upload it.
CSV imports need `date`, `description`, `amount`, and `type` columns; `category` is optional.

## Project files

- `server.py` — starts the API server and opens the app
- `backend/` — API, data analysis, validation, and SQLite storage
- `frontend/` — the web interface
- `data/sample_transactions.csv` — downloadable sample data
- `backend/test_app.py` — backend tests

The app is for educational purposes and does not provide financial advice.
