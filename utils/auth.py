# utils/auth.py - UUID Corrected Version
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
import os
import jwt
import uuid
import logging

logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    raise ValueError("Supabase configuration missing")

security = HTTPBearer()

def validate_uuid_format(user_id: str) -> str:
    """Validate and normalize UUID string."""
    try:
        # This will raise ValueError if invalid UUID
        uuid_obj = uuid.UUID(user_id)
        return str(uuid_obj)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extract and validate user ID from JWT token.
    Returns the user ID as a string UUID if valid, raises HTTPException if invalid.
    """
    try:
        token = credentials.credentials
        
        # Verify token with Supabase
        try:
            response = supabase.auth.get_user(token)
            if response.user and response.user.id:
                # Validate UUID format and return as string
                return validate_uuid_format(response.user.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as supabase_error:
            # If Supabase auth fails, try to decode JWT manually as fallback
            logger.warning(f"Supabase auth failed, trying JWT decode: {str(supabase_error)}")
            
            if SUPABASE_JWT_SECRET:
                try:
                    payload = jwt.decode(
                        token,
                        SUPABASE_JWT_SECRET,
                        algorithms=["HS256"],
                        options={"verify_exp": True}
                    )
                    user_id = payload.get("sub")
                    if user_id:
                        # Validate UUID format and return as string
                        return validate_uuid_format(user_id)
                except jwt.ExpiredSignatureError:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                except jwt.InvalidTokenError:
                    pass  # Fall through to unauthorized
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

async def get_current_user_uuid(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """
    Extract and validate user ID from JWT token.
    Returns the user ID as a UUID object if valid, raises HTTPException if invalid.
    """
    user_id_str = await get_current_user(credentials)
    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Optional authentication - returns user ID as string if valid token provided, None otherwise.
    Does not raise exceptions for missing/invalid tokens.
    """
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
    except Exception:
        return None

async def get_optional_user_uuid(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """
    Optional authentication - returns user ID as UUID if valid token provided, None otherwise.
    Does not raise exceptions for missing/invalid tokens.
    """
    try:
        return await get_current_user_uuid(credentials)
    except HTTPException:
        return None
    except Exception:
        return None

def verify_user_access(authenticated_user_id: str, target_user_id: str) -> bool:
    """
    Verify that the authenticated user has access to the target user's data.
    Returns True if access is allowed, False otherwise.
    """
    try:
        # Normalize both UUIDs for comparison
        auth_uuid = validate_uuid_format(authenticated_user_id)
        target_uuid = validate_uuid_format(target_user_id)
        return auth_uuid == target_uuid
    except Exception:
        return False

def require_user_access(authenticated_user_id: str, target_user_id: str) -> None:
    """
    Verify that the authenticated user has access to the target user's data.
    Raises HTTPException if access is denied.
    """
    if not verify_user_access(authenticated_user_id, target_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access your own data"
        )