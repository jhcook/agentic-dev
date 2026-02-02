
import React, { useEffect, useState } from 'react';
import { Activity, GitPullRequest, FileText } from 'lucide-react';

interface Stats {
    activeStories: number;
    pendingPRs: number;
    totalADRs: number;
}

interface Story {
    id: string;
    title: string;
    status: string;
}

export function Dashboard() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [activeStories, setActiveStories] = useState<Story[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, storiesRes] = await Promise.all([
                    fetch('/api/dashboard/stats'),
                    fetch('/api/dashboard/stories')
                ]);

                if (statsRes.ok) setStats(await statsRes.json());
                if (storiesRes.ok) {
                    const allStories: Story[] = await storiesRes.json();
                    // Filter for Active Work (IN_PROGRESS, REVIEW)
                    const active = allStories.filter(s =>
                        ['IN_PROGRESS', 'REVIEW'].includes(s.status.toUpperCase())
                    );
                    setActiveStories(active);
                }
            } catch (error) {
                console.error("Failed to fetch dashboard data", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div className="p-8 text-gray-400">Loading dashboard...</div>;

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8">
            <header>
                <h2 className="text-3xl font-bold text-white mb-2">Project Dashboard</h2>
                <p className="text-gray-400">Real-time overview of current development status.</p>
            </header>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Active Stories"
                    value={stats?.activeStories || 0}
                    icon={Activity}
                    color="text-blue-500"
                />
                <StatCard
                    title="Pending PRs"
                    value={stats?.pendingPRs || 0}
                    icon={GitPullRequest}
                    color="text-purple-500"
                />
                <StatCard
                    title="Total ADRs"
                    value={stats?.totalADRs || 0}
                    icon={FileText}
                    color="text-green-500"
                />
            </div>

            {/* Active Work List */}
            <section className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                <div className="p-6 border-b border-gray-700">
                    <h3 className="text-xl font-semibold text-white">Active Work</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-gray-700/50 text-gray-400 text-sm uppercase">
                                <th className="px-6 py-4 font-medium">ID</th>
                                <th className="px-6 py-4 font-medium">Title</th>
                                <th className="px-6 py-4 font-medium">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-700">
                            {activeStories.length === 0 ? (
                                <tr>
                                    <td colSpan={3} className="px-6 py-8 text-center text-gray-500">
                                        No active stories found.
                                    </td>
                                </tr>
                            ) : (
                                activeStories.map(story => (
                                    <tr key={story.id} className="hover:bg-gray-700/30 transition-colors">
                                        <td className="px-6 py-4 text-blue-400 font-mono text-sm">{story.id}</td>
                                        <td className="px-6 py-4 text-gray-200">{story.title}</td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${story.status.toUpperCase() === 'IN_PROGRESS'
                                                    ? 'bg-blue-900/50 text-blue-200'
                                                    : 'bg-yellow-900/50 text-yellow-200'
                                                }`}>
                                                {story.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

function StatCard({ title, value, icon: Icon, color }: { title: string, value: number, icon: any, color: string }) {
    return (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 flex items-center justify-between">
            <div>
                <p className="text-gray-400 text-sm font-medium mb-1">{title}</p>
                <p className="text-4xl font-bold text-white">{value}</p>
            </div>
            <div className={`p-3 rounded-lg bg-gray-700/50 ${color}`}>
                <Icon size={32} />
            </div>
        </div>
    );
}
