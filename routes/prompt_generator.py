from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
import openai
from typing import List, Optional

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")

router = APIRouter(prefix="/prompt-generator", tags=["Prompt Generator"])

class PromptRequest(BaseModel):
    draft_prompt: str
    context: Optional[str] = None
    goals: Optional[List[str]] = None

class PromptTemplate(BaseModel):
    name: str
    content: str
    description: Optional[str] = None

@router.post("/enhance")
async def enhance_prompt(
    request: PromptRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Generate an enhanced version of the user's draft prompt."""
    try:
        # Prepare the prompt for OpenAI
        system_prompt = """You are an expert AI prompt engineer. Your job is to improve user prompts to get better results from AI assistants like ChatGPT.
        
When improving prompts:
1. Add clear context and specific goals
2. Include formatting instructions if relevant
3. Break down complex requests into steps
4. Add constraints and examples where helpful
5. Keep the enhanced prompt concise but comprehensive

Return only the improved prompt without explanations or commentary."""

        # Call OpenAI API to enhance the prompt
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # You can use gpt-4 for better results
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here's my draft prompt for ChatGPT: '{request.draft_prompt}'. "
                                            f"Context: {request.context or 'None provided'}. "
                                            f"Goals: {', '.join(request.goals) if request.goals else 'None provided'}. "
                                            f"Please improve it to get better results."}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Extract the enhanced prompt
        enhanced_prompt = response.choices[0].message.content.strip()
        
        # Track usage for analytics
        supabase.table("prompt_enhancements").insert({
            "user_id": user_id,
            "original_prompt": request.draft_prompt,
            "enhanced_prompt": enhanced_prompt,
            "context": request.context,
            "goals": request.goals
        }).execute()
        
        return {
            "success": True,
            "original_prompt": request.draft_prompt,
            "enhanced_prompt": enhanced_prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enhancing prompt: {str(e)}")

@router.post("/save-template")
async def save_prompt_template(
    template: PromptTemplate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Save a prompt template for future use."""
    try:
        response = supabase.table("prompt_templates").insert({
            "user_id": user_id,
            "name": template.name,
            "content": template.content,
            "description": template.description,
            "usage_count": 0
        }).execute()
        
        return {
            "success": True,
            "template_id": response.data[0]["id"] if response.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving template: {str(e)}")

@router.post("/use-template/{template_id}")
async def use_template(
    template_id: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Increment usage count when a template is used."""
    try:
        # Get current usage count
        template = supabase.table("prompt_templates").select("*").eq("id", template_id).eq("user_id", user_id).single().execute()
        
        if not template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Increment usage count
        current_count = template.data.get("usage_count", 0)
        supabase.table("prompt_templates").update({"usage_count": current_count + 1}).eq("id", template_id).execute()
        
        return {
            "success": True,
            "template": template.data
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating template usage: {str(e)}")