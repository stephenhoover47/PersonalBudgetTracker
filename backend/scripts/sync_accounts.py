#!/usr/bin/env python3
"""
Script to sync account data from Plaid

This script syncs account information from Plaid to populate the accounts table.
This needs to be done before syncing transactions.
"""

import os
import sys
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, engine, Base
from app.db.models import PlaidItem, Account, User
from app.plaid_client import sync_accounts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_all_accounts(db: Session, plaid_item_id: int = None):
    """
    Sync account data for all Plaid items
    
    Args:
        db: Database session
        plaid_item_id: Optional specific Plaid item ID to sync
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
            print("No Plaid items found to sync.")
            return
        
        print(f"Syncing accounts for {len(plaid_items)} Plaid item(s)...")
        
        total_accounts = 0
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            print(f"\nSyncing accounts for {user.full_name if user else 'Unknown'} (Item {item.id})...")
            print(f"Institution: {item.institution_name}")
            
            try:
                # Get accounts from Plaid
                plaid_accounts = sync_accounts(item.plaid_access_token)
                
                if not plaid_accounts:
                    print(f"  ⚠️  No accounts found for {item.institution_name}")
                    continue
                
                print(f"  📊 Plaid returned {len(plaid_accounts)} accounts")
                
                # Process each account
                added_count = 0
                for account_data in plaid_accounts:
                    # Check if account already exists
                    existing_account = db.query(Account).filter(
                        Account.plaid_account_id == account_data.get("account_id"),
                        Account.plaid_item_id == item.id
                    ).first()
                    
                    if existing_account:
                        print(f"  ⏭️  Account {account_data.get('name')} already exists")
                        continue
                    
                    # Create new account
                    account = Account(
                        user_id=item.user_id,
                        plaid_item_id=item.id,
                        plaid_account_id=account_data.get("account_id"),
                        name=account_data.get("name"),
                        official_name=account_data.get("official_name"),
                        account_type=account_data.get("type"),
                        account_subtype=account_data.get("subtype"),
                        mask=account_data.get("mask"),
                        available_balance=account_data.get("balances", {}).get("available"),
                        current_balance=account_data.get("balances", {}).get("current"),
                        currency_code=account_data.get("balances", {}).get("iso_currency_code", "USD")
                    )
                    
                    db.add(account)
                    added_count += 1
                    print(f"  ✅ Added account: {account_data.get('name')} ({account_data.get('type')})")
                
                # Commit the accounts
                db.commit()
                
                total_accounts += added_count
                print(f"  📊 Successfully added {added_count} accounts for {item.institution_name}")
                
            except Exception as e:
                print(f"  ❌ Error syncing accounts for {item.institution_name}: {str(e)}")
                db.rollback()
        
        print(f"\n✅ Account sync complete! Total accounts added: {total_accounts}")
        
    except Exception as e:
        logger.error(f"Error syncing accounts: {str(e)}")
        raise

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync account data from Plaid")
    parser.add_argument("--item-id", type=int, help="Specific Plaid item ID to sync")
    
    args = parser.parse_args()
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        # Sync accounts
        sync_all_accounts(db, args.item_id)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 