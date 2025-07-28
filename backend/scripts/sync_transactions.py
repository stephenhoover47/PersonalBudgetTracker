#!/usr/bin/env python3
"""
Automated transaction sync script for Personal Budget Tracker

This script syncs transactions for all linked Plaid accounts.
It can be run manually or scheduled as a cron job.

Usage:
    python scripts/sync_transactions.py [--user-id USER_ID] [--dry-run] [--verbose]
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

from app.db.database import get_db, engine
from app.db.models import PlaidItem, Account, User
from app.services.plaid_service import sync_transactions
from app.plaid_client import sync_accounts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sync_transactions.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def sync_account_balances(db: Session, plaid_item: PlaidItem) -> Dict[str, Any]:
    """
    Sync account balances for a Plaid item
    
    Args:
        db: Database session
        plaid_item: Plaid item to sync accounts for
        
    Returns:
        Dict with sync results
    """
    try:
        # Get accounts from Plaid
        plaid_accounts = sync_accounts(plaid_item.plaid_access_token)
        
        updated_count = 0
        for account_data in plaid_accounts:
            # Find existing account
            account = db.query(Account).filter(
                Account.plaid_account_id == account_data.get("account_id"),
                Account.plaid_item_id == plaid_item.id
            ).first()
            
            if account:
                # Update existing account
                account.name = account_data.get("name")
                account.official_name = account_data.get("official_name")
                account.available_balance = account_data.get("balances", {}).get("available")
                account.current_balance = account_data.get("balances", {}).get("current")
                account.currency_code = account_data.get("balances", {}).get("iso_currency_code", "USD")
                updated_count += 1
            else:
                # Create new account
                account = Account(
                    user_id=plaid_item.user_id,
                    plaid_item_id=plaid_item.id,
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
                updated_count += 1
        
        db.commit()
        return {"status": "success", "accounts_updated": updated_count}
        
    except Exception as e:
        logger.error(f"Error syncing accounts for item {plaid_item.id}: {str(e)}")
        db.rollback()
        return {"status": "error", "error": str(e)}

def sync_all_transactions(db: Session, user_id: int = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Sync transactions for all linked accounts
    
    Args:
        db: Database session
        user_id: Optional user ID to sync only for specific user
        dry_run: If True, don't actually save to database
        
    Returns:
        Dict with sync results
    """
    start_time = datetime.now()
    logger.info(f"Starting transaction sync at {start_time}")
    
    # Get all Plaid items
    query = db.query(PlaidItem)
    if user_id:
        query = query.filter(PlaidItem.user_id == user_id)
    
    plaid_items = query.all()
    
    if not plaid_items:
        logger.info("No Plaid items found to sync")
        return {"status": "success", "message": "No items to sync"}
    
    total_results = {
        "items_processed": 0,
        "items_successful": 0,
        "items_failed": 0,
        "total_transactions_added": 0,
        "total_transactions_modified": 0,
        "total_transactions_removed": 0,
        "errors": []
    }
    
    for plaid_item in plaid_items:
        try:
            logger.info(f"Processing Plaid item {plaid_item.id} for user {plaid_item.user_id}")
            
            # Get user info for logging
            user = db.query(User).filter(User.id == plaid_item.user_id).first()
            user_name = user.full_name if user else f"User {plaid_item.user_id}"
            
            total_results["items_processed"] += 1
            
            if dry_run:
                logger.info(f"[DRY RUN] Would sync transactions for {user_name} (Item {plaid_item.id})")
                total_results["items_successful"] += 1
                continue
            
            # Sync account balances first
            account_result = sync_account_balances(db, plaid_item)
            if account_result["status"] == "success":
                logger.info(f"Account balances synced for {user_name}: {account_result['accounts_updated']} accounts")
            
            # Sync transactions
            sync_result = sync_transactions(db, plaid_item.plaid_access_token, plaid_item.user_id)
            
            if sync_result["status"] == "success":
                total_results["items_successful"] += 1
                total_results["total_transactions_added"] += sync_result["added_count"]
                total_results["total_transactions_modified"] += sync_result["modified_count"]
                total_results["total_transactions_removed"] += sync_result["removed_count"]
                
                logger.info(f"Successfully synced transactions for {user_name}: "
                          f"{sync_result['added_count']} added, "
                          f"{sync_result['modified_count']} modified, "
                          f"{sync_result['removed_count']} removed")
            else:
                total_results["items_failed"] += 1
                error_msg = f"Failed to sync transactions for {user_name}: {sync_result.get('error', 'Unknown error')}"
                total_results["errors"].append(error_msg)
                logger.error(error_msg)
                
        except Exception as e:
            total_results["items_failed"] += 1
            error_msg = f"Error processing Plaid item {plaid_item.id}: {str(e)}"
            total_results["errors"].append(error_msg)
            logger.error(error_msg)
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    total_results["duration_seconds"] = duration.total_seconds()
    total_results["start_time"] = start_time.isoformat()
    total_results["end_time"] = end_time.isoformat()
    
    logger.info(f"Sync completed in {duration.total_seconds():.2f} seconds")
    logger.info(f"Results: {total_results['items_successful']} successful, "
               f"{total_results['items_failed']} failed")
    
    return total_results

def main():
    """Main function to run the sync script"""
    parser = argparse.ArgumentParser(description="Sync transactions for all linked accounts")
    parser.add_argument("--user-id", type=int, help="Sync only for specific user ID")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to database")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Starting automated transaction sync")
    logger.info(f"Arguments: user_id={args.user_id}, dry_run={args.dry_run}, verbose={args.verbose}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Run the sync
        results = sync_all_transactions(db, user_id=args.user_id, dry_run=args.dry_run)
        
        # Log final results
        if results["items_failed"] == 0:
            logger.info("All items synced successfully!")
        else:
            logger.warning(f"{results['items_failed']} items failed to sync")
            for error in results["errors"]:
                logger.error(f"Error: {error}")
        
        # Exit with appropriate code
        if results["items_failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error during sync: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 