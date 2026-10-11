"""
FinSight — main.py
FastAPI backend. All API routes are defined here.

Routes:
  GET  /api                     — health check
  GET  /api/transactions        — list all transactions (with optional filters)
  POST /api/transactions        — add a new transaction
  DELETE /api/transactions/{id} — delete a transaction
  POST /api/upload              — upload and import a CSV file
  GET  /api/dashboard           — summary + charts data
  GET  /api/analysis            — detailed statistics and category/monthly breakdown
  GET  /api/insights            — list of auto-generated insight strings
  POST /api/ai-summary          — optional AI narrative (requires API key)

Run:
  uvicorn main:app --reload
"""

import io
import os
import sys
import json

# Allow running from repo root (e.g. Render: uvicorn backend.main:app)
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db, get_connection
from models import Transaction
from finance_analysis import (
    clean_data, auto_categorize,
    calculate_summary, category_analysis,
    monthly_analysis, basic_stats,
    detect_high_expenses, generate_insights,
)
from ai_service import get_ai_summary

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FinSight API",
    description="Personal Finance Data Analyzer — B.Tech Project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create DB table on startup
init_db()

# ── Serve frontend static files ───────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Also serve the sample CSV from the data folder
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    if os.path.isdir(DATA_DIR):
        app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


# ── Helper: load all transactions as a DataFrame ──────────────────────────────

def load_df() -> pd.DataFrame:
    """Read all rows from SQLite into a Pandas DataFrame."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, description, amount, type, category FROM transactions ORDER BY date DESC"
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame(columns=["id", "date", "description", "amount", "type", "category"])
    return pd.DataFrame([dict(r) for r in rows])


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api")
def health_check():
    """Confirms the backend is running."""
    return {"message": "FinSight is running", "server_version": 2}


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get("/api/transactions")
def get_transactions(
    search:   str = Query("", description="Filter by description keyword"),
    type:     str = Query("", description="Filter by 'income' or 'expense'"),
    category: str = Query("", description="Filter by category name"),
):
    """Return all transactions, with optional filters."""
    df = load_df()
    if df.empty:
        return []

    # Apply filters
    if search:
        df = df[df["description"].str.contains(search, case=False, na=False)]
    if type and type in ("income", "expense"):
        df = df[df["type"] == type]
    if category:
        df = df[df["category"] == category]

    # Mark high expenses
    df = detect_high_expenses(df)
    records = df.to_dict(orient="records")

    # Convert numpy bool to Python bool so JSON serialisation works
    for r in records:
        r["is_high_expense"] = bool(r.get("is_high_expense", False))
    return records


@app.post("/api/transactions", status_code=201)
def add_transaction(txn: Transaction):
    """Add a single transaction entered manually by the user."""
    # Auto-categorize if category is default/empty
    category = txn.category or "Other"
    if category == "Other":
        category = auto_categorize(txn.description)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO transactions (date, description, amount, type, category) VALUES (?, ?, ?, ?, ?)",
            (txn.date, txn.description, txn.amount, txn.type, category),
        )
        conn.commit()
    finally:
        conn.close()
    return {"message": "Transaction added successfully"}


@app.delete("/api/transactions/{txn_id}", status_code=200)
def delete_transaction(txn_id: int):
    """Delete a transaction by ID."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Transaction not found")
    finally:
        conn.close()
    return {"message": "Transaction deleted"}


