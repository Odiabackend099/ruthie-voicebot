"""
N8N Webhook Client for Ruthie AI Voice Agent (Callwaiting AI)
Handles communication with N8N workflows for booking, messaging, and other actions.

N8N Webhook URL: https://digital-odia.app.n8n.cloud/webhook/serenity-webhook-v2

Available Actions:
1. book_appointment - Book a new appointment
2. reschedule_appointment - Reschedule existing appointment
3. cancel_appointment - Cancel an appointment
4. send_email - Send email via Gmail
5. send_sms - Send SMS via Twilio
6. send_whatsapp - Send WhatsApp message
7. search_web - Search the web via SerpAPI
8. get_current_datetime - Get current date/time
9. get_location_info - Get ODIADEV location info
"""

import os
import httpx
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# N8N Configuration
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://digital-odia.app.n8n.cloud/webhook/serenity-webhook-v2"
)

# Timeout for N8N calls (8 seconds as per cheat sheet)
N8N_TIMEOUT_SECONDS = 8.0

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_MS = 500
MAX_DELAY_MS = 2000


async def call_n8n_action(
    action: str,
    parameters: Dict[str, Any],
    session_id: str,
    callback_url: Optional[str] = None,
    timeout: float = N8N_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    Call N8N webhook with action and parameters.
    Implements exponential backoff retry logic.

    Args:
        action: The action to perform (e.g., 'book_appointment', 'send_email')
        parameters: Action-specific parameters
        session_id: Unique session/call identifier for tracking
        callback_url: Optional URL for N8N to call back with results
        timeout: Request timeout in seconds (default: 8s)

    Returns:
        Dict with response from N8N or error information
    """
    payload = {
        "action": action,
        "session_id": session_id,
        "callback_url": callback_url,
        "timestamp": datetime.utcnow().isoformat(),
        **parameters
    }

    logger.info(f"N8N call: action={action}, session_id={session_id}")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    N8N_WEBHOOK_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"N8N success: action={action}, attempt={attempt+1}")
                    return {
                        "success": True,
                        "action": action,
                        "data": result,
                        "attempts": attempt + 1
                    }

                elif response.status_code == 429:
                    # Rate limited - use exponential backoff
                    delay = min(BASE_DELAY_MS * (2 ** attempt), MAX_DELAY_MS) / 1000
                    logger.warning(f"N8N rate limited, retry in {delay}s (attempt {attempt+1})")
                    await asyncio.sleep(delay)
                    continue

                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    delay = min(BASE_DELAY_MS * (2 ** attempt), MAX_DELAY_MS) / 1000
                    logger.warning(f"N8N server error {response.status_code}, retry in {delay}s")
                    await asyncio.sleep(delay)
                    continue

                else:
                    # Client error (4xx except 429) - don't retry
                    logger.error(f"N8N client error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "action": action,
                        "error": f"Client error: {response.status_code}",
                        "details": response.text,
                        "attempts": attempt + 1
                    }

        except httpx.TimeoutException as e:
            last_error = str(e)
            delay = min(BASE_DELAY_MS * (2 ** attempt), MAX_DELAY_MS) / 1000
            logger.warning(f"N8N timeout, retry in {delay}s (attempt {attempt+1})")
            await asyncio.sleep(delay)

        except Exception as e:
            last_error = str(e)
            delay = min(BASE_DELAY_MS * (2 ** attempt), MAX_DELAY_MS) / 1000
            logger.error(f"N8N error: {e}, retry in {delay}s (attempt {attempt+1})")
            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error(f"N8N failed after {MAX_RETRIES} attempts: {last_error}")
    return {
        "success": False,
        "action": action,
        "error": "Max retries exceeded",
        "last_error": last_error,
        "attempts": MAX_RETRIES
    }


# Convenience functions for specific actions

async def book_appointment(
    session_id: str,
    client_name: str,
    client_email: str,
    client_phone: str,
    company_name: str,
    booking_date: str,
    booking_time: str,
    service_type: str,
    purpose: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Book a new appointment via N8N"""
    return await call_n8n_action(
        action="book_appointment",
        parameters={
            "client_name": client_name,
            "client_email": client_email,
            "client_phone": client_phone,
            "company_name": company_name,
            "booking_date": booking_date,
            "booking_time": booking_time,
            "service_type": service_type,
            "purpose": purpose
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def reschedule_appointment(
    session_id: str,
    client_email: str,
    new_date: str,
    new_time: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Reschedule an existing appointment via N8N"""
    return await call_n8n_action(
        action="reschedule_appointment",
        parameters={
            "client_email": client_email,
            "new_date": new_date,
            "new_time": new_time
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def cancel_appointment(
    session_id: str,
    client_email: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Cancel an appointment via N8N"""
    return await call_n8n_action(
        action="cancel_appointment",
        parameters={
            "client_email": client_email
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def send_email(
    session_id: str,
    to: str,
    subject: str,
    message: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Send email via N8N (Gmail)"""
    return await call_n8n_action(
        action="send_email",
        parameters={
            "to": to,
            "subject": subject,
            "message": message
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def send_sms(
    session_id: str,
    to: str,
    message: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Send SMS via N8N (Twilio)"""
    return await call_n8n_action(
        action="send_sms",
        parameters={
            "to": to,
            "message": message
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def send_whatsapp(
    session_id: str,
    to: str,
    message: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Send WhatsApp message via N8N (Twilio)"""
    return await call_n8n_action(
        action="send_whatsapp",
        parameters={
            "to": to,
            "message": message
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def search_web(
    session_id: str,
    query: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Search the web via N8N (SerpAPI)"""
    return await call_n8n_action(
        action="search_web",
        parameters={
            "query": query
        },
        session_id=session_id,
        callback_url=callback_url
    )


async def get_current_datetime(
    session_id: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Get current date and time via N8N"""
    return await call_n8n_action(
        action="get_current_datetime",
        parameters={},
        session_id=session_id,
        callback_url=callback_url
    )


async def get_location_info(
    session_id: str,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Get ODIADEV location info via N8N"""
    return await call_n8n_action(
        action="get_location_info",
        parameters={},
        session_id=session_id,
        callback_url=callback_url
    )


# Utility function for call summaries
async def log_call_summary(
    session_id: str,
    call_sid: str,
    transcript: str,
    duration_seconds: int,
    caller_phone: Optional[str] = None,
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    """Log call summary to N8N for further processing"""
    return await call_n8n_action(
        action="log_call_summary",
        parameters={
            "call_sid": call_sid,
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "caller_phone": caller_phone,
            "timestamp": datetime.utcnow().isoformat()
        },
        session_id=session_id,
        callback_url=callback_url
    )
