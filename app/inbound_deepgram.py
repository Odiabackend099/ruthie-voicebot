"""
Inbound call handler using Twilio + Deepgram Agent API (no Vocode)
Handles phone calls through Twilio Media Streams -> Deepgram Agent

FIXED: Removed "Please wait" message, added greeting, added missing endpoints
"""

import os
import json
import base64
import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from collections import OrderedDict
from functools import wraps
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from app.function_handler import handle_function_call
from app.conversation_context import get_context, clear_context

logger = logging.getLogger(__name__)


def mask_phone(phone: str) -> str:
    """Mask phone number for logging - only show last 4 digits"""
    if phone and len(phone) >= 4:
        return f"***{phone[-4:]}"
    return "***"


def async_retry(max_retries: int = 3, base_delay: float = 0.25, max_delay: float = 2.0):
    """Decorator for async functions with exponential backoff retry logic"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {type(e).__name__}")
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


class TTLDict:
    """Thread-safe dictionary with TTL-based eviction and max size limit"""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        self._dict = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()

    def set(self, key, value):
        with self._lock:
            self._evict_expired()
            if len(self._dict) >= self._max_size:
                self._dict.popitem(last=False)  # Remove oldest
            self._dict[key] = (datetime.utcnow(), value)

    def get(self, key, default=None):
        with self._lock:
            if key in self._dict:
                ts, val = self._dict[key]
                if datetime.utcnow() - ts < timedelta(seconds=self._ttl):
                    return val
                del self._dict[key]
            return default

    def update(self, key, updates: dict):
        """Update an existing entry's value dict"""
        with self._lock:
            if key in self._dict:
                ts, val = self._dict[key]
                if datetime.utcnow() - ts < timedelta(seconds=self._ttl):
                    if isinstance(val, dict):
                        val.update(updates)
                        self._dict[key] = (ts, val)
                        return True
            return False

    def delete(self, key):
        with self._lock:
            self._dict.pop(key, None)

    def __contains__(self, key):
        with self._lock:
            if key in self._dict:
                ts, _ = self._dict[key]
                if datetime.utcnow() - ts < timedelta(seconds=self._ttl):
                    return True
                del self._dict[key]
            return False

    def values(self):
        with self._lock:
            self._evict_expired()
            return [val for _, val in self._dict.values()]

    def __len__(self):
        with self._lock:
            self._evict_expired()
            return len(self._dict)

    def _evict_expired(self):
        """Remove expired entries (must be called with lock held)"""
        now = datetime.utcnow()
        expired = [k for k, (ts, _) in self._dict.items()
                   if now - ts >= timedelta(seconds=self._ttl)]
        for k in expired:
            del self._dict[k]


def handle_task_exception(task: asyncio.Task):
    """Callback to log exceptions from background tasks"""
    try:
        exc = task.exception()
        if exc:
            logger.error(f"Background task failed: {exc}", exc_info=exc)
    except asyncio.CancelledError:
        pass

router = APIRouter()

# Store active call sessions with TTL (1 hour) and max size (1000 calls)
active_calls = TTLDict(ttl_seconds=3600, max_size=1000)

# Maximum transcript entries per call to prevent memory exhaustion
MAX_TRANSCRIPT_ENTRIES = 500

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Import prompt handler for comprehensive system prompt
from app.prompt_handler import get_system_prompt
from app.function_definitions import FUNCTION_DEFINITIONS

# Deepgram Agent Settings with greeting
def get_agent_settings():
    """Get Deepgram Agent settings configured for Twilio (8kHz mulaw)"""
    # Load comprehensive system prompt from file
    system_prompt = get_system_prompt()
    logger.info(f"Loaded system prompt for inbound calls ({len(system_prompt)} characters)")
    logger.info(f"Loaded {len(FUNCTION_DEFINITIONS)} function definitions for inbound calls")

    return {
        "type": "Settings",
        "audio": {
            "input": {
                "encoding": "mulaw",
                "sample_rate": 8000,
            },
            "output": {
                "encoding": "mulaw",
                "sample_rate": 8000,
                "container": "none",
            },
        },
        "agent": {
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": "nova-2",
                },
            },
            "think": {
                "provider": {
                    "type": "groq",
                    "model": "llama-3.3-70b-versatile",
                },
                "endpoint": {
                    "url": "https://api.groq.com/openai/v1/chat/completions",
                    "headers": {
                        "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
                    },
                },
                "prompt": system_prompt,
                "functions": FUNCTION_DEFINITIONS,
            },
            "speak": {
                "provider": {
                    "type": "deepgram",
                    "model": "aura-asteria-en",
                },
            },
            # CRITICAL: This makes the AI greet automatically
            "greeting": "Hi! Thanks for calling Callwaiting AI. I'm Ruthie. What can I help you with today?",
        },
    }


