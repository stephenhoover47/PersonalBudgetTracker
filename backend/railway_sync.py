#!/usr/bin/env python3
"""
Railway automated transaction sync script

This script is designed to run on Railway's scheduled jobs.
It syncs transactions for all linked accounts and logs the results.
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy.orm import Session

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import get_db, engine, Base
from app.db.models import PlaidItem, Account, User
from app.services.plaid_service import sync_transactions
from app.plaid_client import sync_accounts

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_all_transactions():
    """Sync transactions for all linked accounts"""
    start_time = datetime.now()
    logger.info(f"Starting automated transaction sync at {start_time}")
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        # Get all Plaid items
        plaid_items = db.query(PlaidItem).all()
        
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
                
                # Sync account balances first
                try:
                    accounts_data = sync_accounts(plaid_item.plaid_access_token)
                    logger.info(f"Account balances synced for {user_name}: {len(accounts_data)} accounts")
                except Exception as e:
                    logger.warning(f"Failed to sync accounts for {user_name}: {str(e)}")
                
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
        
    except Exception as e:
        logger.error(f"Fatal error during sync: {str(e)}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    result = sync_all_transactions()
    if result.get("items_failed", 0) > 0:
        sys.exit(1)
    else:
        sys.exit(0) 