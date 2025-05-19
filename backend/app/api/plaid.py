from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PlaidItem, Account
from app.plaid_client import get_access_token, create_sandbox_public_token, create_link_token, create_hosted_link_token
from app.services.plaid_service import sync_transactions

router = APIRouter(
    prefix="/plaid",
    tags=["plaid"],
    responses={404: {"description": "Not found"}},
)

class LinkTokenRequest(BaseModel):
    user_id: int
    client_name: Optional[str] = "Personal Budget Tracker"

class HostedLinkTokenRequest(BaseModel):
    user_id: int
    redirect_uri: str
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
    
class PlaidLinkCallbackRequest(BaseModel):
    """Request model for handling Plaid link callback"""
    link_token: str

@router.post("/create_link_token/")
def create_plaid_link_token(request: LinkTokenRequest):
    """
    Create a Plaid Link token for initializing Plaid Link (legacy method)
    """
    try:
        link_token = create_link_token(str(request.user_id), request.client_name)
        return {"link_token": link_token, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {str(e)}"
        )

@router.post("/create_hosted_link/")
def create_plaid_hosted_link(request: HostedLinkTokenRequest):
    """
    Create a Plaid Hosted Link URL and token for using Plaid's fully hosted experience
    """
    try:
        result = create_hosted_link_token(
            str(request.user_id),
            request.redirect_uri,
            request.client_name
        )
        return {
            "link_token": result["link_token"],
            "hosted_link_url": result["hosted_link_url"],
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create hosted link token: {str(e)}"
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
        
@router.get("/oauth-callback/")
def plaid_oauth_callback(
    state: Optional[str] = None, 
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle OAuth callback from Plaid Hosted Link
    
    This endpoint serves as the redirect_uri that Plaid will redirect to after
    a user completes the Plaid Hosted Link flow. 
    
    When using Hosted Link, the public_token will be available through:
    1. The SESSION_FINISHED webhook
    2. The /link/token/get Plaid API endpoint
    
    This endpoint simply confirms receipt of the callback and provides instructions
    on next steps for the user.
    """
    return {
        "status": "success",
        "message": "Authentication completed. You may close this window and return to the application.",
        "received_state": state,
        "received_code": code is not None
    }