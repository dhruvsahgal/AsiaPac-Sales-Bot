from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import date, datetime

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# User operations
def get_user(telegram_id: int):
    result = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return result.data[0] if result.data else None


def create_user(telegram_id: int, name: str):
    result = supabase.table("users").insert({
        "telegram_id": telegram_id,
        "name": name
    }).execute()
    return result.data[0] if result.data else None


def set_ooo(telegram_id: int, until_date: date | None):
    supabase.table("users").update({
        "ooo_until": until_date.isoformat() if until_date else None
    }).eq("telegram_id", telegram_id).execute()


def get_active_users():
    """Get users not on OOO or whose OOO has expired."""
    today = date.today().isoformat()
    result = supabase.table("users").select("*").or_(
        f"ooo_until.is.null,ooo_until.lt.{today}"
    ).execute()
    return result.data


def get_all_users():
    result = supabase.table("users").select("*").execute()
    return result.data


# Lead operations
def add_lead(user_id: int, name: str, company: str, next_steps: str, follow_up_date: date = None):
    data = {
        "user_id": user_id,
        "name": name,
        "company": company,
        "next_steps": next_steps,
        "status": "active"
    }
    if follow_up_date:
        data["follow_up_date"] = follow_up_date.isoformat()
    result = supabase.table("leads").insert(data).execute()
    return result.data[0] if result.data else None


def get_leads(user_id: int, status: str = "active"):
    result = supabase.table("leads").select("*").eq("user_id", user_id).eq("status", status).execute()
    return result.data


def get_lead_by_id(lead_id: int):
    result = supabase.table("leads").select("*").eq("id", lead_id).execute()
    return result.data[0] if result.data else None


def update_lead(lead_id: int, **kwargs):
    kwargs["updated_at"] = datetime.now().isoformat()
    if "follow_up_date" in kwargs and kwargs["follow_up_date"]:
        kwargs["follow_up_date"] = kwargs["follow_up_date"].isoformat()
    supabase.table("leads").update(kwargs).eq("id", lead_id).execute()


def get_leads_due_today(user_id: int):
    today = date.today().isoformat()
    result = supabase.table("leads").select("*").eq("user_id", user_id).eq("status", "active").eq("follow_up_date", today).execute()
    return result.data


def get_leads_due_this_week(user_id: int, start_date: date, end_date: date):
    result = supabase.table("leads").select("*").eq("user_id", user_id).eq("status", "active").gte("follow_up_date", start_date.isoformat()).lte("follow_up_date", end_date.isoformat()).execute()
    return result.data


def get_overdue_leads(user_id: int):
    today = date.today().isoformat()
    result = supabase.table("leads").select("*").eq("user_id", user_id).eq("status", "active").lt("follow_up_date", today).execute()
    return result.data
