from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db.database import get_db
from sqlalchemy.orm import Session
from app.analytics import (
    monthly_spending_by_category,
    income_vs_expenses_by_month,
    budget_vs_actual,
    top_merchants_by_spending,
    spending_trends,
    account_balances,
    transaction_stats,
    recurring_transactions,
    category_breakdown_by_year,
    spending_by_day_of_week,
    savings_rate_analysis
)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

@router.get("/monthly-spending/{user_id}")
def get_monthly_spending(
    user_id: int,
    year: int = datetime.now().year,
    month: int = datetime.now().month,
    db: Session = Depends(get_db)
):
    """
    Get monthly spending by category for a user
    """
    try:
        result = monthly_spending_by_category(user_id, year, month)
        return {
            "status": "success",
            "data": [
                {"category": row[0], "amount": row[1]} 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/income-vs-expenses/{user_id}")
def get_income_vs_expenses(
    user_id: int,
    year: int = datetime.now().year,
    db: Session = Depends(get_db)
):
    """
    Get income vs expenses by month for a user
    """
    try:
        result = income_vs_expenses_by_month(user_id, year)
        return {
            "status": "success",
            "data": [
                {"month": int(row[0]), "income": row[1], "expenses": row[2]} 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/budget-vs-actual/{user_id}")
def get_budget_vs_actual(
    user_id: int,
    year: int = datetime.now().year,
    month: int = datetime.now().month,
    db: Session = Depends(get_db)
):
    """
    Get budget vs actual spending by category for a user
    """
    try:
        result = budget_vs_actual(user_id, year, month)
        return {
            "status": "success",
            "data": [
                {
                    "category": row[0],
                    "budget": row[1],
                    "actual": row[2],
                    "difference": row[3],
                    "over_budget": row[4]
                } 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/top-merchants/{user_id}")
def get_top_merchants(
    user_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get top merchants by spending for a user
    """
    try:
        result = top_merchants_by_spending(user_id, limit)
        return {
            "status": "success",
            "data": [
                {
                    "merchant": row[0],
                    "transaction_count": row[1],
                    "total_spent": row[2]
                } 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/spending-trends/{user_id}")
def get_spending_trends(
    user_id: int,
    months: int = 6,
    db: Session = Depends(get_db)
):
    """
    Get spending trends for a user
    """
    try:
        result = spending_trends(user_id, months)
        
        # Reorganize data for easier charting
        months = {}
        for row in result:
            month = row[0]
            category = row[1]
            amount = row[2]
            
            if month not in months:
                months[month] = {}
                
            months[month][category] = amount
        
        return {
            "status": "success",
            "data": months
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account-balances/{user_id}")
def get_account_balances(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get account balances for a user
    """
    try:
        result = account_balances(user_id)
        return {
            "status": "success",
            "data": [
                {
                    "account_name": row[0],
                    "account_type": row[1],
                    "current_balance": row[2],
                    "available_balance": row[3],
                    "currency_code": row[4]
                } 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transaction-stats/{user_id}")
def get_transaction_stats(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get transaction statistics for a user
    """
    try:
        result = transaction_stats(user_id)
        return {
            "status": "success",
            "data": {
                "total_transactions": result[0],
                "average_transaction": result[1],
                "largest_transaction": result[2],
                "smallest_transaction": result[3],
                "median_transaction": result[4]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recurring-transactions/{user_id}")
def get_recurring_transactions(
    user_id: int,
    min_occurrences: int = 3,
    db: Session = Depends(get_db)
):
    """
    Get recurring transactions for a user
    """
    try:
        result = recurring_transactions(user_id, min_occurrences)
        return {
            "status": "success",
            "data": [
                {
                    "transaction_name": row[0],
                    "merchant_name": row[1],
                    "amount": row[2],
                    "occurrence_count": row[3],
                    "avg_day_of_month": row[4],
                    "first_date": row[5].strftime('%Y-%m-%d') if row[5] else None,
                    "last_date": row[6].strftime('%Y-%m-%d') if row[6] else None,
                    "estimated_period_days": row[7]
                } 
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/category-breakdown/{user_id}")
def get_category_breakdown(
    user_id: int,
    year: int = datetime.now().year,
    db: Session = Depends(get_db)
):
    """
    Get category breakdown by month for a year
    """
    try:
        result = category_breakdown_by_year(user_id, year)
        
        # Organize data by month
        breakdown = {}
        for row in result:
            month = int(row[0])
            category = row[1]
            amount = row[2]
            
            if month not in breakdown:
                breakdown[month] = {}
                
            breakdown[month][category] = amount
            
        return {
            "status": "success",
            "data": breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/spending-by-day-of-week/{user_id}")
def get_spending_by_day_of_week(
    user_id: int,
    months: int = 3,
    db: Session = Depends(get_db)
):
    """
    Get spending patterns by day of week
    """
    try:
        result = spending_by_day_of_week(user_id, months)
        return {
            "status": "success",
            "data": [
                {
                    "day_of_week": int(row[0]),
                    "day_name": row[4],
                    "transaction_count": row[1],
                    "total_amount": row[2],
                    "average_amount": row[3]
                }
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/savings-rate/{user_id}")
def get_savings_rate(
    user_id: int,
    months: int = 12,
    db: Session = Depends(get_db)
):
    """
    Get savings rate analysis over time
    """
    try:
        result = savings_rate_analysis(user_id, months)
        return {
            "status": "success",
            "data": [
                {
                    "month": row[0],
                    "income": row[1],
                    "expenses": row[2],
                    "savings": row[3],
                    "savings_rate_percent": row[4]
                }
                for row in result
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/{user_id}")
def get_dashboard(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for a user
    """
    try:
        # Current month spending
        year = datetime.now().year
        month = datetime.now().month
        
        monthly = monthly_spending_by_category(user_id, year, month)
        balances = account_balances(user_id)
        stats = transaction_stats(user_id)
        top = top_merchants_by_spending(user_id, 5)
        recurring = recurring_transactions(user_id, 3)
        day_of_week = spending_by_day_of_week(user_id, 3)
        savings = savings_rate_analysis(user_id, 6)
        
        return {
            "status": "success",
            "data": {
                "monthly_spending": [
                    {"category": row[0], "amount": row[1]} 
                    for row in monthly
                ],
                "account_balances": [
                    {
                        "account_name": row[0],
                        "account_type": row[1],
                        "current_balance": row[2]
                    } 
                    for row in balances
                ],
                "transaction_stats": {
                    "total_transactions": stats[0],
                    "average_transaction": stats[1]
                },
                "top_merchants": [
                    {
                        "merchant": row[0],
                        "total_spent": row[2]
                    } 
                    for row in top
                ],
                "recurring_transactions": [
                    {
                        "name": row[0],
                        "amount": row[2],
                        "occurrence_count": row[3]
                    }
                    for row in recurring[:5]  # Limit to top 5
                ],
                "day_of_week_spending": [
                    {
                        "day_name": row[4],
                        "total_amount": row[2]
                    }
                    for row in day_of_week
                ],
                "savings_rate": [
                    {
                        "month": row[0],
                        "savings_rate_percent": row[4]
                    }
                    for row in savings
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))