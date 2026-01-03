import httpx
import tempfile
import os
import json
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


async def transcribe_voice(file_url: str, bot_token: str) -> str:
    """Download voice file from Telegram and transcribe with Groq Whisper."""
    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(file_url)
        audio_data = response.content

    # Write to temp file - Groq needs a proper file
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language="en"
            )
        return transcription.text
    finally:
        os.unlink(tmp_path)


def parse_intent_with_llm(text: str, today_date: str) -> dict | None:
    """Use Groq LLM to parse natural language into structured intent."""
    prompt = f"""Parse this sales note into a JSON action. Return ONLY valid JSON, no other text.

Today's date: {today_date} (use this to calculate any relative dates)

Input: "{text}"

Possible actions:
1. add_lead: {{"action": "add_lead", "name": "person name", "company": "company name", "next_steps": "what to do next", "follow_up_date": "YYYY-MM-DD or null"}}
2. update_lead: {{"action": "update_lead", "name": "person or company name", "next_steps": "new status/next steps", "follow_up_date": "YYYY-MM-DD or null"}}
3. done_lead: {{"action": "done_lead", "name": "person or company name", "status": "won" or "lost"}}
4. list_leads: {{"action": "list_leads"}}
5. unknown: {{"action": "unknown"}}

Rules:
- For add_lead: extract name (person), company, and what needs to be done
- If only a company name is mentioned without a person, use "Contact" as the name
- If company is unclear, use the most likely company/organization name mentioned
- Convert relative dates to actual YYYY-MM-DD format:
  - "Monday" = next Monday from today
  - "next week" = Monday of next week
  - "tomorrow" = tomorrow's date
  - "in 3 days" = 3 days from today
  - "end of week" = this Friday
  - "next month" = 1st of next month
- If no date/time mentioned, set follow_up_date to null
- The name field can be a person name OR company name - whatever helps identify the lead

JSON response:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200
        )
        result = response.choices[0].message.content.strip()
        # Clean up response - remove markdown if present
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()
        return json.loads(result)
    except Exception as e:
        print(f"LLM parse error: {e}")
        return None


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
