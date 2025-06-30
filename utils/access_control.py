from supabase import Client
from typing import Optional


def get_user_metadata(supabase: Client, user_id: str) -> dict:
    """Fetch organization_ids and company_id for a user."""
    response = (
        supabase.table("users_metadata")
        .select("organization_ids, company_id")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return response.data or {}


def get_access_conditions(supabase: Client, user_id: str) -> list[str]:
    """Build OR conditions to filter records accessible by the user."""
    metadata = get_user_metadata(supabase, user_id)
    conditions = [f"user_id.eq.{user_id}"]
    company_id = metadata.get("company_id")
    if company_id:
        conditions.append(f"company_id.eq.{company_id}")

    for org_id in metadata.get("organization_ids", []) or []:
        conditions.append(f"organization_id.eq.{org_id}")

    return conditions


def apply_access_conditions(query, supabase: Client, user_id: str):
    """Apply user access filters to a Supabase query."""
    conditions = get_access_conditions(supabase, user_id)
    if conditions:
        query = query.or_(",".join(conditions))
    return query


def user_has_access_to_folder(supabase: Client, user_id: str, folder_id: int) -> Optional[bool]:
    """Return True if user has access to the folder, False if not, None if folder doesn't exist."""
    resp = (
        supabase.table("prompt_folders")
        .select("user_id, company_id, organization_id")
        .eq("id", folder_id)
        .single()
        .execute()
    )

    folder = resp.data
    if not folder:
        return None

    metadata = get_user_metadata(supabase, user_id)

    if folder.get("user_id"):
        return folder.get("user_id") == user_id

    if folder.get("company_id"):
        return folder.get("company_id") == metadata.get("company_id")

    if folder.get("organization_id"):
        return folder.get("organization_id") in (metadata.get("organization_ids") or [])

    return True


def user_has_access_to_template(supabase: Client, user_id: str, template_id: int) -> Optional[bool]:
    """Return True if user has access to the template, False if not, None if template doesn't exist."""
    resp = (
        supabase.table("prompt_templates")
        .select("user_id, company_id, organization_id")
        .eq("id", template_id)
        .single()
        .execute()
    )

    template = resp.data
    if not template:
        return None

    metadata = get_user_metadata(supabase, user_id)

    if template.get("user_id"):
        return template.get("user_id") == user_id

    if template.get("company_id"):
        return template.get("company_id") == metadata.get("company_id")

    if template.get("organization_id"):
        return template.get("organization_id") in (metadata.get("organization_ids") or [])

    return True
