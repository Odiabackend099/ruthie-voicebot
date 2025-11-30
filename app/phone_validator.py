"""
Phone Number Validation Module for Ruthie AI
Validates, formats, and converts phone numbers to E.164 format with spoken pronunciation.

Based on industry best practices from:
- Bland.ai phone number handling
- Retell AI validation patterns
- Google Duplex pronunciation strategies
"""

import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Common country codes and their regions
COUNTRY_CODES = {
    "234": "NG",  # Nigeria
    "1": "US",    # United States/Canada
    "44": "GB",   # United Kingdom
    "91": "IN",   # India
    "254": "KE",  # Kenya
    "27": "ZA",   # South Africa
}


def normalize_phone_input(phone: str) -> str:
    """
    Normalize phone number input by removing common formatting.
    
    Examples:
        "+234 814 199 5397" -> "+2348141995397"
        "(952) 333-8443" -> "9523338443"
        "1-800-555-1234" -> "18005551234"
    """
    # Remove all non-digit characters except leading +
    if phone.startswith('+'):
        return '+' + re.sub(r'\D', '', phone[1:])
    return re.sub(r'\D', '', phone)


def detect_country_code(phone: str) -> Optional[str]:
    """
    Detect country code from phone number.
    Returns country code or None if not detected.
    """
    phone = normalize_phone_input(phone)
    
    # Check if starts with +
    if phone.startswith('+'):
        # Try 3-digit codes first (e.g., +234)
        if len(phone) >= 4 and phone[1:4] in COUNTRY_CODES:
            return phone[1:4]
        # Try 2-digit codes (e.g., +44)
        if len(phone) >= 3 and phone[1:3] in COUNTRY_CODES:
            return phone[1:3]
        # Try 1-digit codes (e.g., +1)
        if len(phone) >= 2 and phone[1:2] in COUNTRY_CODES:
            return phone[1:2]
    
    return None


def validate_phone_number(phone: str, default_country_code: str = "234") -> Dict[str, any]:
    """
    Validate phone number and return validation result.
    
    Args:
        phone: Raw phone number input
        default_country_code: Default country code if not provided (default: 234 for Nigeria)
    
    Returns:
        {
            "valid": bool,
            "formatted": str (E.164 format),
            "spoken": str (digit-by-digit for TTS),
            "country_code": str,
            "error": str (if invalid)
        }
    """
    try:
        normalized = normalize_phone_input(phone)
        
        # Detect country code
        country_code = detect_country_code(normalized)
        
        # If no country code detected, add default
        if not country_code:
            # Handle Nigerian numbers starting with 0 (e.g., 08141995397)
            if len(normalized) == 11 and normalized.startswith('0') and default_country_code == "234":
                # Strip leading 0 and add country code
                normalized = f"+{default_country_code}{normalized[1:]}"
                country_code = default_country_code
            elif len(normalized) == 10:
                # Assume it's a local number, add default country code
                normalized = f"+{default_country_code}{normalized}"
                country_code = default_country_code
            else:
                return {
                    "valid": False,
                    "formatted": phone,
                    "spoken": phone,
                    "country_code": None,
                    "error": "Missing country code. Please include the country code, like plus 2 3 4 for Nigeria."
                }
        
        # Ensure it starts with +
        if not normalized.startswith('+'):
            normalized = '+' + normalized
        
        # Validate length (E.164 format: + followed by 1-15 digits)
        digits_only = normalized[1:]  # Remove +
        if not digits_only.isdigit():
            return {
                "valid": False,
                "formatted": phone,
                "spoken": phone,
                "country_code": country_code,
                "error": "Phone number contains invalid characters."
            }
        
        if len(digits_only) < 10 or len(digits_only) > 15:
            return {
                "valid": False,
                "formatted": phone,
                "spoken": phone,
                "country_code": country_code,
                "error": "Phone number length is invalid. Should be 10-15 digits including country code."
            }
        
        # Format for speech (digit-by-digit with grouping)
        spoken = format_phone_for_speech(normalized)
        
        return {
            "valid": True,
            "formatted": normalized,  # E.164 format
            "spoken": spoken,
            "country_code": country_code,
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Phone validation error: {e}")
        return {
            "valid": False,
            "formatted": phone,
            "spoken": phone,
            "country_code": None,
            "error": "Unable to validate phone number. Please try again."
        }


def format_phone_for_speech(phone: str) -> str:
    """
    Convert phone number to TTS-friendly spoken format.
    
    Examples:
        "+2348141995397" -> "plus 2, 3, 4, 8, 1, 4, 1, 9, 9, 5, 3, 9, 7"
        "+18005551234" -> "plus 1, 8, 0, 0, 5, 5, 5, 1, 2, 3, 4"
    
    Based on Google Duplex pronunciation patterns.
    """
    normalized = normalize_phone_input(phone)
    
    # Remove + for processing
    if normalized.startswith('+'):
        digits = normalized[1:]
        prefix = "plus "
    else:
        digits = normalized
        prefix = ""
    
    # Convert to comma-separated digits for natural speech pauses
    spoken_digits = ', '.join(list(digits))
    
    return f"{prefix}{spoken_digits}"


def test_phone_validation():
    """Test phone number validation with common cases."""
    test_cases = [
        "+2348141995397",      # Valid Nigerian
        "08141995397",         # Nigerian without country code
        "+1-800-555-1234",     # Valid US with formatting
        "(952) 333-8443",      # US with area code
        "8141995397",          # 10 digits, no country code
        "+44 20 7946 0958",    # UK with formatting
        "invalid",             # Invalid
        "123",                 # Too short
        "+234 814 199 5397",   # Nigerian with spaces
    ]
    
    print("PHONE VALIDATION TEST RESULTS:\n")
    print("=" * 80)
    
    for phone in test_cases:
        result = validate_phone_number(phone)
        print(f"\nInput: {phone}")
        print(f"  Valid: {result['valid']}")
        if result['valid']:
            print(f"  Formatted: {result['formatted']}")
            print(f"  Spoken: {result['spoken']}")
            print(f"  Country Code: {result['country_code']}")
        else:
            print(f"  Error: {result['error']}")
        print("-" * 80)
    
    print("\n✅ Phone validation tests complete\n")


if __name__ == "__main__":
    # Run tests when executed directly
    test_phone_validation()
