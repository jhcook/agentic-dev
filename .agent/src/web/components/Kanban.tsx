
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

import { useEffect, useState } from 'react';

interface Story {
    id: string;
    title: string;
    status: string;
}

const COLUMNS = ['DRAFT', 'IN_PROGRESS', 'REVIEW', 'COMMITTED'];

export function Kanban() {
    const [stories, setStories] = useState<Story[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStories = async () => {
            try {
                const res = await fetch('/api/dashboard/stories');
                if (res.ok) {
                    const data = await res.json();
                    setStories(data);
                }
            } catch (error) {
                console.error("Failed to fetch stories", error);
            } finally {
                setLoading(false);
            }
        };
        fetchStories();
    }, []);

    if (loading) return <div className="p-8 text-gray-400">Loading board...</div>;

    return (
        <div className="p-8 h-full flex flex-col">
            <header className="mb-6">
                <h2 className="text-3xl font-bold text-white mb-2">Kanban Board</h2>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                    <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-gray-500"></span> Draft
                    </span>
                    <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-blue-500"></span> In Progress
                    </span>
                    <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-yellow-500"></span> Review
                    </span>
                    <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-green-500"></span> Committed
                    </span>
                </div>
            </header>

            <div className="flex-1 grid grid-cols-4 gap-6 min-h-0 overflow-x-auto pb-4">
                {COLUMNS.map(column => (
                    <div key={column} className="bg-gray-800/50 rounded-xl border border-gray-700 flex flex-col h-full max-h-full">
                        <div className="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800 rounded-t-xl sticky top-0">
                            <h3 className="font-semibold text-gray-300">{column}</h3>
                            <span className="bg-gray-700 text-gray-400 text-xs px-2 py-1 rounded-full">
                                {stories.filter(s => s.status.toUpperCase() === column).length}
                            </span>
                        </div>
                        <div className="p-4 space-y-3 overflow-y-auto flex-1 custom-scrollbar">
                            {stories
                                .filter(s => s.status.toUpperCase() === column)
                                .map(story => (
                                    <div key={story.id} className="bg-gray-700 p-4 rounded-lg border border-gray-600 shadow-sm hover:border-blue-500 transition-colors cursor-pointer group">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="text-xs font-mono text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded">
                                                {story.id}
                                            </span>
                                        </div>
                                        <h4 className="text-sm font-medium text-gray-200 leading-snug group-hover:text-white">
                                            {story.title}
                                        </h4>
                                    </div>
                                ))}
                            {stories.filter(s => s.status.toUpperCase() === column).length === 0 && (
                                <div className="text-center py-8 text-gray-600 text-sm border-2 border-dashed border-gray-700 rounded-lg">
                                    Empty
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
