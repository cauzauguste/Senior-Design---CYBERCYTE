#!/usr/bin/env python3
"""
Test script for AI models in CyberCyte
"""
import asyncio
import os
import sys
from asyncio import to_thread
from dotenv import load_dotenv

# Load environment variables
load_dotenv('conf.env')

# Add the backend to path
sys.path.append('backend')

# Import only the specific functions we need
from app.threat_detector import call_gemini, call_openai

async def test_ai_models():
    """Test both AI models with a sample threat."""
    test_prompt = "Analyze this security threat: Port scan detected from IP 192.168.1.100 targeting ports 1-1024 on server 192.168.1.50. Suggest mitigation steps."

    print("🔍 Testing CyberCyte AI Threat Analysis")
    print("=" * 50)

    print("\n🤖 Testing Gemini AI...")
    try:
        gemini_result = await to_thread(call_gemini, test_prompt)
        print(f"Gemini Response: {gemini_result}")
    except Exception as e:
        print(f"Gemini Error: {e}")

    print("\n🧠 Testing OpenAI...")
    try:
        openai_result = await call_openai(test_prompt)
        print(f"OpenAI Response: {openai_result}")
    except Exception as e:
        print(f"OpenAI Error: {e}")

    print("\n✅ AI Model Testing Complete!")

if __name__ == "__main__":
    asyncio.run(test_ai_models())