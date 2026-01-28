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
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    Mic,
    MicOff,
    Headphones,
    Sparkles,
    CircleStop,
    Trash2,
    Activity,
    User,
    Bot,
} from 'lucide-react';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { WaveformVisualizer } from './WaveformVisualizer';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface VoiceClientProps {
    /** Optional class overrides for NativeWind/Mobile styling */
    className?: string;
}

export function VoiceClient({ className }: VoiceClientProps) {
    const [hasPermission, setHasPermission] = useState(false);
    // Modified Transcript Type to include 'console' role implicitly via string
    const [transcript, setTranscript] = useState<Array<{ role: string; text: string; partial?: boolean }>>([]);
    const [inputValue, setInputValue] = useState("");

    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const audioQueueRef = useRef<AudioBuffer[]>([]);
    const isPlayingRef = useRef(false);
    const playNextChunkRef = useRef<(() => void) | null>(null);
    const transcriptEndRef = useRef<HTMLDivElement>(null);
    const lastClearedGenIdRef = useRef(-1);
    const currentGenerationRef = useRef<number>(0);

    // Mute State
    const [isMuted, setIsMuted] = useState(false);
    const isMutedRef = useRef(false);

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

    const {
        state,
        error,
        connect,
        disconnect,
        sendAudio,
        sendText,
        sendJson,
        setOnAudioChunk,
        setOnClearBuffer,
        setOnTranscript,
        setOnEvent
    } = useVoiceWebSocket(wsUrl);

    const toggleMute = useCallback(() => {
        const newValue = !isMutedRef.current;
        isMutedRef.current = newValue;
        setIsMuted(newValue);
        // Notify backend to flush buffer if muting
        sendJson({
            type: 'mute_changed',
            muted: newValue
        });
    }, [sendJson]);

    // VAD Settings State
    const [showSettings, setShowSettings] = useState(false);
    const [vadSettings, setVadSettings] = useState({
        autotune: true,
        aggressiveness: 3,
        threshold: 0.5,
        noise_floor: 0,
        rms_peak: 0
    });

    // Event Handler: Console & VAD
    useEffect(() => {
        setOnEvent((type, data) => {
            if (type === 'console') {
                setTranscript(prev => {
                    // Check if we should start a new bubble
                    // Heuristic: If data starts with "> " (command start), force new bubble
                    // Or if existing last message is NOT console, force new bubble
                    const isCommandStart = data.trim().startsWith("> ");

                    if (prev.length > 0 && prev[prev.length - 1].role === 'console' && !isCommandStart) {
                        const last = prev[prev.length - 1];
                        const newHistory = [...prev];
                        newHistory[newHistory.length - 1] = { ...last, text: last.text + data };
                        return newHistory;
                    } else {
                        return [...prev, { role: 'console', text: data }];
                    }
                });
            } else if (type === 'vad_state') {
                setVadSettings(prev => ({ ...prev, ...data }));
            } else if (type === 'open_url') {
                if (data && data.url) {
                    window.open(data.url, '_blank');
                }
            }
        });
    }, [setOnEvent]);

    const updateVadSetting = (key: string, value: any) => {
        const newSettings = { ...vadSettings, [key]: value };
        setVadSettings(newSettings);
        sendJson({
            ...newSettings,
            type: 'update_settings'
        });
    };

    // History Fetch
    useEffect(() => {
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
                            const lines = data.history.map((msg: { role: string, text: string }) => ({
                                role: msg.role,
                                text: msg.text,
                                partial: false
                            }));
                            setTranscript(lines);
                        }
                    }
                } catch (e) {
                    console.error("Failed to fetch history:", e);
                }
            };
            fetchHistory();
        }

        // Audio Player Logic
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

            if (analyserRef.current) {
                source.connect(analyserRef.current);
            }
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

    // Audio Chunk & Transcript Handlers
    useEffect(() => {
        setOnAudioChunk((chunk: ArrayBuffer) => {
            if (chunk.byteLength < 4) return;
            const view = new DataView(chunk);
            const chunkGenId = view.getUint32(0);
            if (chunkGenId <= lastClearedGenIdRef.current) return;
            const audioData = chunk.slice(4);
            if (audioContextRef.current) {
                audioContextRef.current.decodeAudioData(audioData.slice(0), (buffer) => {
                    if (chunkGenId <= lastClearedGenIdRef.current) return;
                    audioQueueRef.current.push(buffer);
                    if (!isPlayingRef.current) { playNextChunkRef.current?.(); }
                }).catch((err) => { console.error('[Voice] Failed to decode audio:', err); });
            }
        });

        setOnClearBuffer((payload?: { generation_id: number }) => {
            console.log("[Voice] Interrupt received. Clearing buffer.", payload);
            if (payload && typeof payload.generation_id === 'number') {
                currentGenerationRef.current = payload.generation_id + 1;
            } else {
                currentGenerationRef.current++;
            }
            audioQueueRef.current = [];
            if (activeSourceRef.current) {
                try { activeSourceRef.current.stop(); } catch (e) { }
                activeSourceRef.current = null;
            }
            isPlayingRef.current = false;
        });

        setOnTranscript((role: string, text: string, partial?: boolean) => {
            setTranscript(prev => {
                if (prev.length === 0) return [{ role, text, partial }];
                const last = prev[prev.length - 1];

                // Merge logic for assistant (streaming)
                const isAssistantMerge = role === 'assistant' && last.role === 'assistant';
                if (isAssistantMerge) {
                    const newHistory = [...prev];
                    if (partial) {
                        const joiner = (last.partial === false) ? ' ' : '';
                        newHistory[newHistory.length - 1] = {
                            ...last,
                            text: last.text + joiner + text,
                            partial: true
                        };
                    } else {
                        newHistory[newHistory.length - 1] = { ...last, text: text, partial: false };
                    }
                    return newHistory;
                }

                // Merge logic for user (partial speech)
                if (role === 'user' && last.role === 'user' && last.partial) {
                    const newHistory = [...prev];
                    newHistory[newHistory.length - 1] = { ...last, text: last.text + text, partial };
                    return newHistory;
                }

                return [...prev, { role, text, partial }];
            });
        });
    }, [setOnAudioChunk, setOnClearBuffer, setOnTranscript]);

    // Auto-scroll on transcript change
    useEffect(() => {
        transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcript]);

    const requestMicrophoneAccess = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
            });
            setHasPermission(true);
            const audioContext = new AudioContext({ sampleRate: 48000 });
            if (audioContext.state === 'suspended') await audioContext.resume();
            await audioContext.audioWorklet.addModule(`/audio-processor.js?t=${Date.now()}`);
            const source = audioContext.createMediaStreamSource(stream);
            const gainNode = audioContext.createGain();
            gainNode.gain.value = 2.0;
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            analyserRef.current = analyser;

            const workletNode = new AudioWorkletNode(audioContext, 'audio-downsampler');
            workletNode.port.onmessage = (e) => {
                if (!isMutedRef.current) {
                    sendAudio(e.data);
                }
            };
            source.connect(gainNode);
            gainNode.connect(analyser);
            gainNode.connect(workletNode);

            audioContextRef.current = audioContext;
            workletNodeRef.current = workletNode;
            connect();
        } catch (err) {
            console.error('[Voice] Mic denied:', err);
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
    }, [disconnect]);

    useEffect(() => { return () => { stopVoice(); }; }, [stopVoice]);

    const getStatusTheme = () => {
        switch (state) {
            case 'listening': return { color: 'text-green-400', label: 'Listening', icon: <Mic className="w-5 h-5 animate-pulse" /> };
            case 'thinking': return { color: 'text-amber-400', label: 'Thinking', icon: <Sparkles className="w-5 h-5 animate-spin-slow" /> };
            case 'speaking': return { color: 'text-blue-400', label: 'Speaking', icon: <Headphones className="w-5 h-5" /> };
            case 'connecting': return { color: 'text-gray-400', label: 'Connecting', icon: <Activity className="w-5 h-5 animate-pulse" /> };
            default: return { color: 'text-gray-500', label: 'Disconnected', icon: <MicOff className="w-5 h-5" /> };
        }
    };

    const theme = getStatusTheme();

    return (
        <div className="flex flex-col h-screen bg-[#0a0a0c] text-slate-200 font-sans relative">
            {/* Header */}
            <header className="flex items-center justify-between px-8 py-5 border-b border-white/5 bg-black/20 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-600/20 rounded-xl border border-blue-500/30">
                        <Activity className="w-6 h-6 text-blue-400" />
                    </div>
                    <h1 className="text-xl font-bold tracking-tight text-white">Voice Agent</h1>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setShowSettings(!showSettings)}
                        className={cn("p-2.5 rounded-full border transition-all duration-300",
                            showSettings ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-white/5 border-white/10 text-slate-400 hover:text-white")}
                        title="VAD Settings"
                    >
                        <Activity className="w-5 h-5" />
                    </button>

                    <button
                        onClick={toggleMute}
                        disabled={state === 'idle' || state === 'connecting'}
                        className={cn(
                            "p-2.5 rounded-full border transition-all duration-300 flex items-center justify-center",
                            isMuted
                                ? "bg-red-500/20 border-red-500 text-red-500 shadow-[0_0_15px_-3px_rgba(239,68,68,0.5)] scale-110"
                                : "bg-white/5 border-white/10 text-slate-400 hover:text-white hover:bg-white/10 disabled:opacity-30"
                        )}
                        title={isMuted ? "Unmute Microphone" : "Mute Microphone"}
                    >
                        {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                    </button>

                    <div className={cn("px-4 py-1.5 rounded-full border flex items-center gap-2.5 text-sm font-medium transition-all duration-300",
                        theme.color,
                        "bg-white/5 border-white/10 shadow-lg"
                    )}>
                        {theme.icon}
                        {theme.label}
                    </div>
                </div>
            </header>

            {/* Settings Poppover */}
            {showSettings && (
                <div className="absolute top-20 right-8 z-50 w-80 bg-[#16161a] border border-white/10 rounded-2xl shadow-2xl p-6 backdrop-blur-xl">
                    <h3 className="text-white font-bold mb-4 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-blue-400" /> VAD Settings
                    </h3>

                    <div className="space-y-6">
                        {/* Autotune Toggle */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-400">Autotune</span>
                            <button
                                onClick={() => updateVadSetting('autotune', !vadSettings.autotune)}
                                className={cn("w-10 h-5 rounded-full relative transition-colors", vadSettings.autotune ? "bg-blue-600" : "bg-white/10")}
                            >
                                <div className={cn("absolute top-1 w-3 h-3 rounded-full bg-white transition-all", vadSettings.autotune ? "left-6" : "left-1")} />
                            </button>
                        </div>

                        {/* Threshold Slider (Sensitivity) */}
                        <div className="space-y-2">
                            <div className="flex justify-between text-xs text-slate-500">
                                <span>Sensitivity (RMS Thresh)</span>
                                <span>{vadSettings.threshold}</span>
                            </div>
                            <input
                                type="range"
                                min="0" max="1.0" step="0.05"
                                value={vadSettings.threshold}
                                onChange={(e) => updateVadSetting('threshold', parseFloat(e.target.value))}
                                className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500"
                            />
                        </div>

                        {/* Live Meters */}
                        <div className="space-y-2 pt-2 border-t border-white/5">
                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider">Live Metrics</div>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                                <div className="bg-black/30 p-2 rounded">
                                    <div className="text-slate-500">Noise Floor</div>
                                    <div className="text-blue-400 font-mono">{vadSettings.noise_floor.toFixed(0)}</div>
                                </div>
                                <div className="bg-black/30 p-2 rounded">
                                    <div className="text-slate-500">Peak RMS</div>
                                    <div className="text-green-400 font-mono">{vadSettings.rms_peak.toFixed(0)}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Main Content */}
            <main className="flex-1 flex flex-col max-w-5xl w-full mx-auto px-6 py-8 overflow-hidden">
                {!hasPermission ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center">
                        <div className="w-20 h-20 bg-blue-600/10 rounded-3xl flex items-center justify-center mb-8 border border-blue-500/20 shadow-2xl">
                            <Mic className="w-10 h-10 text-blue-400" />
                        </div>
                        <h2 className="text-3xl font-bold text-white mb-4">Start Conversing</h2>
                        <p className="text-slate-400 max-w-sm mb-10 leading-relaxed">
                            Interact with your agent using natural voice. Your audio is processed locally and securely.
                        </p>
                        <button
                            onClick={requestMicrophoneAccess}
                            className="group relative px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold transition-all duration-300 shadow-[0_0_40px_-10px_rgba(37,99,235,0.4)] active:scale-95"
                        >
                            Enable Microphone
                        </button>
                    </div>
                ) : (
                    <>
                        {/* Transcript Area */}
                        <div className="flex-1 overflow-y-auto pr-4 custom-scrollbar space-y-6 mb-8">
                            {transcript.length === 0 && (
                                <div className="h-full flex items-center justify-center text-slate-500 italic">
                                    Awaiting your command...
                                </div>
                            )}
                            {transcript.map((msg, i) => {
                                // Console Output Render
                                if (msg.role === 'console') {
                                    return (
                                        <div key={i} className="flex w-full justify-start animate-fade-in-up">
                                            <div className="max-w-full w-full px-5 py-4 rounded-3xl bg-[#0d0d10] border border-white/10 shadow-xl font-mono text-xs overflow-x-auto">
                                                <div className="flex items-center gap-2 mb-2 opacity-60 text-xs font-bold uppercase tracking-widest text-amber-500">
                                                    <Activity className="w-3 h-3" />
                                                    Terminal Output
                                                </div>
                                                <pre className="whitespace-pre-wrap text-slate-400 leading-relaxed">
                                                    {msg.text}
                                                </pre>
                                            </div>
                                        </div>
                                    );
                                }
                                // Standard Chat Render
                                return (
                                    <div key={i} className={cn("flex w-full", msg.role === 'user' ? "justify-end" : "justify-start")}>
                                        <div className={cn(
                                            "max-w-[85%] px-5 py-4 rounded-3xl shadow-xl transition-all duration-300",
                                            msg.role === 'user'
                                                ? "bg-blue-700 text-white rounded-tr-none border border-blue-500/30"
                                                : "bg-[#16161a] border border-white/5 rounded-tl-none"
                                        )}>
                                            <div className="flex items-center gap-2 mb-2 opacity-60 text-xs font-bold uppercase tracking-widest">
                                                {msg.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3 text-blue-400" />}
                                                {msg.role}
                                            </div>
                                            <div className={cn("prose prose-invert max-w-none text-sm leading-relaxed", msg.partial && "opacity-70 animate-pulse")}>
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {msg.text}
                                                </ReactMarkdown>
                                            </div>
                                        </div>
                                    </div>
                                )
                            })}
                            <div ref={transcriptEndRef} />
                        </div>

                        {/* Visualizer & Controls */}
                        <div className="bg-[#121216] border border-white/5 rounded-[2.5rem] p-10 shadow-2xl relative overflow-hidden group">
                            {/* BG Glow */}
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 bg-blue-500/20 rounded-full blur-[80px] opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none" />

                            <div className="relative z-10 flex flex-col gap-8">
                                <div className="h-20 max-w-2xl mx-auto w-full flex items-center justify-center bg-black/40 rounded-2xl border border-white/5 overflow-hidden px-4">
                                    <WaveformVisualizer
                                        analyserRef={analyserRef}
                                        isActive={state === 'listening' || state === 'speaking' || state === 'thinking'}
                                    />
                                </div>

                                <div className="flex items-center justify-between">
                                    <div className="flex gap-4">
                                        <button
                                            onClick={stopVoice}
                                            className="px-6 py-3 bg-red-600/10 hover:bg-red-600/20 text-red-500 border border-red-500/20 rounded-2xl font-semibold transition-all flex items-center gap-2"
                                        >
                                            <CircleStop className="w-5 h-5" />
                                            Stop
                                        </button>
                                        <button
                                            onClick={() => { setTranscript([]); }}
                                            className="px-6 py-3 bg-white/5 hover:bg-white/10 text-slate-400 border border-white/10 rounded-2xl font-semibold transition-all disabled:opacity-30 flex items-center gap-2"
                                            disabled={transcript.length === 0}
                                        >
                                            <Trash2 className="w-5 h-5" />
                                            Clear
                                        </button>
                                    </div>

                                    <div className="hidden sm:flex text-slate-500 text-xs gap-6 items-center uppercase tracking-widest font-bold">
                                        <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-blue-500" /> 48khz PCM</span>
                                        <span className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-green-500" /> AES-256</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Text Input Area */}
                        <div className="mt-8 relative group">
                            <form
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    if (inputValue.trim()) {
                                        sendText(inputValue.trim());
                                        setTranscript(prev => [...prev, { role: 'user', text: inputValue.trim() }]);
                                        setInputValue("");
                                    }
                                }}
                                className="flex items-center gap-4 bg-[#16161a] border border-white/10 p-2 rounded-2xl shadow-xl focus-within:border-blue-500/50 transition-all"
                            >
                                <input
                                    type="text"
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    placeholder="Type a message to the agent..."
                                    className="flex-1 bg-transparent px-4 py-3 outline-none text-slate-200 placeholder-slate-600 text-sm"
                                />
                                <button
                                    type="submit"
                                    disabled={!inputValue.trim()}
                                    className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl font-bold transition-all text-sm"
                                >
                                    Send
                                </button>
                            </form>
                        </div>
                    </>
                )}
            </main>

            {/* Footer */}
            <footer className="px-8 py-5 text-center text-[10px] text-slate-600 font-bold uppercase tracking-[0.2em]">
                System Ready • Latency: &lt;150ms • Build 2026.1.27
            </footer>

            <style dangerouslySetInnerHTML={{
                __html: `
                .custom-scrollbar::-webkit-scrollbar { width: 6px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.1); }
                .animate-spin-slow { animation: spin 3s linear infinite; }
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .animate-fade-in-up { animation: fadeInUp 0.3s ease-out; }
                @keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            `}} />
        </div>
    );
}
