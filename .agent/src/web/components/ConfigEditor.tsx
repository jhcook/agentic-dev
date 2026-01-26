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
import { useForm } from 'react-hook-form';
import { Save, RefreshCcw, AlertTriangle } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface SchemaProperty {
    type?: string;
    title?: string;
    description?: string;
    default?: unknown;
    enum?: string[];
    properties?: Record<string, SchemaProperty>;
    $ref?: string;
}

interface ConfigSchema {
    title: string;
    properties: Record<string, SchemaProperty>;
    $defs?: Record<string, SchemaProperty>;
}

export function ConfigEditor() {
    const [schema, setSchema] = useState<ConfigSchema | null>(null);
    const [loading, setLoading] = useState(true);
    const [status, setStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

    const { register, handleSubmit, reset } = useForm();

    useEffect(() => {
        async function fetchData() {
            try {
                const [schemaRes, configRes] = await Promise.all([
                    fetch('/api/admin/config/schema'),
                    fetch('/api/admin/config/voice'),
                ]);

                const schemaData = await schemaRes.json();
                const configData = await configRes.json();

                setSchema(schemaData);
                reset(configData);
            } catch (err) {
                console.error('Failed to fetch config:', err);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [reset]);

    const onSubmit = async (data: Record<string, unknown>) => {
        setStatus('saving');
        try {
            const res = await fetch('/api/admin/config/voice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (!res.ok) throw new Error('Save failed');
            setStatus('success');
            setTimeout(() => setStatus('idle'), 3000);
        } catch (err) {
            console.error('Save failed:', err);
            setStatus('error');
        }
    };

    if (loading || !schema) {
        return (
            <div className="p-8 flex items-center justify-center text-gray-400">
                <RefreshCcw className="animate-spin mr-2" />
                Loading configuration...
            </div>
        );
    }

    const resolveRef = (ref: string) => {
        const key = ref.split('/').pop()!;
        return schema.$defs?.[key];
    };

    const renderField = (name: string, prop: SchemaProperty, path: string = '') => {
        const fullPath = path ? `${path}.${name}` : name;

        // Resolve $ref if present
        const actualProp = prop.$ref ? resolveRef(prop.$ref) : prop;
        if (!actualProp) return null;

        if (actualProp.type === 'object' && actualProp.properties) {
            return (
                <div key={fullPath} className="mb-8 border-l-2 border-gray-700 pl-4">
                    <h3 className="text-lg font-semibold text-white mb-2 capitalize">{actualProp.title || name}</h3>
                    <p className="text-sm text-gray-500 mb-4">{actualProp.description}</p>
                    <div className="space-y-4">
                        {Object.entries(actualProp.properties).map(([subKey, subProp]) =>
                            renderField(subKey, subProp, fullPath)
                        )}
                    </div>
                </div>
            );
        }

        return (
            <div key={fullPath} className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-300 capitalize">
                    {actualProp.title || name}
                </label>
                {actualProp.enum ? (
                    <select
                        {...register(fullPath)}
                        className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        {actualProp.enum.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                        ))}
                    </select>
                ) : (
                    <input
                        type={actualProp.type === 'number' ? 'number' : 'text'}
                        step={actualProp.type === 'number' ? '0.1' : undefined}
                        {...register(fullPath)}
                        className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                )}
                <p className="text-xs text-gray-500">{actualProp.description}</p>
            </div>
        );
    };

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white">Advanced Configuration</h1>
                    <p className="text-gray-400 mt-1">Manage STT, TTS, and LLM providers for the Voice Agent.</p>
                </div>
                <button
                    onClick={handleSubmit(onSubmit)}
                    disabled={status === 'saving'}
                    className={cn(
                        "flex items-center gap-2 px-6 py-2 rounded-lg font-semibold transition-all shadow-lg",
                        status === 'saving' ? "bg-gray-700 cursor-not-allowed" :
                            status === 'success' ? "bg-green-600 text-white" :
                                status === 'error' ? "bg-red-600 text-white" :
                                    "bg-blue-600 hover:bg-blue-700 text-white active:scale-95"
                    )}
                >
                    {status === 'saving' ? <RefreshCcw className="animate-spin" size={18} /> :
                        status === 'success' ? "Saved!" :
                            status === 'error' ? "Error!" :
                                <Save size={18} />}
                    {status === 'idle' && "Save Configuration"}
                </button>
            </div>

            <div className="bg-gray-800/50 rounded-xl border border-gray-700 p-6 backdrop-blur-sm">
                <form className="space-y-6">
                    {Object.entries(schema.properties).map(([name, prop]) =>
                        renderField(name, prop)
                    )}
                </form>
            </div>

            <div className="mt-8 flex items-start gap-3 p-4 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-200/80 text-sm">
                <AlertTriangle size={20} className="shrink-0 text-yellow-500" />
                <p>
                    <strong>Warning:</strong> Changes are applied immediately to the agent's hot-runtime.
                    Ensure providers and API keys are correctly configured before saving.
                </p>
            </div>
        </div>
    );
}
