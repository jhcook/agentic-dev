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

import { Mic, Settings, Activity, FileText, LayoutDashboard, SquareKanban } from 'lucide-react';
import { useViewStore, type View } from '../store/viewStore';

const navItems: { id: View; label: string; icon: React.ElementType }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'kanban', label: 'Kanban Board', icon: SquareKanban },
    { id: 'voice', label: 'Voice Client', icon: Mic },
    { id: 'config', label: 'Configuration', icon: Settings },
    { id: 'prompts', label: 'Persona Studio', icon: FileText },
    { id: 'governance', label: 'Governance Desk', icon: Activity }, // Activity icon reused or similar
    { id: 'logs', label: 'Activity Log', icon: Activity },
];

export function Navigation() {
    const { activeView, setActiveView } = useViewStore();

    return (
        <nav className="w-64 bg-gray-800 border-r border-gray-700 h-screen flex flex-col">
            <div className="p-6 border-b border-gray-700">
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                    <Activity className="text-blue-500" />
                    Agent Console
                </h1>
            </div>

            <div className="flex-1 overflow-y-auto py-4">
                <ul className="space-y-2 px-3">
                    {navItems.map((item) => (
                        <li key={item.id}>
                            <button
                                onClick={() => setActiveView(item.id)}
                                className={`w-full flex items-center gap-3 px-4 py-2 rounded-lg font-medium transition-colors ${activeView === item.id
                                    ? 'bg-blue-600 text-white'
                                    : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                                    }`}
                            >
                                <item.icon size={20} />
                                {item.label}
                            </button>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="p-4 border-t border-gray-700">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                    <div className="w-2 h-2 rounded-full bg-green-500"></div>
                    Status: Online
                </div>
            </div>
        </nav>
    );
}
