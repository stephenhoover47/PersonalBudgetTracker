#!/usr/bin/env python
"""
Initialize sample data for testing purposes.
This script creates a sample user, accounts, categories, and transactions.
"""
import sys
import os
import datetime
import random
from decimal import Decimal

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal, engine, Base
from app.db.models import User, PlaidItem, Account, Transaction, Category, Budget, BudgetPeriod

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Create a session
db = SessionLocal()

def create_sample_user():
    """Create a sample user"""
    user = User(
        email="user@example.com",
        hashed_password="not_a_real_password",  # In production, use proper password hashing
        full_name="Sample User",
        is_active=True
    )
    db.add(user)
    db.commit()
    return user

def create_sample_plaid_item(user):
    """Create a sample Plaid item"""
    plaid_item = PlaidItem(
        user_id=user.id,
        plaid_item_id="sample_item_id",
        plaid_access_token="sample_access_token",
        institution_id="ins_1",
        institution_name="Sample Bank",
        latest_cursor=""
    )
    db.add(plaid_item)
    db.commit()
    return plaid_item

def create_sample_accounts(user, plaid_item):
    """Create sample accounts"""
    accounts = [
        Account(
            user_id=user.id,
            plaid_item_id=plaid_item.id,
            plaid_account_id=f"acc_{i}",
            name=f"{name}",
            official_name=f"{name} Account",
            account_type=account_type,
            account_subtype=subtype,
            mask=f"{1000+i}"[-4:],
            available_balance=float(random.randint(1000, 50000)),
            current_balance=float(random.randint(1000, 50000)),
            is_active=True
        )
        for i, (name, account_type, subtype) in enumerate([
            ("Checking", "depository", "checking"),
            ("Savings", "depository", "savings"),
            ("Credit Card", "credit", "credit card"),
            ("Investment", "investment", "brokerage")
        ])
    ]
    
    for account in accounts:
        db.add(account)
    
    db.commit()
    return accounts

def create_sample_categories(user):
    """Create sample categories"""
    # Income categories
    income_categories = [
        Category(user_id=user.id, name="Salary", is_income=True, color="#4CAF50"),
        Category(user_id=user.id, name="Dividends", is_income=True, color="#8BC34A"),
        Category(user_id=user.id, name="Gifts", is_income=True, color="#CDDC39"),
        Category(user_id=user.id, name="Other Income", is_income=True, color="#FFEB3B")
    ]
    
    # Expense categories
    expense_categories = [
        Category(user_id=user.id, name="Rent/Mortgage", is_income=False, color="#F44336"),
        Category(user_id=user.id, name="Groceries", is_income=False, color="#E91E63"),
        Category(user_id=user.id, name="Dining Out", is_income=False, color="#9C27B0"),
        Category(user_id=user.id, name="Transportation", is_income=False, color="#673AB7"),
        Category(user_id=user.id, name="Shopping", is_income=False, color="#3F51B5"),
        Category(user_id=user.id, name="Entertainment", is_income=False, color="#2196F3"),
        Category(user_id=user.id, name="Utilities", is_income=False, color="#03A9F4"),
        Category(user_id=user.id, name="Insurance", is_income=False, color="#00BCD4"),
        Category(user_id=user.id, name="Healthcare", is_income=False, color="#009688"),
        Category(user_id=user.id, name="Travel", is_income=False, color="#FF9800"),
        Category(user_id=user.id, name="Subscriptions", is_income=False, color="#FF5722"),
        Category(user_id=user.id, name="Miscellaneous", is_income=False, color="#795548")
    ]
    
    for category in income_categories + expense_categories:
        db.add(category)
    
    db.commit()
    return income_categories, expense_categories

def create_sample_budgets(user, expense_categories):
    """Create sample budgets"""
    start_date = datetime.datetime.now().replace(day=1)
    
    budgets = [
        Budget(
            user_id=user.id,
            category_id=category.id,
            name=f"{category.name} Budget",
            amount=float(random.randint(50, 1000)),
            period=BudgetPeriod.MONTHLY,
            start_date=start_date,
            is_active=True
        )
        for category in expense_categories
    ]
    
    for budget in budgets:
        db.add(budget)
    
    db.commit()
    return budgets

