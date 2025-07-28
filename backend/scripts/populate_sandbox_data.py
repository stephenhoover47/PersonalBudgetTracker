#!/usr/bin/env python3
"""
Script to populate sandbox database with real transaction data

This script helps you populate your sandbox database with real transaction data
from your linked accounts. It provides several options for data population.

Usage:
    python scripts/populate_sandbox_data.py [--option OPTION]
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, engine, Base
from app.db.models import User, PlaidItem, Account, Transaction, Category
from app.plaid_client import sync_accounts, sync_transactions
from app.services.plaid_service import sync_transactions as service_sync_transactions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_linked_accounts(db: Session):
    """List all linked accounts in the database"""
    plaid_items = db.query(PlaidItem).all()
    
    if not plaid_items:
        print("No linked accounts found in database.")
        return []
    
    print(f"\nFound {len(plaid_items)} linked account(s):")
    print("-" * 50)
    
    for item in plaid_items:
        user = db.query(User).filter(User.id == item.user_id).first()
        accounts = db.query(Account).filter(Account.plaid_item_id == item.id).all()
        
        print(f"Plaid Item ID: {item.id}")
        print(f"User: {user.full_name if user else 'Unknown'} (ID: {item.user_id})")
        print(f"Institution: {item.institution_name}")
        print(f"Accounts: {len(accounts)}")
        
        for account in accounts:
            print(f"  - {account.name} ({account.account_type}) - Balance: ${account.current_balance or 0}")
        
        print("-" * 50)
    
    return plaid_items

def sync_real_data_to_sandbox(db: Session, plaid_item_id: int = None):
    """
    Sync real transaction data from linked accounts
    
    This will fetch real transaction data from your linked accounts
    and store it in your sandbox database for testing.
    """
    try:
        # Get Plaid items to sync
        if plaid_item_id:
            plaid_items = [db.query(PlaidItem).filter(PlaidItem.id == plaid_item_id).first()]
            if not plaid_items[0]:
                print(f"Plaid item {plaid_item_id} not found.")
                return
        else:
            plaid_items = db.query(PlaidItem).all()
        
        if not plaid_items:
            print("No linked accounts found to sync.")
            return
        
        print(f"Syncing data for {len(plaid_items)} linked account(s)...")
        
        total_transactions = 0
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            print(f"\nSyncing for {user.full_name if user else 'Unknown'} (Item {item.id})...")
            
            # Sync account balances
            try:
                accounts_data = sync_accounts(item.plaid_access_token)
                print(f"  ✓ Synced {len(accounts_data)} accounts")
            except Exception as e:
                print(f"  ✗ Failed to sync accounts: {str(e)}")
                continue
            
            # Sync transactions
            try:
                # Get existing transaction count
                existing_count = db.query(Transaction).filter(
                    Transaction.plaid_item_id == item.id
                ).count()
                
                # Sync transactions
                sync_result = service_sync_transactions(db, item.plaid_access_token, item.user_id)
                
                new_count = db.query(Transaction).filter(
                    Transaction.plaid_item_id == item.id
                ).count()
                
                added = new_count - existing_count
                total_transactions += added
                
                print(f"  ✓ Synced transactions: {sync_result['added_count']} added, "
                      f"{sync_result['modified_count']} modified, "
                      f"{sync_result['removed_count']} removed")
                
            except Exception as e:
                print(f"  ✗ Failed to sync transactions: {str(e)}")
        
        print(f"\n✅ Sync complete! Total transactions added: {total_transactions}")
        
    except Exception as e:
        logger.error(f"Error syncing real data: {str(e)}")
        raise

def create_sample_categories(db: Session):
    """Create sample spending categories for testing"""
    categories = [
        {"name": "Food & Dining", "description": "Restaurants, groceries, food delivery"},
        {"name": "Transportation", "description": "Gas, public transit, rideshare"},
        {"name": "Shopping", "description": "Clothing, electronics, general shopping"},
        {"name": "Entertainment", "description": "Movies, concerts, streaming services"},
        {"name": "Utilities", "description": "Electricity, water, internet, phone"},
        {"name": "Healthcare", "description": "Medical expenses, prescriptions"},
        {"name": "Travel", "description": "Flights, hotels, vacation expenses"},
        {"name": "Income", "description": "Salary, freelance, investment income", "is_income": True},
    ]
    
    # Get the first user (or create one if none exists)
    user = db.query(User).first()
    if not user:
        print("No users found. Please create a user first.")
        return
    
    created_count = 0
    for cat_data in categories:
        # Check if category already exists
        existing = db.query(Category).filter(
            Category.name == cat_data["name"],
            Category.user_id == user.id
        ).first()
        
        if not existing:
            category = Category(
                user_id=user.id,
                name=cat_data["name"],
                description=cat_data["description"],
                is_income=cat_data.get("is_income", False),
                color=f"#{hash(cat_data['name']) % 0xFFFFFF:06x}"  # Generate a color
            )
            db.add(category)
            created_count += 1
    
    db.commit()
    print(f"✅ Created {created_count} sample categories")

def show_database_stats(db: Session):
    """Show current database statistics"""
    users_count = db.query(User).count()
    plaid_items_count = db.query(PlaidItem).count()
    accounts_count = db.query(Account).count()
    transactions_count = db.query(Transaction).count()
    categories_count = db.query(Category).count()
    
    print("\n📊 Database Statistics:")
    print("-" * 30)
    print(f"Users: {users_count}")
    print(f"Linked Accounts: {plaid_items_count}")
    print(f"Bank Accounts: {accounts_count}")
    print(f"Transactions: {transactions_count}")
    print(f"Categories: {categories_count}")
    
    if transactions_count > 0:
        # Show recent transactions
        recent_transactions = db.query(Transaction).order_by(
            Transaction.date.desc()
        ).limit(5).all()
        
        print(f"\n📝 Recent Transactions:")
        print("-" * 30)
        for tx in recent_transactions:
            print(f"{tx.date.strftime('%Y-%m-%d')} - {tx.name} - ${tx.amount}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Populate sandbox database with real data")
    parser.add_argument("--option", choices=["list", "sync", "categories", "stats"], 
                       default="list", help="What to do")
    parser.add_argument("--item-id", type=int, help="Specific Plaid item ID to sync")
    parser.add_argument("--force", action="store_true", help="Force sync even if errors occur")
    
    args = parser.parse_args()
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        if args.option == "list":
            list_linked_accounts(db)
            
        elif args.option == "sync":
            sync_real_data_to_sandbox(db, args.item_id)
            
        elif args.option == "categories":
            create_sample_categories(db)
            
        elif args.option == "stats":
            show_database_stats(db)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if not args.force:
            sys.exit(1)

if __name__ == "__main__":
    main() 