# WEB-003-runbook.md

## Status

ACCEPTED

## Goal

Implement the Voice Web Client to provide a rich, visual interface for voice interactions with the agent.

## Panel Review Findings

### @Architect

**Sentiment**: Positive with Caveats
**Key Advice**:

- Use AudioWorklet for \u003c20ms latency requirement
- Implement WebSocket reconnection with exponential backoff
- Design state machine for voice states (Idle → Listening → Thinking → Speaking)

### @Security

**Sentiment**: Warning
**Key Advice**:

- Use WSS in production, implement CSP headers
- Explicit microphone consent flow with privacy messaging
- Validate all WebSocket messages

### @QA

**Sentiment**: Neutral
**Key Advice**:

- Expand test strategy: unit tests for AudioWorklet, integration tests for WebSocket
- Browser compatibility testing (Chrome, Firefox, Safari)
- Visual regression tests for waveform rendering

### @Web

**Sentiment**: Positive
**Key Advice**:

- Use React hooks with proper cleanup to prevent memory leaks
- Implement accessibility (ARIA labels, keyboard shortcuts)
- Use TailwindCSS dark mode utilities

### @Compliance

**Sentiment**: Warning
**Key Advice**:

- Session-only audio storage (no persistence)
- GDPR compliance with clear privacy notices
- Implement "Clear Conversation" button

## Implementation Steps

### 1. Project Foundation

**Location**: `.agent/web/`

The web project already exists from WEB-002. We'll add voice-specific components.

```bash
cd .agent/web
npm install --save-dev @types/audioworklet
```

### 2. AudioWorklet Processor

**File**: `.agent/web/public/audio-processor.js`

Create the AudioWorklet processor for 16kHz downsampling:

```javascript
// public/audio-processor.js
class AudioDownsamplerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.buffer = [];
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const inputData = input[0]; // Mono channel
    const inputSampleRate = sampleRate; // Global from AudioWorkletGlobalScope
    const ratio = inputSampleRate / this.targetSampleRate;

    // Simple downsampling (take every Nth sample)
    for (let i = 0; i < inputData.length; i += ratio) {
      this.buffer.push(inputData[Math.floor(i)]);
    }

    // Send chunks of ~100ms (1600 samples at 16kHz)
    while (this.buffer.length >= 1600) {
      const chunk = this.buffer.splice(0, 1600);
      const pcm16 = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        pcm16[i] = Math.max(-1, Math.min(1, chunk[i])) * 0x7FFF;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    return true;
  }
}

registerProcessor('audio-downsampler', AudioDownsamplerProcessor);
```

### 3. WebSocket Hook

**File**: `.agent/web/src/hooks/useVoiceWebSocket.ts`

```typescript
import { useEffect, useRef, useState } from 'react';

type VoiceState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking';

export function useVoiceWebSocket(url: string) {
  const [state, setState] = useState<VoiceState>('idle');
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>(1000);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);

  const connect = () => {
    setState('connecting');
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setState('listening');
      reconnectTimeoutRef.current = 1000; // Reset backoff
      setError(null);
    };

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data);
        if (msg.type === 'clear_buffer') {
          // Handle clear buffer (barge-in)
          // Emit event for audio player to clear
        }
      } else {
        // Audio chunk (ArrayBuffer)
        // Emit for audio player
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection failed');
    };

    ws.onclose = () => {
      setState('idle');
      // Exponential backoff reconnection
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimeoutRef.current = Math.min(reconnectTimeoutRef.current * 2, 30000);
        connect();
      }, reconnectTimeoutRef.current);
    };

    wsRef.current = ws;
  };

  const disconnect = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
    setState('idle');
  };

  const sendAudio = (data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  };

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  return { state, error, connect, disconnect, sendAudio };
}
```

### 4. Waveform Visualizer

**File**: `.agent/web/src/components/WaveformVisualizer.tsx`

```typescript
import { useEffect, useRef } from 'react';

export function WaveformVisualizer({ audioData }: { audioData: Float32Array | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !audioData) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d')!;
    const { width, height } = canvas;

    // Clear
    ctx.fillStyle = '#1f2937'; // dark:bg-gray-800
    ctx.fillRect(0, 0, width, height);

    // Draw waveform
    ctx.strokeStyle = '#3b82f6'; // blue-500
    ctx.lineWidth = 2;
    ctx.beginPath();

    const step = Math.ceil(audioData.length / width);
    const amp = height / 2;

    for (let i = 0; i < width; i++) {
      const min = Math.min(...Array.from(audioData.slice(i * step, (i + 1) * step)));
      const max = Math.max(...Array.from(audioData.slice(i * step, (i + 1) * step)));
      ctx.moveTo(i, (1 + min) * amp);
      ctx.lineTo(i, (1 + max) * amp);
    }

    ctx.stroke();
  }, [audioData]);

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={200}
      className="w-full h-48 bg-gray-800 rounded-lg"
      aria-label="Audio waveform visualization"
    />
  );
}
```

