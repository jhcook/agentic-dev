// Copyright 2026 Justin Cook
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { useEffect, useRef, useState, useCallback } from 'react';

type VoiceState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking';

interface VoiceMessage {
    type: 'clear_buffer' | 'status' | 'transcript';
    state?: VoiceState;
    data?: unknown;
}

export function useVoiceWebSocket(url: string) {
    const [state, setState] = useState<VoiceState>('idle');
    const [error, setError] = useState<string | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<number>(1000);
    const reconnectTimerRef = useRef<number | null>(null);
    const onAudioChunkRef = useRef<((chunk: ArrayBuffer) => void) | null>(null);
    const onClearBufferRef = useRef<(() => void) | null>(null);
    const onTranscriptRef = useRef<((role: string, text: string, partial?: boolean) => void) | null>(null);
    const connectFnRef = useRef<(() => void) | null>(null);

    const connect = useCallback(() => {
        setState('connecting');
        const ws = new WebSocket(url);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            console.log('[Voice] WebSocket connected');
            setState('listening');
            reconnectTimeoutRef.current = 1000; // Reset backoff
            setError(null);
        };

        ws.onmessage = (event) => {
            if (typeof event.data === 'string') {
                try {
                    const msg: VoiceMessage = JSON.parse(event.data);
                    if (msg.type === 'clear_buffer') {
                        console.log('[Voice] Clear buffer received (barge-in)');
                        onClearBufferRef.current?.();
                    } else if (msg.type === 'status') {
                        if (msg.state) {
                            console.log('[Voice] Status update:', msg.state);
                            setState(msg.state);
                        }
                    } else if (msg.type === 'transcript') {
                        // @ts-expect-error - dynamic payload
                        const { role, text, partial } = msg;
                        onTranscriptRef.current?.(role, text, partial);
                    }
                } catch (err) {
                    console.error('[Voice] Failed to parse message:', err);
                }
            } else {
                // Audio chunk (ArrayBuffer)
                onAudioChunkRef.current?.(event.data);
            }
        };

        ws.onerror = (event) => {
            console.error('[Voice] WebSocket error:', event);
            setError('WebSocket connection failed');
        };

        ws.onclose = () => {
            console.log('[Voice] WebSocket closed');
            setState('idle');

            // Exponential backoff reconnection
            reconnectTimerRef.current = setTimeout(() => {
                console.log(`[Voice] Reconnecting in ${reconnectTimeoutRef.current}ms...`);
                reconnectTimeoutRef.current = Math.min(reconnectTimeoutRef.current * 2, 30000);
                connectFnRef.current?.();
            }, reconnectTimeoutRef.current);
        };

        wsRef.current = ws;
    }, [url]);

    useEffect(() => {
        connectFnRef.current = connect;
    }, [connect]);

    const disconnect = useCallback(() => {
        if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
        wsRef.current?.close();
        wsRef.current = null;
        setState('idle');
    }, []);

    const sendAudio = useCallback((data: ArrayBuffer) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            // console.log("[useVoiceWebSocket] Sending audio bytes:", data.byteLength); // DEBUG
            wsRef.current.send(data);
        } else {
            console.warn("[useVoiceWebSocket] WebSocket not open, dropping audio");
        }
    }, []);

    const sendText = useCallback((text: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'text', text }));
        } else {
            console.warn("[useVoiceWebSocket] WebSocket not open, dropping text");
        }
    }, []);

    const setOnAudioChunk = useCallback((callback: (chunk: ArrayBuffer) => void) => {
        onAudioChunkRef.current = callback;
    }, []);

    const setOnClearBuffer = useCallback((callback: () => void) => {
        onClearBufferRef.current = callback;
    }, []);

    const setOnTranscript = useCallback((callback: (role: string, text: string, partial?: boolean) => void) => {
        onTranscriptRef.current = callback;
    }, []);

    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        state,
        error,
        connect,
        disconnect,
        sendAudio,
        sendText,
        setOnAudioChunk,
        setOnClearBuffer,
        setOnTranscript
    };
}
