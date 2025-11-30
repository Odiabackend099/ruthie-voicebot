"""
Groq Chat Handler for Ruthie AI Text Chat Widget
Uses Groq's LLM API directly for text-to-text conversations.
Integrates with knowledge base for verified information.
"""

import os
import sys
import json
import logging
import httpx
import re
from typing import AsyncGenerator, List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Groq API configuration
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Knowledge base paths - ONLY use the voice-bot/knowledge_base directory
# This contains the Callwaiting AI / Ruthie knowledge base (NOT the old ODIADEV/Sam one)
KB_PATHS = [
    Path(__file__).parent.parent / "knowledge_base",  # /app/knowledge_base in Docker & local
]


def find_knowledge_base() -> Optional[Path]:
    """Find the knowledge base file in possible locations."""
    for kb_dir in KB_PATHS:
        kb_path = kb_dir / "knowledge_base.txt"
        if kb_path.exists():
            return kb_path
    return None


class KnowledgeBaseIntegration:
    """Integrates with the company knowledge base for verified information."""

    def __init__(self):
        self.kb_content = ""
        self.kb_loaded = False
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Load the knowledge base file from available locations."""
        try:
            kb_path = find_knowledge_base()
            if kb_path:
                with open(kb_path, 'r', encoding='utf-8') as f:
                    self.kb_content = f.read()
                self.kb_loaded = True
                logger.info(f"✅ Knowledge base loaded from {kb_path}: {len(self.kb_content)} characters")
            else:
                logger.warning(f"⚠️ Knowledge base not found in any location: {KB_PATHS}")
        except Exception as e:
            logger.error(f"❌ Error loading knowledge base: {e}")

    def search(self, query: str) -> Optional[str]:
        """
        Search the knowledge base for relevant information.
        Returns context to inject into the prompt, or None if not found.
        """
        if not self.kb_loaded:
            return None

        query_lower = query.lower()
        relevant_sections = []

        # Keywords to look for
        keywords_found = []

        # Check for product-related queries
        if any(word in query_lower for word in ['adaqua', 'product', 'service', 'offering']):
            keywords_found.append('ADAQUA AI')
        if any(word in query_lower for word in ['cross ai', 'emergency', 'dispatch', '911']):
            keywords_found.append('CROSS AI')
        if any(word in query_lower for word in ['miss legal', 'legal', 'law firm', 'lawyer']):
            keywords_found.append('MISS LEGAL AI')

        # Check for pricing queries
        if any(word in query_lower for word in ['price', 'pricing', 'cost', 'how much', 'fee', 'charge', 'plan']):
            keywords_found.append('Pricing')

        # Check for contact queries
        if any(word in query_lower for word in ['contact', 'email', 'phone', 'call', 'reach']):
            keywords_found.append('CONTACT INFORMATION')

        # Check for team/leadership queries
        if any(word in query_lower for word in ['ceo', 'founder', 'team', 'leadership', 'who', 'austyn', 'peter', 'benjamin']):
            keywords_found.append('LEADERSHIP TEAM')

        # Check for company info
        if any(word in query_lower for word in ['company', 'odiadev', 'about', 'registration', 'cac', 'tin']):
            keywords_found.append('COMPANY IDENTITY')

        # Check for achievements/stats
        if any(word in query_lower for word in ['achievement', 'statistic', 'uptime', 'client', 'customer']):
            keywords_found.append('COMPANY ACHIEVEMENTS')

        # Check for language support
        if any(word in query_lower for word in ['language', 'yoruba', 'igbo', 'hausa', 'pidgin', 'english']):
            keywords_found.append('LANGUAGES SUPPORTED')

        # Check for SLA/support
        if any(word in query_lower for word in ['sla', 'uptime', 'support', 'guarantee', 'tier']):
            keywords_found.append('SERVICE LEVEL AGREEMENTS')

        # Extract relevant sections from knowledge base
        if keywords_found:
            lines = self.kb_content.split('\n')
            for keyword in keywords_found:
                in_section = False
                section_content = []
                for line in lines:
                    if keyword.upper() in line.upper() or keyword in line:
                        in_section = True
                        section_content = [line]
                    elif in_section:
                        if line.strip() and (line.startswith('---') or (line.isupper() and len(line) > 3)):
                            break
                        section_content.append(line)

                if section_content:
                    relevant_sections.extend(section_content[:30])  # Limit per section

        if relevant_sections:
            context = '\n'.join(relevant_sections[:100])  # Limit total context
            return f"""
[VERIFIED KNOWLEDGE BASE INFORMATION - Use this to answer accurately]
{context}
[END OF KNOWLEDGE BASE]

IMPORTANT: Only use the information above. If the user's question cannot be answered from this knowledge base, say "I don't have that specific information. Please contact sales@odia.dev for details."
"""

        return None

    def get_full_context(self) -> str:
        """Get the full knowledge base for comprehensive context."""
        if self.kb_loaded:
            return f"""
[COMPLETE COMPANY KNOWLEDGE BASE - Reference for accurate responses]
{self.kb_content}
[END OF KNOWLEDGE BASE]
"""
        return ""


class GroqChatHandler:
    """Handles text chat conversations using Groq API with knowledge base integration."""

    def __init__(self, system_prompt: str):
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment")

        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, str]] = []
        self.client = httpx.AsyncClient(timeout=30.0)
        self.knowledge_base = KnowledgeBaseIntegration()

        # Add knowledge base context to system prompt
        if self.knowledge_base.kb_loaded:
            kb_context = self.knowledge_base.get_full_context()
            self.system_prompt = f"{self.system_prompt}\n\n{kb_context}"
            logger.info("📚 Knowledge base integrated into system prompt")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Build the messages array for the API request."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add conversation history (keep last 10 exchanges to manage context)
        messages.extend(self.conversation_history[-20:])

        # Search knowledge base for relevant context
        kb_context = self.knowledge_base.search(user_message)
        if kb_context:
            # Inject knowledge base context before user message
            user_message_with_context = f"{kb_context}\n\nUser Question: {user_message}"
            messages.append({"role": "user", "content": user_message_with_context})
        else:
            messages.append({"role": "user", "content": user_message})

        return messages

    async def get_response(self, user_message: str) -> str:
        """
        Get a response from Groq for the given user message.
        Returns the complete response text.
        """
        messages = self._build_messages(user_message)

        try:
            response = await self.client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.3,  # Lower temperature for more factual responses
                    "max_tokens": 500,
                    "stream": False,
                },
            )

            response.raise_for_status()
            data = response.json()

            assistant_message = data["choices"][0]["message"]["content"]

            # Update conversation history (store original user message)
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})

            logger.info(f"Groq response: {assistant_message[:100]}...")
            return assistant_message

        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            return "I'm having trouble processing that right now. Please try again."
        except Exception as e:
            logger.error(f"Groq chat error: {e}", exc_info=True)
            return "Something went wrong. Please try again."

    async def get_streaming_response(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Get a streaming response from Groq for the given user message.
        Yields text chunks as they arrive.
        """
        messages = self._build_messages(user_message)
        full_response = ""

        try:
            async with self.client.stream(
                "POST",
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.3,  # Lower temperature for more factual responses
                    "max_tokens": 500,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_response += content
                                yield content
                        except json.JSONDecodeError:
                            continue

                # Update conversation history after complete response
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": full_response})

        except httpx.HTTPStatusError as e:
            logger.error(f"Groq streaming error: {e.response.status_code}")
            yield "I'm having trouble processing that right now. Please try again."
        except Exception as e:
            logger.error(f"Groq streaming error: {e}", exc_info=True)
            yield "Something went wrong. Please try again."

    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")