### 5. Main Voice Component

**File**: `.agent/web/src/components/VoiceClient.tsx`

```typescript
import { useState, useEffect, useRef } from 'react';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { WaveformVisualizer } from './WaveformVisualizer';

export function VoiceClient() {
  const [hasPermission, setHasPermission] = useState(false);
  const [audioData, setAudioData] = useState<Float32Array | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);

  const { state, error, connect, disconnect, sendAudio } = useVoiceWebSocket(
    'ws://localhost:8000/ws/voice'
  );

  const requestMicrophoneAccess = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setHasPermission(true);

      // Initialize AudioContext
      const audioContext = new AudioContext({ sampleRate: 48000 });
      await audioContext.audioWorklet.addModule('/audio-processor.js');

      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'audio-downsampler');

      workletNode.port.onmessage = (event) => {
        // Send to WebSocket
        sendAudio(event.data);
      };

      source.connect(workletNode);
      workletNode.connect(audioContext.destination); // For monitoring (optional)

      audioContextRef.current = audioContext;
      workletNodeRef.current = workletNode;

      connect();
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  };

  const stopVoice = () => {
    audioContextRef.current?.close();
    audioContextRef.current = null;
    workletNodeRef.current = null;
    disconnect();
    setHasPermission(false);
  };

  useEffect(() => {
    return () => {
      stopVoice();
    };
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-4xl font-bold mb-8">Voice Agent</h1>

      {!hasPermission ? (
        <div className="text-center">
          <p className="mb-4 text-gray-400">
            This app needs microphone access to enable voice interactions.
          </p>
          <button
            onClick={requestMicrophoneAccess}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold"
          >
            Enable Microphone
          </button>
        </div>
      ) : (
        <>
          <div className="mb-4 text-2xl font-semibold" aria-live="polite">
            Status: {state}
          </div>

          {error && <div className="text-red-500 mb-4">{error}</div>}

          <WaveformVisualizer audioData={audioData} />

          <button
            onClick={stopVoice}
            className="mt-8 px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg font-semibold"
          >
            Stop Voice
          </button>
        </>
      )}
    </div>
  );
}
```

### 6. Security: CSP Headers

**File**: `.agent/web/index.html`

Add CSP meta tag:

```html
<meta
  http-equiv="Content-Security-Policy"
  content="default-src 'self'; connect-src 'self' ws://localhost:8000 wss://localhost:8000; media-src 'self'"
/>
```

### 7. Documentation

**File**: `.agent/web/README.md`

Update with Voice Client section:

```markdown
## Voice Client

The Voice Client provides a visual interface for voice interactions.

### Browser Compatibility
- Chrome 66+ (AudioWorklet support)
- Firefox 76+
- Safari 14.1+

### Running Locally
1. Start backend: `agent admin start`
2. Navigate to `http://localhost:8080`
3. Click "Enable Microphone" and grant permissions
```

## Verification Plan

### Automated Tests

1. **AudioWorklet Unit Test**:

   ```bash
   # Test downsampling logic
   npm run test -- audio-processor.test.ts
   ```

2. **WebSocket Integration Test**:

   ```bash
   # Mock WebSocket server, test connection/reconnection
   npm run test -- useVoiceWebSocket.test.ts
   ```

3. **Lint**:

   ```bash
   npm run lint
   ```

### Manual Verification

1. **Microphone Permission Flow**:
   - Open `http://localhost:8080`
   - Click "Enable Microphone"
   - Verify browser prompts for permission
   - Verify status changes to "listening"

2. **Audio Streaming**:
   - Speak into microphone
   - Verify waveform visualization updates in real-time
   - Verify WebSocket sends audio chunks

3. **Barge-in (Interrupt)**:
   - Wait for agent to speak
   - Interrupt by speaking
   - Verify `clear_buffer` message received
   - Verify audio playback stops immediately

4. **Reconnection**:
   - Stop backend (`agent admin stop`)
   - Verify UI shows "connecting" state
   - Restart backend
   - Verify automatic reconnection

5. **Browser Compatibility**:
   - Test on Chrome, Firefox, Safari
   - Verify AudioWorklet support

### Performance Verification

1. **Latency**:
   - Use browser DevTools Performance tab
   - Measure time from microphone input to WebSocket send
   - Target: \u003c 20ms

2. **Waveform Rendering**:
   - Use `performance.mark()` in visualizer
   - Verify 60fps (16.67ms per frame)

## Rollback Plan

If issues arise:

1. Remove voice-specific components from `web/src/components/`
2. Remove AudioWorklet processor from `web/public/`
3. Revert to WEB-002 baseline
