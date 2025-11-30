"""
Conversation Context Tracking for Ruthie AI
Enables dynamic, adaptive conversations with sentiment detection and context awareness.

Based on industry best practices from:
- Perplexity Voice conversational patterns
- ElevenLabs Conversational AI framework
- Adaptive Conversational Interaction Dynamics (ACID) framework
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    Tracks conversation state, user sentiment, and enables adaptive responses.
    """
    
    def __init__(self, session_id: str, max_history: int = 50):
        self.session_id = session_id
        self.history = deque(maxlen=max_history)  # Auto-truncate old history
        self.user_sentiment = "neutral"
        self.topic_stack = []
        self.clarification_count = 0
        self.retry_count = 0
        self.created_at = datetime.utcnow()
        self.last_user_speech_time = None
        self.silence_count = 0
        
    def add_turn(self, role: str, content: str):
        """
        Add conversation turn and analyze sentiment.
        
        Args:
            role: "user", "assistant", or "function"
            content: What was said
        """
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.history.append(turn)
        
        # Update last user speech time
        if role == "user":
            self.last_user_speech_time = datetime.utcnow()
            self.silence_count = 0  # Reset silence counter
            
            # Analyze sentiment
            self.user_sentiment = self.detect_sentiment(content)
            
            # Track clarification requests
            if self.is_clarification_request(content):
                self.clarification_count += 1
        
        logger.info(f"[{self.session_id}] {role}: {content[:100]}... (sentiment: {self.user_sentiment})")
    
    def detect_sentiment(self, text: str) -> str:
        """
        Detect user frustration, confusion, or satisfaction.
        
        Returns: "frustrated", "confused", "satisfied", or "neutral"
        """
        text_lower = text.lower()
        
        # Frustration indicators
        frustration_keywords = [
            "frustrated", "annoyed", "angry", "upset", "ridiculous",
            "forget it", "never mind", "this is stupid", "waste of time",
            "not working", "doesn't work", "broken"
        ]
        
        # Confusion indicators
        confusion_keywords = [
            "confused", "don't understand", "what", "huh", "unclear",
            "not sure", "don't get it", "explain", "clarify", "repeat"
        ]
        
        # Satisfaction indicators
        satisfaction_keywords = [
            "great", "perfect", "excellent", "wonderful", "awesome",
            "thank you", "thanks", "appreciate", "helpful", "good"
        ]
        
        if any(kw in text_lower for kw in frustration_keywords):
            return "frustrated"
        elif any(kw in text_lower for kw in confusion_keywords):
            return "confused"
        elif any(kw in text_lower for kw in satisfaction_keywords):
            return "satisfied"
        
        return "neutral"
    
    def is_clarification_request(self, text: str) -> bool:
        """Check if user is asking for clarification."""
        clarification_patterns = [
            "what", "huh", "repeat", "again", "didn't catch",
            "didn't hear", "pardon", "sorry", "unclear"
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in clarification_patterns)
    
    def get_adaptive_prompt_suffix(self) -> str:
        """
        Return dynamic instructions based on conversation state.
        This gets appended to the system prompt for adaptive behavior.
        """
        suffixes = []
        
        # Sentiment-based adaptations
        if self.user_sentiment == "frustrated":
            suffixes.append(
                "\n\n🚨 USER IS FRUSTRATED. Be extra empathetic, apologize sincerely, "
                "slow down, and offer to transfer to a human team member."
            )
        elif self.user_sentiment == "confused":
            suffixes.append(
                "\n\n🤔 USER IS CONFUSED. Slow down, use simpler language, "
                "break down information into smaller steps, and offer to repeat."
            )
        elif self.user_sentiment == "satisfied":
            suffixes.append(
                "\n\n😊 USER IS SATISFIED. Maintain positive energy, "
                "be efficient, and ask if there's anything else you can help with."
            )
        
        # Clarification count threshold
        if self.clarification_count >= 3:
            suffixes.append(
                "\n\n⚠️ USER HAS ASKED FOR CLARIFICATION 3+ TIMES. "
                "Offer to transfer to a human team member who can help better."
            )
        
        # Retry count threshold
        if self.retry_count >= 3:
            suffixes.append(
                "\n\n⚠️ USER HAS RETRIED 3+ TIMES. "
                "Something isn't working. Offer alternative approach or human transfer."
            )
        
        return ''.join(suffixes)
    
    def get_silence_duration(self) -> Optional[float]:
        """
        Get duration of current silence in seconds.
        Returns None if user hasn't spoken yet.
        """
        if not self.last_user_speech_time:
            return None
        
        return (datetime.utcnow() - self.last_user_speech_time).total_seconds()
    
    def should_check_presence(self) -> bool:
        """
        Check if we should verify call presence (6+ seconds of silence).
        """
        silence_duration = self.get_silence_duration()
        return silence_duration is not None and silence_duration >= 6.0
    
    def get_silence_response(self) -> Optional[str]:
        """
        Get appropriate response based on silence duration.
        Returns None if no response needed.
        """
        silence_duration = self.get_silence_duration()
        
        if silence_duration is None:
            return None
        
        # Graduated silence responses
        if silence_duration >= 18 and self.silence_count < 3:
            self.silence_count = 3
            return "I haven't heard from you in a while. Let me connect you with our team. One moment please."
        
        elif silence_duration >= 12 and self.silence_count < 2:
            self.silence_count = 2
            return "Take your time. I'll wait for you to respond."
        
        elif silence_duration >= 6 and self.silence_count < 1:
            self.silence_count = 1
            return "Are you still there? I'm here to help."
        
        return None
    
    def increment_retry(self):
        """Increment retry counter (for failed validations, etc.)"""
        self.retry_count += 1
    
    def reset_retry(self):
        """Reset retry counter (when user succeeds)"""
        self.retry_count = 0
    
    def get_conversation_summary(self, max_turns: int = 10) -> str:
        """
        Get a summary of recent conversation for context.
        Useful for maintaining context across long conversations.
        """
        recent_turns = list(self.history)[-max_turns:]
        
        summary_lines = []
        for turn in recent_turns:
            role = turn['role']
            content = turn['content'][:100]  # Truncate long messages
            summary_lines.append(f"{role}: {content}")
        
        return "\n".join(summary_lines)
    
    def __repr__(self):
        return (
            f"ConversationContext(session={self.session_id}, "
            f"turns={len(self.history)}, sentiment={self.user_sentiment}, "
            f"clarifications={self.clarification_count}, retries={self.retry_count})"
        )


# Global context storage (in production, use Redis)
_contexts: Dict[str, ConversationContext] = {}


def get_context(session_id: str) -> ConversationContext:
    """Get or create conversation context for a session."""
    if session_id not in _contexts:
        _contexts[session_id] = ConversationContext(session_id)
        logger.info(f"Created new conversation context for {session_id}")
    return _contexts[session_id]


def clear_context(session_id: str):
    """Clear conversation context after call ends."""
    if session_id in _contexts:
        del _contexts[session_id]
        logger.info(f"Cleared conversation context for {session_id}")


def get_all_active_contexts() -> List[ConversationContext]:
    """Get all active conversation contexts."""
    return list(_contexts.values())