@router.post("/inbound_call")
async def handle_inbound_call(request: Request):
    """
    Twilio webhook endpoint for inbound calls
    Returns TwiML to start Media Stream - NO "Please wait" message
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")
    to_number = form_data.get("To")

    logger.info(f"Inbound call received: {call_sid}")
    logger.info(f"   From: {mask_phone(from_number)}")
    logger.info(f"   To: {mask_phone(to_number)}")

    # Store call metadata using TTLDict
    active_calls.set(call_sid, {
        "call_sid": call_sid,
        "from": from_number,
        "to": to_number,
        "start_time": datetime.utcnow().isoformat(),
        "status": "initiated"
    })

    # Get the WebSocket URL (base URI from env)
    base_uri = os.environ.get("BASE_URI", "https://ruthie-voice-bot.fly.dev")
    ws_url = base_uri.replace("https://", "wss://").replace("http://", "ws://")
    media_stream_url = f"{ws_url}/media_stream"

    # Return TwiML - Connect directly to WebSocket, NO <Say> element
    # The AI greeting comes from Deepgram Agent "greeting" setting
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{media_stream_url}">
            <Parameter name="CallSid" value="{call_sid}"/>
            <Parameter name="From" value="{from_number}"/>
            <Parameter name="To" value="{to_number}"/>
        </Stream>
    </Connect>
</Response>'''

    logger.info(f"Returning TwiML for call {call_sid} (direct connect, no wait message)")
    return Response(content=twiml, media_type="application/xml")


@router.post("/call_status_callback")
async def call_status_callback(request: Request):
    """
    Twilio status callback endpoint - receives call status updates
    Fixes HTTP 422 error
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        duration = form_data.get("CallDuration")

        logger.info(f"Call status callback: {call_sid} -> {call_status}")

        if call_sid in active_calls:
            updates = {"status": call_status}
            if duration:
                updates["duration"] = int(duration)
            if call_status in ["completed", "failed", "busy", "no-answer"]:
                updates["end_time"] = datetime.utcnow().isoformat()
            active_calls.update(call_sid, updates)

        # Log to Supabase if call completed
        if call_status == "completed":
            call_data = active_calls.get(call_sid)
            if call_data:
                task = asyncio.create_task(log_call_to_supabase(call_data, []))
                task.add_done_callback(handle_task_exception)

    except Exception as e:
        logger.error(f"Error in call_status_callback: {e}")

    # Return empty 204 response (Twilio expects this)
    return Response(status_code=204)


@router.post("/voice_fallback")
async def voice_fallback(request: Request):
    """
    Twilio fallback endpoint - called if primary webhook fails
    Returns simple TwiML with apology message
    """
    logger.warning("Voice fallback triggered - primary handler may have failed")

    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">We apologize, but we're experiencing technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>'''

    return Response(content=twiml, media_type="application/xml")


