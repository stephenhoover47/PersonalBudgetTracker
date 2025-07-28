#!/usr/bin/env python3
"""
Script to pull historical transaction data from linked accounts

This script uses Plaid's transactions/get endpoint to retrieve
historical transaction data for all linked accounts.
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

def get_historical_transactions(access_token: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Get historical transactions from Plaid
    
    Args:
        access_token: Plaid access token
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of transaction dictionaries
    """
    try:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(
                include_personal_finance_category=True,
                include_account_data=True
            )
        )
        
        response = client.transactions_get(request)
        
        # Convert Plaid objects to dictionaries
        transactions = [tx.to_dict() for tx in response.get('transactions', [])]
        
        logger.info(f"Retrieved {len(transactions)} historical transactions from {start_date} to {end_date}")
        return transactions
        
    except Exception as e:
        logger.error(f"Error getting historical transactions: {str(e)}")
        raise

def sync_historical_transactions(db: Session, plaid_item_id: int = None, pull_all_available: bool = True):
    """
    Sync historical transactions for all linked accounts
    
    Args:
        db: Database session
        plaid_item_id: Optional specific Plaid item ID
        pull_all_available: If True, pull maximum available data (up to 2 years)
    """
    try:
        # Calculate date range - pull maximum available data (2 years)
        end_date = datetime.now().date()
        if pull_all_available:
            start_date = end_date - timedelta(days=2 * 365)  # 2 years back
        else:
            start_date = end_date - timedelta(days=6 * 30)  # 6 months back
        
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
        
        print(f"Pulling historical transactions for {len(plaid_items)} linked account(s)...")
        print(f"Date range: {start_date} to {end_date} ({'Maximum available (2 years)' if pull_all_available else '6 months'})")
        
        total_transactions = 0
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            print(f"\nProcessing {user.full_name if user else 'Unknown'} (Item {item.id})...")
            
            try:
                # Get historical transactions
                transactions_data = get_historical_transactions(
                    item.plaid_access_token,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
                
                if not transactions_data:
                    print(f"  No historical transactions found for {user.full_name if user else 'Unknown'}")
                    continue
                
                # Get existing transaction count
                existing_count = db.query(Transaction).filter(
                    Transaction.plaid_item_id == item.id
                ).count()
                
                # Process each transaction
                added_count = 0
                for tx_data in transactions_data:
                    # Check if transaction already exists
                    existing_tx = db.query(Transaction).filter(
                        Transaction.plaid_transaction_id == tx_data.get("transaction_id")
                    ).first()
                    
                    if existing_tx:
                        continue  # Skip if already exists
                    
                    # Find the account
                    account = db.query(Account).filter(
                        Account.plaid_account_id == tx_data.get("account_id"),
                        Account.plaid_item_id == item.id
                    ).first()
                    
                    if not account:
                        print(f"  Warning: Account not found for transaction {tx_data.get('transaction_id')}")
                        continue
                    
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
                    
                    # Add location data if available
                    location = tx_data.get("location", {})
                    if location:
                        transaction.location_address = location.get("address")
                        transaction.location_city = location.get("city")
                        transaction.location_region = location.get("region")
                        transaction.location_postal_code = location.get("postal_code")
                        transaction.location_country = location.get("country")
                        transaction.location_lat = location.get("lat")
                        transaction.location_lon = location.get("lon")
                    
                    db.add(transaction)
                    added_count += 1
                
                # Commit the transactions
                db.commit()
                
                new_count = db.query(Transaction).filter(
                    Transaction.plaid_item_id == item.id
                ).count()
                
                total_transactions += added_count
                
                print(f"  ✓ Added {added_count} historical transactions")
                print(f"  ✓ Total transactions for this account: {new_count}")
                
            except Exception as e:
                print(f"  ✗ Error processing {user.full_name if user else 'Unknown'}: {str(e)}")
                db.rollback()
        
        print(f"\n✅ Historical sync complete! Total transactions added: {total_transactions}")
        print(f"📊 Date range covered: {start_date} to {end_date}")
        print(f"🎯 Pulled maximum available data from Plaid")
        
    except Exception as e:
        logger.error(f"Error syncing historical transactions: {str(e)}")
        raise

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull historical transaction data")
    parser.add_argument("--item-id", type=int, help="Specific Plaid item ID to sync")
    parser.add_argument("--max-data", action="store_true", default=True, help="Pull maximum available data (default: True)")
    parser.add_argument("--months", type=int, default=6, help="Number of months if not pulling max data")
    
    args = parser.parse_args()
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        # Sync historical transactions
        sync_historical_transactions(db, args.item_id, args.max_data)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 