from supabase import create_client, Client
import dotenv
import os
from datetime import datetime, timezone
import uuid

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

class NotificationService:
    """Service for creating and managing system notifications."""
    
    @staticmethod
    async def create_welcome_notification(user_id: str, username: str = ""):
        """
        Create a welcome notification for new users with LinkedIn follow button.
        Should be called when a user first signs up.
        """
        try:
            # Check if user already has this notification
            existing_notification = supabase.table("notifications") \
                .select("id") \
                .eq("user_id", user_id) \
                .eq("type", "welcome_new_user") \
                .execute()
            
            # If no existing welcome notification
            if len(existing_notification.data) == 0:
                # Create personalized greeting if username is provided
                greeting = f"Hi {username}! " if username else ""
                
                # Create the notification
                notification = {
                    "user_id": user_id,
                    "type": "welcome_new_user",
                    "title": "welcome_notification_title", # Use localization key
                    "body": f"{greeting}welcome_notification_body", # Use localization key with personalization
                    "metadata": {
                        "action_type": "openLinkedIn",
                        "action_title_key": "followOnLinkedIn",
                        "action_url": "https://www.linkedin.com/company/104914264/admin/dashboard/"
                    }
                }
                
                # Insert notification
                supabase.table("notifications").insert(notification).execute()
                return True
                
            return False
        except Exception as e:
            print(f"Error creating welcome notification: {str(e)}")
            return False

    
    @staticmethod
    async def create_notification(user_id: str, notification_type: str, title: str, body: str, metadata: str = None):
        """Create a notification for a user."""
        try:
            notification = {
                "user_id": user_id,
                "type": notification_type,
                "title": title,
                "body": body,
                "metadata": metadata
            }
            
            response = supabase.table("notifications").insert(notification).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating notification: {str(e)}")
            return None
    
    @staticmethod
    async def create_analytics_insight_notification(user_id: str, insight_type: str, insight_text: str):
        """Create an analytics insight notification."""
        insights = {
            "prompt_length": {
                "title": "prompt_length_insight_title",
                "body": insight_text,
                "metadata": "View Details"
            },
            "response_time": {
                "title": "response_time_insight_title",
                "body": insight_text,
                "metadata": "View Details"
            },
            "conversation_quality": {
                "title": "conversation_quality_insight_title",
                "body": insight_text,
                "metadata": "View Details"
            }
        }
        
        insight = insights.get(insight_type, {
            "title": "new_insight_title",
            "body": insight_text,
            "metadata": "View Details"
        })
        
        return await NotificationService.create_notification(
            user_id=user_id,
            notification_type=f"insight_{insight_type}",
            title=insight["title"],
            body=insight["body"],
            metadata=insight["metadata"]
        )

# Helper functions to use in API routes

async def create_first_notification(user_id: str, username: str = ""):
    """
    Check various notification conditions for a user.
    Call this whenever user logs in or starts using the extension.
    """
    # Check for welcome notification for new users
    await NotificationService.create_welcome_notification(user_id, username)
    
    # Additional notification checks can be added here in the future
    # For example:
    # - Prompt optimization suggestions
    # - Weekly usage reports
    # - New feature announcements