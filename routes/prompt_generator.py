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
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    # Add these new models to your existing BaseModel imports
class TemplateFolder(BaseModel):
    path: str
    name: str
    
class TemplateCreate(BaseModel):
    content: str
    name: str
    folder: Optional[str] = None
    description: Optional[str] = None
    based_on_official_id: Optional[int] = None

@router.get("/templates")
async def get_user_templates(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get user's prompt templates organized by folders."""
    try:
        response = supabase.table("prompt_templates").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        templates = response.data
        folders = {}
        
        # Process templates and organize by folders
        for template in templates:
            folder_path = template.get('folder')
            
            if not folder_path:
                # Root level template
                if 'root' not in folders:
                    folders['root'] = []
                folders['root'].append(template)
            else:
                # Template in a folder
                if folder_path not in folders:
                    folders[folder_path] = []
                folders[folder_path].append(template)
        
        # Get unique folder paths
        unique_folders = []
        for path in folders.keys():
            if path != 'root':
                # Split folder paths to get hierarchy
                parts = path.split('/')
                current_path = ""
                
                for i, part in enumerate(parts):
                    if i > 0:
                        current_path += "/"
                    current_path += part
                    
                    # Add folder if not already in list
                    if not any(f['path'] == current_path for f in unique_folders):
                        unique_folders.append({
                            'path': current_path,
                            'name': part,
                            'level': i
                        })
        
        return {
            "success": True,
            "templates": templates,
            "folders": unique_folders,
            "templates_by_folder": folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

@router.get("/official-templates")
async def get_official_templates(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get official prompt templates that can be used as a basis."""
    try:
        response = supabase.table("official_prompt_templates").select("*").order("category", desc=False).execute()
        
        # Organize templates by category
        templates = response.data
        categories = {}
        
        for template in templates:
            category = template.get('category', 'Uncategorized')
            if category not in categories:
                categories[category] = []
            categories[category].append(template)
        
        return {
            "success": True,
            "templates": templates,
            "categories": categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving official templates: {str(e)}")

@router.post("/template")
async def create_template(
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new template, optionally based on an official template."""
    try:
        # If based on an official template, retrieve it first
        content = template.content
        name = template.name
        description = template.description
        
        if template.based_on_official_id:
            official = supabase.table("official_prompt_templates").select("*").eq("id", template.based_on_official_id).single().execute()
            if official.data:
                # Use official template content if not provided by user
                if not content:
                    content = official.data.get('content')
                # Use official template name if not provided by user
                if not name:
                    name = f"Copy of {official.data.get('name')}"
                # Use official template description if not provided by user
                if not description:
                    description = official.data.get('description')
        
        # Insert new template
        response = supabase.table("prompt_templates").insert({
            "user_id": user_id,
            "name": name,
            "content": content,
            "description": description,
            "folder": template.folder,
            "based_on_official_id": template.based_on_official_id,
            "usage_count": 0
        }).execute()
        
        return {
            "success": True,
            "template": response.data[0] if response.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/template/{template_id}")
async def update_template(
    template_id: str,
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing template."""
    try:
        # Verify template belongs to user
        verify = supabase.table("prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Update fields
        update_data = {}
        if template.name is not None:
            update_data["name"] = template.name
        if template.content is not None:
            update_data["content"] = template.content
        if template.description is not None:
            update_data["description"] = template.description
        if template.folder is not None:
            update_data["folder"] = template.folder
        
        response = supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
        
        return {
            "success": True,
            "template": response.data[0] if response.data else None
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

@router.delete("/template/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a template."""
    try:
        # Verify template belongs to user
        verify = supabase.table("prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Delete template
        supabase.table("prompt_templates").delete().eq("id", template_id).execute()
        
        return {
            "success": True,
            "message": "Template deleted"
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")