# ── CSV Upload ────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file, clean it with Pandas, and store valid rows in SQLite.
    Returns an import summary.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        raw_df = pd.read_csv(io.BytesIO(content), encoding="utf-8", on_bad_lines="skip")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {str(e)}")

    if raw_df.empty:
        raise HTTPException(status_code=400, detail="The CSV file has no data rows.")

    # Clean with Pandas
    try:
        clean_df, summary = clean_data(raw_df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Insert valid rows into SQLite
    conn = get_connection()
    try:
        for _, row in clean_df.iterrows():
            conn.execute(
                "INSERT INTO transactions (date, description, amount, type, category) VALUES (?, ?, ?, ?, ?)",
                (row["date"], row["description"], float(row["amount"]), row["type"], row["category"]),
            )
        conn.commit()
    finally:
        conn.close()

    return summary


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    """
    Returns all data needed by the dashboard:
    summary cards, chart data, category totals, recent transactions.
    """
    df = load_df()
    summary = calculate_summary(df)

    # Monthly trend data for charts
    monthly = monthly_analysis(df)
    monthly_trend = {
        "months":   [m["month"] for m in monthly],
        "income":   [m["income"] for m in monthly],
        "expenses": [m["expenses"] for m in monthly],
        "savings":  [m["savings"] for m in monthly],
    }

    # Category totals for pie chart
    cat_data = category_analysis(df)
    category_totals = {c["category"]: c["total"] for c in cat_data}

    # Recent 10 transactions
    if not df.empty:
        df_high = detect_high_expenses(df)
        recent = df_high.head(10).to_dict(orient="records")
        for r in recent:
            r["is_high_expense"] = bool(r.get("is_high_expense", False))
    else:
        recent = []

    return {
        **summary,
        "monthly_trend":   monthly_trend,
        "category_totals": category_totals,
        "recent":          recent,
    }


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.get("/api/analysis")
def analysis(
    month:    str = Query("", description="Filter to a specific month, e.g. 2026-10"),
    type:     str = Query("", description="Filter by 'income' or 'expense'"),
    category: str = Query("", description="Filter by category"),
):
    """Detailed statistics, category breakdown, and monthly summary."""
    df = load_df()

    if df.empty:
        raise HTTPException(status_code=404, detail="No transactions found.")

    # Apply filters
    if month:
        _month_col = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").astype(str)
        df = df[_month_col == month]
    if type and type in ("income", "expense"):
        df = df[df["type"] == type]
    if category:
        df = df[df["category"] == category]

    if df.empty:
        raise HTTPException(status_code=404, detail="No transactions match the given filters.")

    return {
        **basic_stats(df),
        "category_breakdown": category_analysis(df),
        "monthly_summary":    monthly_analysis(df),
    }


# ── Insights ──────────────────────────────────────────────────────────────────

@app.get("/api/insights")
def insights():
    """Return a list of auto-generated financial insight strings."""
    df = load_df()
    return {"insights": generate_insights(df)}


# ── AI Summary ────────────────────────────────────────────────────────────────

@app.post("/api/ai-summary")
def ai_summary():
    """
    Build a short text summary of the analysis and send it to an LLM.
    Returns the AI response, or a message if the AI is unavailable.

    NOTE: Provides educational observations only — not financial advice.
    """
    df = load_df()
    if df.empty:
        raise HTTPException(status_code=400, detail="No transactions found to summarise.")

    summary   = calculate_summary(df)
    cat_data  = category_analysis(df)
    stats     = basic_stats(df)

    # Build a compact text block to send to the AI
    lines = [
        f"Total Income: ₹{summary['total_income']:,.2f}",
        f"Total Expenses: ₹{summary['total_expenses']:,.2f}",
        f"Savings: ₹{summary['savings']:,.2f}",
        f"Savings Rate: {summary['savings_pct']}%",
        f"Total Transactions: {stats['total_transactions']}",
        f"Average Expense: ₹{stats['avg_expense']:,.2f}",
        f"Highest Spending Month: {stats['highest_spending_month']}",
        "",
        "Spending by Category:",
    ]
    for c in cat_data[:6]:
        lines.append(f"  {c['category']}: ₹{c['total']:,.2f} ({c['percentage']}%)")

    analysis_text = "\n".join(lines)
    result = get_ai_summary(analysis_text)

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Copy .env.example to .env, add a valid OPENAI_API_KEY, and restart server.py.",
        )
    return {"summary": result}
