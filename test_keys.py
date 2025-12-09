#!/usr/bin/env python3
"""
Simple test for API keys
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('conf.env')

print("🔍 Testing CyberCyte API Key Configuration")
print("=" * 50)

openai_key = os.getenv('OPENAI_API_KEY')
gemini_key = os.getenv('GEMINI_API_KEY')

print(f"OpenAI API Key: {'SET' if openai_key else 'NOT SET'}")
if openai_key:
    print(f"  Key starts with: {openai_key[:15]}...")
    print(f"  Key length: {len(openai_key)}")

print(f"Gemini API Key: {'SET' if gemini_key else 'NOT SET'}")
if gemini_key:
    print(f"  Key starts with: {gemini_key[:15]}...")
    print(f"  Key length: {len(gemini_key)}")

print("\n✅ API Key Configuration Check Complete!")

# Test basic connectivity
print("\n🌐 Testing basic connectivity...")
try:
    import requests
    response = requests.get('https://httpbin.org/status/200', timeout=5)
    print(f"HTTP connectivity: {'✅ OK' if response.status_code == 200 else '❌ FAILED'}")
except Exception as e:
    print(f"HTTP connectivity: ❌ FAILED - {e}")