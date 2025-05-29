# routes/prompts/blocks.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from models.prompts.blocks import BlockCreate, BlockUpdate, BlockResponse, BlockType
from utils import supabase_helpers
from utils.access_control import get_access_conditions
from supabase import create_client, Client
import os
from models.common import APIResponse
router = APIRouter(tags=["Blocks"])

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


@router.get("", response_model=APIResponse[List[BlockResponse]])
async def get_blocks(
    type: Optional[BlockType] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get blocks accessible to the user"""
    try:
        # Base query
        query = supabase.table("prompt_blocks").select("*")

        # Add type filter if specified
        if type:
            query = query.eq("type", type)

        # Apply access restrictions
        access_conditions = get_access_conditions(supabase, user_id)
        query = query.or_(",".join(access_conditions))
        
        # Add ordering
        query = query.order("created_at", desc=True)
        
        response = query.execute()
        return APIResponse(success=True, data=response.data or [])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching blocks: {str(e)}")

# Add a new endpoint to get blocks by type
@router.get("/by-type/{block_type}", response_model=APIResponse[List[BlockResponse]])
async def get_blocks_by_type(
    block_type: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get all blocks of a specific type accessible to the user."""
    try:
        # Build query for blocks of this type
        query = supabase.table("prompt_blocks").select("*").eq("type", block_type)
        
        # Apply access restrictions
        access_conditions = get_access_conditions(supabase, user_id)
        query = query.or_(",".join(access_conditions))
        
        # Add ordering
        query = query.order("created_at", desc=True)
        
        response = query.execute()
        
        return APIResponse(success=True, data=response.data or [])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching blocks: {str(e)}")

@router.post("", response_model=APIResponse[BlockResponse])
async def create_block(
    block: BlockCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new block"""
    try:
        
        block_data = {
            "type": block.type,
            "content": block.content,
            "title": block.title,
            "description": block.description,
            "user_id": user_id,
            "organization_id": block.organization_id,
            "company_id": block.company_id,
        }
        
        response = supabase.table("prompt_blocks").insert(block_data).execute()
        
        if response.data:
            return APIResponse(success=True, data=response.data[0])
        else:
            raise HTTPException(status_code=400, detail="Failed to create block")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating block: {str(e)}")

@router.put("/{block_id}", response_model=APIResponse[BlockResponse])
async def update_block(
    block_id: int,
    block: BlockUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update a block (only if user owns it)"""
    try:
        # Check if user owns the block
        existing_block = supabase.table("prompt_blocks").select("*").eq("id", block_id).eq("user_id", user_id).single().execute()
        
        if not existing_block.data:
            raise HTTPException(status_code=404, detail="Block not found or access denied")
        
        # Prepare update data
        update_data = {}
        if block.type is not None:
            update_data["type"] = block.type
        if block.content is not None:
            update_data["content"] = block.content
        if block.title is not None:
            update_data["title"] = block.title
        if block.description is not None:
            update_data["description"] = block.description
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        response = supabase.table("prompt_blocks").update(update_data).eq("id", block_id).execute()
        
        if response.data:
            return APIResponse(success=True, data=response.data[0])
        else:
            raise HTTPException(status_code=400, detail="Failed to update block")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating block: {str(e)}")

@router.delete("/{block_id}")
async def delete_block(
    block_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a block (only if user owns it)"""
    try:
        # Check if user owns the block
        existing_block = supabase.table("prompt_blocks").select("*").eq("id", block_id).eq("user_id", user_id).single().execute()
        print(existing_block.data)
        
        if not existing_block.data:
            raise HTTPException(status_code=404, detail="Block not found or access denied")
        
        # Check if block is being used in any templates
        templates_using_block = (
            supabase.table("prompt_templates")
            .select("id")
            .filter("blocks", "cs", f"{{{block_id}}}")
            .execute()
        )
        
        if templates_using_block.data:
            raise HTTPException(status_code=400, detail="Cannot delete block that is being used in templates")
        
        supabase.table("prompt_blocks").delete().eq("id", block_id).execute()
        
        return APIResponse(success=True, message="Block deleted")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting block: {str(e)}")

@router.get("/types", response_model=APIResponse[List[str]])
async def get_block_types():
    """Get all available block types"""
    return APIResponse(success=True, data=[block_type.value for block_type in BlockType])

@router.post("/seed-sample-blocks")
async def seed_sample_blocks(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Seed some sample blocks for testing (development only)"""
    try:
        sample_blocks = [
            {
                "type": "content",
                "content": {"en": "Write a comprehensive analysis of [topic]"},
                "title": {"en": "Analysis Template"},
                "description": {"en": "Template for comprehensive analysis"},
                "user_id": None,  # Global block
                "organization_id": None,
                "company_id": None
            },
            {
                "type": "context",
                "content": {"en": "You are working with a professional audience"},
                "title": {"en": "Professional Context"},
                "description": {"en": "Context for professional communications"},
                "user_id": None,
                "organization_id": None,
                "company_id": None
            },
            {
                "type": "role",
                "content": {"en": "You are an expert copywriter"},
                "title": {"en": "Copywriter Role"},
                "description": {"en": "Expert copywriter persona"},
                "user_id": None,
                "organization_id": None,
                "company_id": None
            }
        ]
        
        response = supabase.table("prompt_blocks").insert(sample_blocks).execute()
        
        return APIResponse(success=True, data=response.data, message="Sample blocks created")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error seeding sample blocks: {str(e)}")