@router.websocket("/media_stream")
async def media_stream(websocket: WebSocket):
    """
    Twilio Media Stream WebSocket endpoint
    Bridges Twilio audio <-> Deepgram Agent API
    """
    await websocket.accept()
    logger.info("Twilio Media Stream connected")

    call_sid = None
    call_metadata = {}
    transcript = []

    # Silence detection state
    last_user_speech_time = None  # Timestamp of last user speech
    silence_monitoring_active = True  # Flag to control silence monitor

    # Deepgram Voice Agent URL
    deepgram_url = "wss://agent.deepgram.com/v1/agent/converse"
    headers = {
        "Authorization": f"Token {os.environ.get('DEEPGRAM_API_KEY')}"
    }

    # Get agent settings (already configured for 8kHz mulaw + greeting)
    agent_settings = get_agent_settings()

    try:
        import websockets
        async with websockets.connect(deepgram_url, extra_headers=headers) as deepgram_ws:
            logger.info("Connected to Deepgram Voice Agent")

            # Send initial settings
            await deepgram_ws.send(json.dumps(agent_settings))
            logger.info("Sent Agent Settings to Deepgram (8kHz mulaw, with greeting)")

            # Wait for SettingsApplied
            while True:
                msg = await deepgram_ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("type") == "SettingsApplied":
                        logger.info("SettingsApplied received from Deepgram")
                        break
                    elif data.get("type") == "Error":
                        logger.error(f"Deepgram Error during setup: {data}")
                        raise Exception(f"Deepgram Error: {data}")

            async def twilio_to_deepgram():
                """Forward audio from Twilio to Deepgram"""
                nonlocal call_sid, call_metadata
                audio_chunk_count = 0
                last_audio_log_time = datetime.utcnow()

                try:
                    while True:
                        message = await websocket.receive_text()
                        data = json.loads(message)
                        event_type = data.get("event")

                        if event_type == "start":
                            # Call started, extract metadata
                            start_data = data.get("start", {})
                            call_sid = start_data.get("callSid")
                            custom_params = start_data.get("customParameters", {})

                            call_metadata = {
                                "call_sid": call_sid,
                                "from": custom_params.get("From"),
                                "to": custom_params.get("To"),
                                "stream_sid": start_data.get("streamSid"),
                                "start_time": datetime.utcnow().isoformat()
                            }

                            logger.info(f"Call started: {call_sid}")
                            logger.info(f"   From: {mask_phone(call_metadata.get('from'))}")
                            logger.info(f"   To: {mask_phone(call_metadata.get('to'))}")
                            logger.info(f"   Stream SID: {start_data.get('streamSid')}")

                            # Update active calls using TTLDict
                            call_metadata["status"] = "connected"
                            if call_sid in active_calls:
                                active_calls.update(call_sid, call_metadata)
                            else:
                                active_calls.set(call_sid, call_metadata)

                        elif event_type == "media":
                            # Audio chunk from Twilio -> Deepgram
                            media_data = data.get("media", {})
                            payload = media_data.get("payload")

                            if payload:
                                # Decode base64 mulaw audio
                                audio_data = base64.b64decode(payload)
                                await deepgram_ws.send(audio_data)

                                # Log audio flow periodically (every 2 seconds)
                                audio_chunk_count += 1
                                now = datetime.utcnow()
                                if (now - last_audio_log_time).total_seconds() >= 2:
                                    logger.info(f"🎤 Audio flowing: {audio_chunk_count} chunks sent to Deepgram")
                                    last_audio_log_time = now
                            else:
                                logger.warning(f"⚠️  Empty audio payload received from Twilio")

                        elif event_type == "stop":
                            # Call ended
                            logger.info(f"Call stopped: {call_sid}")
                            if call_sid in active_calls:
                                active_calls.update(call_sid, {
                                    "status": "completed",
                                    "end_time": datetime.utcnow().isoformat()
                                })
                            break

                        elif event_type == "mark":
                            # Mark event (optional, for tracking)
                            pass

                except WebSocketDisconnect:
                    logger.info("Twilio disconnected")
                except Exception as e:
                    logger.error(f"Error in twilio_to_deepgram: {e}", exc_info=True)
                    raise

            async def silence_monitor():
                """Monitor for extended silence and proactively engage (6s, 12s, 18s intervals)"""
                nonlocal last_user_speech_time, silence_monitoring_active
                
                try:
                    while silence_monitoring_active:
                        await asyncio.sleep(2)  # Check every 2 seconds
                        
                        if last_user_speech_time and call_sid:
                            context = get_context(call_sid)
                            silence_response = context.get_silence_response()
                            
                            if silence_response:
                                # Send proactive engagement message
                                logger.info(f"Silence detected ({context.get_silence_duration():.1f}s) for call {call_sid}")
                                
                                proactive_msg = {
                                    "type": "InjectAgent",
                                    "content": silence_response
                                }
                                await deepgram_ws.send(json.dumps(proactive_msg))
                                logger.info(f"Sent silence recovery prompt: {silence_response}")
                                
                                # If 18+ seconds, prepare for transfer/hangup
                                if context.get_silence_duration() >= 18:
                                    # TODO: Trigger transfer to human agent or graceful hangup
                                    logger.warning(f"Extended silence (18s+) on call {call_sid} - should transfer to human")
                                    silence_monitoring_active = False
                                    break
                
                except Exception as e:
                    if "ConnectionClosed" not in str(type(e)):
                        logger.error(f"Error in silence_monitor: {e}", exc_info=True)

            async def deepgram_to_twilio():
                """Forward audio and transcripts from Deepgram to Twilio"""
                nonlocal transcript, last_user_speech_time
                audio_response_count = 0
                last_audio_response_log = datetime.utcnow()

                try:
                    async for message in deepgram_ws:
                        if isinstance(message, bytes):
                            # Audio from Deepgram -> Twilio
                            # Encode to base64 for Twilio
                            encoded_audio = base64.b64encode(message).decode("utf-8")

                            # Send to Twilio in their media format
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": call_metadata.get("stream_sid"),
                                "media": {
                                    "payload": encoded_audio
                                }
                            })

                            # Log audio response periodically
                            audio_response_count += 1
                            now = datetime.utcnow()
                            if (now - last_audio_response_log).total_seconds() >= 2:
                                logger.info(f"🔊 Audio response: {audio_response_count} chunks sent to Twilio")
                                last_audio_response_log = now

                        else:
                            # JSON message from Deepgram
                            msg_json = json.loads(message)
                            msg_type = msg_json.get("type")

                            # DIAGNOSTIC: Log all message types
                            logger.info(f"📨 Deepgram message type: {msg_type}")
                            if msg_type not in ["ConversationText"]:
                                logger.info(f"   Full message: {json.dumps(msg_json, indent=2)[:500]}")

                            if msg_type == "ConversationText":
                                # Store transcript with size limit
                                role = msg_json.get("role")  # "user" or "assistant"
                                content = msg_json.get("content")

                                # Track user speech for silence detection
                                if role == "user":
                                    last_user_speech_time = datetime.utcnow()
                                    
                                    # Update conversation context
                                    if call_sid:
                                        context = get_context(call_sid)
                                        context.add_turn(role, content)

                                if len(transcript) < MAX_TRANSCRIPT_ENTRIES:
                                    transcript.append({
                                        "role": role,
                                        "content": content,
                                        "timestamp": datetime.utcnow().isoformat()
                                    })
                                elif len(transcript) == MAX_TRANSCRIPT_ENTRIES:
                                    logger.warning(f"Transcript limit ({MAX_TRANSCRIPT_ENTRIES}) reached for call {call_sid}")
                                    transcript.append({"role": "system", "content": "[Transcript truncated]", "timestamp": datetime.utcnow().isoformat()})

                                logger.info(f"{role}: {content}")

                            elif msg_type == "FunctionCallRequest":
                                # Handle function calls from Deepgram Agent
                                function_name = msg_json.get("function_name") or msg_json.get("name")
                                function_id = msg_json.get("function_call_id") or msg_json.get("id")
                                arguments = msg_json.get("input") or msg_json.get("arguments", {})

                                logger.info(f"🔧 Function call for {call_sid}: {function_name}({arguments})")
                                logger.info(f"   Function ID: {function_id}")
                                logger.info(f"   Full message: {json.dumps(msg_json, indent=2)}")

                                # CRITICAL: Validate function_id before proceeding
                                if not function_id:
                                    logger.error(f"❌ CRITICAL: No function_id found in FunctionCallRequest! Keys: {list(msg_json.keys())}")
                                    logger.error(f"   Full message: {msg_json}")
                                    # Try to recover by using a generated ID
                                    function_id = f"generated_{datetime.utcnow().timestamp()}"
                                    logger.warning(f"   Using generated ID: {function_id}")

                                try:
                                    # Execute the function using call_sid as session_id
                                    result = await handle_function_call(
                                        function_name=function_name,
                                        arguments=arguments,
                                        session_id=call_sid
                                    )

                                    logger.info(f"   Function result: {result}")

                                    # CRITICAL: Deepgram expects "output" to be a STRING containing JSON
                                    # The "speak" field should be at the top level of the output JSON
                                    response = {
                                        "type": "FunctionCallResponse",
                                        "function_call_id": function_id,
                                        "output": json.dumps(result)
                                    }

                                    logger.info(f"   Sending FunctionCallResponse: {json.dumps(response, indent=2)}")
                                    await deepgram_ws.send(json.dumps(response))
                                    logger.info(f"✅ Function response sent for {call_sid}: {result.get('speak', 'no speak')[:50]}...")

                                    # Log function call to transcript
                                    if len(transcript) < MAX_TRANSCRIPT_ENTRIES:
                                        transcript.append({
                                            "role": "function",
                                            "content": f"{function_name}: {result.get('speak', '')}",
                                            "timestamp": datetime.utcnow().isoformat()
                                        })

                                    # Track assistant response in context
                                    if call_sid:
                                        context = get_context(call_sid)
                                        context.add_turn("assistant", result.get('speak', ''))

                                except Exception as e:
                                    logger.error(f"❌ Function execution error for {call_sid}: {e}", exc_info=True)
                                    logger.error(f"   Function name: {function_name}")
                                    logger.error(f"   Arguments: {arguments}")
                                    logger.error(f"   Call SID: {call_sid}")

                                    # Send error response - MUST include function_call_id
                                    error_response = {
                                        "type": "FunctionCallResponse",
                                        "function_call_id": function_id,
                                        "output": json.dumps({"speak": "I'm sorry, something went wrong. Could you try again?"})
                                    }
                                    logger.info(f"   Sending error FunctionCallResponse: {json.dumps(error_response)}")
                                    await deepgram_ws.send(json.dumps(error_response))

                            elif msg_type == "Error":
                                error_code = msg_json.get("code", "")
                                error_msg = msg_json.get("message", "Unknown error")
                                
                                # Log all errors (silence is now handled by silence_monitor)
                                if error_code != "CLIENT_MESSAGE_TIMEOUT":
                                    logger.error(f"Deepgram Error: {error_msg} (code: {error_code})")

                            elif msg_type == "UserStartedSpeaking":
                                # BARGE-IN: User interrupted while agent was speaking
                                # Send clear event to Twilio to flush audio buffer immediately
                                stream_sid = call_metadata.get("stream_sid")
                                if stream_sid:
                                    logger.info(f"Barge-in detected for call {call_sid} - clearing Twilio audio buffer")
                                    await websocket.send_json({
                                        "event": "clear",
                                        "streamSid": stream_sid
                                    })

                except Exception as e:
                    if "ConnectionClosed" not in str(type(e)):
                        logger.error(f"Error in deepgram_to_twilio: {e}", exc_info=True)
                    raise

            # Run all direction handlers concurrently with exception handling
            results = await asyncio.gather(
                twilio_to_deepgram(),
                deepgram_to_twilio(),
                silence_monitor(),  # Add silence monitoring task
                return_exceptions=True
            )
            # Log any exceptions from the tasks
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = ["twilio_to_deepgram", "deepgram_to_twilio", "silence_monitor"][i]
                    logger.error(f"Task {task_name} failed: {result}")

    except Exception as e:
        logger.error(f"Media stream error: {e}", exc_info=True)

    finally:
        # Log call summary and save to Supabase
        if call_sid:
            logger.info(f"Call {call_sid} ended")
            logger.info(f"   Transcript exchanges: {len(transcript)}")

            # Save to Supabase with exception handling
            call_metadata["end_time"] = datetime.utcnow().isoformat()
            task = asyncio.create_task(log_call_to_supabase(call_metadata, transcript))
            task.add_done_callback(handle_task_exception)

            # Clean up active calls using TTLDict
            active_calls.delete(call_sid)

        try:
            await websocket.close()
        except Exception as e:
            logger.debug(f"WebSocket close error (expected): {e}")


