"""
Outbound calling system using Twilio + Deepgram Agent API
Allows programmatic outbound calls with AI voice agent
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


def mask_phone(phone: str) -> str:
    """Mask phone number for logging - only show last 4 digits"""
    if phone and len(phone) >= 4:
        return f"***{phone[-4:]}"
    return "***"


def validate_e164(phone: str) -> bool:
    """Validate phone number is in E.164 format"""
    return bool(re.match(r'^\+[1-9]\d{1,14}$', phone))

router = APIRouter()

# Initialize Twilio client (optional - only needed for outbound calls)
try:
    twilio_client = Client(
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN")
    )
    logger.info("✅ Twilio client initialized")
except Exception as e:
    logger.warning(f"⚠️ Twilio client not initialized (credentials missing): {e}")
    logger.warning("   Outbound calling features will be disabled")
    twilio_client = None



class OutboundCallRequest(BaseModel):
    """Request model for outbound calls"""
    phone_number: str = Field(..., description="Phone number to call (E.164 format, e.g., +14155551234)")
    message_type: str = Field(default="general", description="Type of message: general, appointment_reminder, follow_up, demo")
    custom_prompt: Optional[str] = Field(None, description="Custom AI prompt/message (overrides message_type)")
    from_number: Optional[str] = Field(None, description="Twilio number to call from (defaults to env TWILIO_PHONE_NUMBER)")
    client_id: Optional[str] = Field(None, description="Client ID for tracking")

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        if not validate_e164(v):
            raise ValueError('Phone number must be in E.164 format (e.g., +14155551234)')
        return v


class OutboundCallResponse(BaseModel):
    """Response model for outbound calls"""
    success: bool
    call_sid: str
    status: str
    message: str
    phone_number: str


# Predefined message templates
MESSAGE_TEMPLATES = {
    "general": "Hello! This is Ruthie from {company_name}. I'm calling to check in and see how we can assist you today. How are you doing?",

    "appointment_reminder": "Hi! This is Ruthie from {company_name}. I'm calling to remind you about your appointment scheduled for {appointment_time}. Can you confirm if you'll be able to make it?",

    "follow_up": "Hello! This is Ruthie from {company_name}. I'm following up on our previous conversation. Do you have a few minutes to chat about {topic}?",

    "demo": "Hi there! This is Ruthie, an AI voice assistant from Callwaiting AI. I'm calling to demonstrate how I can help businesses handle customer calls. Is now a good time to chat?",

    "booking": "Hello! This is Ruthie from {company_name}. I'd like to help you schedule an appointment. What day works best for you?",

    "survey": "Hi! This is Ruthie from {company_name}. We'd love to get your feedback. Do you have 2 minutes for a quick survey?",

    "payment_reminder": "Hello! This is Ruthie from {company_name}. I'm calling regarding your account balance. Can we discuss payment options?",
}


def get_system_prompt(message_type: str, custom_prompt: Optional[str] = None, **kwargs) -> str:
    """
    Generate system prompt based on message type

    Args:
        message_type: Type of message/call
        custom_prompt: Custom prompt (overrides template)
        **kwargs: Additional variables for template substitution

    Returns:
        System prompt string for Deepgram Agent
    """
    if custom_prompt:
        return custom_prompt

    template = MESSAGE_TEMPLATES.get(message_type, MESSAGE_TEMPLATES["general"])

    # Default values
    defaults = {
        "company_name": "Callwaiting AI",
        "appointment_time": "tomorrow at 2 PM",
        "topic": "your inquiry"
    }
    defaults.update(kwargs)

    try:
        return template.format(**defaults)
    except KeyError as e:
        logger.warning(f"Missing template variable: {e}, using defaults")
        return template.format(**defaults)


@router.post("/api/calls/outbound", response_model=OutboundCallResponse)
async def place_outbound_call(request: OutboundCallRequest):
    """
    Place an outbound call using Twilio + Deepgram Agent

    Example:
        POST /api/calls/outbound
        {
            "phone_number": "+14155551234",
            "message_type": "appointment_reminder",
            "client_id": "client-123"
        }
    """
    # Log without exposing full phone number (PII protection)
    phone_last4 = request.phone_number[-4:] if len(request.phone_number) >= 4 else "***"
    logger.info(f"Outbound call request to: ***{phone_last4}")
    logger.info(f"   Message type: {request.message_type}")
    logger.info(f"   Client ID: {request.client_id}")

    try:
        # Check Twilio client is initialized
        if twilio_client is None:
            raise HTTPException(
                status_code=503,
                detail="Twilio client not initialized. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
            )

        # Get from number (use env var or request)
        from_number = request.from_number or os.environ.get("TWILIO_PHONE_NUMBER")

        if not from_number:
            raise HTTPException(
                status_code=400,
                detail="No Twilio phone number configured. Set TWILIO_PHONE_NUMBER in environment or provide from_number in request"
            )

        # Get base URI for TwiML callback
        base_uri = os.environ.get("BASE_URI", "https://ruthie-voice-bot.fly.dev")

        # Generate system prompt
        system_prompt = get_system_prompt(
            message_type=request.message_type,
            custom_prompt=request.custom_prompt
        )

        # Create TwiML URL with parameters
        twiml_url = f"{base_uri}/outbound_twiml"

        # Store call context (we'll need this for the TwiML endpoint)
        # In production, use Redis or database
        call_context = {
            "phone_number": request.phone_number,
            "message_type": request.message_type,
            "system_prompt": system_prompt,
            "client_id": request.client_id,
            "initiated_at": datetime.utcnow().isoformat()
        }

        # Place the call
        call = twilio_client.calls.create(
            to=request.phone_number,
            from_=from_number,
            url=twiml_url,
            method="POST",
            status_callback=f"{base_uri}/call_status_callback",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            record=True,  # Record call
            timeout=30,  # Ring for 30 seconds
            machine_detection="DetectMessageEnd",  # Detect voicemail
        )

        logger.info(f"✅ Call initiated: {call.sid}")
        logger.info(f"   Status: {call.status}")

        # TODO: Store call_context in database with call.sid
        # await save_outbound_call_context(call.sid, call_context)

        return OutboundCallResponse(
            success=True,
            call_sid=call.sid,
            status=call.status,
            message=f"Call initiated to {request.phone_number}",
            phone_number=request.phone_number
        )

    except TwilioRestException as e:
        logger.error(f"❌ Twilio error: {e}")
        raise HTTPException(status_code=400, detail=f"Twilio error: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Error placing outbound call: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/outbound_twiml")
async def outbound_twiml(request: Request):
    """
    TwiML endpoint for outbound calls
    Returns TwiML to connect call to Deepgram Agent via Media Stream
    """
    from fastapi.responses import Response

    # Get call details from Twilio
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    answered_by = form_data.get("AnsweredBy")  # human, machine, fax, unknown

    logger.info(f"📱 Outbound TwiML requested for call: {call_sid}")
    logger.info(f"   Answered by: {answered_by}")

    # Handle voicemail/machine detection (all machine types)
    if answered_by and answered_by.startswith("machine"):
        # Leave voicemail message
        twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Hello! This is Ruthie from Callwaiting AI.
        We were trying to reach you.
        Please give us a call back at your convenience.
        Thank you!
    </Say>
    <Hangup/>
</Response>'''
        logger.info(f"📬 Leaving voicemail for call {call_sid}")
        return Response(content=twiml, media_type="application/xml")

    # Connect to Media Stream for live conversation
    base_uri = os.environ.get("BASE_URI", "https://ruthie-voice-bot.fly.dev")
    ws_url = base_uri.replace("https://", "wss://").replace("http://", "ws://")
    media_stream_url = f"{ws_url}/media_stream"

    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{media_stream_url}">
            <Parameter name="CallSid" value="{call_sid}"/>
            <Parameter name="CallType" value="outbound"/>
        </Stream>
    </Connect>
</Response>'''

    logger.info(f"✅ Returning TwiML for outbound call {call_sid}")
    return Response(content=twiml, media_type="application/xml")


# Note: /call_status_callback is now handled by inbound_deepgram.py
# It works for both inbound and outbound calls


@router.get("/api/calls/{call_sid}")
async def get_call_details(call_sid: str):
    """
    Get details of a specific call from Twilio

    Args:
        call_sid: Twilio call SID

    Returns:
        Call details including status, duration, cost, etc.
    """
    if twilio_client is None:
        raise HTTPException(status_code=503, detail="Twilio client not initialized")

    try:
        call = twilio_client.calls(call_sid).fetch()

        return {
            "call_sid": call.sid,
            "status": call.status,
            "from": call.from_,
            "to": call.to,
            "duration": call.duration,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "end_time": call.end_time.isoformat() if call.end_time else None,
            "price": call.price,
            "price_unit": call.price_unit,
            "direction": call.direction,
            "answered_by": call.answered_by
        }

    except TwilioRestException as e:
        logger.error(f"Error fetching call {call_sid}: {e}")
        raise HTTPException(status_code=404, detail="Call not found")


@router.get("/api/calls")
async def list_recent_calls(limit: int = 50):
    """
    List recent calls from Twilio

    Args:
        limit: Number of calls to return (max 100)

    Returns:
        List of recent calls
    """
    if twilio_client is None:
        raise HTTPException(status_code=503, detail="Twilio client not initialized")

    try:
        # Cap at 100 for performance
        calls = twilio_client.calls.list(limit=min(limit, 100))

        return {
            "count": len(calls),
            "calls": [
                {
                    "call_sid": call.sid,
                    "from": call.from_,
                    "to": call.to,
                    "status": call.status,
                    "duration": call.duration,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "direction": call.direction,
                    "price": call.price
                }
                for call in calls
            ]
        }

    except TwilioRestException as e:
        logger.error(f"Error listing calls: {e}")
        raise HTTPException(status_code=500, detail="Error fetching calls")


# Batch outbound calling (for campaigns)
class BatchOutboundRequest(BaseModel):
    """Request model for batch outbound calls"""
    phone_numbers: list[str] = Field(
        ...,
        max_length=50,  # Rate limit: max 50 numbers per batch
        description="List of phone numbers to call (max 50)"
    )
    message_type: str = Field(default="general", description="Type of message")
    custom_prompt: Optional[str] = Field(None, description="Custom AI prompt")
    from_number: Optional[str] = Field(None, description="Twilio number to call from")
    delay_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Delay between calls (1-60 seconds)"
    )

    @field_validator('phone_numbers')
    @classmethod
    def validate_phone_numbers(cls, v: list[str]) -> list[str]:
        for phone in v:
            if not validate_e164(phone):
                raise ValueError(f'Invalid phone number format: {mask_phone(phone)} - must be E.164 format')
        return v


@router.post("/api/calls/outbound/batch")
async def place_batch_outbound_calls(request: BatchOutboundRequest):
    """
    Place multiple outbound calls with delay between each

    Example:
        POST /api/calls/outbound/batch
        {
            "phone_numbers": ["+14155551234", "+14155555678"],
            "message_type": "survey",
            "delay_seconds": 10
        }
    """
    logger.info(f"📞 Batch outbound call request: {len(request.phone_numbers)} numbers")

    results = []

    for i, phone_number in enumerate(request.phone_numbers):
        try:
            # Place individual call
            call_request = OutboundCallRequest(
                phone_number=phone_number,
                message_type=request.message_type,
                custom_prompt=request.custom_prompt,
                from_number=request.from_number
            )

            result = await place_outbound_call(call_request)
            results.append(result.dict())

            logger.info(f"✅ Call {i+1}/{len(request.phone_numbers)} placed: {mask_phone(phone_number)}")

            # Delay before next call (except for last one)
            if i < len(request.phone_numbers) - 1:
                await asyncio.sleep(request.delay_seconds)

        except Exception as e:
            logger.error(f"❌ Error calling {mask_phone(phone_number)}: {e}")
            results.append({
                "success": False,
                "phone_number": phone_number,
                "error": str(e)
            })

    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "results": results
    }
