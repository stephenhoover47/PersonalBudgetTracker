# app/plaid_client.py
import os
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_sync_request_options import TransactionsSyncRequestOptions
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.api_client import ApiClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file

# Validate required environment variables
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", 'sandbox')  # Default to sandbox if not set

if not PLAID_CLIENT_ID:
    raise ValueError("PLAID_CLIENT_ID environment variable is required")
if not PLAID_SECRET:
    raise ValueError("PLAID_SECRET environment variable is required")

# Validate environment value
valid_environments = ["sandbox", "development", "production"]
if PLAID_ENV not in valid_environments:
    raise ValueError(f"PLAID_ENV must be one of: {', '.join(valid_environments)}")

host_map = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com"
}

logger.info(f"Initializing Plaid client with environment: {PLAID_ENV}")

configuration = Configuration(
    host=host_map[PLAID_ENV],
    api_key={
        "clientId": PLAID_CLIENT_ID,
        "secret": PLAID_SECRET,
    }
)
api_client = ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def retry_api_call(func, *args, max_retries=3, **kwargs):
    """
    Retry an API call with exponential backoff
    
    Args:
        func: The function to call
        *args: Arguments to pass to the function
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function call
        
    Raises:
        Exception: If all retries fail
    """
    import time
    
    retries = 0
    last_exception = None
    
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            retry_delay = 2 ** retries  # Exponential backoff: 1, 2, 4 seconds
            logger.warning(f"API call failed: {str(e)}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retries += 1
    
    # If we get here, all retries failed
    logger.error(f"All retries failed: {str(last_exception)}")
    raise last_exception

def create_sandbox_public_token():
    """
    Create a sandbox public token for testing
    
    Returns:
        str: The public token
    """
    try:
        request = SandboxPublicTokenCreateRequest(
            institution_id="ins_109508",  # This is "First Platypus Bank"
            initial_products=[Products("transactions")],
            options={}
        )
        response = retry_api_call(client.sandbox_public_token_create, request)
        return response.public_token
    except Exception as e:
        logger.error(f"Error creating sandbox public token: {str(e)}")
        raise Exception(f"Error creating sandbox public token: {str(e)}")

def get_access_token(public_token: str) -> str:
    """
    Exchange a public token for an access token
    
    Args:
        public_token: The public token from Plaid Link
        
    Returns:
        str: The access token
    """
    try:
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = retry_api_call(client.item_public_token_exchange, request)
        return response['access_token']
    except Exception as e:
        logger.error(f"Error exchanging public token: {str(e)}")
        raise


def create_link_token(user_id: str, client_name: str = "Personal Budget Tracker") -> str:
    """
    Create a link token for Plaid Link initialization
    
    Args:
        user_id: The user ID for the current user
        client_name: The name of your application

    Returns:
        str: The link token
    """
    try:
        request = LinkTokenCreateRequest(
            client_name=client_name,
            language="en",
            country_codes=[CountryCode("US")],
            user=LinkTokenCreateRequestUser(
                client_user_id=str(user_id)
            ),
            products=[Products("transactions")],
            webhook="https://webhook.example.com",  # Replace with your actual webhook URL in production
        )

        response = retry_api_call(client.link_token_create, request)
        return response['link_token']
    except Exception as e:
        logger.error(f"Error creating link token: {str(e)}")
        raise Exception(f"Error creating link token: {str(e)}")

def sync_transactions(access_token: str, cursor: str = "") -> Dict[str, Any]:
    """
    Sync transactions from Plaid API

    Args:
        access_token: The Plaid access token
        cursor: The cursor for pagination (optional)

    Returns:
        Dict with transaction data and next cursor
    """
    added = []
    modified = []
    removed = []
    has_more = True

    # For debug purposes, limit the number of pagination loops
    max_loops = 5
    loop_count = 0

    try:
        while has_more and loop_count < max_loops:
            request = TransactionsSyncRequest(
                access_token=access_token,
                cursor=cursor,
                options=TransactionsSyncRequestOptions(
                    include_personal_finance_category=True,
                )
            )
            # Use retry logic for API call
            response = retry_api_call(client.transactions_sync, request)

            logger.info(f"Received batch: {len(response.get('added', []))} added, " +
                       f"{len(response.get('modified', []))} modified, " +
                       f"{len(response.get('removed', []))} removed")

            # Convert Plaid objects to dictionaries for JSON serialization
            added.extend([tx.to_dict() for tx in response.get('added', [])])
            modified.extend([tx.to_dict() for tx in response.get('modified', [])])
            removed.extend([tx.to_dict() for tx in response.get('removed', [])])

            has_more = response['has_more']
            cursor = response['next_cursor']
            loop_count += 1

            if has_more and loop_count >= max_loops:
                logger.warning(f"Reached maximum pagination loops ({max_loops}), returning partial results")

        # Note: The actual DB save logic is implemented in app/services/plaid_service.py
        # This function only fetches data from Plaid and returns it
        logger.info(f"Sync complete: {len(added)} new, {len(modified)} modified, {len(removed)} removed transactions")

        # Return structured response with actual transaction data
        return {
            "status": "success",
            "added_count": len(added),
            "modified_count": len(modified),
            "removed_count": len(removed),
            "added": added[:100],  # Limit to first 100 to avoid huge responses
            "modified": modified[:100],
            "removed": removed[:100],
            "next_cursor": cursor,
            "has_more": has_more
        }
    except Exception as e:
        logger.error(f"Error syncing transactions: {str(e)}")
        raise

def sync_accounts(access_token: str) -> List[Dict[str, Any]]:
    """
    Get account balances from Plaid API
    
    Args:
        access_token: The Plaid access token
        
    Returns:
        List of account data dictionaries
    """
    try:
        request = AccountsBalanceGetRequest(access_token=access_token)
        response = retry_api_call(client.accounts_balance_get, request)
        
        # Convert Plaid objects to dictionaries
        accounts = [account.to_dict() for account in response.get('accounts', [])]
        
        logger.info(f"Retrieved {len(accounts)} accounts from Plaid")
        return accounts
        
    except Exception as e:
        logger.error(f"Error syncing accounts: {str(e)}")
        raise