@async_retry(max_retries=3, base_delay=0.25, max_delay=2.0)
async def log_call_to_supabase(call_metadata: dict, transcript: list):
    """
    Save call log to Supabase using httpx (async) with retry logic
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured, skipping call log")
        return

    try:
        # Calculate duration
        start_time = datetime.fromisoformat(call_metadata.get("start_time", datetime.utcnow().isoformat()))
        end_time = datetime.fromisoformat(call_metadata.get("end_time", datetime.utcnow().isoformat()))
        duration_seconds = int((end_time - start_time).total_seconds())

        # Build transcript text for search
        transcript_text = "\n".join([
            f"{t.get('role', 'unknown')}: {t.get('content', '')}"
            for t in transcript
        ])

        # Prepare data
        # Get Tenant ID from env
        tenant_id = os.environ.get("TENANT_ID")
        
        # Determine phone number (customer's number)
        phone_number = call_metadata.get("from") if call_metadata.get("direction") == "inbound" else call_metadata.get("to")
        if not phone_number:
            phone_number = call_metadata.get("from") # Fallback

        data = {
            "tenant_id": tenant_id,
            "phone_number": phone_number,
            "twilio_call_sid": call_metadata.get("call_sid"), # Mapped from call_sid
            "from_number": call_metadata.get("from"),
            "to_number": call_metadata.get("to"),
            "duration_seconds": duration_seconds,
            "transcript_json": transcript, # Mapped to new JSONB column
            "transcript": transcript_text, # Mapped to existing TEXT column
            "status": "completed",
            "call_type": "inbound",
            "created_at": call_metadata.get("start_time")
        }

        # Insert via REST API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/call_logs",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                json=data,
                timeout=10.0
            )

            if response.status_code in [200, 201]:
                logger.info(f"Call log saved to Supabase: {call_metadata.get('call_sid')}")
            else:
                logger.error(f"Failed to save call log: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Error saving call log to Supabase: {e}", exc_info=True)


@router.get("/call_status/{call_sid}")
async def get_call_status(call_sid: str):
    """Get status of an active call"""
    call_data = active_calls.get(call_sid)
    if call_data:
        return call_data
    else:
        return {"error": "Call not found", "call_sid": call_sid}


@router.get("/active_calls")
async def get_active_calls():
    """Get list of all active calls"""
    calls = active_calls.values()
    return {
        "count": len(calls),
        "calls": calls
    }
