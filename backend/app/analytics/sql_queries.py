"""
SQL-based analytics for budget tracking.
This module uses raw SQL queries to provide advanced analytics.
"""
from app.db.database import execute_raw_sql

def monthly_spending_by_category(user_id, year, month):
    """
    Get monthly spending by category.
    
    Args:
        user_id: User ID
        year: Year
        month: Month
        
    Returns:
        List of categories with spending amounts
    """
    query = """
    SELECT 
        c.name AS category_name,
        SUM(t.amount) AS total_amount
    FROM transactions t
    JOIN categories c ON t.category_id = c.id
    JOIN accounts a ON t.account_id = a.id
    WHERE 
        a.user_id = :user_id
        AND EXTRACT(YEAR FROM t.date) = :year
        AND EXTRACT(MONTH FROM t.date) = :month
        AND t.amount > 0  -- Only count expenses
    GROUP BY c.name
    ORDER BY total_amount DESC
    """
    params = {"user_id": user_id, "year": year, "month": month}
    return execute_raw_sql(query, params).fetchall()

def income_vs_expenses_by_month(user_id, year):
    """
    Compare income vs expenses by month.
    
    Args:
        user_id: User ID
        year: Year
        
    Returns:
        Monthly income and expense data
    """
    query = """
    SELECT
        EXTRACT(MONTH FROM t.date) AS month,
        SUM(CASE WHEN c.is_income = true THEN t.amount ELSE 0 END) AS income,
        SUM(CASE WHEN c.is_income = false THEN t.amount ELSE 0 END) AS expenses
    FROM transactions t
    JOIN categories c ON t.category_id = c.id
    JOIN accounts a ON t.account_id = a.id
    WHERE 
        a.user_id = :user_id
        AND EXTRACT(YEAR FROM t.date) = :year
    GROUP BY month
    ORDER BY month
    """
    params = {"user_id": user_id, "year": year}
    return execute_raw_sql(query, params).fetchall()

def budget_vs_actual(user_id, year, month):
    """
    Compare budget vs actual spending by category.
    
    Args:
        user_id: User ID
        year: Year
        month: Month
        
    Returns:
        Categories with budget and actual spending
    """
    query = """
    WITH monthly_spending AS (
        SELECT 
            c.id AS category_id,
            c.name AS category_name,
            SUM(t.amount) AS actual_amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN accounts a ON t.account_id = a.id
        WHERE 
            a.user_id = :user_id
            AND EXTRACT(YEAR FROM t.date) = :year
            AND EXTRACT(MONTH FROM t.date) = :month
            AND t.amount > 0
        GROUP BY c.id, c.name
    )
    SELECT 
        ms.category_name,
        b.amount AS budget_amount,
        ms.actual_amount,
        (ms.actual_amount - b.amount) AS difference,
        CASE 
            WHEN ms.actual_amount > b.amount THEN true 
            ELSE false 
        END AS over_budget
    FROM monthly_spending ms
    LEFT JOIN budgets b ON ms.category_id = b.category_id
    WHERE b.user_id = :user_id
    AND b.period = 'monthly'
    ORDER BY difference DESC
    """
    params = {"user_id": user_id, "year": year, "month": month}
    return execute_raw_sql(query, params).fetchall()

def top_merchants_by_spending(user_id, limit=10):
    """
    Get top merchants by total spending.
    
    Args:
        user_id: User ID
        limit: Number of merchants to return
        
    Returns:
        Top merchants with total spending
    """
    query = """
    SELECT 
        COALESCE(t.merchant_name, t.name) AS merchant,
        COUNT(*) AS transaction_count,
        SUM(t.amount) AS total_spent
    FROM transactions t
    JOIN accounts a ON t.account_id = a.id
    WHERE 
        a.user_id = :user_id
        AND t.amount > 0
    GROUP BY merchant
    ORDER BY total_spent DESC
    LIMIT :limit
    """
    params = {"user_id": user_id, "limit": limit}
    return execute_raw_sql(query, params).fetchall()

