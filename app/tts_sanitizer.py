"""
TTS Sanitization Layer for Ruthie AI
Prevents technical artifacts, function names, and code from reaching Text-to-Speech.
Formats phone numbers, emails, and special characters for natural speech.

Based on industry best practices from:
- Google Duplex TTS preprocessing
- Deepgram TTS formatting guidelines
- Bland.ai voice AI implementation patterns
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Forbidden patterns that should NEVER appear in TTS output
FORBIDDEN_PATTERNS = [
    # Function names from function_definitions.py
    r'\binitiate_\w+\b',
    r'\bcollect_\w+\b',
    r'\bconfirm_and_\w+\b',
    r'\bsearch_web\b',
    r'\bget_current_datetime\b',
    r'\bget_location_info\b',
    r'\bsend_email\b',
    r'\bsend_sms\b',
    r'\bsend_whatsapp\b',
    r'\bbook_appointment\b',
    r'\breschedule_appointment\b',
    r'\bcancel_appointment\b',

    # Code syntax
    r'\{[^}]*\}',  # {variable} syntax
    r'\[[^\]]*\]',  # [parameter] syntax
    r'<[^>]*>',     # <tag> syntax
    r'\bfunction\(',  # function( calls
    r'\bawait\s+',    # await keyword
    r'\basync\s+',    # async keyword
    r'\breturn\s+',   # return keyword
    r'\bconst\s+',    # const keyword
    r'\blet\s+',      # let keyword
    r'\bvar\s+',      # var keyword

    # Technical terms
    r'\bN8N\b',
    r'\bn8n\b',
    r'\bwebhook\b',
    r'\bAPI\b',
    r'\bJSON\b',
    r'\bHTTP\b',
    r'\bREST\b',
    r'\berror\s+code\s+\d+',
    r'\bsession\s+state\b',
    r'\bdatabase\b',
    r'\bsupabase\b',
    r'\bCRM\b',
    r'\bendpoint\b',
    r'\bpayload\b',
    r'\brequest\b',
    r'\bresponse\b',
]

# Compile patterns for performance
FORBIDDEN_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in FORBIDDEN_PATTERNS]


def sanitize_for_tts(text: str) -> str:
    """
    Sanitize text before sending to TTS to prevent technical artifacts.

    Args:
        text: Raw text that may contain function names, code, symbols

    Returns:
        Cleaned text safe for TTS
    """
    if not text:
        return ""

    original_text = text

    # Step 1: Remove forbidden patterns
    for regex in FORBIDDEN_REGEX:
        matches = regex.findall(text)
        if matches:
            logger.warning(f"TTS SANITIZATION: Removed forbidden pattern: {matches}")
        text = regex.sub('', text)  # Remove completely, don't replace with [REDACTED]

    # Step 2: Format phone numbers for natural speech
    text = format_phone_numbers_for_speech(text)

    # Step 3: Format email addresses for natural speech
    text = format_emails_for_speech(text)

    # Step 4: Remove special characters that sound bad when spoken
    text = remove_tts_unfriendly_chars(text)

    # Step 5: Clean up excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Step 6: Validate output doesn't contain {braces} or [brackets]
    if '{' in text or '[' in text or '<' in text:
        logger.error(f"TTS SANITIZATION FAILED: Template variables still present: {text}")
        # Replace with safe fallback
        text = text.replace('{', '').replace('}', '').replace('[', '').replace(']', '').replace('<', '').replace('>', '')
        text = re.sub(r'\s+', ' ', text).strip()

    if text != original_text:
        logger.info(f"TTS Sanitized:\n  Before: {original_text}\n  After: {text}")

    return text


def format_phone_numbers_for_speech(text: str) -> str:
    """
    Convert phone numbers to TTS-friendly format.

    Examples:
        +1-800-555-1234 → "country code one, eight hundred, five five five, one two three four"
        (952) 333-8443 → "area code nine five two, three three three, eight four four three"
        8141995397 → "eight one four, one nine nine five three nine seven"

    Based on Google Duplex phone number pronunciation patterns.
    """
    # Pattern: +1-800-555-1234 or +18005551234
    pattern_intl = r'\+(\d{1,3})[-.\s]?(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})'
    def replace_intl(match):
        country, area, first, last = match.groups()
        country_spoken = ', '.join(list(country))
        area_spoken = ', '.join(list(area))
        first_spoken = ', '.join(list(first))
        last_spoken = ', '.join(list(last))
        return f"country code {country_spoken}, {area_spoken}, {first_spoken}, {last_spoken}"

    text = re.sub(pattern_intl, replace_intl, text)

    # Pattern: (952) 333-8443
    pattern_us = r'\((\d{3})\)\s?(\d{3})[-.\s]?(\d{4})'
    def replace_us(match):
        area, first, last = match.groups()
        area_spoken = ', '.join(list(area))
        first_spoken = ', '.join(list(first))
        last_spoken = ', '.join(list(last))
        return f"{area_spoken}, {first_spoken}, {last_spoken}"

    text = re.sub(pattern_us, replace_us, text)

    # Pattern: 10-digit number without formatting
    pattern_plain = r'\b(\d{10})\b'
    def replace_plain(match):
        number = match.group(1)
        area = number[:3]
        first = number[3:6]
        last = number[6:]
        area_spoken = ', '.join(list(area))
        first_spoken = ', '.join(list(first))
        last_spoken = ', '.join(list(last))
        return f"{area_spoken}, {first_spoken}, {last_spoken}"

    text = re.sub(pattern_plain, replace_plain, text)

    # Pattern: 7-digit number (local)
    pattern_local = r'\b(\d{3})[-.\s]?(\d{4})\b'
    def replace_local(match):
        first, last = match.groups()
        first_spoken = ', '.join(list(first))
        last_spoken = ', '.join(list(last))
        return f"{first_spoken}, {last_spoken}"

    text = re.sub(pattern_local, replace_local, text)

    return text


def format_emails_for_speech(text: str) -> str:
    """
    Convert email addresses to TTS-friendly format.

    Example:
        support@callwaitingai.dev → "support at callwaiting A I dot dev"
        john.doe@company.com → "john dot doe at company dot com"
    """
    # Pattern: email@domain.com
    pattern = r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+)\.([a-zA-Z]{2,})\b'

    def replace_email(match):
        local, domain, tld = match.groups()

        # Format local part (replace dots with "dot")
        local_spoken = local.replace('.', ' dot ')

        # Format domain (split camelCase and handle "ai" specially)
        domain_spoken = re.sub(r'([a-z])([A-Z])', r'\1 \2', domain)
        domain_spoken = domain_spoken.replace('ai', 'A I').replace('AI', 'A I')
        domain_spoken = domain_spoken.replace('.', ' dot ')

        return f"{local_spoken} at {domain_spoken} dot {tld}"

    text = re.sub(pattern, replace_email, text)

    return text


def remove_tts_unfriendly_chars(text: str) -> str:
    """
    Remove or replace characters that sound bad when spoken by TTS.
    Based on Deepgram TTS best practices.
    """
    replacements = {
        '#': ' number ',
        '@': ' at ',
        '$': ' dollars ',
        '%': ' percent ',
        '&': ' and ',
        '*': ' ',
        '_': ' ',
        '|': ' ',
        '~': ' ',
        '^': ' ',
        '`': ' ',
        '=': ' equals ',
        '+': ' plus ',
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    # Remove excessive spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def validate_template_variables(template: str, params: Dict[str, Any]) -> str:
    """
    Safely format a template string, ensuring ALL variables are present.
    If any variable is missing, return a safe fallback instead of raw template.

    Args:
        template: Template string with {variable} placeholders
        params: Dictionary of variable values

    Returns:
        Formatted string or safe fallback
    """
    try:
        # First, check if all required variables are present
        required_vars = re.findall(r'\{(\w+)\}', template)
        missing_vars = [var for var in required_vars if var not in params]

        if missing_vars:
            logger.error(f"Template variables missing: {missing_vars}. Template: {template}")
            # Return a generic safe response
            return "I apologize, but I'm having trouble processing that information. Could you please repeat?"

        # All variables present, safe to format
        formatted = template.format(**params)

        # Final validation: no {braces} should remain
        if '{' in formatted or '}' in formatted:
            logger.error(f"Template formatting failed, braces still present: {formatted}")
            return "I'm here to help. What would you like to do next?"

        return formatted

    except KeyError as e:
        logger.error(f"Template formatting KeyError: {e}")
        return "I'm here to help. How can I assist you?"
    except Exception as e:
        logger.error(f"Template formatting error: {e}")
        return "I'm here to help. How can I assist you?"


def test_sanitization():
    """Test the sanitization functions with common cases."""
    test_cases = [
        # Function names
        ("Let me call initiate_booking for you", "Function name removal"),
        ("I'll use collect_client_name to get that", "Collector function removal"),

        # Template variables
        ("{client_name} is confirmed for {booking_date}", "Template variable removal"),
        ("Hello [user], your appointment is at <time>", "Bracket removal"),

        # Phone numbers
        ("+1-800-555-1234", "International phone"),
        ("(952) 333-8443", "US phone with area code"),
        ("8141995397", "10-digit plain phone"),

        # Emails
        ("Contact support@callwaitingai.dev", "Email formatting"),
        ("Reach me at john.doe@company.com", "Email with dots"),

        # Technical terms
        ("The N8N webhook failed with error code 422", "Technical jargon"),
        ("Let me query the database via REST API", "API references"),
    ]

    print("TTS SANITIZATION TEST RESULTS:\n")
    print("=" * 80)

    for text, description in test_cases:
        result = sanitize_for_tts(text)
        print(f"\n{description}:")
        print(f"  Input:  {text}")
        print(f"  Output: {result}")
        print("-" * 80)

    print("\n✅ Sanitization tests complete\n")


if __name__ == "__main__":
    # Run tests when executed directly
    test_sanitization()
