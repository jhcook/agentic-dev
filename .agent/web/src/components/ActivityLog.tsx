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

import { useState, useEffect, useRef } from 'react';
import { Terminal, Trash2, Pause, Play, Download, Activity } from 'lucide-react';
import { cn } from '../lib/utils';

interface ActivityMessage {
    timestamp: number;
    type: 'thought' | 'tool' | 'error' | 'info';
    content: string;
    level: string;
}

export function ActivityLog() {
    const [messages, setMessages] = useState<ActivityMessage[]>([]);
    const [isPaused, setIsPaused] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [filter, setFilter] = useState<string>('all');
    const scrollRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        const wsUrl = import.meta.env.PROD
            ? `wss://${window.location.host}/ws/admin/logs`
            : 'ws://localhost:8000/ws/admin/logs';

        const connect = () => {
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                setIsConnected(true);
            };

            ws.onmessage = (event) => {
                if (isPaused) return;
                try {
                    const msg = JSON.parse(event.data);
                    setMessages(prev => [...prev.slice(-100), msg]); // Keep last 100
                } catch (err) {
                    console.error('Failed to parse log message:', err);
                }
            };

            ws.onclose = () => {
                setIsConnected(false);
                setTimeout(connect, 3000); // Reconnect
            };
            wsRef.current = ws;
        };

        connect();
        return () => wsRef.current?.close();
    }, [isPaused]);

    useEffect(() => {
        if (scrollRef.current && !isPaused) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isPaused]);

    const filteredMessages = messages.filter(msg =>
        filter === 'all' || msg.type === filter
    );

    const downloadLogs = () => {
        const blob = new Blob([JSON.stringify(messages, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `agent-activity-${new Date().toISOString()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const clearLogs = () => {
        setMessages([]);
    };

    const getTimeString = (timestamp: number) => {
        return new Date(timestamp * 1000).toLocaleTimeString();
    };

    const getMsgColor = (type: string) => {
        switch (type) {
            case 'thought': return 'text-blue-400';
            case 'tool': return 'text-purple-400';
            case 'error': return 'text-red-400';
            case 'info': return 'text-green-400';
            default: return 'text-gray-400';
        }
    };

    return (
        <div className="flex flex-col h-full bg-black text-gray-300 font-mono text-sm">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900/50">
                <div className="flex items-center gap-3">
                    <Terminal size={18} className="text-blue-500" />
                    <h1 className="text-white font-semibold">Activity Log Stream</h1>
                    <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full border flex items-center gap-1",
                        isConnected
                            ? "bg-green-500/10 text-green-500 border-green-500/20"
                            : "bg-red-500/10 text-red-500 border-red-500/20"
                    )}>
                        <div className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-green-500" : "bg-red-500 animate-pulse")}></div>
                        {isConnected ? "Live" : "Connecting..."}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <select
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none"
                    >
                        <option value="all">All Events</option>
                        <option value="thought">Thoughts</option>
                        <option value="tool">Tools</option>
                        <option value="error">Errors</option>
                    </select>

                    <button onClick={() => setIsPaused(!isPaused)} className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-white" title={isPaused ? "Resume" : "Pause"}>
                        {isPaused ? <Play size={16} /> : <Pause size={16} />}
                    </button>
                    <button onClick={downloadLogs} className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-white" title="Download JSON">
                        <Download size={16} />
                    </button>
                    <button onClick={clearLogs} className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-white" title="Clear">
                        <Trash2 size={16} />
                    </button>
                </div>
            </div>

            {/* Log Canvas */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-6 space-y-1 selection:bg-blue-500/30"
            >
                {filteredMessages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center opacity-20 grayscale">
                        <Activity size={48} className="mb-2" />
                        <p>Waiting for agent activity...</p>
                    </div>
                ) : (
                    filteredMessages.map((msg, i) => (
                        <div key={i} className="flex gap-4 group hover:bg-gray-800/30 rounded px-2 -mx-2">
                            <span className="text-gray-600 shrink-0 select-none">[{getTimeString(msg.timestamp)}]</span>
                            <span className={cn("shrink-0 uppercase text-[10px] tracking-widest pt-0.5 select-none w-16", getMsgColor(msg.type))}>
                                {msg.type}
                            </span>
                            <span className="whitespace-pre-wrap break-all leading-relaxed">
                                {msg.content}
                            </span>
                        </div>
                    ))
                )}
            </div>

            {/* Footer bar */}
            <div className="px-6 py-2 border-t border-gray-800 text-[10px] text-gray-600 flex justify-between items-center">
                <span>Showing {filteredMessages.length} events • Session: {window.crypto.randomUUID().slice(0, 8)}</span>
                <div className="flex gap-4">
                    <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div> Thought</span>
                    <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-green-500"></div> Info</span>
                    <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-red-500"></div> Error</span>
                </div>
            </div>
        </div>
    );
}
