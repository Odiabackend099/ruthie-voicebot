#!/usr/bin/env python3
"""
Test Suite for Ruthie AI Conversational Fixes
Tests TTS sanitization, phone validation, and conversation context.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tts_sanitizer import sanitize_for_tts, validate_template_variables
from app.phone_validator import validate_phone_number, format_phone_for_speech
from app.conversation_context import ConversationContext


def test_tts_sanitization():
    """Test TTS sanitization removes forbidden patterns."""
    print("\n" + "=" * 80)
    print("TEST 1: TTS SANITIZATION")
    print("=" * 80)
    
    test_cases = [
        # Function names
        ("Let me call initiate_booking for you", "Function name removal"),
        ("I'll use collect_client_name to get that", "Collector function removal"),
        ("Executing confirm_and_book now", "Confirm function removal"),
        
        # Template variables
        ("{client_name} is confirmed for {booking_date}", "Template variable removal"),
        ("Hello [user], your appointment is at <time>", "Bracket removal"),
        
        # Technical terms
        ("The N8N webhook failed with error code 422", "Technical jargon"),
        ("Let me query the database via REST API", "API references"),
        ("I'll send this to the CRM endpoint", "CRM/endpoint removal"),
        
        # Phone numbers
        ("+1-800-555-1234", "International phone formatting"),
        ("(952) 333-8443", "US phone with area code"),
        ("8141995397", "10-digit plain phone"),
        
        # Emails
        ("Contact support@callwaitingai.dev", "Email formatting"),
        ("Reach me at john.doe@company.com", "Email with dots"),
    ]
    
    passed = 0
    failed = 0
    
    for text, description in test_cases:
        result = sanitize_for_tts(text)
        
        # Check if forbidden patterns were removed
        forbidden_found = any(
            pattern in result.lower() 
            for pattern in ['initiate_', 'collect_', 'confirm_and_', 'n8n', 'webhook', 'api', '{', '[', '<']
        )
        
        if forbidden_found:
            print(f"\n❌ FAILED: {description}")
            print(f"   Input:  {text}")
            print(f"   Output: {result}")
            print(f"   Issue:  Forbidden pattern still present")
            failed += 1
        else:
            print(f"\n✅ PASSED: {description}")
            print(f"   Input:  {text}")
            print(f"   Output: {result}")
            passed += 1
    
    print(f"\n{'=' * 80}")
    print(f"TTS Sanitization: {passed} passed, {failed} failed")
    return failed == 0


def test_phone_validation():
    """Test phone number validation and formatting."""
    print("\n" + "=" * 80)
    print("TEST 2: PHONE NUMBER VALIDATION")
    print("=" * 80)
    
    test_cases = [
        ("+2348141995397", True, "Valid Nigerian"),
        ("08141995397", True, "Nigerian without country code"),
        ("+1-800-555-1234", True, "Valid US with formatting"),
        ("(952) 333-8443", True, "US with area code"),
        ("8141995397", True, "10 digits, no country code"),
        ("+44 20 7946 0958", True, "UK with formatting"),
        ("invalid", False, "Invalid text"),
        ("123", False, "Too short"),
        ("+234 814 199 5397", True, "Nigerian with spaces"),
    ]
    
    passed = 0
    failed = 0
    
    for phone, should_be_valid, description in test_cases:
        result = validate_phone_number(phone)
        
        if result['valid'] == should_be_valid:
            print(f"\n✅ PASSED: {description}")
            print(f"   Input: {phone}")
            if result['valid']:
                print(f"   Formatted: {result['formatted']}")
                print(f"   Spoken: {result['spoken']}")
            else:
                print(f"   Error: {result['error']}")
            passed += 1
        else:
            print(f"\n❌ FAILED: {description}")
            print(f"   Input: {phone}")
            print(f"   Expected valid: {should_be_valid}, Got: {result['valid']}")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"Phone Validation: {passed} passed, {failed} failed")
    return failed == 0


def test_conversation_context():
    """Test conversation context tracking and sentiment detection."""
    print("\n" + "=" * 80)
    print("TEST 3: CONVERSATION CONTEXT")
    print("=" * 80)
    
    context = ConversationContext("test_session_123")
    
    test_cases = [
        ("I want to book an appointment", "neutral", "Neutral request"),
        ("This is frustrating, it's not working", "frustrated", "Frustrated user"),
        ("I don't understand what you're asking", "confused", "Confused user"),
        ("Great! That's perfect, thank you", "satisfied", "Satisfied user"),
        ("What? I didn't catch that", "confused", "Clarification request"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_sentiment, description in test_cases:
        context.add_turn("user", text)
        
        if context.user_sentiment == expected_sentiment:
            print(f"\n✅ PASSED: {description}")
            print(f"   Input: {text}")
            print(f"   Detected: {context.user_sentiment}")
            passed += 1
        else:
            print(f"\n❌ FAILED: {description}")
            print(f"   Input: {text}")
            print(f"   Expected: {expected_sentiment}, Got: {context.user_sentiment}")
            failed += 1
    
    # Test adaptive prompt suffix
    print(f"\n📋 Adaptive Prompt Suffix:")
    suffix = context.get_adaptive_prompt_suffix()
    if suffix:
        print(suffix)
    else:
        print("   (No special adaptations needed)")
    
    print(f"\n{'=' * 80}")
    print(f"Conversation Context: {passed} passed, {failed} failed")
    return failed == 0


def test_silence_detection():
    """Test silence detection and graduated responses."""
    print("\n" + "=" * 80)
    print("TEST 4: SILENCE DETECTION")
    print("=" * 80)
    
    from datetime import datetime, timedelta
    
    context = ConversationContext("test_session_456")
    
    # Simulate user speech
    context.last_user_speech_time = datetime.utcnow() - timedelta(seconds=7)
    
    # Test 6-second silence
    response = context.get_silence_response()
    if response and "still there" in response.lower():
        print(f"✅ PASSED: 6-second silence detection")
        print(f"   Response: {response}")
    else:
        print(f"❌ FAILED: 6-second silence detection")
        print(f"   Expected 'still there' response, got: {response}")
        return False
    
    # Simulate 12-second silence
    context.last_user_speech_time = datetime.utcnow() - timedelta(seconds=13)
    response = context.get_silence_response()
    if response and "take your time" in response.lower():
        print(f"\n✅ PASSED: 12-second silence detection")
        print(f"   Response: {response}")
    else:
        print(f"\n❌ FAILED: 12-second silence detection")
        print(f"   Expected 'take your time' response, got: {response}")
        return False
    
    # Simulate 18-second silence
    context.last_user_speech_time = datetime.utcnow() - timedelta(seconds=19)
    response = context.get_silence_response()
    if response and "connect you" in response.lower():
        print(f"\n✅ PASSED: 18-second silence detection")
        print(f"   Response: {response}")
    else:
        print(f"\n❌ FAILED: 18-second silence detection")
        print(f"   Expected 'connect you' response, got: {response}")
        return False
    
    print(f"\n{'=' * 80}")
    print(f"Silence Detection: All tests passed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("RUTHIE AI CONVERSATIONAL FIXES - TEST SUITE")
    print("=" * 80)
    
    results = {
        "TTS Sanitization": test_tts_sanitization(),
        "Phone Validation": test_phone_validation(),
        "Conversation Context": test_conversation_context(),
        "Silence Detection": test_silence_detection(),
    }
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Ruthie AI is ready for deployment.")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
