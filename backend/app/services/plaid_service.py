import logging
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional

from app.db.models import PlaidItem, Account, Transaction, Category
from app.plaid_client import sync_transactions as plaid_sync_transactions

logger = logging.getLogger(__name__)

def get_plaid_item_by_access_token(db: Session, access_token: str) -> Optional[PlaidItem]:
    """
    Get a Plaid item by access token
    
    Args:
        db: Database session
        access_token: Plaid access token
        
    Returns:
        PlaidItem or None
    """
    return db.query(PlaidItem).filter(PlaidItem.plaid_access_token == access_token).first()

def get_account_by_plaid_id(db: Session, plaid_account_id: str) -> Optional[Account]:
    """
    Get an account by Plaid account ID
    
    Args:
        db: Database session
        plaid_account_id: Plaid account ID
        
    Returns:
        Account or None
    """
    return db.query(Account).filter(Account.plaid_account_id == plaid_account_id).first()

def get_transaction_by_plaid_id(db: Session, plaid_transaction_id: str) -> Optional[Transaction]:
    """
    Get a transaction by Plaid transaction ID
    
    Args:
        db: Database session
        plaid_transaction_id: Plaid transaction ID
        
    Returns:
        Transaction or None
    """
    return db.query(Transaction).filter(Transaction.plaid_transaction_id == plaid_transaction_id).first()

def sync_transactions(db: Session, access_token: str, user_id: int) -> Dict[str, Any]:
    """
    Sync transactions from Plaid and store in database
    
    Args:
        db: Database session
        access_token: Plaid access token
        user_id: User ID
        
    Returns:
        Dict with transaction counts
    """
    # Get the Plaid item
    plaid_item = get_plaid_item_by_access_token(db, access_token)
    
    if not plaid_item:
        logger.error(f"Plaid item not found for access token")
        raise ValueError("Plaid item not found")
    
    # Get the latest cursor for this item
    cursor = plaid_item.latest_cursor or ""
    
    # Sync transactions from Plaid
    plaid_data = plaid_sync_transactions(access_token, cursor)
    
    # Process added transactions
    added_count = 0
    for tx_data in plaid_data.get("added", []):
        # Check if account exists
        account = get_account_by_plaid_id(db, tx_data.get("account_id"))
        
        if not account:
            logger.warning(f"Account not found for Plaid account ID: {tx_data.get('account_id')}")
            continue
        
        # Create transaction
        transaction = Transaction(
            plaid_item_id=plaid_item.id,
            account_id=account.id,
            plaid_transaction_id=tx_data.get("transaction_id"),
            date=tx_data.get("date"),
            name=tx_data.get("name"),
            merchant_name=tx_data.get("merchant_name"),
            amount=tx_data.get("amount"),
            pending=tx_data.get("pending", False),
            payment_channel=tx_data.get("payment_channel"),
            plaid_category=tx_data.get("category", [None])[0],  # Primary category
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
    
    # Process modified transactions
    modified_count = 0
    for tx_data in plaid_data.get("modified", []):
        transaction = get_transaction_by_plaid_id(db, tx_data.get("transaction_id"))
        
        if transaction:
            # Update existing transaction
            transaction.name = tx_data.get("name")
            transaction.merchant_name = tx_data.get("merchant_name")
            transaction.amount = tx_data.get("amount")
            transaction.pending = tx_data.get("pending", False)
            transaction.plaid_category = tx_data.get("category", [None])[0]
            transaction.plaid_category_id = tx_data.get("category_id")
            transaction.personal_finance_category = tx_data.get("personal_finance_category", {}).get("primary")
            transaction.personal_finance_category_id = tx_data.get("personal_finance_category_id")
            transaction.raw_data = tx_data
            
            modified_count += 1
    
    # Process removed transactions (soft delete or flag)
    removed_count = 0
    for tx_data in plaid_data.get("removed", []):
        transaction = get_transaction_by_plaid_id(db, tx_data.get("transaction_id"))
        
        if transaction:
            # For now, just delete the transaction
            db.delete(transaction)
            removed_count += 1
    
    # Update the item with the latest cursor
    plaid_item.latest_cursor = plaid_data.get("next_cursor")
    
    # Commit all changes
    db.commit()
    
    return {
        "status": "success",
        "added_count": added_count,
        "modified_count": modified_count,
        "removed_count": removed_count,
        "next_cursor": plaid_data.get("next_cursor")
    }