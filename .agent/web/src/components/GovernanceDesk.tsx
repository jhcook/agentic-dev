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
import { KanbanBoard } from './governance/KanbanBoard';
import { EstateGraph } from './governance/EstateGraph';
import { LayoutDashboard, Network, RefreshCcw } from 'lucide-react';
import { cn } from '../lib/utils';

interface Artifact {
    id: string;
    type: string;
    title: string;
    status: string;
    path: string;
    links: string[];
}

export function GovernanceDesk() {
    const [view, setView] = useState<'board' | 'graph'>('board');
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
    const [loading, setLoading] = useState(true);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [artRes, graphRes] = await Promise.all([
                fetch('/api/admin/governance/artifacts'),
                fetch('/api/admin/governance/graph')
            ]);
            setArtifacts(await artRes.json());
            setGraphData(await graphRes.json());
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleStatusChange = async (id: string, newStatus: string) => {
        // Optimistic update
        const prevArtifacts = [...artifacts];
        setArtifacts(prev => prev.map(a => a.id === id ? { ...a, status: newStatus } : a));

        try {
            const res = await fetch(`/api/admin/governance/artifact/${id}/status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });

            if (!res.ok) {
                throw new Error("Failed to persist status");
            }
            console.log(`Updated ${id} to ${newStatus}`);
        } catch (err) {
            console.error("Status update failed:", err);
            // Revert
            setArtifacts(prevArtifacts);
        }
    };

    return (
        <div className="h-full flex flex-col p-6 max-w-[1600px] mx-auto">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <LayoutDashboard className="text-purple-500" />
                        Governance Desk
                    </h1>
                    <p className="text-gray-400 text-sm">Manage the architectural estate.</p>
                </div>

                <div className="flex bg-gray-800 rounded-lg p-1 border border-gray-700">
                    <button
                        onClick={() => setView('board')}
                        className={cn("px-4 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-all",
                            view === 'board' ? "bg-gray-700 text-white shadow" : "text-gray-400 hover:text-white"
                        )}
                    >
                        <LayoutDashboard size={16} /> Board
                    </button>
                    <button
                        onClick={() => setView('graph')}
                        className={cn("px-4 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-all",
                            view === 'graph' ? "bg-gray-700 text-white shadow" : "text-gray-400 hover:text-white"
                        )}
                    >
                        <Network size={16} /> Graph
                    </button>
                </div>

                <button onClick={fetchData} className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 transition-colors">
                    <RefreshCcw size={18} className={cn(loading && "animate-spin")} />
                </button>
            </div>

            <div className="flex-1 min-h-0">
                {loading && artifacts.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-gray-500 animate-pulse">
                        Loading estate...
                    </div>
                ) : (
                    <>
                        {view === 'board' && (
                            <div className="h-full overflow-hidden">
                                <KanbanBoard
                                    artifacts={artifacts.filter(a => a.type === 'story')}
                                    onStatusChange={handleStatusChange}
                                />
                            </div>
                        )}
                        {view === 'graph' && (
                            <EstateGraph nodes={graphData.nodes} edges={graphData.edges} />
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
