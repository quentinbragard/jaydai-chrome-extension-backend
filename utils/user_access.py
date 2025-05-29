import os
import dotenv
from supabase import create_client, Client

dotenv.load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

async def get_user_company_id(user_id: str) -> str | None:
    """Return the company_id attached to the user if any."""
    try:
        resp = (
            supabase.table("users_metadata")
            .select("company_id")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return resp.data.get("company_id") if resp.data else None
    except Exception as exc:
        print(f"Error fetching user company: {exc}")
        return None

async def get_user_organization_ids(user_id: str) -> list[str]:
    """Return the list of organization IDs attached to the user."""
    try:
        resp = (
            supabase.table("users_metadata")
            .select("organization_ids")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if resp.data and resp.data.get("organization_ids"):
            return resp.data["organization_ids"]
    except Exception as exc:
        print(f"Error fetching user organizations: {exc}")
    return []
