#!/bin/bash
# Ruthie AI - Deploy TTS Sanitization Fixes to Fly.io
# Created: November 29, 2025
# Run when network connectivity is stable

set -e  # Exit on error

echo "🚀 RUTHIE AI - DEPLOYING TTS SANITIZATION FIXES"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="sam-ai-voice-bot-twilight-waterfall-1383"
FLYCTL_PATH="$HOME/.fly/bin/flyctl"
VOICE_BOT_DIR="/Users/odiadev/Desktop/Callwaiting AI/voice-bot"

# Change to voice-bot directory
cd "$VOICE_BOT_DIR" || exit 1
echo "✅ Changed to directory: $VOICE_BOT_DIR"
echo ""

# Check if flyctl exists
if [ ! -f "$FLYCTL_PATH" ]; then
    echo -e "${RED}❌ Error: flyctl not found at $FLYCTL_PATH${NC}"
    exit 1
fi

# Check network connectivity
echo "🌐 Checking network connectivity..."
if ! curl -s --max-time 5 https://api.fly.io > /dev/null 2>&1; then
    echo -e "${RED}❌ Network connectivity issue: Cannot reach api.fly.io${NC}"
    echo ""
    echo "Please check:"
    echo "  1. Internet connection is active"
    echo "  2. DNS is resolving correctly (try: ping api.fly.io)"
    echo "  3. No firewall blocking Fly.io"
    echo ""
    exit 1
fi
echo -e "${GREEN}✅ Network connectivity OK${NC}"
echo ""

# Verify critical files exist
echo "📋 Verifying critical files..."
REQUIRED_FILES=(
    "app/tts_sanitizer.py"
    "app/function_handler.py"
    "app/inbound_deepgram.py"
    "app/main_ws.py"
    "Dockerfile"
    "fly.toml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Error: Required file missing: $file${NC}"
        exit 1
    fi
    echo "  ✓ $file"
done
echo -e "${GREEN}✅ All required files present${NC}"
echo ""

# Show what's being deployed
echo "📦 Deployment Summary:"
echo "  App: $APP_NAME"
echo "  Region: iad (US East)"
echo "  New Features:"
echo "    - TTS Sanitization Layer (removes function names)"
echo "    - Phone number pronunciation (digit-by-digit)"
echo "    - Email address formatting for speech"
echo "    - Silence detection and recovery"
echo "    - Template variable validation"
echo ""

# Confirm deployment
read -p "🚀 Ready to deploy? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "🔨 Starting deployment (this may take 5-10 minutes)..."
echo ""

# Deploy to Fly.io with remote build
if "$FLYCTL_PATH" deploy --remote-only -a "$APP_NAME"; then
    echo ""
    echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL!${NC}"
    echo ""

    # Check health endpoint
    echo "🏥 Checking health endpoint..."
    sleep 5  # Give it a moment to stabilize

    if curl -sf "https://$APP_NAME.fly.dev/health" > /dev/null; then
        echo -e "${GREEN}✅ Health check passed${NC}"
        echo ""
        echo "📊 Service Status:"
        curl -s "https://$APP_NAME.fly.dev/health" | python3 -m json.tool || echo "  (health check successful but JSON parse failed)"
    else
        echo -e "${YELLOW}⚠️  Health check failed - may need a moment to start${NC}"
        echo "   Try: curl https://$APP_NAME.fly.dev/health"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📞 NEXT STEPS:"
    echo ""
    echo "1. Verify Twilio webhooks:"
    echo "   cd /Users/odiadev/Desktop/Callwaiting\\ AI"
    echo "   python3 scripts/update_twilio_flyio.py"
    echo ""
    echo "2. Test inbound call:"
    echo "   Call: +1 (252) 645-3035"
    echo "   Listen for natural speech (no function names!)"
    echo ""
    echo "3. Monitor logs:"
    echo "   $FLYCTL_PATH logs -a $APP_NAME"
    echo ""
    echo "4. Look for TTS sanitization in logs:"
    echo "   $FLYCTL_PATH logs -a $APP_NAME | grep -i 'sanitiz'"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    exit 0
else
    echo ""
    echo -e "${RED}❌ DEPLOYMENT FAILED!${NC}"
    echo ""
    echo "Common issues:"
    echo "  1. Network connectivity dropped during deployment"
    echo "  2. Fly.io quota exceeded (check billing)"
    echo "  3. Invalid configuration in fly.toml"
    echo ""
    echo "Check logs:"
    echo "  $FLYCTL_PATH logs -a $APP_NAME"
    echo ""
    exit 1
fi
