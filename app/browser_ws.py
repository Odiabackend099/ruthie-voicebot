import os
import json
import base64
import asyncio
import logging
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agent_config import AGENT_SETTINGS
from app.groq_chat import GroqChatHandler
from app.prompt_handler import get_system_prompt
from app.function_handler import handle_function_call

logger = logging.getLogger(__name__)

router = APIRouter()


def get_websockets_connect_kwargs(headers: dict) -> dict:
    """
    Get the correct keyword arguments for websockets.connect() based on library version.
    websockets >= 14.0 uses 'additional_headers' (renamed from extra_headers)
    websockets 10.x-13.x uses 'extra_headers'
    websockets < 10.0 uses 'extra_headers' in different location
    """
    try:
        # Try to detect version
        import websockets.version
        version = websockets.version.version
        major_version = int(version.split('.')[0])
        logger.info(f"Detected websockets version: {version} (major: {major_version})")
        if major_version >= 14:
            return {"additional_headers": headers}
        else:
            return {"extra_headers": headers}
    except Exception as e:
        logger.warning(f"Could not detect websockets version: {e}, using extra_headers")
        # Fall back to extra_headers (works with websockets 10.x-13.x)
        return {"extra_headers": headers}


# ============================================
# TEXT CHAT ENDPOINT (Groq API - No Audio)
# ============================================
@router.websocket("/ws/chat")
async def text_chat_endpoint(websocket: WebSocket):
    """
    Text-only chat endpoint using Groq API directly.
    Used by the ChatWidget component for text conversations.
    No audio processing - pure text-to-text.
    """
    await websocket.accept()
    logger.info("💬 Text chat WebSocket connected")

    # Initialize Groq chat handler with system prompt
    try:
        system_prompt = get_system_prompt()
        groq_handler = GroqChatHandler(system_prompt)
    except Exception as e:
        logger.error(f"Failed to initialize Groq handler: {e}")
        await websocket.send_json({"type": "error", "message": "Failed to initialize chat"})
        await websocket.close()
        return

    # Send welcome message
    await websocket.send_json({"type": "welcome"})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "websocket_start":
                # Signal ready
                await websocket.send_json({"type": "websocket_ready"})
                logger.info("💬 Text chat ready")

            elif msg_type == "websocket_transcript":
                # User sent a text message
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                logger.info(f"💬 User text: {user_text[:100]}...")

                # Get streaming response from Groq
                full_response = ""
                async for chunk in groq_handler.get_streaming_response(user_text):
                    full_response += chunk
                    # Send incremental updates
                    await websocket.send_json({
                        "type": "agent_response",
                        "text": full_response
                    })

                logger.info(f"💬 Ruthie response: {full_response[:100]}...")

            elif msg_type == "clear_history":
                # Clear conversation history
                groq_handler.clear_history()
                await websocket.send_json({"type": "history_cleared"})

    except WebSocketDisconnect:
        logger.info("💬 Text chat disconnected")
    except Exception as e:
        logger.error(f"💬 Text chat error: {e}", exc_info=True)
    finally:
        await groq_handler.close()
        try:
            await websocket.close()
        except Exception:
            pass


