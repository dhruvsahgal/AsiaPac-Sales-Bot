from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date, timedelta
import pytz

from config import (
    TIMEZONE,
    MORNING_DIGEST_HOUR, MORNING_DIGEST_MINUTE,
    EVENING_DIGEST_HOUR, EVENING_DIGEST_MINUTE,
    SUNDAY_PREVIEW_HOUR, SUNDAY_PREVIEW_MINUTE
)
from database import get_active_users, get_all_users, get_leads_due_today, get_overdue_leads, get_leads_due_this_week, get_user

tz = pytz.timezone(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=tz)


def format_lead_list(leads: list) -> str:
    if not leads:
        return "None"
    lines = []
    for lead in leads:
        lines.append(f"  • {lead['name']} ({lead['company']}) - {lead['next_steps']}")
    return "\n".join(lines)


async def send_morning_digest(bot):
    """Send morning digest to all active users (Mon-Fri)."""
    users = get_active_users()
    
    for user in users:
        today_leads = get_leads_due_today(user["id"])
        overdue_leads = get_overdue_leads(user["id"])
        
        if not today_leads and not overdue_leads:
            msg = f"Good morning, {user['name']}! No follow-ups scheduled for today. Have a great day!"
        else:
            msg = f"Good morning, {user['name']}! Here's your day:\n\n"
            
            if overdue_leads:
                msg += f"⚠️ OVERDUE ({len(overdue_leads)}):\n{format_lead_list(overdue_leads)}\n\n"
            
            if today_leads:
                msg += f"📋 TODAY ({len(today_leads)}):\n{format_lead_list(today_leads)}"
        
        try:
            await bot.send_message(chat_id=user["telegram_id"], text=msg)
        except Exception as e:
            print(f"Failed to send morning digest to {user['name']}: {e}")


async def send_evening_digest(bot):
    """Send evening check-in to users with pending items (Mon-Fri)."""
    users = get_active_users()
    
    for user in users:
        today_leads = get_leads_due_today(user["id"])
        overdue_leads = get_overdue_leads(user["id"])
        
        pending = today_leads + overdue_leads
        
        if pending:
            msg = f"EOD check-in, {user['name']}!\n\n"
            msg += f"📌 Still pending ({len(pending)}):\n{format_lead_list(pending)}\n\n"
            msg += "Update with: 'Done with [name]' or 'Update [name] - [new status]'"
            
            try:
                await bot.send_message(chat_id=user["telegram_id"], text=msg)
            except Exception as e:
                print(f"Failed to send evening digest to {user['name']}: {e}")


async def send_sunday_preview(bot):
    """Send week-ahead preview on Sunday evening."""
    users = get_all_users()  # Include OOO users for planning
    
    # Calculate Monday to Friday of upcoming week (Sunday -> next day is Monday)
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 1  # Sunday: Monday is tomorrow
    monday = today + timedelta(days=days_until_monday)
    friday = monday + timedelta(days=4)
    
    for user in users:
        week_leads = get_leads_due_this_week(user["id"], monday, friday)
        overdue = get_overdue_leads(user["id"])
        
        msg = f"Week ahead preview, {user['name']}!\n\n"
        
        if user.get("ooo_until"):
            msg += f"🏖️ You're marked OOO until {user['ooo_until']}\n\n"
        
        if overdue:
            msg += f"⚠️ OVERDUE ({len(overdue)}):\n{format_lead_list(overdue)}\n\n"
        
        if week_leads:
            msg += f"📅 THIS WEEK ({len(week_leads)}):\n{format_lead_list(week_leads)}"
        else:
            msg += "No follow-ups scheduled for this week."
        
        try:
            await bot.send_message(chat_id=user["telegram_id"], text=msg)
        except Exception as e:
            print(f"Failed to send Sunday preview to {user['name']}: {e}")


def setup_scheduler(bot):
    """Set up all scheduled jobs."""
    
    # Morning digest: Mon-Fri at 8:30 AM
    scheduler.add_job(
        send_morning_digest,
        CronTrigger(day_of_week="mon-fri", hour=MORNING_DIGEST_HOUR, minute=MORNING_DIGEST_MINUTE),
        args=[bot],
        id="morning_digest"
    )
    
    # Evening digest: Mon-Fri at 5:30 PM
    scheduler.add_job(
        send_evening_digest,
        CronTrigger(day_of_week="mon-fri", hour=EVENING_DIGEST_HOUR, minute=EVENING_DIGEST_MINUTE),
        args=[bot],
        id="evening_digest"
    )
    
    # Sunday preview: Sunday at 8:00 PM
    scheduler.add_job(
        send_sunday_preview,
        CronTrigger(day_of_week="sun", hour=SUNDAY_PREVIEW_HOUR, minute=SUNDAY_PREVIEW_MINUTE),
        args=[bot],
        id="sunday_preview"
    )
    
    scheduler.start()
    print("Scheduler started with morning/evening digests and Sunday preview")
