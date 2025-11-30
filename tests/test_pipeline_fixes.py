#!/usr/bin/env python3
"""
Quick Verification Script for Ruthie AI Pipeline Fixes
Tests that function descriptions don't contain TTS-hostile language.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.function_definitions import FUNCTION_DEFINITIONS


def test_function_descriptions():
    """Test that function descriptions are TTS-safe."""
    print("\n" + "=" * 80)
    print("FUNCTION DESCRIPTION TTS SAFETY TEST")
    print("=" * 80)
    
    # Forbidden phrases that should NOT appear in descriptions
    forbidden_phrases = [
        "Call this FIRST",
        "Call this AFTER",
        "tells you to",
        "stores the",
        "This starts the",
        "asks for their",
    ]
    
    violations = []
    passed = 0
    
    for func in FUNCTION_DEFINITIONS:
        name = func["name"]
        description = func["description"]
        
        # Check for forbidden phrases
        found_violations = []
        for phrase in forbidden_phrases:
            if phrase.lower() in description.lower():
                found_violations.append(phrase)
        
        if found_violations:
            violations.append({
                "function": name,
                "description": description,
                "violations": found_violations
            })
            print(f"\n❌ FAILED: {name}")
            print(f"   Description: {description[:100]}...")
            print(f"   Violations: {', '.join(found_violations)}")
        else:
            passed += 1
            print(f"\n✅ PASSED: {name}")
            print(f"   Description: {description[:80]}...")
    
    print(f"\n{'=' * 80}")
    print(f"Results: {passed} passed, {len(violations)} failed")
    
    if violations:
        print(f"\n⚠️  VIOLATIONS FOUND:")
        for v in violations:
            print(f"  - {v['function']}: {v['violations']}")
        return False
    else:
        print(f"\n🎉 ALL FUNCTION DESCRIPTIONS ARE TTS-SAFE!")
        return True


def test_intent_parameters():
    """Test that all initiate_* functions have user_intent parameter."""
    print("\n" + "=" * 80)
    print("INTENT PARAMETER TEST")
    print("=" * 80)
    
    initiate_functions = [f for f in FUNCTION_DEFINITIONS if f["name"].startswith("initiate_")]
    
    passed = 0
    failed = 0
    
    for func in initiate_functions:
        name = func["name"]
        params = func["parameters"]["properties"]
        required = func["parameters"]["required"]
        
        if "user_intent" in params and "user_intent" in required:
            print(f"\n✅ PASSED: {name} has required user_intent parameter")
            passed += 1
        else:
            print(f"\n❌ FAILED: {name} missing user_intent parameter")
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"Results: {passed} passed, {failed} failed")
    
    return failed == 0


def test_function_count():
    """Test that we have all expected functions."""
    print("\n" + "=" * 80)
    print("FUNCTION COUNT TEST")
    print("=" * 80)
    
    expected_functions = {
        "booking": 10,
        "reschedule": 5,
        "cancel": 3,
        "email": 5,
        "sms": 4,
        "whatsapp": 4,
        "simple": 4,
    }
    
    from app.function_definitions import FUNCTION_FLOWS
    
    actual_counts = {}
    for func_name, flow in FUNCTION_FLOWS.items():
        actual_counts[flow] = actual_counts.get(flow, 0) + 1
    
    all_passed = True
    for flow, expected_count in expected_functions.items():
        actual_count = actual_counts.get(flow, 0)
        if actual_count == expected_count:
            print(f"✅ {flow}: {actual_count}/{expected_count}")
        else:
            print(f"❌ {flow}: {actual_count}/{expected_count}")
            all_passed = False
    
    print(f"\nTotal functions: {len(FUNCTION_DEFINITIONS)}")
    
    return all_passed


def main():
    """Run all verification tests."""
    print("\n" + "=" * 80)
    print("RUTHIE AI PIPELINE FIXES - VERIFICATION SUITE")
    print("=" * 80)
    
    results = {
        "TTS Safety": test_function_descriptions(),
        "Intent Parameters": test_intent_parameters(),
        "Function Count": test_function_count(),
    }
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL VERIFICATION TESTS PASSED! Pipeline fixes are ready for deployment.")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
