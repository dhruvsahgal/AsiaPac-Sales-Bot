from datetime import datetime, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

from config import TELEGRAM_BOT_TOKEN
from database import (
    get_user, create_user, set_ooo, add_lead, get_leads, 
    update_lead, get_lead_by_id, get_leads_due_today, get_overdue_leads
)
from voice import transcribe_voice, parse_intent_with_llm
from scheduler import setup_scheduler

# Conversation states
AWAITING_CONTINUE = 0
AWAITING_NAME = 1

WELCOME_MESSAGE = """Welcome to the AsiaPac Sales Bot!

I help you track leads and follow-ups using voice or text.

What I can do:
• Add leads with voice notes or text
• Remind you each morning of today's follow-ups
• Check in each evening on what's still pending
• Sunday night preview of your week ahead
• Set out-of-office to pause reminders

Reminders run Mon-Fri, Singapore time.

Ready to get started?"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show welcome or resume if already registered."""
    user = get_user(update.effective_user.id)
    
    if user:
        await update.message.reply_text(
            f"Welcome back, {user['name']}! Send a voice note or type /help for commands."
        )
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("Continue →", callback_data="continue_onboarding")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)
    return AWAITING_CONTINUE


async def continue_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle continue button press."""
    query = update.callback_query
    await query.answer()
    
    print(f"Continue pressed by {query.from_user.id}, moving to AWAITING_NAME")
    await query.edit_message_text("What's your name?")
    return AWAITING_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive name and complete registration."""
    print(f"receive_name called with: {update.message.text}")
    name = update.message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text("Please enter a valid name (2-50 characters).")
        return AWAITING_NAME
    
    create_user(update.effective_user.id, name)
    
    await update.message.reply_text(
        f"Great, {name}! You're all set.\n\n"
        "Send me a voice note like:\n"
        "'Add lead John at Acme, need to send proposal'\n\n"
        "Or type /help anytime."
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    help_text = """Commands & Voice Examples:

ADD A LEAD:
• Voice: "Add lead John at Acme, need to send proposal"
• Text: /add John | Acme Corp | Send proposal | 2024-01-15

UPDATE A LEAD:
• Voice: "Update John - meeting scheduled"
• Text: /update 1 next_steps Meeting scheduled

LIST LEADS:
• Voice: "Show my leads"
• Text: /leads

MARK COMPLETE:
• Voice: "Done with John" or "Won John"
• Text: /done 1 won

OUT OF OFFICE:
• Voice: "Out until Jan 15"
• Text: /ooo 2024-01-15 (or /ooo off to disable)

VIEW TODAY:
• /today - See today's follow-ups"""
    
    await update.message.reply_text(help_text)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command: /add Name | Company | Next Steps | YYYY-MM-DD (optional)"""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    args = " ".join(context.args) if context.args else ""
    parts = [p.strip() for p in args.split("|")]
    
    if len(parts) < 3:
        await update.message.reply_text(
            "Usage: /add Name | Company | Next Steps | YYYY-MM-DD (date optional)\n"
            "Example: /add John | Acme Corp | Send proposal | 2024-01-15"
        )
        return
    
    name, company, next_steps = parts[0], parts[1], parts[2]
    follow_up = None
    
    if len(parts) >= 4:
        try:
            follow_up = datetime.strptime(parts[3], "%Y-%m-%d").date()
        except ValueError:
            await update.message.reply_text("Invalid date format. Use YYYY-MM-DD.")
            return
    
    lead = add_lead(user["id"], name, company, next_steps, follow_up)
    
    msg = f"Added: {name} at {company}\nNext: {next_steps}"
    if follow_up:
        msg += f"\nFollow-up: {follow_up}"
    
    await update.message.reply_text(msg)


async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all active leads."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    leads = get_leads(user["id"], status="active")
    
    if not leads:
        await update.message.reply_text("No active leads. Add one with a voice note or /add.")
        return
    
    msg = f"Your active leads ({len(leads)}):\n\n"
    for lead in leads:
        line = f"#{lead['id']} {lead['name']} ({lead['company']})\n   → {lead['next_steps']}"
        if lead.get("follow_up_date"):
            line += f"\n   📅 {lead['follow_up_date']}"
        msg += line + "\n\n"
    
    await update.message.reply_text(msg)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's follow-ups and overdue."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    today_leads = get_leads_due_today(user["id"])
    overdue = get_overdue_leads(user["id"])
    
    if not today_leads and not overdue:
        await update.message.reply_text("Nothing due today! 🎉")
        return
    
    msg = ""
    if overdue:
        msg += f"⚠️ OVERDUE ({len(overdue)}):\n"
        for lead in overdue:
            msg += f"  • #{lead['id']} {lead['name']} ({lead['company']})\n"
        msg += "\n"
    
    if today_leads:
        msg += f"📋 TODAY ({len(today_leads)}):\n"
        for lead in today_leads:
            msg += f"  • #{lead['id']} {lead['name']} ({lead['company']}) - {lead['next_steps']}\n"
    
    await update.message.reply_text(msg)


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update a lead: /update ID field value"""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /update ID field value\n"
            "Fields: next_steps, follow_up (YYYY-MM-DD)\n"
            "Example: /update 1 next_steps Meeting scheduled"
        )
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return
    
    lead = get_lead_by_id(lead_id)
    if not lead or lead["user_id"] != user["id"]:
        await update.message.reply_text("Lead not found.")
        return
    
    field = context.args[1].lower()
    value = " ".join(context.args[2:])
    
    if field == "next_steps":
        update_lead(lead_id, next_steps=value)
    elif field == "follow_up":
        try:
            follow_date = datetime.strptime(value, "%Y-%m-%d").date()
            update_lead(lead_id, follow_up_date=follow_date)
        except ValueError:
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD.")
            return
    else:
        await update.message.reply_text("Unknown field. Use: next_steps, follow_up")
        return
    
    await update.message.reply_text(f"Updated #{lead_id}: {field} = {value}")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark lead as won/lost: /done ID [won|lost]"""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /done ID [won|lost]\nExample: /done 1 won")
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return
    
    lead = get_lead_by_id(lead_id)
    if not lead or lead["user_id"] != user["id"]:
        await update.message.reply_text("Lead not found.")
        return
    
    status = "won"
    if len(context.args) > 1 and context.args[1].lower() in ["won", "lost"]:
        status = context.args[1].lower()
    
    update_lead(lead_id, status=status)
    await update.message.reply_text(f"Marked #{lead_id} {lead['name']} as {status.upper()}! 🎉" if status == "won" else f"Marked #{lead_id} {lead['name']} as {status}.")


async def ooo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set out of office: /ooo YYYY-MM-DD or /ooo off"""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    if not context.args:
        if user.get("ooo_until"):
            await update.message.reply_text(f"You're OOO until {user['ooo_until']}. Use /ooo off to disable.")
        else:
            await update.message.reply_text("Usage: /ooo YYYY-MM-DD or /ooo off")
        return
    
    arg = context.args[0].lower()
    
    if arg == "off":
        set_ooo(update.effective_user.id, None)
        await update.message.reply_text("OOO disabled. You'll receive reminders again.")
        return
    
    try:
        ooo_date = datetime.strptime(arg, "%Y-%m-%d").date()
        if ooo_date < date.today():
            await update.message.reply_text("OOO date must be in the future.")
            return
        set_ooo(update.effective_user.id, ooo_date)
        await update.message.reply_text(f"OOO set until {ooo_date}. No reminders until then!")
    except ValueError:
        await update.message.reply_text("Invalid date. Use YYYY-MM-DD format.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - transcribe and parse intent."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first to register.")
        return
    
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    
    # file.file_path might be full URL or relative path
    if file.file_path.startswith("http"):
        file_url = file.file_path
    else:
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"
    
    print(f"Voice file URL: {file_url}")
    await update.message.reply_text("🎤 Processing...")
    
    try:
        text = await transcribe_voice(file_url, TELEGRAM_BOT_TOKEN)
    except Exception as e:
        await update.message.reply_text(f"Couldn't transcribe audio: {e}")
        return
    
    await update.message.reply_text(f"Heard: \"{text}\"")
    
    # Use LLM to parse intent (pass today's date for relative date calculation)
    today_str = date.today().strftime("%Y-%m-%d (%A)")  # e.g., "2026-01-03 (Saturday)"
    intent = parse_intent_with_llm(text, today_str)
    print(f"Parsed intent: {intent}")
    
    if not intent or intent.get("action") == "unknown":
        await update.message.reply_text(
            "I didn't understand that. Try saying something like:\n"
            "• 'Add lead John at Acme, need to send proposal'\n"
            "• 'Show my leads'\n"
            "• 'Done with John'\n"
            "• 'Update John - meeting scheduled'"
        )
        return
    
    action = intent.get("action")
    
    if action == "add_lead":
        name = intent.get("name", "Unknown")
        company = intent.get("company", "Unknown")
        next_steps = intent.get("next_steps", "Follow up")
        follow_up_date = intent.get("follow_up_date")
        
        # Parse follow_up_date if provided
        follow_up = None
        if follow_up_date and follow_up_date != "null":
            try:
                follow_up = datetime.strptime(follow_up_date, "%Y-%m-%d").date()
            except ValueError:
                print(f"Could not parse follow_up_date: {follow_up_date}")
        
        lead = add_lead(user["id"], name, company, next_steps, follow_up)
        
        msg = f"Added lead:\n  Name: {name}\n  Company: {company}\n  Next: {next_steps}"
        if follow_up:
            msg += f"\n  Follow-up: {follow_up.strftime('%A, %b %d')}"
        else:
            msg += f"\n\nSet follow-up with: /update {lead['id']} follow_up YYYY-MM-DD"
        await update.message.reply_text(msg)
    
    elif action == "list_leads":
        leads = get_leads(user["id"], status="active")
        if not leads:
            await update.message.reply_text("No active leads.")
        else:
            msg = f"Your leads ({len(leads)}):\n"
            for lead in leads:
                msg += f"  • #{lead['id']} {lead['name']} ({lead['company']}) - {lead['next_steps']}\n"
            await update.message.reply_text(msg)
    
    elif action == "update_lead":
        name = intent.get("name", "")
        next_steps = intent.get("next_steps", "")
        follow_up_date = intent.get("follow_up_date")
        
        if not name:
            await update.message.reply_text("Couldn't determine which lead to update.")
            return
        
        # Parse follow_up_date if provided
        follow_up = None
        if follow_up_date and follow_up_date != "null":
            try:
                follow_up = datetime.strptime(follow_up_date, "%Y-%m-%d").date()
            except ValueError:
                print(f"Could not parse follow_up_date: {follow_up_date}")
            
        leads = get_leads(user["id"], status="active")
        matching = [l for l in leads if name.lower() in l["name"].lower() or name.lower() in l["company"].lower()]
        
        if len(matching) == 1:
            updates = {}
            if next_steps:
                updates["next_steps"] = next_steps
            if follow_up:
                updates["follow_up_date"] = follow_up
            
            if updates:
                update_lead(matching[0]["id"], **updates)
                msg = f"Updated {matching[0]['name']} ({matching[0]['company']}):"
                if next_steps:
                    msg += f"\n  Next: {next_steps}"
                if follow_up:
                    msg += f"\n  Follow-up: {follow_up.strftime('%A, %b %d')}"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("Nothing to update.")
        elif len(matching) > 1:
            msg = "Multiple leads match. Which one?\n"
            for l in matching:
                msg += f"  #{l['id']} {l['name']} ({l['company']})\n"
            msg += "\nUse: /update ID next_steps ..."
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"No lead found matching '{name}'")
    
    elif action == "done_lead":
        name = intent.get("name", "")
        status = intent.get("status", "won")
        
        if not name:
            await update.message.reply_text("Couldn't determine which lead to mark done.")
            return
            
        leads = get_leads(user["id"], status="active")
        matching = [l for l in leads if name.lower() in l["name"].lower() or name.lower() in l["company"].lower()]
        
        if len(matching) == 1:
            update_lead(matching[0]["id"], status=status)
            emoji = "🎉" if status == "won" else ""
            await update.message.reply_text(f"Marked {matching[0]['name']} as {status.upper()}! {emoji}")
        elif len(matching) > 1:
            msg = "Multiple leads match. Which one?\n"
            for l in matching:
                msg += f"  #{l['id']} {l['name']} ({l['company']})\n"
            msg += "\nUse: /done ID [won|lost]"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"No lead found matching '{name}'")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text that isn't a command."""
    print(f"handle_text called with: {update.message.text}")
    user = get_user(update.effective_user.id)
    if not user:
        # Might be name input during onboarding - let ConversationHandler handle it
        print("User not found, ignoring in handle_text")
        return
    
    await update.message.reply_text("Type /help to see what I can do, or send a voice note.")


def main():
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Onboarding conversation
    onboarding_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AWAITING_CONTINUE: [CallbackQueryHandler(continue_onboarding, pattern="^continue_onboarding$")],
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Register handlers
    application.add_handler(onboarding_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("leads", leads_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("ooo", ooo_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Setup scheduler
    setup_scheduler(application.bot)
    
    print("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