# ============================================
# VOICE CHAT ENDPOINT (Deepgram Voice Agent)
# ============================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Browser WebSocket connected")
    
    # Send welcome message to trigger frontend handshake
    await websocket.send_json({"type": "welcome"})

    # Deepgram Voice Agent URL
    deepgram_url = "wss://agent.deepgram.com/v1/agent/converse"
    headers = {
        "Authorization": f"Token {os.environ.get('DEEPGRAM_API_KEY')}"
    }

    try:
        # Get correct kwargs for websockets version (handles both old and new API)
        ws_kwargs = get_websockets_connect_kwargs(headers)
        async with websockets.connect(deepgram_url, **ws_kwargs) as deepgram_ws:
            logger.info("Connected to Deepgram Voice Agent")

            # Send initial settings
            await deepgram_ws.send(json.dumps(AGENT_SETTINGS))
            logger.info("Sent Agent Settings to Deepgram")

            # Wait for SettingsApplied
            while True:
                msg = await deepgram_ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("type") == "SettingsApplied":
                        logger.info("✅ SettingsApplied received from Deepgram")
                        break
                    elif data.get("type") == "Error":
                        logger.error(f"❌ Deepgram Error during setup: {data}")
                        raise Exception(f"Deepgram Error: {data}")
                else:
                    logger.warning(f"Received unexpected binary message during setup: {len(msg)} bytes")

            async def browser_to_deepgram():
                try:
                    while True:
                        data = await websocket.receive_json()
                        
                        if data.get("type") == "websocket_audio":
                            # Decode base64 audio from browser and send raw bytes to Deepgram
                            audio_data = base64.b64decode(data["audio"])
                            logger.debug(f"📤 Sending {len(audio_data)} bytes to Deepgram")
                            try:
                                await deepgram_ws.send(audio_data)
                            except websockets.exceptions.ConnectionClosed as e:
                                logger.error(f"❌ Deepgram connection closed while sending audio: {e}")
                                raise
                            except Exception as e:
                                logger.error(f"❌ Error sending to Deepgram: {e}")
                                raise

                        elif data.get("type") == "websocket_transcript":
                            # TEXT CHAT: Send user text message to Deepgram as InjectUserMessage
                            user_text = data.get("text", "").strip()
                            if user_text:
                                logger.info(f"💬 Chat text input: {user_text[:100]}...")
                                try:
                                    await deepgram_ws.send(json.dumps({
                                        "type": "InjectUserMessage",
                                        "content": user_text
                                    }))
                                except websockets.exceptions.ConnectionClosed as e:
                                    logger.error(f"❌ Deepgram connection closed while sending text: {e}")
                                    raise
                                except Exception as e:
                                    logger.error(f"❌ Error sending text to Deepgram: {e}")
                                    raise

                        elif data.get("type") == "websocket_start":
                            # Signal readiness (optional, but good for protocol)
                            await websocket.send_json({"type": "websocket_ready"})

                        elif data.get("type") == "keepalive":
                            # Frontend keepalive to prevent Deepgram 10s timeout
                            # Send empty bytes to keep the Deepgram connection alive
                            logger.debug("💓 Keepalive received from frontend")
                            try:
                                # Send minimal audio packet to keep Deepgram alive
                                await deepgram_ws.send(b'\x00' * 320)  # 20ms of silence at 16kHz
                            except Exception as e:
                                logger.warning(f"Keepalive forward failed: {e}")

                        elif data.get("type") == "silence_detected":
                            # User has been silent for 6+ seconds - inject prompt
                            duration_ms = data.get("duration_ms", 6000)
                            logger.info(f"🔇 Silence detected ({duration_ms}ms) - injecting confirmation prompt")
                            try:
                                # Inject a system message to prompt the user
                                await deepgram_ws.send(json.dumps({
                                    "type": "InjectAgentMessage",
                                    "content": "Are you still there? I'm here to help whenever you're ready."
                                }))
                            except Exception as e:
                                logger.warning(f"Failed to inject silence prompt: {e}")

                except WebSocketDisconnect:
                    logger.info("Browser disconnected")
                except websockets.exceptions.ConnectionClosed as e:
                    logger.error(f"Deepgram WebSocket closed: code={e.code}, reason={e.reason if hasattr(e, 'reason') else 'N/A'}")
                    raise
                except Exception as e:
                    logger.error(f"Error in browser_to_deepgram: {e}", exc_info=True)
                    raise

            # Generate a session ID for this browser connection
            import uuid
            browser_session_id = f"browser-{uuid.uuid4()}"
            logger.info(f"Browser session started: {browser_session_id}")

            async def deepgram_to_browser():
                try:
                    async for message in deepgram_ws:
                        if isinstance(message, bytes):
                            # Audio from Deepgram -> Browser
                            logger.debug(f"📥 Received audio from Deepgram: {len(message)} bytes")
                            encoded_audio = base64.b64encode(message).decode("utf-8")
                            await websocket.send_json({
                                "type": "websocket_audio",
                                "audio": encoded_audio
                            })
                        else:
                            # JSON message from Deepgram -> Browser
                            logger.info(f"📩 Deepgram message: {message[:200]}")  # Log first 200 chars
                            msg_json = json.loads(message)
                            msg_type = msg_json.get("type")

                            if msg_type == "UserStartedSpeaking":
                                await websocket.send_json({"type": "user_started_speaking"})
                            elif msg_type == "AgentStartedSpeaking":
                                await websocket.send_json({"type": "agent_started_speaking"})
                            elif msg_type == "ConversationText":
                                role = msg_json.get("role")
                                content = msg_json.get("content")
                                if role == "assistant":
                                    await websocket.send_json({
                                        "type": "agent_response",
                                        "text": content
                                    })
                                elif role == "user":
                                    await websocket.send_json({
                                        "type": "websocket_transcript",
                                        "text": content
                                    })
                            elif msg_type == "FunctionCallRequest":
                                # Handle function calls from Deepgram Agent
                                function_name = msg_json.get("function_name") or msg_json.get("name")
                                function_id = msg_json.get("function_call_id") or msg_json.get("id")
                                arguments = msg_json.get("input") or msg_json.get("arguments", {})

                                logger.info(f"🔧 Function call: {function_name}({arguments})")

                                try:
                                    # Execute the function
                                    result = await handle_function_call(
                                        function_name=function_name,
                                        arguments=arguments,
                                        session_id=browser_session_id
                                    )

                                    # Send response back to Deepgram
                                    response = {
                                        "type": "FunctionCallResponse",
                                        "function_call_id": function_id,
                                        "output": json.dumps(result)
                                    }
                                    await deepgram_ws.send(json.dumps(response))
                                    logger.info(f"✅ Function response sent: {result.get('speak', 'no speak')[:50]}...")

                                except Exception as e:
                                    logger.error(f"❌ Function execution error: {e}")
                                    # Send error response
                                    error_response = {
                                        "type": "FunctionCallResponse",
                                        "function_call_id": function_id,
                                        "output": json.dumps({"speak": "I'm sorry, something went wrong. Could you try again?"})
                                    }
                                    await deepgram_ws.send(json.dumps(error_response))

                            elif msg_type == "Error":
                                # Suppress harmless timeout during silence
                                error_code = msg_json.get("code", "")
                                if error_code == "CLIENT_MESSAGE_TIMEOUT":
                                    logger.debug("⏱️ Deepgram timeout (idle - normal)")
                                    # Don't send to frontend, just log and move on
                                else:
                                    # Real error - send to frontend
                                    error_msg = msg_json.get("message", "Unknown error")
                                    logger.error(f"🚨 Deepgram Error: {error_msg}")
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": f"Deepgram error: {error_msg}"
                                    })
                            else:
                                # Pass through other message types
                                logger.debug(f"🔄 Passing through: {msg_type}")
                                await websocket.send_json(msg_json)
                                
                except websockets.exceptions.ConnectionClosed as e:
                    logger.error(f"Deepgram->Browser: Deepgram closed connection: code={e.code}, reason={e.reason if hasattr(e, 'reason') else 'N/A'}")
                    raise
                except Exception as e:
                    logger.error(f"Error in deepgram_to_browser: {e}", exc_info=True)
                    raise

            # Run both tasks concurrently with exception handling
            results = await asyncio.gather(
                browser_to_deepgram(),
                deepgram_to_browser(),
                return_exceptions=True
            )
            # Log any exceptions from the tasks
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = ["browser_to_deepgram", "deepgram_to_browser"][i]
                    logger.error(f"Task {task_name} failed: {result}")

    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception as e:
            logger.debug(f"WebSocket close error (expected): {e}")
