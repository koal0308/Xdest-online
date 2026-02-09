#!/bin/bash
# Quick Test Script für AEra Chat Server

echo "🧪 Testing AEra Chat Server..."
echo ""

# Check if server is running
echo "1. Health Check..."
HEALTH=$(curl -s http://localhost:8850/health)
if [ $? -eq 0 ]; then
    echo "✅ Server is running"
    echo "$HEALTH" | python3 -m json.tool
else
    echo "❌ Server is not running"
    echo "   Start with: ./start.sh"
    exit 1
fi

echo ""
echo "2. Testing Chat Endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8850/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Was ist AEraLogIn?"}')

if [ $? -eq 0 ]; then
    echo "✅ Chat endpoint working"
    echo "$RESPONSE" | python3 -m json.tool
else
    echo "❌ Chat endpoint failed"
    exit 1
fi

echo ""
echo "✅ All tests passed!"
echo ""
echo "🌀 AEra Chat Server is ready!"
echo "   API: http://localhost:8850/api/chat"
echo "   Docs: http://localhost:8850/docs"
