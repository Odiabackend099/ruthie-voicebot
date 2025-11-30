#!/bin/bash
set -e

echo "🔍 RUTHIE IDENTITY FIX - Deployment Verification & Fix"
echo "=================================================="

# 1. Verify local files are correct
echo ""
echo "Step 1: Verifying local files..."
echo "--------------------------------"

# Check for any "Sam" references (should ONLY be in NEVER rules)
SAM_COUNT=$(grep -r "I'm Sam\|Thanks for calling ODIADEV" app/ knowledge_base/ --exclude="*.pyc" 2>/dev/null | grep -v "NEVER" | grep -v "never say" | grep -v "NOT Sam" | wc -l | tr -d ' ')

if [ "$SAM_COUNT" -gt 0 ]; then
    echo "❌ ERROR: Found $SAM_COUNT 'Sam' references in code (excluding prohibition rules)"
    grep -r "I'm Sam\|Thanks for calling ODIADEV" app/ knowledge_base/ --exclude="*.pyc" 2>/dev/null | grep -v "NEVER" | grep -v "never say" | grep -v "NOT Sam"
    exit 1
else
    echo "✅ Local code verified: No 'Sam' references found (only in prohibition rules)"
fi

# 2. Check greeting configurations
echo ""
echo "Step 2: Checking greeting configurations..."
echo "-------------------------------------------"

INBOUND_GREETING=$(grep '"greeting":' app/inbound_deepgram.py | grep -v "^#" | head -1 | sed 's/.*"greeting": "\(.*\)".*/\1/')
AGENT_GREETING=$(grep '"greeting":' app/agent_config.py | grep -v "^#" | head -1 | sed 's/.*"greeting": "\(.*\)".*/\1/')

echo "Inbound greeting: $INBOUND_GREETING"
echo "Agent greeting: $AGENT_GREETING"

if echo "$INBOUND_GREETING" | grep -q "Ruthie" && echo "$AGENT_GREETING" | grep -q "Ruthie"; then
    echo "✅ Greetings verified: Both contain 'Ruthie'"
else
    echo "❌ ERROR: Greetings don't contain 'Ruthie'"
    exit 1
fi

# 3. Verify system prompt
echo ""
echo "Step 3: Verifying system prompt..."
echo "----------------------------------"

if grep -q "Your name is RUTHIE" app/system_prompt.md 2>/dev/null && grep -q 'never say "I'\''m Sam"' app/system_prompt.md 2>/dev/null; then
    echo "✅ system_prompt.md verified: Contains Ruthie identity and anti-Sam rules"
else
    echo "⚠️  WARNING: system_prompt.md may be missing (this is okay if using knowledge_base.txt only)"
fi

# 4. Verify knowledge base
echo ""
echo "Step 4: Verifying knowledge base..."
echo "-----------------------------------"

if grep -q 'NEVER say "I'\''m Sam"' knowledge_base/knowledge_base.txt 2>/dev/null; then
    echo "✅ knowledge_base.txt verified: Contains anti-Sam rules"
else
    echo "❌ ERROR: knowledge_base.txt missing anti-Sam rules"
    exit 1
fi

# 5. Clear Python cache
echo ""
echo "Step 5: Clearing Python cache..."
echo "--------------------------------"

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Python cache cleared"

# 6. Deploy to Fly.io
echo ""
echo "Step 6: Deploying to Fly.io..."
echo "------------------------------"

~/.fly/bin/flyctl deploy --remote-only

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed"
    exit 1
fi

# 7. Wait for deployment to stabilize
echo ""
echo "Step 7: Waiting for deployment to stabilize..."
echo "----------------------------------------------"
sleep 10

# 8. Verify deployment
echo ""
echo "Step 8: Verifying deployment..."
echo "-------------------------------"

HEALTH_RESPONSE=$(curl -s https://sam-ai-voice-bot-twilight-waterfall-1383.fly.dev/health)
echo "Health check response: $HEALTH_RESPONSE"

if echo "$HEALTH_RESPONSE" | grep -q "Ruthie"; then
    echo "✅ Deployment verified: Service identifies as Ruthie"
else
    echo "⚠️  WARNING: Service name doesn't contain 'Ruthie'"
fi

# 9. Check deployed files on Fly.io
echo ""
echo "Step 9: Verification commands (run manually)..."
echo "-----------------------------------------------"
echo "To verify deployed files on Fly.io, run:"
echo "  ~/.fly/bin/flyctl ssh console --app sam-ai-voice-bot-twilight-waterfall-1383"
echo "  cat /app/knowledge_base/knowledge_base.txt | grep -A 3 'NEVER say'"
echo "  cat /app/app/system_prompt.md | grep -A 2 'Your name' 2>/dev/null || echo 'File not found (okay)'"
echo "  exit"

# 10. Test call
echo ""
echo "Step 10: Manual test required"
echo "-----------------------------"
echo "📞 Call +1 (952) 333-8443 and verify greeting is:"
echo "   'Hi! Thanks for calling Callwaiting AI. I'm Ruthie. What can I help you with today?'"
echo ""
echo "🌐 Or test browser demo at:"
echo "   https://ordervoice.ai"
echo "   (Use hard refresh: Cmd+Shift+R or Ctrl+Shift+R)"
echo ""
echo "=================================================="
echo "✅ FIX DEPLOYMENT COMPLETE"
echo "=================================================="
