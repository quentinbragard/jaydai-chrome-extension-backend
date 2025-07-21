# routes/share.py - UPDATED VERSION
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from supabase import create_client, Client
from utils import supabase_helpers
from utils.middleware.localization import extract_locale_from_request
import os
import dotenv
import logging
import httpx
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(prefix="/share", tags=["Share"])

async def get_user_info(user_id: str):
    """Get user information from auth.users table"""
    try:
        # Get user info from auth.users table
        user_response = supabase.auth.admin.get_user_by_id(user_id)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_response.user
        user_email = user.email
        
        # Try to get display name from user metadata or use email
        user_name = None
        if user.user_metadata:
            user_name = user.user_metadata.get('name') or user.user_metadata.get('full_name')
        
        if not user_name:
            # Fallback to part before @ in email
            user_name = user_email.split('@')[0] if user_email else 'Someone'
        
        return {
            "email": user_email,
            "name": user_name
        }
    except Exception as e:
        logger.error(f"Error getting user info for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not retrieve user information")

async def call_edge_function_directly(function_name: str, payload: dict):
    """Directly call edge function - works better for local development"""
    try:
        # Use local URL for development, production URL for production
        base_url = os.getenv("SUPABASE_URL", "http://localhost:54321")
        if "localhost" in base_url:
            function_url = f"http://localhost:54321/functions/v1/{function_name}"
        else:
            # Extract project ID from Supabase URL for production
            project_id = base_url.split("//")[1].split(".")[0]
            function_url = f"https://{project_id}.supabase.co/functions/v1/{function_name}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(function_url, json=payload, headers=headers)
            logger.info(f"Edge function {function_name} called with status: {response.status_code}")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error calling edge function {function_name}: {e}")
        return False

# Updated Pydantic models
class InviteFriendRequest(BaseModel):
    friendEmail: EmailStr

class InviteTeamRequest(BaseModel):
    pass  # Empty - all info comes from user_id

class JoinReferralRequest(BaseModel):
    pass  # Empty - all info comes from user_id

@router.post("/invite-friend")
async def invite_friend(
    request: InviteFriendRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """
    Send friend invitation - creates record that triggers edge function
    Backend now gets user info from user_id instead of request
    """
    try:
        # Get user information from auth.users table
        user_info = await get_user_info(user_id)
        
        # Insert friend invitation record with user info from backend
        invitation_data = {
            "user_id": user_id,
            "inviter_email": user_info["email"],
            "inviter_name": user_info["name"],
            "friend_email": request.friendEmail,
            "invitation_type": "friend",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Check if invitation already exists for this friend
        existing_invite = supabase.table("share_invitations") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("friend_email", request.friendEmail) \
            .eq("invitation_type", "friend") \
            .execute()
        
        if existing_invite.data and len(existing_invite.data) > 0:
            return {
                "success": False,
                "message": "You've already sent an invitation to this email address"
            }
        
        # Insert new invitation
        result = supabase.table("share_invitations") \
            .insert(invitation_data) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invitation record")
        
        # Directly call edge function for local development
        await call_edge_function_directly("send-friend-invitation", {"record": result.data[0]})
        
        logger.info(f"Friend invitation created for user {user_id} to {request.friendEmail}")
        
        return {
            "success": True,
            "message": "Friend invitation sent successfully!",
            "data": {
                "invitation_id": result.data[0]["id"],
                "friend_email": request.friendEmail,
                "inviter_name": user_info["name"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating friend invitation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending friend invitation: {str(e)}")

@router.post("/invite-team")
async def invite_team(
    request: InviteTeamRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """
    Request team members invitation - creates record that triggers internal notification
    Backend now gets user info from user_id instead of request
    """
    try:
        # Get user information from auth.users table
        user_info = await get_user_info(user_id)
        
        # Insert team invitation request with user info from backend
        invitation_data = {
            "user_id": user_id,
            "inviter_email": user_info["email"],
            "inviter_name": user_info["name"],
            "invitation_type": "team",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Check if recent team request exists (within last 24 hours)
        from datetime import datetime, timedelta
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        existing_request = supabase.table("share_invitations") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("invitation_type", "team") \
            .gte("created_at", yesterday) \
            .execute()
        
        if existing_request.data and len(existing_request.data) > 0:
            return {
                "success": False,
                "message": "You've already requested team invitations recently. We'll be in touch soon!"
            }
        
        # Insert new team request
        result = supabase.table("share_invitations") \
            .insert(invitation_data) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create team invitation request")
        
        # Directly call edge function for local development
        await call_edge_function_directly("send-internal-notifications", {"record": result.data[0]})
        
        logger.info(f"Team invitation request created for user {user_id}")
        
        return {
            "success": True,
            "message": "Team invitation request sent! We'll contact you soon.",
            "data": {
                "invitation_id": result.data[0]["id"],
                "user_name": user_info["name"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating team invitation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending team invitation request: {str(e)}")

@router.post("/join-referral")
async def join_referral(
    request: JoinReferralRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """
    Join referral program - creates record that triggers internal notification
    Backend now gets user info from user_id instead of request
    """
    try:
        # Get user information from auth.users table
        user_info = await get_user_info(user_id)
        
        # Insert referral program request with user info from backend
        invitation_data = {
            "user_id": user_id,
            "inviter_email": user_info["email"],
            "inviter_name": user_info["name"],
            "invitation_type": "referral",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Check if referral request already exists
        existing_request = supabase.table("share_invitations") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("invitation_type", "referral") \
            .execute()
        
        if existing_request.data and len(existing_request.data) > 0:
            return {
                "success": False,
                "message": "You've already joined the referral program! We'll be in touch."
            }
        
        # Insert new referral request
        result = supabase.table("share_invitations") \
            .insert(invitation_data) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create referral program request")
        
        # Directly call edge function for local development
        await call_edge_function_directly("send-internal-notifications", {"record": result.data[0]})
        
        logger.info(f"Referral program request created for user {user_id}")
        
        return {
            "success": True,
            "message": "Referral program request sent! We'll get back to you soon.",
            "data": {
                "invitation_id": result.data[0]["id"],
                "user_name": user_info["name"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error joining referral program: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error joining referral program: {str(e)}")

@router.get("/stats")
async def get_share_stats(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """
    Get sharing statistics for the user
    """
    try:
        # Get user's sharing statistics
        invitations = supabase.table("share_invitations") \
            .select("invitation_type, status, created_at") \
            .eq("user_id", user_id) \
            .execute()
        
        stats = {
            "total_invitations": len(invitations.data) if invitations.data else 0,
            "friend_invitations": 0,
            "team_requests": 0,
            "referral_requests": 0,
            "pending_invitations": 0,
            "accepted_invitations": 0,
        }
        
        if invitations.data:
            for invitation in invitations.data:
                invitation_type = invitation.get("invitation_type")
                status = invitation.get("status", "pending")
                
                if invitation_type == "friend":
                    stats["friend_invitations"] += 1
                elif invitation_type == "team":
                    stats["team_requests"] += 1
                elif invitation_type == "referral":
                    stats["referral_requests"] += 1
                
                if status == "pending":
                    stats["pending_invitations"] += 1
                elif status == "accepted":
                    stats["accepted_invitations"] += 1
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting share stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting sharing statistics: {str(e)}")