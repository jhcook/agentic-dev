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

import { useState, useEffect } from 'react';
import { Save, FileText, Check, AlertCircle, Loader2 } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function PromptStudio() {
    const [prompts, setPrompts] = useState<string[]>([]);
    const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

    useEffect(() => {
        async function fetchPrompts() {
            try {
                const res = await fetch('/api/admin/prompts');
                const data = await res.json();
                setPrompts(data);
                if (data.length > 0) {
                    handleSelect(data[0]);
                }
            } catch (err) {
                console.error('Failed to fetch prompts:', err);
            } finally {
                setLoading(false);
            }
        }
        fetchPrompts();
    }, []);

    const handleSelect = async (filename: string) => {
        setSelectedPrompt(filename);
        setLoading(true);
        try {
            const res = await fetch(`/api/admin/prompts/${filename}`);
            const data = await res.json();
            setContent(data.content);
        } catch (err) {
            console.error('Failed to fetch prompt content:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!selectedPrompt) return;
        setSaving(true);
        setStatus('idle');
        try {
            const res = await fetch(`/api/admin/prompts/${selectedPrompt}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content }),
            });
            if (!res.ok) throw new Error('Save failed');
            setStatus('success');
            setTimeout(() => setStatus('idle'), 3000);
        } catch (err) {
            console.error('Save failed:', err);
            setStatus('error');
        } finally {
            setSaving(false);
        }
    };

    if (loading && prompts.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 className="animate-spin mr-2" />
                Loading prompts...
            </div>
        );
    }

    return (
        <div className="flex h-screen bg-gray-900 overflow-hidden">
            {/* Sidebar List */}
            <div className="w-64 border-r border-gray-800 bg-gray-900/50 flex flex-col">
                <div className="p-4 border-b border-gray-800">
                    <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">System Personas</h2>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {prompts.map((p) => (
                        <button
                            key={p}
                            onClick={() => handleSelect(p)}
                            className={cn(
                                "w-full flex items-center gap-3 px-4 py-3 text-sm transition-colors border-l-2",
                                selectedPrompt === p
                                    ? "bg-blue-600/10 border-blue-500 text-blue-400"
                                    : "border-transparent text-gray-400 hover:bg-gray-800 hover:text-gray-300"
                            )}
                        >
                            <FileText size={16} />
                            <span className="truncate">{p.replace('.txt', '')}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Main Editor */}
            <div className="flex-1 flex flex-col bg-gray-950">
                <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h1 className="text-lg font-bold text-white">Prompt Studio</h1>
                        {selectedPrompt && (
                            <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded-full border border-gray-700">
                                {selectedPrompt}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-4">
                        {status === 'success' && (
                            <span className="text-green-500 text-sm flex items-center gap-1">
                                <Check size={16} /> Persona Saved
                            </span>
                        )}
                        {status === 'error' && (
                            <span className="text-red-500 text-sm flex items-center gap-1">
                                <AlertCircle size={16} /> Failed to save
                            </span>
                        )}
                        <button
                            onClick={handleSave}
                            disabled={saving || !selectedPrompt}
                            className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded-md text-sm font-semibold transition-all shadow-md active:scale-95"
                        >
                            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                            Save Persona
                        </button>
                    </div>
                </div>

                <div className="flex-1 p-6 flex flex-col">
                    {selectedPrompt ? (
                        <>
                            <div className="mb-4 flex items-start gap-3 p-3 bg-blue-900/10 border border-blue-800/30 rounded-lg text-xs text-blue-300/80">
                                <AlertCircle size={16} className="shrink-0 text-blue-500" />
                                <p>
                                    System prompts define the agent's core behavior, tone, and constraints.
                                    Changes are applied to <strong>new</strong> conversation turns immediately.
                                </p>
                            </div>
                            <textarea
                                value={content}
                                onChange={(e) => setContent(e.target.value)}
                                className="flex-1 w-full bg-black/40 border border-gray-800 rounded-lg p-6 text-gray-300 font-mono text-sm leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all placeholder-gray-700 shadow-inner"
                                placeholder="Enter system prompt instructions here..."
                                disabled={loading}
                            />
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-gray-600">
                            <FileText size={48} className="mb-4 opacity-20" />
                            <p>Select a persona from the sidebar to start editing</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
