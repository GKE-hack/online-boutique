#!/usr/bin/env python3
"""
Test script for the chatbot service integration
This script tests the chatbot service API endpoints and basic functionality
"""

import json
import requests
import sys
import time
from typing import Dict, Any

def test_health_endpoint(base_url: str) -> bool:
    """Test the health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed with error: {e}")
        return False

def test_chat_endpoint(base_url: str, message: str, history: list = None) -> Dict[str, Any]:
    """Test the chat endpoint"""
    try:
        payload = {
            "message": message,
            "history": history or []
        }
        
        response = requests.post(
            f"{base_url}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat response received")
            print(f"   Message: {message}")
            print(f"   Response: {data.get('response', 'N/A')}")
            print(f"   Recommended products: {data.get('recommended_products', [])}")
            print(f"   Products considered: {data.get('total_products_considered', 0)}")
            return data
        else:
            print(f"❌ Chat request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return {}
    except Exception as e:
        print(f"❌ Chat request failed with error: {e}")
        return {}

def test_frontend_integration(frontend_url: str, message: str) -> bool:
    """Test the frontend bot endpoint"""
    try:
        payload = {
            "message": message,
            "history": []
        }
        
        response = requests.post(
            f"{frontend_url}/bot",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Frontend integration test passed")
            print(f"   Message: {message}")
            print(f"   Response: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ Frontend integration test failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Frontend integration test failed with error: {e}")
        return False

def main():
    """Main test function"""
    print("🤖 Testing Chatbot Service Integration")
    print("=" * 50)
    
    # Configuration
    chatbot_service_url = "http://localhost:8080"  # Change this to your chatbot service URL
    frontend_service_url = "http://localhost:8080"  # Change this to your frontend service URL
    
    # Check if custom URLs are provided
    if len(sys.argv) > 1:
        chatbot_service_url = sys.argv[1]
    if len(sys.argv) > 2:
        frontend_service_url = sys.argv[2]
    
    print(f"Chatbot Service URL: {chatbot_service_url}")
    print(f"Frontend Service URL: {frontend_service_url}")
    print()
    
    # Test 1: Health Check
    print("🔍 Test 1: Health Check")
    health_ok = test_health_endpoint(chatbot_service_url)
    print()
    
    if not health_ok:
        print("❌ Health check failed. Please ensure the chatbot service is running.")
        return 1
    
    # Test 2: Basic Chat Functionality
    print("🔍 Test 2: Basic Chat Functionality")
    test_messages = [
        "Hello, what products do you have?",
        "I'm looking for something for my kitchen",
        "What accessories do you sell?",
        "Show me items under $20",
        "I need something for a summer party"
    ]
    
    conversation_history = []
    for i, message in enumerate(test_messages, 1):
        print(f"\n   Test 2.{i}:")
        response = test_chat_endpoint(chatbot_service_url, message, conversation_history)
        if response:
            conversation_history.append(f"User: {message}")
            conversation_history.append(f"Assistant: {response.get('response', '')}")
        time.sleep(1)  # Brief pause between requests
    
    print()
    
    # Test 3: Frontend Integration (if different URL)
    if frontend_service_url != chatbot_service_url:
        print("🔍 Test 3: Frontend Integration")
        test_frontend_integration(frontend_service_url, "Test message from frontend")
        print()
    
    # Test 4: Edge Cases
    print("🔍 Test 4: Edge Cases")
    edge_cases = [
        "",  # Empty message
        "What is the meaning of life?",  # Non-product related
        "×" * 1000,  # Very long message
    ]
    
    for i, message in enumerate(edge_cases, 1):
        print(f"\n   Test 4.{i}: Testing edge case")
        if message == "":
            print("   Testing empty message...")
        elif len(message) > 100:
            print("   Testing very long message...")
        else:
            print(f"   Testing: {message}")
        
        response = test_chat_endpoint(chatbot_service_url, message)
        time.sleep(0.5)
    
    print()
    print("✅ Integration tests completed!")
    print("\n📋 Next Steps:")
    print("1. Deploy the services to your Kubernetes cluster")
    print("2. Update the ConfigMap with your Google Cloud Project ID")
    print("3. Ensure Vertex AI is enabled in your project")
    print("4. Test the integration in your live environment")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 