def spending_trends(user_id, months=6):
    """
    Analyze spending trends over time.
    
    Args:
        user_id: User ID
        months: Number of months to analyze
        
    Returns:
        Monthly spending trends
    """
    query = """
    WITH date_series AS (
        SELECT 
            generate_series(
                date_trunc('month', current_date) - interval ':months month',
                date_trunc('month', current_date),
                interval '1 month'
            ) AS month_date
    ),
    monthly_spending AS (
        SELECT 
            date_trunc('month', t.date) AS month_date,
            c.name AS category_name,
            SUM(t.amount) AS total_amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN accounts a ON t.account_id = a.id
        WHERE 
            a.user_id = :user_id
            AND t.date >= date_trunc('month', current_date) - interval ':months month'
        GROUP BY month_date, c.name
    )
    SELECT 
        to_char(ds.month_date, 'YYYY-MM') AS month,
        ms.category_name,
        COALESCE(ms.total_amount, 0) AS amount
    FROM date_series ds
    LEFT JOIN monthly_spending ms ON ds.month_date = ms.month_date
    ORDER BY ds.month_date, ms.category_name
    """
    params = {"user_id": user_id, "months": months}
    return execute_raw_sql(query, params).fetchall()

def account_balances(user_id):
    """
    Get current balances for all accounts.
    
    Args:
        user_id: User ID
        
    Returns:
        Account balances
    """
    query = """
    SELECT 
        a.name AS account_name,
        a.account_type,
        a.current_balance,
        a.available_balance,
        a.currency_code
    FROM accounts a
    WHERE a.user_id = :user_id
    ORDER BY a.current_balance DESC
    """
    params = {"user_id": user_id}
    return execute_raw_sql(query, params).fetchall()

def transaction_stats(user_id):
    """
    Get transaction statistics.
    
    Args:
        user_id: User ID
        
    Returns:
        Transaction statistics
    """
    query = """
    SELECT 
        COUNT(*) AS total_transactions,
        AVG(t.amount) AS average_transaction,
        MAX(t.amount) AS largest_transaction,
        MIN(t.amount) AS smallest_transaction,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.amount) AS median_transaction
    FROM transactions t
    JOIN accounts a ON t.account_id = a.id
    WHERE a.user_id = :user_id
    """
    params = {"user_id": user_id}
    return execute_raw_sql(query, params).fetchall()[0]

def recurring_transactions(user_id, min_occurrences=3, similarity_threshold=0.9):
    """
    Identify recurring transactions based on name similarity and amount.
    
    Args:
        user_id: User ID
        min_occurrences: Minimum occurrences to consider a transaction recurring
        similarity_threshold: Name similarity threshold (0-1)
        
    Returns:
        List of recurring transactions
    """
    query = """
    WITH similar_transactions AS (
        SELECT 
            t1.name AS transaction_name,
            t1.merchant_name,
            t1.amount,
            COUNT(*) AS occurrence_count,
            AVG(EXTRACT(DAY FROM t1.date)) AS avg_day_of_month,
            ARRAY_AGG(t1.date ORDER BY t1.date) AS transaction_dates
        FROM transactions t1
        JOIN accounts a ON t1.account_id = a.id
        WHERE a.user_id = :user_id
        GROUP BY t1.name, t1.merchant_name, t1.amount
        HAVING COUNT(*) >= :min_occurrences
    )
    SELECT 
        transaction_name,
        merchant_name,
        amount,
        occurrence_count,
        avg_day_of_month,
        transaction_dates[1] AS first_date,
        transaction_dates[array_length(transaction_dates, 1)] AS last_date,
        -- Estimate periodicity (in days)
        EXTRACT(EPOCH FROM (transaction_dates[array_length(transaction_dates, 1)] - transaction_dates[1])) / 
            (86400 * (occurrence_count - 1)) AS estimated_period_days
    FROM similar_transactions
    ORDER BY occurrence_count DESC, amount DESC
    """
    params = {"user_id": user_id, "min_occurrences": min_occurrences}
    return execute_raw_sql(query, params).fetchall()

