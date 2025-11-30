# Voice Agent Test Plan

## Test Environment

**Frontend**: http://localhost:4050/demo  
**Backend**: http://localhost:6000 (WebSocket: ws://localhost:6000/ws)  
**Ngrok**: Pending URL (for Twilio webhook)  
**Phone Numbers**:
- FROM: +19523338443 (Twilio)
- TO: +2348128772405 (Your number)

---

## Phase 1: Frontend UI Testing (Ready Now)

### Test 1.1: Visual Layout
**Objective**: Verify Perplexity-style UI improvements

**Steps**:
1. Open http://localhost:4050/demo
2. Hard refresh (Cmd+Shift+R)

**Expected Results**:
- ✅ "Odi AI" title perfectly centered vertically
- ✅ Transcription panel collapsed on right side
- ✅ Clean, minimal interface
- ✅ Particle sphere animating smoothly

**Status**: Ready to test

---

### Test 1.2: Live Transcription Display
**Objective**: Verify speech bubbles appear above particle sphere

**Steps**:
1. Click "Start Conversation"
2. Allow microphone access
3. Speak into microphone

**Expected Results**:
- ✅ Purple bubble appears above sphere with "You're speaking..."
- ✅ Your speech transcribed in real-time
- ✅ Smooth fade-in animation
- ✅ Pulsing purple indicator dot

**Status**: Ready to test (demo mode will simulate AI responses)

---

## Phase 2: Backend WebSocket Testing (Waiting for Docker)

### Test 2.1: WebSocket Connection
**Objective**: Verify browser can connect to Python backend

**Command**:
```bash
source venv/bin/activate
python test_browser_ws.py
```

**Expected Output**:
```
🔌 Connecting to ws://localhost:6000/ws...
✅ Connected!
📩 Received: {"type":"welcome"}
📤 Sending 'websocket_start'...
📩 Received: {"type":"websocket_ready"}
✅ Backend is READY. Sending dummy audio...
⏳ Waiting for audio response (Deepgram TTS)...
✅ Received TTS Audio Chunk: XXXX bytes
```

**Status**: Waiting for Docker containers

---

### Test 2.2: Frontend-Backend Integration
**Objective**: Verify full browser voice pipeline

**Steps**:
1. Open http://localhost:4050/demo
2. Click "Start Conversation"
3. Speak: "Hello, can you hear me?"
4. Wait for AI response

**Expected Results**:
- ✅ Purple bubble shows your speech
- ✅ Yellow bubble shows AI response
- ✅ Audio plays from speakers
- ✅ Transcription panel (if expanded) shows full conversation

**Status**: Waiting for Docker containers

---

## Phase 3: Telephony Testing (Requires Ngrok URL)

### Test 3.1: Outbound Call
**Objective**: Verify agent can call your phone

**Command**:
```bash
source venv/bin/activate
python app/outbound_call.py
```

**Expected Results**:
- ✅ Your phone rings (+2348128772405)
- ✅ You answer and hear AI greeting
- ✅ You speak and AI responds
- ✅ Conversation flows naturally

**Status**: Waiting for Docker + Ngrok URL

---

### Test 3.2: Inbound Call
**Objective**: Verify you can call the agent

**Prerequisites**:
1. Docker containers running
2. Ngrok URL configured in Twilio webhook

**Steps**:
1. Call +19523338443 from your phone
2. Wait for AI to answer
3. Have a conversation

**Expected Results**:
- ✅ AI answers with greeting
- ✅ AI understands your speech (Deepgram STT)
- ✅ AI responds intelligently (Groq LLM)
- ✅ AI voice is clear (Deepgram TTS)

**Status**: Waiting for Docker + Ngrok URL + Twilio webhook config

---

## Phase 4: End-to-End Pipeline Verification

### Test 4.1: STT Accuracy (Deepgram)
**Test Phrases**:
- "What's the weather like today?"
- "Tell me a joke"
- "What is 25 times 4?"

**Expected**: Accurate transcription in logs/UI

---

### Test 4.2: LLM Response Quality (Groq)
**Objective**: Verify intelligent responses

**Test Scenarios**:
- Simple question: "What is your name?"
- Follow-up: "What can you help me with?"
- Complex: "Explain quantum computing in simple terms"

**Expected**: Coherent, contextual responses

---

### Test 4.3: TTS Quality (Deepgram)
**Objective**: Verify natural-sounding voice

**Listen for**:
- Clear pronunciation
- Natural intonation
- No robotic artifacts
- Appropriate pacing

---

## Phase 5: Error Handling & Edge Cases

### Test 5.1: Network Interruption
**Steps**:
1. Start conversation
2. Toggle airplane mode mid-sentence
3. Re-enable network

**Expected**: Graceful retry or error message

---

### Test 5.2: Silence Handling
**Steps**:
1. Start conversation
2. Stay silent for 30 seconds

**Expected**: AI prompts or times out gracefully

---

### Test 5.3: Rapid Speech
**Steps**:
1. Speak very quickly without pausing

**Expected**: VAD detects speech, transcription keeps up

---

## Automated Test Script

**File**: `test_full_pipeline.sh`

```bash
#!/bin/bash
set -e

echo "🧪 Voice Agent Full Pipeline Test"
echo "=================================="

# Test 1: Backend Health
echo "1️⃣ Testing backend health..."
curl -f http://localhost:6000/health || echo "❌ Backend not ready"

# Test 2: WebSocket Connection
echo "2️⃣ Testing WebSocket..."
python test_browser_ws.py || echo "❌ WebSocket failed"

# Test 3: Outbound Call (requires user confirmation)
echo "3️⃣ Ready for outbound call test?"
read -p "Press enter to call +2348128772405..."
python app/outbound_call.py

echo "✅ All automated tests complete!"
echo "📞 Manual test: Call +19523338443 to test inbound"
```

---

## Success Criteria

**Minimum Viable**:
- ✅ Frontend UI loads and looks correct
- ✅ WebSocket connects to backend
- ✅ Audio flows: Mic → STT → LLM → TTS → Speakers

**Full Success**:
- ✅ All of above
- ✅ Outbound calls work
- ✅ Inbound calls work
- ✅ Transcription accurate (>90%)
- ✅ Responses intelligent and contextual
- ✅ Voice quality natural

---

## Current Blockers

1. ⏳ **Docker containers still downloading** (~66% complete)
2. ⏳ **Ngrok URL not configured** (need to update Twilio webhook)

**ETA**: ~5-10 minutes for Docker to complete

---

## Quick Start (When Ready)

```bash
# 1. Test frontend
open http://localhost:4050/demo

# 2. Test backend WebSocket
source venv/bin/activate && python test_browser_ws.py

# 3. Test outbound call
python app/outbound_call.py

# 4. Test inbound call
# Call +19523338443 from your phone
```
