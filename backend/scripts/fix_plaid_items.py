#!/usr/bin/env python3
"""
Script to fix NULL plaid_item_id values in existing Plaid items

This script helps fix the issue where plaid_item_id is NULL in the database.
Since we can't recover the original Plaid item IDs, this script will:
1. Show the current state of Plaid items
2. Provide instructions for re-linking accounts
3. Optionally clean up the database for fresh linking
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def show_plaid_items_status(db: Session):
    """
    Show the current status of Plaid items in the database
    """
    print("🔍 Current Plaid Items Status:")
    print("=" * 50)
    
    plaid_items = db.query(PlaidItem).all()
    
    if not plaid_items:
        print("❌ No Plaid items found in database")
        return
    
    print(f"📊 Total Plaid items: {len(plaid_items)}")
    print()
    
    for item in plaid_items:
        user = db.query(User).filter(User.id == item.user_id).first()
        accounts_count = db.query(Account).filter(Account.plaid_item_id == item.id).count()
        
        print(f"Item ID: {item.id}")
        print(f"  User: {user.full_name if user else 'Unknown'} (ID: {item.user_id})")
        print(f"  Institution: {item.institution_name}")
        print(f"  Plaid Item ID: {'✅ ' + item.plaid_item_id if item.plaid_item_id else '❌ NULL'}")
        print(f"  Access Token: {'✅ Present' if item.plaid_access_token else '❌ Missing'}")
        print(f"  Accounts: {accounts_count}")
        print(f"  Created: {item.created_at}")
        print()

def cleanup_null_plaid_items(db: Session, confirm: bool = False):
    """
    Clean up Plaid items with NULL plaid_item_id
    
    Args:
        db: Database session
        confirm: Whether to actually perform the cleanup
    """
    print("🧹 Cleanup NULL Plaid Items")
    print("=" * 30)
    
    # Find items with NULL plaid_item_id
    null_items = db.query(PlaidItem).filter(PlaidItem.plaid_item_id.is_(None)).all()
    
    if not null_items:
        print("✅ No Plaid items with NULL plaid_item_id found")
        return
    
    print(f"⚠️  Found {len(null_items)} Plaid items with NULL plaid_item_id:")
    for item in null_items:
        user = db.query(User).filter(User.id == item.user_id).first()
        print(f"  - {item.institution_name} (User: {user.full_name if user else 'Unknown'})")
    
    if not confirm:
        print("\n⚠️  WARNING: This will delete these Plaid items and their associated accounts/transactions!")
        print("   You will need to re-link these accounts through the frontend.")
        print("\n   To proceed, run: python fix_plaid_items.py --cleanup")
        return
    
    print("\n🗑️  Deleting NULL Plaid items...")
    
    for item in null_items:
        # Delete associated accounts first
        accounts = db.query(Account).filter(Account.plaid_item_id == item.id).all()
        for account in accounts:
            db.delete(account)
        
        # Delete the Plaid item
        db.delete(item)
        print(f"  ✅ Deleted {item.institution_name}")
    
    db.commit()
    print(f"\n✅ Cleanup complete! Deleted {len(null_items)} Plaid items")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix NULL plaid_item_id values in Plaid items")
    parser.add_argument("--cleanup", action="store_true", help="Clean up NULL Plaid items")
    
    args = parser.parse_args()
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        # Show current status
        show_plaid_items_status(db)
        
        # Perform cleanup if requested
        if args.cleanup:
            cleanup_null_plaid_items(db, confirm=True)
        
        print("\n📋 Next Steps:")
        print("1. If you have NULL plaid_item_id values, you'll need to re-link your accounts")
        print("2. Go to your frontend and re-link each institution")
        print("3. The new linking process will properly store the plaid_item_id")
        print("4. After re-linking, run the account sync: curl -X POST 'https://personalbudgettrackerdev.up.railway.app/plaid/sync_accounts/'")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 