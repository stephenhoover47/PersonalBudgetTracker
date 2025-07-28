#!/usr/bin/env python3
"""
Debug script for historical transaction sync

This script helps debug why historical transactions aren't being added to the database.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, engine, Base
from app.db.models import PlaidItem, Account, Transaction, User
from app.plaid_client import client
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_plaid_connection():
    """Test Plaid connection and get account info"""
    print("🔍 Testing Plaid connection...")
    
    try:
        # Get all Plaid items
        db = next(get_db())
        plaid_items = db.query(PlaidItem).all()
        
        if not plaid_items:
            print("❌ No Plaid items found in database")
            return
        
        print(f"✅ Found {len(plaid_items)} Plaid items")
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            accounts = db.query(Account).filter(Account.plaid_item_id == item.id).all()
            
            print(f"\n📋 Plaid Item {item.id}:")
            print(f"   User: {user.full_name if user else 'Unknown'}")
            print(f"   Institution: {item.institution_name}")
            print(f"   Access Token: {item.plaid_access_token[:20]}...")
            print(f"   Accounts: {len(accounts)}")
            
            for account in accounts:
                print(f"     - {account.name} ({account.account_type}) - Balance: ${account.current_balance or 0}")
            
            # Test getting account info from Plaid
            try:
                from app.plaid_client import sync_accounts
                plaid_accounts = sync_accounts(item.plaid_access_token)
                print(f"   ✅ Plaid API: Retrieved {len(plaid_accounts)} accounts")
                
                # Test getting transactions
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)  # Just 30 days for testing
                
                request = TransactionsGetRequest(
                    access_token=item.plaid_access_token,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    options=TransactionsGetRequestOptions(
                        include_personal_finance_category=True,
                        include_account_data=True
                    )
                )
                
                response = client.transactions_get(request)
                transactions = response.get('transactions', [])
                
                print(f"   ✅ Plaid API: Retrieved {len(transactions)} transactions (last 30 days)")
                
                if transactions:
                    print(f"   📝 Sample transaction: {transactions[0].name} - ${transactions[0].amount}")
                else:
                    print(f"   ⚠️  No transactions found in last 30 days")
                
            except Exception as e:
                print(f"   ❌ Plaid API Error: {str(e)}")
        
        return plaid_items
        
    except Exception as e:
        print(f"❌ Database Error: {str(e)}")
        return []

def test_historical_sync():
    """Test the historical sync with detailed logging"""
    print("\n🔄 Testing Historical Sync...")
    
    try:
        db = next(get_db())
        plaid_items = db.query(PlaidItem).all()
        
        if not plaid_items:
            print("❌ No Plaid items to sync")
            return
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            print(f"\n🔄 Syncing for {user.full_name if user else 'Unknown'} (Item {item.id})...")
            
            # Calculate date range (2 years back)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=2 * 365)
            
            print(f"   📅 Date range: {start_date} to {end_date}")
            
            try:
                # Get historical transactions
                request = TransactionsGetRequest(
                    access_token=item.plaid_access_token,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    options=TransactionsGetRequestOptions(
                        include_personal_finance_category=True,
                        include_account_data=True
                    )
                )
                
                response = client.transactions_get(request)
                transactions = response.get('transactions', [])
                
                print(f"   📊 Plaid returned {len(transactions)} transactions")
                
                if not transactions:
                    print(f"   ⚠️  No historical transactions found")
                    continue
                
                # Check existing transactions
                existing_count = db.query(Transaction).filter(
                    Transaction.plaid_item_id == item.id
                ).count()
                
                print(f"   📊 Existing transactions in DB: {existing_count}")
                
                # Process transactions
                added_count = 0
                for tx in transactions[:5]:  # Process first 5 for testing
                    tx_data = tx.to_dict()
                    
                    # Check if transaction already exists
                    existing_tx = db.query(Transaction).filter(
                        Transaction.plaid_transaction_id == tx_data.get("transaction_id")
                    ).first()
                    
                    if existing_tx:
                        print(f"   ⏭️  Transaction {tx_data.get('transaction_id')} already exists")
                        continue
                    
                    # Find the account
                    account = db.query(Account).filter(
                        Account.plaid_account_id == tx_data.get("account_id"),
                        Account.plaid_item_id == item.id
                    ).first()
                    
                    if not account:
                        print(f"   ❌ Account not found for transaction {tx_data.get('transaction_id')}")
                        continue
                    
                    print(f"   ✅ Adding transaction: {tx_data.get('name')} - ${tx_data.get('amount')}")
                    
                    # Create transaction
                    transaction = Transaction(
                        plaid_item_id=item.id,
                        account_id=account.id,
                        plaid_transaction_id=tx_data.get("transaction_id"),
                        date=datetime.strptime(tx_data.get("date"), "%Y-%m-%d").date(),
                        name=tx_data.get("name"),
                        merchant_name=tx_data.get("merchant_name"),
                        amount=tx_data.get("amount"),
                        currency_code=tx_data.get("iso_currency_code", "USD"),
                        pending=tx_data.get("pending", False),
                        payment_channel=tx_data.get("payment_channel"),
                        plaid_category=tx_data.get("category", [None])[0] if tx_data.get("category") else None,
                        plaid_category_id=tx_data.get("category_id"),
                        personal_finance_category=tx_data.get("personal_finance_category", {}).get("primary"),
                        personal_finance_category_id=tx_data.get("personal_finance_category_id"),
                        original_description=tx_data.get("original_description"),
                        iso_currency_code=tx_data.get("iso_currency_code"),
                        unofficial_currency_code=tx_data.get("unofficial_currency_code"),
                        raw_data=tx_data
                    )
                    
                    db.add(transaction)
                    added_count += 1
                
                # Commit the transactions
                db.commit()
                
                print(f"   ✅ Successfully added {added_count} transactions")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                db.rollback()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    """Main debug function"""
    print("🔍 Historical Sync Debug Tool")
    print("=" * 50)
    
    # Test Plaid connection
    plaid_items = debug_plaid_connection()
    
    if plaid_items:
        # Test historical sync
        test_historical_sync()
    
    print("\n✅ Debug complete!")

if __name__ == "__main__":
    main() 