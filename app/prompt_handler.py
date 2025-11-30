import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default prompt fallback
DEFAULT_PROMPT = """You are Ruthie, a helpful and friendly AI voice assistant for Callwaiting AI.
You help customers with inquiries, book appointments, and provide information about Callwaiting AI's products.
Keep your responses concise (1-2 sentences) and conversational.
Be warm, professional, and efficient."""

def get_system_prompt():
    """
    Reads and returns the system prompt from the system_prompt_v2.md file.
    Uses absolute path relative to this file to work correctly in all environments.
    If the file doesn't exist, returns a default prompt.
    """
    # Use absolute path relative to this file's location
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Try v2 first (enhanced prompt), fallback to v1, then default
    prompt_files = [
        current_dir / "system_prompt_v2.md",
        current_dir / "system_prompt.md"
    ]
    
    for prompt_file in prompt_files:
        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as file:
                    prompt = file.read().strip()
                    logger.info(f"Loaded system prompt from {prompt_file} ({len(prompt)} chars)")
                    return prompt
            except Exception as e:
                logger.error(f"Error reading system prompt from {prompt_file}: {e}")
                continue
    
    logger.warning(f"No system prompt files found, using default")
    return DEFAULT_PROMPT

def update_system_prompt(new_prompt):
    """
    Updates the system_prompt.md file with a new prompt.

    Args:
    new_prompt (str): The new system prompt to be written to the file.
    """
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    prompt_file = current_dir / "system_prompt.md"

    try:
        with open(prompt_file, "w", encoding="utf-8") as file:
            file.write(new_prompt)
        logger.info(f"Updated system prompt at {prompt_file}")
    except Exception as e:
        logger.error(f"Error updating system prompt: {e}")
        raise

# Additional functions can be added here as needed for prompt handling
