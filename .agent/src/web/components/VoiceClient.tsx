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

import { useState, useEffect, useRef, useCallback } from 'react';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { WaveformVisualizer } from './WaveformVisualizer';

export function VoiceClient() {
    const [hasPermission, setHasPermission] = useState(false);
    const [audioData, setAudioData] = useState<Float32Array | null>(null);
    const [transcript, setTranscript] = useState<string[]>([]);

    const audioContextRef = useRef<AudioContext | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const audioQueueRef = useRef<AudioBuffer[]>([]);
    const isPlayingRef = useRef(false);
    const playNextChunkRef = useRef<(() => void) | null>(null);

    // Persistent Session ID
    const [sessionId] = useState(() => {
        const stored = localStorage.getItem('agent_voice_session');
        if (stored) return stored;
        const newId = crypto.randomUUID();
        localStorage.setItem('agent_voice_session', newId);
        return newId;
    });

    const wsUrl = import.meta.env.PROD
        ? `wss://${window.location.host}/ws/voice?session_id=${sessionId}`
        : `ws://localhost:8000/ws/voice?session_id=${sessionId}`;

    const { state, error, connect, disconnect, sendAudio, setOnAudioChunk, setOnClearBuffer, setOnTranscript } =
        useVoiceWebSocket(wsUrl);

    // Define playNextChunk function in useEffect to avoid ref assignment during render
    useEffect(() => {
        // Fetch history
        if (sessionId) {
            const fetchHistory = async () => {
                try {
                    const protocol = window.location.protocol;
                    const host = window.location.host;
                    const baseUrl = import.meta.env.PROD
                        ? `${protocol}//${host}`
                        : 'http://localhost:8000';

                    const res = await fetch(`${baseUrl}/history/${sessionId}`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.history && Array.isArray(data.history)) {
                            const lines = data.history.map((msg: { role: string, text: string }) =>
                                `${msg.role === 'user' ? '👤' : '🤖'} ${msg.text}`
                            );
                            setTranscript(lines);
                        }
                    }
                } catch (e) {
                    console.error("Failed to fetch history:", e);
                }
            };
            fetchHistory();
        }

        playNextChunkRef.current = () => {
            if (audioQueueRef.current.length === 0) {
                isPlayingRef.current = false;
                activeSourceRef.current = null;
                return;
            }

            isPlayingRef.current = true;
            const buffer = audioQueueRef.current.shift()!;
            const source = audioContextRef.current!.createBufferSource();
            activeSourceRef.current = source;
            source.buffer = buffer;
            source.connect(audioContextRef.current!.destination);

            source.onended = () => {
                if (activeSourceRef.current === source) {
                    activeSourceRef.current = null;
                    playNextChunkRef.current?.();
                }
            };

            source.start();
        };
    }, [sessionId]);

    // Handle incoming audio chunks
    useEffect(() => {
        setOnAudioChunk((chunk: ArrayBuffer) => {
            // Queue audio for playback
            if (audioContextRef.current) {
                const audioContext = audioContextRef.current;
                audioContext.decodeAudioData(chunk.slice(0), (buffer) => {
                    audioQueueRef.current.push(buffer);
                    if (!isPlayingRef.current) {
                        playNextChunkRef.current?.();
                    }
                }).catch((err) => {
                    console.error('[Voice] Failed to decode audio:', err);
                });
            }
        });

        setOnClearBuffer(() => {
            // Clear playback queue on barge-in
            console.log('[Voice] Clearing audio queue (barge-in)');
            audioQueueRef.current = [];

            // Stop active playback immediately
            if (activeSourceRef.current) {
                try {
                    activeSourceRef.current.stop();
                } catch (e) {
                    // Ignore if already stopped
                }
                activeSourceRef.current = null;
            }

            isPlayingRef.current = false;
        });

        // Handle transcripts
        setOnTranscript((role: string, text: string) => {
            setTranscript(prev => [...prev, `${role === 'user' ? '👤' : '🤖'} ${text}`]);
        });
    }, [setOnAudioChunk, setOnClearBuffer, setOnTranscript]);

    const requestMicrophoneAccess = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });

            setHasPermission(true);

            // Initialize AudioContext
            const audioContext = new AudioContext({ sampleRate: 48000 });

            // Ensure context is running (fixes potential 'suspended' state on start)
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            await audioContext.audioWorklet.addModule(`/audio-processor.js?t=${Date.now()}`);

            const source = audioContext.createMediaStreamSource(stream);

            // Add a GainNode to boost the mic signal by 2x for better STT recognition
            const gainNode = audioContext.createGain();
            gainNode.gain.value = 2.0;

            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Float32Array(bufferLength);

            const workletNode = new AudioWorkletNode(audioContext, 'audio-downsampler');

            workletNode.port.onmessage = (event) => {
                // Send to WebSocket
                sendAudio(event.data);
            };

            // Pipeline: source -> gain -> analyser -> worklet
            source.connect(gainNode);
            gainNode.connect(analyser);
            gainNode.connect(workletNode);

            // Update waveform visualization
            const updateWaveform = () => {
                analyser.getFloatTimeDomainData(dataArray);
                setAudioData(new Float32Array(dataArray));
                requestAnimationFrame(updateWaveform);
            };
            updateWaveform();

            audioContextRef.current = audioContext;
            workletNodeRef.current = workletNode;

            connect();
        } catch (err) {
            console.error('[Voice] Microphone access denied:', err);
            alert(`Microphone access denied: ${err instanceof Error ? err.message : 'Unknown error'}\n\nPlease grant microphone permissions in your browser settings.`);
        }
    };

    const stopVoice = useCallback(() => {
        audioContextRef.current?.close();
        audioContextRef.current = null;
        workletNodeRef.current = null;
        activeSourceRef.current = null;
        audioQueueRef.current = [];
        isPlayingRef.current = false;
        disconnect();
        setHasPermission(false);
        setAudioData(null);
    }, [disconnect]);

    useEffect(() => {
        return () => {
            stopVoice();
        };
    }, [stopVoice]);

    const getStatusColor = () => {
        switch (state) {
            case 'listening': return 'text-green-400';
            case 'thinking': return 'text-yellow-400';
            case 'speaking': return 'text-blue-400';
            case 'connecting': return 'text-gray-400';
            default: return 'text-gray-500';
        }
    };

    const getStatusIcon = () => {
        switch (state) {
            case 'listening': return '🎤';
            case 'thinking': return '🤔';
            case 'speaking': return '🔊';
            case 'connecting': return '⏳';
            default: return '⭕';
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-8">
            <h1 className="text-4xl font-bold mb-8">Voice Agent</h1>

            {!hasPermission ? (
                <div className="text-center max-w-md">
                    <p className="mb-4 text-gray-400">
                        This app needs microphone access to enable voice interactions with the agent.
                    </p>
                    <p className="mb-6 text-sm text-gray-500">
                        Your audio is processed securely and is not stored beyond the current session.
                    </p>
                    <button
                        onClick={requestMicrophoneAccess}
                        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition-colors"
                    >
                        Enable Microphone
                    </button>
                </div>
            ) : (
                <>
                    <div
                        className={`mb-4 text-2xl font-semibold flex items-center gap-3 ${getStatusColor()}`}
                        aria-live="polite"
                    >
                        <span className="text-3xl">{getStatusIcon()}</span>
                        <span className="capitalize">{state}</span>
                    </div>

                    {error && (
                        <div className="mb-4 px-4 py-2 bg-red-900/50 border border-red-500 rounded-lg text-red-200">
                            {error}
                        </div>
                    )}

                    <div className="w-full max-w-4xl mb-6">
                        <WaveformVisualizer
                            audioData={audioData}
                            isActive={state === 'listening' || state === 'speaking'}
                        />
                    </div>

                    {transcript.length > 0 && (
                        <div className="w-full max-w-4xl mb-6 p-4 bg-gray-800 rounded-lg max-h-64 overflow-y-auto">
                            <h2 className="text-lg font-semibold mb-2">Transcript</h2>
                            <div className="space-y-2">
                                {transcript.map((line, i) => (
                                    <p key={i} className="text-gray-300">{line}</p>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="flex gap-4">
                        <button
                            onClick={stopVoice}
                            className="px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg font-semibold transition-colors"
                        >
                            Stop Voice
                        </button>
                        <button
                            onClick={() => setTranscript([])}
                            className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition-colors"
                            disabled={transcript.length === 0}
                        >
                            Clear Transcript
                        </button>
                    </div>

                    <p className="mt-8 text-sm text-gray-500">
                        Press Esc to stop • Audio is session-only
                    </p>
                </>
            )}
        </div>
    );
}
