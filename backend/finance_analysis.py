"""
FinSight — finance_analysis.py
Core data analysis using Pandas and NumPy.

Functions:
  clean_data(df)           — clean a raw DataFrame from CSV upload
  auto_categorize(desc)    — rule-based keyword category detection
  calculate_summary(df)    — total income, expenses, savings, savings %
  category_analysis(df)    — spending totals and % per category
  monthly_analysis(df)     — income / expenses / savings per month
  basic_stats(df)          — avg, max, min, count, highest month
  detect_high_expenses(df) — flag expenses > 2× average
  generate_insights(df)    — list of plain-English insight strings
"""

import re
import pandas as pd
import numpy as np

# ── Category keyword rules ────────────────────────────────────────────────────

CATEGORY_RULES = {
    "Food":          ["zomato", "swiggy", "restaurant", "cafe", "coffee",
                      "grocery", "supermarket", "food", "eat", "pizza",
                      "burger", "kfc", "dominos", "bakery", "vegetables"],
    "Transport":     ["uber", "ola", "petrol", "diesel", "bus", "metro",
                      "train", "auto", "taxi", "cab", "rapido", "toll",
                      "parking", "fuel", "irctc"],
    "Shopping":      ["amazon", "flipkart", "myntra", "mall", "clothes",
                      "fashion", "shop", "store", "purchase", "retail"],
    "Entertainment": ["netflix", "spotify", "movie", "cinema", "pvr",
                      "youtube", "game", "hotstar", "concert"],
    "Healthcare":    ["hospital", "clinic", "doctor", "medicine",
                      "pharmacy", "medical", "health", "diagnostic"],
    "Education":     ["college", "school", "course", "books", "udemy",
                      "fees", "tuition", "library", "stationery"],
    "Bills":         ["electricity", "water bill", "internet", "broadband",
                      "recharge", "phone bill", "dth", "airtel", "jio",
                      "vodafone", "bsnl", "insurance"],
    "Rent":          ["rent", "lease", "pg", "hostel", "accommodation"],
    "Travel":        ["hotel", "resort", "makemytrip", "goibibo",
                      "booking", "airbnb", "trip", "tour", "holiday"],
    "Salary":        ["salary", "wage", "payroll", "stipend"],
}


def auto_categorize(description: str) -> str:
    """Return a category based on keywords in the description."""
    text = description.lower()
    for category, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            if kw in text:
                return category
    return "Other"


# ── Data cleaning ─────────────────────────────────────────────────────────────

