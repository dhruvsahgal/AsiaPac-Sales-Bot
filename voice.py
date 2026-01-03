import httpx
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


async def transcribe_voice(file_url: str, bot_token: str) -> str:
    """Download voice file from Telegram and transcribe with Groq Whisper."""
    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(file_url)
        audio_data = response.content

    transcription = client.audio.transcriptions.create(
        file=("voice.ogg", audio_data),
        model="whisper-large-v3",
        language="en"
    )
    return transcription.text


def parse_lead_from_text(text: str) -> dict | None:
    """
    Parse lead info from natural text.
    Expected patterns:
    - "Add lead John at Acme, need to send proposal"
    - "Add John from Acme Corp, follow up on pricing"
    """
    text_lower = text.lower()
    
    if "add" not in text_lower and "new lead" not in text_lower:
        return None
    
    # Remove common prefixes
    for prefix in ["add lead", "add a lead", "new lead", "add"]:
        if text_lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Try to find company separator
    company = ""
    name = ""
    next_steps = ""
    
    # Look for "at" or "from" to split name and company
    for sep in [" at ", " from ", " @ "]:
        if sep in text.lower():
            parts = text.split(sep, 1)
            name = parts[0].strip()
            remainder = parts[1] if len(parts) > 1 else ""
            
            # Look for next steps after comma
            if "," in remainder:
                company_part, next_steps = remainder.split(",", 1)
                company = company_part.strip()
                next_steps = next_steps.strip()
            else:
                company = remainder.strip()
            break
    
    if not name:
        return None
    
    return {
        "name": name.title(),
        "company": company.title() if company else "Unknown",
        "next_steps": next_steps if next_steps else "Follow up"
    }


def parse_update_from_text(text: str) -> dict | None:
    """
    Parse update info from text.
    Expected: "Update John - meeting scheduled" or "John: sent proposal"
    """
    text_lower = text.lower()
    
    if "update" in text_lower:
        text = text.lower().replace("update", "").strip()
    
    # Look for separators
    for sep in [" - ", ": ", ", "]:
        if sep in text:
            parts = text.split(sep, 1)
            return {
                "name": parts[0].strip().title(),
                "next_steps": parts[1].strip() if len(parts) > 1 else None
            }
    
    return None


def parse_done_from_text(text: str) -> str | None:
    """
    Parse done/complete commands.
    Expected: "Done with John" or "Mark John complete" or "Won John"
    """
    text_lower = text.lower()
    
    for pattern in ["done with ", "mark ", "complete ", "won ", "lost "]:
        if pattern in text_lower:
            remainder = text_lower.split(pattern, 1)[1]
            # Remove trailing words like "complete", "done"
            for suffix in [" complete", " done", " as won", " as lost"]:
                remainder = remainder.replace(suffix, "")
            return remainder.strip().title()
    
    return None


def parse_ooo_from_text(text: str) -> str | None:
    """
    Parse OOO date from text.
    Expected: "Out until Jan 15" or "OOO until next Monday"
    """
    text_lower = text.lower()
    
    for pattern in ["until ", "till "]:
        if pattern in text_lower:
            return text_lower.split(pattern, 1)[1].strip()
    
    return None
