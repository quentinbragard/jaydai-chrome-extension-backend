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
    async def check_and_create_first_message_notification(user_id: str):
        """
        Check if user needs a first conversation notification.
        This happens when they have 0 messages saved.
        """
        try:
            # Check if user already has messages
            message_count = supabase.table("messages").select("id").eq("user_id", user_id).execute()
            
            # Check if user already has this notification
            existing_notification = supabase.table("notifications") \
                .select("id") \
                .eq("user_id", user_id) \
                .eq("type", "welcome_first_conversation") \
                .execute()
            
            # If user has no messages and no existing notification of this type
            if len(message_count.data) == 0 and len(existing_notification.data) == 0:
                # Create the notification
                notification = {
                    "user_id": user_id,
                    "type": "welcome_first_conversation",
                    "title": "Analyze Your First Conversation",
                    "body": "Start your AI analytics journey by sending your first message to ChatGPT or loading a past conversation.",
                    "metadata": "Start Conversation"
                }
                
                # Insert notification
                supabase.table("notifications").insert(notification).execute()
                return True
                
            return False
        except Exception as e:
            print(f"Error checking/creating first message notification: {str(e)}")
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
                "title": "Prompt Length Insight",
                "body": insight_text,
                "metadata": "View Details"
            },
            "response_time": {
                "title": "Response Time Insight",
                "body": insight_text,
                "metadata": "View Details"
            },
            "conversation_quality": {
                "title": "Conversation Quality Insight",
                "body": insight_text,
                "metadata": "View Details"
            }
        }
        
        insight = insights.get(insight_type, {
            "title": "New Insight Available",
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

async def check_user_notifications(user_id: str):
    """
    Check various notification conditions for a user.
    Call this whenever user logs in or starts using the extension.
    """
    # Check for first conversation notification
    await NotificationService.check_and_create_first_message_notification(user_id)
    
    # Additional notification checks can be added here in the future
    # For example:
    # - Prompt optimization suggestions
    # - Weekly usage reports
    # - New feature announcements