def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean a raw CSV DataFrame.
    Returns (cleaned_df, summary_dict).
    """
    original_count = len(df)
    errors = []

    # Lowercase column names and strip whitespace
    df.columns = [c.strip().lower() for c in df.columns]

    # Check required columns
    required = {"date", "description", "amount", "type"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Drop rows where all values are NaN
    df = df.dropna(how="all")

    # Track rows dropped
    invalid_count = 0

    # --- Amount: convert to numeric, drop invalid ---
    df["amount"] = pd.to_numeric(
        df["amount"].astype(str).str.replace(",", "", regex=False).str.replace("₹", "", regex=False).str.strip(),
        errors="coerce"
    )
    bad_amount = df["amount"].isna() | (df["amount"] <= 0)
    if bad_amount.sum():
        errors.append(f"{bad_amount.sum()} rows had invalid or missing amounts")
        invalid_count += bad_amount.sum()
    df = df[~bad_amount]

    # --- Type: must be income or expense ---
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    bad_type = ~df["type"].isin(["income", "expense"])
    if bad_type.sum():
        errors.append(f"{bad_type.sum()} rows had invalid type (not income/expense)")
        invalid_count += bad_type.sum()
    df = df[~bad_type]

    # --- Date: parse and normalise to YYYY-MM-DD ---
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    bad_date = df["date"].isna()
    if bad_date.sum():
        errors.append(f"{bad_date.sum()} rows had unparseable dates")
        invalid_count += bad_date.sum()
    df = df[~bad_date]

    # --- Description: fill blanks ---
    df["description"] = df["description"].fillna("Unknown").astype(str).str.strip()
    df["description"] = df["description"].replace("", "Unknown")

    # --- Category: auto-fill if missing ---
    if "category" not in df.columns:
        df["category"] = df["description"].apply(auto_categorize)
    else:
        df["category"] = df["category"].fillna("").astype(str).str.strip()
        empty_cat = df["category"] == ""
        df.loc[empty_cat, "category"] = df.loc[empty_cat, "description"].apply(auto_categorize)

    # --- Remove duplicates ---
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["date", "description", "amount", "type"])
    duplicates_removed = before_dedup - len(df)

    # Round amount
    df["amount"] = df["amount"].round(2)

    summary = {
        "total_rows":        original_count,
        "imported":          len(df),
        "invalid":           int(invalid_count),
        "duplicates":        duplicates_removed,
        "errors":            errors,
    }
    return df.reset_index(drop=True), summary


# ── Analysis functions ────────────────────────────────────────────────────────

def calculate_summary(df: pd.DataFrame) -> dict:
    """Total income, total expenses, savings, and savings percentage."""
    if df.empty:
        return {"total_income": 0, "total_expenses": 0, "savings": 0, "savings_pct": 0}

    total_income   = float(df[df["type"] == "income"]["amount"].sum())
    total_expenses = float(df[df["type"] == "expense"]["amount"].sum())
    savings        = total_income - total_expenses
    savings_pct    = (savings / total_income * 100) if total_income > 0 else 0

    return {
        "total_income":   round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "savings":        round(savings, 2),
        "savings_pct":    round(savings_pct, 1),
    }


def category_analysis(df: pd.DataFrame) -> list:
    """Return a list of {category, total, percentage} dicts, sorted by total desc."""
    if df.empty:
        return []
    expenses = df[df["type"] == "expense"]
    if expenses.empty:
        return []

    grouped = expenses.groupby("category")["amount"].sum().reset_index()
    grouped.columns = ["category", "total"]
    grouped = grouped.sort_values("total", ascending=False)

    total_exp = grouped["total"].sum()
    result = []
    for _, row in grouped.iterrows():
        result.append({
            "category":   row["category"],
            "total":      round(float(row["total"]), 2),
            "percentage": round(float(row["total"]) / total_exp * 100, 1) if total_exp > 0 else 0,
        })
    return result


def monthly_analysis(df: pd.DataFrame) -> list:
    """Return per-month income, expenses and savings sorted by month."""
    if df.empty:
        return []

    df = df.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").astype(str)

    monthly = df.groupby(["month", "type"])["amount"].sum().unstack(fill_value=0)
    if "income" not in monthly.columns:
        monthly["income"] = 0
    if "expense" not in monthly.columns:
        monthly["expense"] = 0

    monthly = monthly.sort_index().reset_index()
    result = []
    for _, row in monthly.iterrows():
        inc  = round(float(row["income"]), 2)
        exp  = round(float(row["expense"]), 2)
        result.append({
            "month":    row["month"],
            "income":   inc,
            "expenses": exp,
            "savings":  round(inc - exp, 2),
        })
    return result


def basic_stats(df: pd.DataFrame) -> dict:
    """Average, max, min expense; transaction count; highest spending month."""
    if df.empty:
        return {
            "avg_expense": 0, "max_expense": 0, "min_expense": 0,
            "total_transactions": 0, "avg_monthly_expense": 0,
            "highest_spending_month": None,
        }

    expenses = df[df["type"] == "expense"]["amount"]
    monthly  = monthly_analysis(df)

    avg_expense = round(float(expenses.mean()), 2)  if not expenses.empty else 0
    max_expense = round(float(expenses.max()), 2)   if not expenses.empty else 0
    min_expense = round(float(expenses.min()), 2)   if not expenses.empty else 0

    monthly_expenses = [m["expenses"] for m in monthly]
    avg_monthly = round(float(np.mean(monthly_expenses)), 2) if monthly_expenses else 0

    highest_month = None
    if monthly:
        highest_month = max(monthly, key=lambda m: m["expenses"])["month"]

    return {
        "avg_expense":            avg_expense,
        "max_expense":            max_expense,
        "min_expense":            min_expense,
        "total_transactions":     len(df),
        "avg_monthly_expense":    avg_monthly,
        "highest_spending_month": highest_month,
    }


def detect_high_expenses(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag expense transactions that are more than 2× the average expense.
    Adds a boolean column 'is_high_expense'.
    """
    df = df.copy()
    df["is_high_expense"] = False
    expenses = df[df["type"] == "expense"]
    if expenses.empty:
        return df

    avg = float(expenses["amount"].mean())
    threshold = avg * 2
    df.loc[df["type"] == "expense", "is_high_expense"] = expenses["amount"] > threshold
    return df


def generate_insights(df: pd.DataFrame) -> list:
    """
    Generate a list of plain-English financial insight strings.
    These are computed entirely from the data — no AI needed.
    """
    if df.empty:
        return ["No transaction data found. Please upload or add transactions."]

    insights = []
    summary  = calculate_summary(df)
    cat_data = category_analysis(df)
    monthly  = monthly_analysis(df)
    stats    = basic_stats(df)

    # 1 — Savings rate
    if summary["total_income"] > 0:
        pct = summary["savings_pct"]
        if pct >= 30:
            insights.append(f"Great job! Your savings rate is {pct}% — well above the recommended 20%.")
        elif pct >= 20:
            insights.append(f"Your savings rate is {pct}%. You're saving a healthy portion of your income.")
        elif pct > 0:
            insights.append(f"Your savings rate is {pct}%. Try to increase it towards 20%.")
        else:
            insights.append("Your expenses exceed your income. Review your spending immediately.")

    # 2 — Top spending category
    if cat_data:
        top = cat_data[0]
        insights.append(
            f"Your highest spending category is {top['category']} "
            f"(₹{top['total']:,.2f}, {top['percentage']}% of total expenses)."
        )

    # 3 — Number of categories
    if len(cat_data) > 1:
        second = cat_data[1]
        insights.append(
            f"{second['category']} is your second largest expense "
            f"at ₹{second['total']:,.2f} ({second['percentage']}%)."
        )

    # 4 — Month-over-month change
    if len(monthly) >= 2:
        prev = monthly[-2]["expenses"]
        curr = monthly[-1]["expenses"]
        if prev > 0:
            change = (curr - prev) / prev * 100
            direction = "increased" if change > 0 else "decreased"
            insights.append(
                f"Your expenses {direction} by {abs(change):.1f}% "
                f"compared to last month (₹{prev:,.2f} → ₹{curr:,.2f})."
            )

    # 5 — High expense transactions
    high_df = detect_high_expenses(df)
    high_count = int(high_df["is_high_expense"].sum())
    if high_count > 0:
        insights.append(
            f"You have {high_count} unusually high expense transaction(s) "
            f"(more than 2× your average expense of ₹{stats['avg_expense']:,.2f})."
        )

    # 6 — Highest spending month
    if stats["highest_spending_month"]:
        insights.append(
            f"Your highest spending month was {stats['highest_spending_month']}."
        )

    return insights
