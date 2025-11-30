import os
import logging
from dotenv import load_dotenv
from app.prompt_handler import get_system_prompt
from app.function_definitions import FUNCTION_DEFINITIONS

logger = logging.getLogger(__name__)

# Load environment variables from .env.local in the parent directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env.local')
load_dotenv(env_path)

# Validate GROQ_API_KEY exists (without exposing it)
if not os.environ.get('GROQ_API_KEY'):
    logger.warning("GROQ_API_KEY not found in environment variables")

# Load the comprehensive system prompt
SYSTEM_PROMPT = get_system_prompt()
logger.info(f"Agent config loaded system prompt ({len(SYSTEM_PROMPT)} characters)")
logger.info(f"Agent config loaded {len(FUNCTION_DEFINITIONS)} function definitions")

AGENT_SETTINGS = {
    "type": "Settings",
    "audio": {
        "input": {
            "encoding": "linear16",
            "sample_rate": 16000,
        },
        "output": {
            "encoding": "linear16",
            "sample_rate": 16000,
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
            "prompt": SYSTEM_PROMPT,
            "functions": FUNCTION_DEFINITIONS,
        },
        "speak": {
            "provider": {
                "type": "deepgram",
                "model": "aura-asteria-en",
            },
        },
        # Ruthie greets the user first when they connect
        "greeting": "Hi! I'm Ruthie from Callwaiting AI. How can I help you today?",
    },
}