def category_breakdown_by_year(user_id, year):
    """
    Get spending breakdown by category for an entire year.
    
    Args:
        user_id: User ID
        year: Year to analyze
        
    Returns:
        Monthly category breakdown
    """
    query = """
    WITH months AS (
        SELECT generate_series(1, 12) AS month
    ),
    categories AS (
        SELECT id, name
        FROM categories
        WHERE user_id = :user_id OR parent_id IN (SELECT id FROM categories WHERE user_id = :user_id)
    ),
    monthly_category_spend AS (
        SELECT
            EXTRACT(MONTH FROM t.date) AS month,
            c.id AS category_id,
            c.name AS category_name,
            SUM(t.amount) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN accounts a ON t.account_id = a.id
        WHERE
            a.user_id = :user_id
            AND EXTRACT(YEAR FROM t.date) = :year
            AND t.amount > 0
        GROUP BY month, c.id, c.name
    )
    SELECT
        m.month,
        c.name AS category_name,
        COALESCE(mcs.amount, 0) AS amount
    FROM months m
    CROSS JOIN categories c
    LEFT JOIN monthly_category_spend mcs 
        ON m.month = mcs.month 
        AND c.id = mcs.category_id
    ORDER BY m.month, c.name
    """
    params = {"user_id": user_id, "year": year}
    return execute_raw_sql(query, params).fetchall()

def spending_by_day_of_week(user_id, months=3):
    """
    Analyze spending patterns by day of week.
    
    Args:
        user_id: User ID
        months: Number of months to analyze
        
    Returns:
        Spending by day of week
    """
    query = """
    SELECT
        EXTRACT(DOW FROM t.date) AS day_of_week,
        COUNT(*) AS transaction_count,
        SUM(t.amount) AS total_amount,
        AVG(t.amount) AS average_amount,
        CASE EXTRACT(DOW FROM t.date)
            WHEN 0 THEN 'Sunday'
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
        END AS day_name
    FROM transactions t
    JOIN accounts a ON t.account_id = a.id
    WHERE
        a.user_id = :user_id
        AND t.date >= CURRENT_DATE - INTERVAL ':months months'
        AND t.amount > 0
    GROUP BY day_of_week, day_name
    ORDER BY day_of_week
    """
    params = {"user_id": user_id, "months": months}
    return execute_raw_sql(query, params).fetchall()

def savings_rate_analysis(user_id, months=12):
    """
    Calculate savings rate over time.
    
    Args:
        user_id: User ID
        months: Number of months to analyze
        
    Returns:
        Monthly savings rate data
    """
    query = """
    WITH monthly_flows AS (
        SELECT
            date_trunc('month', t.date) AS month,
            SUM(CASE 
                WHEN c.is_income = true THEN t.amount 
                ELSE 0 
            END) AS income,
            SUM(CASE 
                WHEN c.is_income = false THEN t.amount 
                ELSE 0 
            END) AS expenses
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN accounts a ON t.account_id = a.id
        WHERE
            a.user_id = :user_id
            AND t.date >= CURRENT_DATE - INTERVAL ':months months'
        GROUP BY month
        ORDER BY month
    )
    SELECT
        to_char(month, 'YYYY-MM') AS month_name,
        income,
        expenses,
        income - expenses AS savings,
        CASE 
            WHEN income = 0 THEN 0
            ELSE round(((income - expenses) / income * 100)::numeric, 2)
        END AS savings_rate_percent
    FROM monthly_flows
    WHERE income > 0
    ORDER BY month
    """
    params = {"user_id": user_id, "months": months}
    return execute_raw_sql(query, params).fetchall()