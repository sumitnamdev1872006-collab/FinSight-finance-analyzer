"""
FinSight — test_app.py
Basic tests for all major features.
Run: pytest test_app.py -v
"""
import io
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))

# Use a separate test database
os.environ["FINSIGHT_TEST"] = "1"
import database
database.DATABASE_FILE = "test_finsight.db"

from fastapi.testclient import TestClient
import main as app_module
app_module.init_db = database.init_db   # patch to use test DB

from main import app
database.init_db()
client = TestClient(app)


def teardown_module():
    import os
    if os.path.exists("test_finsight.db"):
        os.remove("test_finsight.db")


# ── Health check ──────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api")
    assert r.status_code == 200
    assert r.json()["message"] == "FinSight is running"


# ── Transactions ──────────────────────────────────────────────────────────────

TXN = {"date": "2026-01-01", "description": "Salary", "amount": 30000, "type": "income", "category": "Salary"}

def test_add_transaction():
    r = client.post("/api/transactions", json=TXN)
    assert r.status_code == 201

def test_list_transactions():
    r = client.get("/api/transactions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_delete_transaction():
    client.post("/api/transactions", json={"date":"2026-01-05","description":"test del","amount":100,"type":"expense","category":"Food"})
    txns = client.get("/api/transactions?search=test del").json()
    assert len(txns) >= 1
    tid = txns[0]["id"]
    r = client.delete(f"/api/transactions/{tid}")
    assert r.status_code == 200

def test_invalid_amount():
    r = client.post("/api/transactions", json={**TXN, "amount": -50})
    assert r.status_code == 422

def test_invalid_type():
    r = client.post("/api/transactions", json={**TXN, "type": "unknown"})
    assert r.status_code == 422

def test_empty_description():
    r = client.post("/api/transactions", json={**TXN, "description": "  "})
    assert r.status_code == 422


# ── CSV Upload ────────────────────────────────────────────────────────────────

def test_csv_upload():
    csv = b"date,description,amount,type,category\n2026-02-01,Grocery,500,expense,Food\n2026-02-02,Salary,25000,income,Salary\n"
    r = client.post("/api/upload", files={"file": ("test.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200
    d = r.json()
    assert d["imported"] >= 1

def test_csv_empty():
    r = client.post("/api/upload", files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")})
    assert r.status_code == 400

def test_csv_wrong_format():
    r = client.post("/api/upload", files={"file": ("file.txt", io.BytesIO(b"data"), "text/plain")})
    assert r.status_code == 400

def test_csv_missing_columns():
    csv = b"name,value\nfoo,100\n"
    r = client.post("/api/upload", files={"file": ("bad.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 400


# ── Data Analysis ─────────────────────────────────────────────────────────────

import pandas as pd
from finance_analysis import (
    clean_data, auto_categorize,
    calculate_summary, category_analysis,
    monthly_analysis, basic_stats,
    detect_high_expenses, generate_insights,
)

SAMPLE_DF = pd.DataFrame([
    {"date": "2026-01-01", "description": "Salary",  "amount": 30000, "type": "income",  "category": "Salary"},
    {"date": "2026-01-02", "description": "Zomato",  "amount": 500,   "type": "expense", "category": "Food"},
    {"date": "2026-01-03", "description": "Uber",    "amount": 300,   "type": "expense", "category": "Transport"},
    {"date": "2026-01-04", "description": "Amazon",  "amount": 5000,  "type": "expense", "category": "Shopping"},
    {"date": "2026-02-01", "description": "Salary",  "amount": 30000, "type": "income",  "category": "Salary"},
    {"date": "2026-02-02", "description": "Grocery", "amount": 800,   "type": "expense", "category": "Food"},
])

def test_income_calculation():
    s = calculate_summary(SAMPLE_DF)
    assert s["total_income"] == 60000

def test_expense_calculation():
    s = calculate_summary(SAMPLE_DF)
    assert s["total_expenses"] == 6600

def test_savings_calculation():
    s = calculate_summary(SAMPLE_DF)
    assert s["savings"] == 53400

def test_savings_percentage():
    s = calculate_summary(SAMPLE_DF)
    assert s["savings_pct"] == round(53400/60000*100, 1)

def test_category_analysis():
    cats = category_analysis(SAMPLE_DF)
    assert len(cats) > 0
    totals = {c["category"]: c["total"] for c in cats}
    assert totals["Food"] == 1300
    assert totals["Shopping"] == 5000

def test_monthly_analysis():
    months = monthly_analysis(SAMPLE_DF)
    assert len(months) == 2
    assert months[0]["month"] == "2026-01"

def test_high_expense_detection():
    df = detect_high_expenses(SAMPLE_DF)
    # Average expense = (500+300+5000+800)/4 = 1650; threshold = 3300
    # Amazon 5000 > 3300 → high
    high = df[df["is_high_expense"] == True]
    assert len(high) >= 1
    assert "Amazon" in high["description"].values

def test_auto_categorize():
    assert auto_categorize("Zomato food delivery") == "Food"
    assert auto_categorize("Uber cab ride") == "Transport"
    assert auto_categorize("Amazon shopping") == "Shopping"
    assert auto_categorize("Netflix subscription") == "Entertainment"
    assert auto_categorize("random unknown") == "Other"

def test_clean_data():
    raw = pd.DataFrame([
        {"date": "2026-01-01", "description": "Salary", "amount": "30,000", "type": "income",  "category": ""},
        {"date": "bad-date",   "description": "bad",    "amount": 100,      "type": "expense", "category": "Food"},
        {"date": "2026-01-03", "description": "Dup",    "amount": 100,      "type": "expense", "category": "Food"},
        {"date": "2026-01-03", "description": "Dup",    "amount": 100,      "type": "expense", "category": "Food"},
    ])
    df, summary = clean_data(raw)
    assert summary["total_rows"] == 4
    assert summary["invalid"] >= 1   # bad-date row rejected
    assert summary["duplicates"] == 1
    assert summary["imported"] == 2   # Salary + 1 Dup

def test_generate_insights_not_empty():
    insights = generate_insights(SAMPLE_DF)
    assert len(insights) > 0
    assert all(isinstance(i, str) for i in insights)

def test_empty_df_summary():
    s = calculate_summary(pd.DataFrame())
    assert s["total_income"] == 0
    assert s["savings_pct"] == 0
