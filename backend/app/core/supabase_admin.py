import logging

from supabase import create_client, Client

from app.core.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

logger = logging.getLogger(__name__)

_admin_client: Client | None = None


def get_supabase_admin() -> Client:
    """Service-role Supabase client. Background jobs and post-response notification
    tasks only (resolving a seller's email for sale/first-message alerts) —
    never inject this into a request-scoped dependency."""
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _admin_client


async def fetch_user_email(user_id: str) -> str | None:
    """Resolve a user's email from auth.users via the service role.
    public.users has no email column — Supabase Auth owns identity."""
    admin = get_supabase_admin()
    try:
        response = admin.auth.admin.get_user_by_id(user_id)
        return response.user.email if response.user else None
    except Exception as e:
        logger.error("Failed to fetch email for user=%s: %s", user_id, str(e))
        return None