def create_sample_transactions(user, accounts, income_categories, expense_categories):
    """Create sample transactions"""
    # List of sample merchants
    merchants = {
        "Groceries": ["Whole Foods", "Trader Joe's", "Safeway", "Kroger", "Albertsons"],
        "Dining Out": ["McDonald's", "Chipotle", "Starbucks", "Subway", "Panera Bread"],
        "Transportation": ["Uber", "Lyft", "Shell", "Chevron", "Exxon"],
        "Shopping": ["Amazon", "Walmart", "Target", "Best Buy", "Macy's"],
        "Entertainment": ["Netflix", "Spotify", "AMC Theaters", "Steam", "Hulu"],
        "Utilities": ["PG&E", "AT&T", "Comcast", "Verizon", "T-Mobile"],
        "Insurance": ["State Farm", "Geico", "Progressive", "Allstate", "Liberty Mutual"],
        "Healthcare": ["CVS", "Walgreens", "Kaiser", "Blue Cross", "United Healthcare"],
        "Travel": ["Airbnb", "Expedia", "Delta", "Marriott", "Southwest"],
        "Subscriptions": ["Adobe", "Microsoft", "Amazon Prime", "Disney+", "Apple"],
        "Miscellaneous": ["Home Depot", "Lowe's", "Staples", "Office Depot", "Petco"],
        "Salary": ["Employer Payroll"],
        "Dividends": ["Vanguard", "Fidelity", "Charles Schwab"],
        "Gifts": ["PayPal", "Venmo", "Cash App"],
        "Other Income": ["Etsy", "eBay", "Freelance Payment"]
    }
    
    # Get category maps for easier lookup
    category_map = {}
    for category in income_categories + expense_categories:
        category_map[category.name] = category
    
    transactions = []
    
    # Generate transactions for the past 6 months
    today = datetime.datetime.now()
    for month_offset in range(6):
        current_date = today - datetime.timedelta(days=30 * month_offset)
        
        # Add salary income at the beginning of each month
        salary_date = current_date.replace(day=1)
        salary_amount = -5000  # Negative amount represents money coming in
        
        transactions.append(
            Transaction(
                plaid_item_id=accounts[0].plaid_item_id,
                account_id=accounts[0].id,
                plaid_transaction_id=f"tx_income_{month_offset}",
                category_id=category_map["Salary"].id,
                date=salary_date,
                name="DIRECT DEPOSIT - EMPLOYER",
                merchant_name="Employer Payroll",
                amount=salary_amount,
                pending=False,
                payment_channel="other",
                plaid_category="Transfer",
                plaid_category_id="21009000",
                personal_finance_category="INCOME",
                personal_finance_category_id="INCOME"
            )
        )
        
        # Generate 30-50 expense transactions per month
        num_transactions = random.randint(30, 50)
        for i in range(num_transactions):
            # Pick a random expense category
            category = random.choice(expense_categories)
            
            # Generate a transaction date within the month
            day = random.randint(1, 28)
            tx_date = current_date.replace(day=day)
            
            # Generate an amount appropriate for the category
            if category.name in ["Rent/Mortgage"]:
                amount = float(random.randint(800, 2500))
            elif category.name in ["Groceries", "Utilities", "Insurance"]:
                amount = float(random.randint(50, 300))
            elif category.name in ["Dining Out", "Entertainment", "Subscriptions"]:
                amount = float(random.randint(10, 100))
            elif category.name in ["Shopping", "Healthcare"]:
                amount = float(random.randint(20, 200))
            elif category.name in ["Travel"]:
                amount = float(random.randint(100, 1000))
            else:
                amount = float(random.randint(5, 150))
            
            # Pick a random merchant for the category
            merchant = random.choice(merchants.get(category.name, ["Unknown"]))
            
            # Create the transaction
            transactions.append(
                Transaction(
                    plaid_item_id=accounts[0].plaid_item_id,
                    account_id=random.choice(accounts).id,
                    plaid_transaction_id=f"tx_{month_offset}_{i}",
                    category_id=category.id,
                    date=tx_date,
                    name=f"Purchase - {merchant}",
                    merchant_name=merchant,
                    amount=amount,
                    pending=False,
                    payment_channel=random.choice(["in store", "online", "other"]),
                    plaid_category=category.name,
                    plaid_category_id=f"1{i}001",
                    personal_finance_category=category.name.upper(),
                    personal_finance_category_id=category.name.upper().replace(" ", "_")
                )
            )
    
    for transaction in transactions:
        db.add(transaction)
    
    db.commit()
    return transactions

def main():
    """Main function to create sample data"""
    try:
        # Check if there's already data
        existing_user = db.query(User).first()
        if existing_user:
            print("Sample data already exists. Skipping...")
            return
        
        # Create sample data
        print("Creating sample user...")
        user = create_sample_user()
        
        print("Creating sample Plaid item...")
        plaid_item = create_sample_plaid_item(user)
        
        print("Creating sample accounts...")
        accounts = create_sample_accounts(user, plaid_item)
        
        print("Creating sample categories...")
        income_categories, expense_categories = create_sample_categories(user)
        
        print("Creating sample budgets...")
        budgets = create_sample_budgets(user, expense_categories)
        
        print("Creating sample transactions...")
        transactions = create_sample_transactions(user, accounts, income_categories, expense_categories)
        
        print(f"Sample data created successfully!")
        print(f"- User ID: {user.id}")
        print(f"- Number of accounts: {len(accounts)}")
        print(f"- Number of categories: {len(income_categories) + len(expense_categories)}")
        print(f"- Number of budgets: {len(budgets)}")
        print(f"- Number of transactions: {len(transactions)}")
        
    except Exception as e:
        print(f"Error creating sample data: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()