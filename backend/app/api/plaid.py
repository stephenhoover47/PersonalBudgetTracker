from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PlaidItem, Account, User
from app.plaid_client import get_access_token, create_sandbox_public_token, create_link_token
from app.services.plaid_service import sync_transactions

router = APIRouter(
    prefix="/plaid",
    tags=["plaid"],
    responses={404: {"description": "Not found"}},
)

class LinkTokenRequest(BaseModel):
    user_id: int
    client_name: Optional[str] = "Personal Budget Tracker"

class PublicTokenRequest(BaseModel):
    public_token: str
    user_id: int
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None

class SyncTransactionsRequest(BaseModel):
    access_token: str
    user_id: int
    cursor: Optional[str] = None

@router.post("/create_link_token/")
def create_plaid_link_token(request: LinkTokenRequest):
    """
    Create a Plaid Link token for initializing Plaid Link
    """
    try:
        link_token = create_link_token(str(request.user_id), request.client_name)
        return {"link_token": link_token, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {str(e)}"
        )

@router.get("/sandbox_token/")
def get_sandbox_token():
    """
    Create a sandbox public token for testing
    """
    try:
        public_token = create_sandbox_public_token()
        return {"public_token": public_token, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sandbox token: {str(e)}"
        )

@router.post("/exchange_token/")
def exchange_token(
    request: PublicTokenRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Exchange a public token for an access token and store the Plaid item
    """
    try:
        # Exchange the public token for an access token and item ID
        token_response = get_access_token(request.public_token)
        access_token = token_response['access_token']
        plaid_item_id = token_response['item_id']
        
        # Store the Plaid item in the database
        plaid_item = PlaidItem(
            user_id=request.user_id,
            plaid_item_id=plaid_item_id,
            plaid_access_token=access_token,
            institution_id=request.institution_id,
            institution_name=request.institution_name
        )
        
        db.add(plaid_item)
        db.commit()
        db.refresh(plaid_item)
        
        return {
            "status": "success",
            "access_token": access_token,
            "item_id": plaid_item.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange token: {str(e)}"
        )

@router.post("/sync_transactions/")
def sync_plaid_transactions(
    request: SyncTransactionsRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync transactions from Plaid and store in database
    """
    try:
        result = sync_transactions(db, request.access_token, request.user_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync transactions: {str(e)}"
        )

@router.post("/sync_all/")
def sync_all_transactions(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync transactions for all linked accounts (admin endpoint)
    """
    try:
        from railway_sync import sync_all_transactions as sync_all
        
        result = sync_all()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync all transactions: {str(e)}"
        )

@router.post("/sync_all_dry_run/")
def sync_all_transactions_dry_run(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dry run sync for all linked accounts (for testing)
    """
    try:
        from railway_sync import sync_all_transactions as sync_all
        
        result = sync_all()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync all transactions: {str(e)}"
        )

@router.post("/sync_historical/")
def sync_historical_transactions(
    pull_all_available: bool = True,
    plaid_item_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync historical transactions for all linked accounts
    
    Args:
        pull_all_available: If True, pull maximum available data (up to 2 years)
        plaid_item_id: Optional specific Plaid item ID to sync
    """
    try:
        from scripts.pull_historical_transactions import sync_historical_transactions as sync_historical
        
        sync_historical(db, plaid_item_id, pull_all_available)
        
        return {
            "status": "success",
            "message": f"Historical sync completed - pulled maximum available data from Plaid",
            "pull_all_available": pull_all_available,
            "plaid_item_id": plaid_item_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync historical transactions: {str(e)}"
        )

@router.get("/debug_historical/")
def debug_historical_sync(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Debug endpoint to check why historical sync isn't working
    """
    try:
        # Simple debug without complex imports
        plaid_items = db.query(PlaidItem).all()
        
        debug_info = {
            "plaid_items_count": len(plaid_items),
            "plaid_items": []
        }
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            accounts = db.query(Account).filter(Account.plaid_item_id == item.id).all()
            
            item_info = {
                "id": item.id,
                "user_id": item.user_id,
                "user_name": user.full_name if user else "Unknown",
                "institution": item.institution_name,
                "accounts_count": len(accounts),
                "accounts": [
                    {
                        "id": acc.id,
                        "name": acc.name,
                        "plaid_account_id": acc.plaid_account_id,
                        "account_type": acc.account_type
                    } for acc in accounts
                ]
            }
            debug_info["plaid_items"].append(item_info)
        
        return {
            "status": "success",
            "debug_info": debug_info
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/cleanup_null_items/")
def cleanup_null_items_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Clean up Plaid items with NULL plaid_item_id in the cloud database
    """
    try:
        # Find items with NULL plaid_item_id
        null_items = db.query(PlaidItem).filter(PlaidItem.plaid_item_id.is_(None)).all()
        
        if not null_items:
            return {
                "status": "success",
                "message": "No Plaid items with NULL plaid_item_id found",
                "items_cleaned": 0
            }
        
        # Delete associated accounts first
        for item in null_items:
            accounts = db.query(Account).filter(Account.plaid_item_id == item.id).all()
            for account in accounts:
                db.delete(account)
        
        # Delete the Plaid items
        items_deleted = len(null_items)
        for item in null_items:
            db.delete(item)
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Cleaned up {items_deleted} Plaid items with NULL plaid_item_id",
            "items_cleaned": items_deleted
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup NULL items: {str(e)}"
        )

@router.post("/sync_accounts/")
def sync_accounts_endpoint(
    plaid_item_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync account data from Plaid to populate the accounts table
    """
    try:
        # Get Plaid items to sync
        if plaid_item_id:
            plaid_items = [db.query(PlaidItem).filter(PlaidItem.id == plaid_item_id).first()]
            if not plaid_items[0]:
                return {
                    "status": "error",
                    "message": f"Plaid item {plaid_item_id} not found"
                }
        else:
            plaid_items = db.query(PlaidItem).all()
        
        if not plaid_items:
            return {
                "status": "error",
                "message": "No Plaid items found to sync"
            }
        
        print(f"Found {len(plaid_items)} Plaid items to sync")
        
        total_accounts = 0
        sync_results = []
        
        for item in plaid_items:
            user = db.query(User).filter(User.id == item.user_id).first()
            print(f"Syncing accounts for {user.full_name if user else 'Unknown'} (Item {item.id})...")
            print(f"Institution: {item.institution_name}")
            print(f"Plaid Item ID: {item.plaid_item_id}")
            print(f"Access Token: {'Present' if item.plaid_access_token else 'Missing'}")
            
            try:
                from app.plaid_client import sync_accounts
                
                # Get accounts from Plaid
                plaid_accounts = sync_accounts(item.plaid_access_token)
                
                if not plaid_accounts:
                    print(f"No accounts found for {item.institution_name}")
                    sync_results.append({
                        "item_id": item.id,
                        "institution": item.institution_name,
                        "accounts_found": 0,
                        "accounts_added": 0,
                        "error": None
                    })
                    continue
                
                print(f"Plaid returned {len(plaid_accounts)} accounts")
                
                # Process each account
                added_count = 0
                for account_data in plaid_accounts:
                    # Check if account already exists
                    existing_account = db.query(Account).filter(
                        Account.plaid_account_id == account_data.get("account_id"),
                        Account.plaid_item_id == item.id
                    ).first()
                    
                    if existing_account:
                        print(f"Account {account_data.get('name')} already exists")
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
                    print(f"Added account: {account_data.get('name')} ({account_data.get('type')})")
                
                # Commit the accounts
                db.commit()
                
                total_accounts += added_count
                sync_results.append({
                    "item_id": item.id,
                    "institution": item.institution_name,
                    "accounts_found": len(plaid_accounts),
                    "accounts_added": added_count,
                    "error": None
                })
                
                print(f"Successfully added {added_count} accounts for {item.institution_name}")
                
            except Exception as e:
                print(f"Error syncing accounts for {item.institution_name}: {str(e)}")
                db.rollback()
                sync_results.append({
                    "item_id": item.id,
                    "institution": item.institution_name,
                    "accounts_found": 0,
                    "accounts_added": 0,
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "message": f"Account sync completed - {total_accounts} total accounts added",
            "plaid_item_id": plaid_item_id,
            "total_accounts_added": total_accounts,
            "sync_results": sync_results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync accounts: {str(e)}"
        )
        
