from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.browser_ws import router as browser_ws_router
from app.inbound_deepgram import router as inbound_router
from app.outbound import router as outbound_router
import logging
import os
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ruthie AI Voice Bot API",
    description="Real-time voice AI using Deepgram Agent API - Callwaiting AI",
    version="2.0.0"
)

# Add CORS middleware for frontend access
# Includes localhost for development and production domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:4050",
        "http://localhost:4060",
        "https://callwaitingai.odia.dev",
        "https://ordervoice.ai",
        "https://www.ordervoice.ai",
        os.environ.get("FRONTEND_URL", "https://ordervoice.ai"),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include routers
app.include_router(browser_ws_router)  # Browser WebSocket (/ws)
app.include_router(inbound_router)     # Inbound calls (/inbound_call, /media_stream)
app.include_router(outbound_router)    # Outbound calls (/api/calls/outbound, etc.)

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Ruthie AI Voice Bot - Callwaiting AI",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "browser_websocket": "/ws",
            "inbound_call": "/inbound_call",
            "media_stream": "/media_stream",
            "outbound_call": "/api/calls/outbound",
            "call_details": "/api/calls/{call_sid}",
            "active_calls": "/active_calls"
        }
    }

@app.get("/health")
async def health():
    """
    Health check endpoint with actual service connectivity tests
    """
    health_status = {
        "status": "ok",
        "service": "Ruthie AI Voice Bot - Callwaiting AI",
        "version": "2.0.0",
        "checks": {}
    }

    # Check environment variables
    required_vars = [
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN"
    ]

    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        health_status["status"] = "degraded"
        health_status["missing_env_vars"] = missing_vars
        logger.warning(f"Missing environment variables: {missing_vars}")

    # Check Deepgram API connectivity
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY")
    if deepgram_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.deepgram.com/v1/projects",
                    headers={"Authorization": f"Token {deepgram_key}"}
                )
                if resp.status_code == 200:
                    health_status["checks"]["deepgram"] = "ok"
                else:
                    health_status["checks"]["deepgram"] = f"degraded (status: {resp.status_code})"
                    health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["deepgram"] = f"error: {type(e).__name__}"
            health_status["status"] = "degraded"
    else:
        health_status["checks"]["deepgram"] = "not configured"

    # Check Twilio API connectivity
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if twilio_sid and twilio_token:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}.json",
                    auth=(twilio_sid, twilio_token)
                )
                if resp.status_code == 200:
                    health_status["checks"]["twilio"] = "ok"
                else:
                    health_status["checks"]["twilio"] = f"degraded (status: {resp.status_code})"
                    health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["twilio"] = f"error: {type(e).__name__}"
            health_status["status"] = "degraded"
    else:
        health_status["checks"]["twilio"] = "not configured"

    # Check Supabase connectivity (if configured)
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if supabase_url and supabase_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{supabase_url}/rest/v1/",
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}"
                    }
                )
                # Supabase returns 200 even for empty result
                if resp.status_code in [200, 404]:
                    health_status["checks"]["supabase"] = "ok"
                else:
                    health_status["checks"]["supabase"] = f"degraded (status: {resp.status_code})"
        except Exception as e:
            health_status["checks"]["supabase"] = f"error: {type(e).__name__}"
    else:
        health_status["checks"]["supabase"] = "not configured"

    return health_status

# Note: POST /voice_fallback and POST /call_status_callback are handled by inbound_router
# This GET is kept for backwards compatibility

@app.get("/voice_fallback")
async def voice_fallback_get():
    """
    Fallback endpoint for Twilio if main endpoint fails (GET version)
    Returns TwiML with apology message
    """
    from fastapi.responses import Response

    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">We apologize, but we're experiencing technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>'''

    return Response(content=twiml, media_type="application/xml")

logger.info("🚀 Ruthie AI Voice Bot API Server ready!")
logger.info("   - Browser WebSocket: /ws")
logger.info("   - Inbound Calls: /inbound_call")
logger.info("   - Outbound Calls: /api/calls/outbound")
logger.info("   - Health Check: /health")
