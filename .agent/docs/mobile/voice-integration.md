# Mobile Voice Integration Guide

This document outlines the strategy for integrating the Voice Agent into the mobile application (React Native / Expo).

## 1. Expo Router Integration

The Voice Client uses a WebSocket connection governed by `VoiceOrchestrator`. For mobile, this state must persist across navigation.

### Deep Linking Strategy

Voice commands can trigger navigation actions. The backend will emit `navigate` tools which the frontend must handle via Expo Router.

```typescript
// Example Implementation in a specialized MobileVoiceClient wrapper
import { useRouter } from 'expo-router';

// In the tool execution handler:
if (toolCall.name === 'navigate') {
  const router = useRouter();
  router.push(toolCall.args.path);
}
```

## 2. Offline Capabilities & VAD

Reliable Pulse/Voice Detection is critical for mobile.

### Hybrid VAD Strategy

The backend supports a "Graceful Fallback" mechanism (`vad.py`) which is explicitly designed for mobile constraints:

1. **Primary**: Silero VAD (Run via ONNX Runtime). Accurate, but requires model download (~2MB).
2. **Fallback**: WebRTC VAD (compiled C++). Zero-network dependency, extremely fast, battery efficient.
3. **Emergency**: Energy Threshold. Works on any device with a microphone.

**Mobile Requirement**: The mobile app MUST bundle the `silero_vad.onnx` model in the binary assets to prevent runtime download failures, ensuring Tier 1 performance offline.

## 3. UI Responsiveness & Safe Areas

The `VoiceClient` component uses Tailwind CSS (via NativeWind on mobile).

- Ensure all containers use `SafeAreaView` or equivalent padding.
- Touch targets (Mute Button) must be at least 44x44 points.
