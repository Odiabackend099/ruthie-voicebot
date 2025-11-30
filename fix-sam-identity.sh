#!/bin/bash
# RUTHIE IDENTITY FIX - ONE-COMMAND BATTLE-TESTED EXECUTION
# This script fixes the "Sam → Ruthie" identity issue end-to-end

set -e  # Exit on any error
cd "$(dirname "$0")"  # Run from voice-bot directory

echo "🚀 RUTHIE IDENTITY FIX - STARTING"
echo "================================="
date
echo ""

# Run the fix deployment script
bash ./fix-deployment.sh

echo ""
echo "🎉 FIX COMPLETE - Manual verification required:"
echo "1. Call +1 (952) 333-8443"
echo "2. Expected greeting: 'Hi! Thanks for calling Callwaiting AI. I'm Ruthie...'"
echo "3. If you still hear 'Sam', run: ~/.fly/bin/flyctl logs --app sam-ai-voice-bot-twilight-waterfall-1383"
echo ""
echo "================================="
date
