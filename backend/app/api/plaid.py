from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PlaidItem, Account
from app.plaid_client import get_access_token, create_sandbox_public_token
from app.services.plaid_service import sync_transactions

router = APIRouter(
    prefix="/plaid",
    tags=["plaid"],
    responses={404: {"description": "Not found"}},
)

class PublicTokenRequest(BaseModel):
    public_token: str
    user_id: int
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None

class SyncTransactionsRequest(BaseModel):
    access_token: str
    user_id: int
    cursor: Optional[str] = None

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
        # Exchange the public token for an access token
        access_token = get_access_token(request.public_token)
        
        # Store the Plaid item in the database
        plaid_item = PlaidItem(
            user_id=request.user_id,
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