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

import dagre from 'dagre';
import { useCallback, useEffect } from 'react';
import ReactFlow, {
    useNodesState,
    useEdgesState,
    addEdge,
    type Connection,
    type Node,
    type Edge,
    type NodeProps,
    Handle,
    Position,
    MarkerType,
    Controls,
    Background,
    MiniMap
} from 'reactflow';
import 'reactflow/dist/style.css';

// Types matching backend Pydantic models




interface EstateGraphProps {
    isActive: boolean;
}

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 172;
const nodeHeight = 36;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
    const isHorizontal = direction === 'LR';
    dagreGraph.setGraph({
        rankdir: direction,
        ranksep: 80,  // Increase vertical spacing (default 50)
        nodesep: 50,  // Increase horizontal spacing (default 50)
        edgesep: 10,  // Separate edges
        ranker: 'longest-path' // Tries to minimize edge length, good for hierarchy
    });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        // Color-code edges based on relationship
        const sourceNode = nodes.find(n => n.id === edge.source);
        const targetNode = nodes.find(n => n.id === edge.target);

        let edgeColor = '#555'; // Default gray

        if (sourceNode && targetNode) {
            const sType = sourceNode.data?.type?.toLowerCase();
            const tType = targetNode.data?.type?.toLowerCase();

            if (sType === 'story' && tType === 'runbook') edgeColor = '#8b5cf6'; // Purple
            if (sType === 'plan' && tType === 'story') edgeColor = '#3b82f6'; // Blue
            if (sType === 'plan' && tType === 'adr') edgeColor = '#f59e0b'; // Amber
            if (sType === 'adr') edgeColor = '#f59e0b'; // ADR outgoing also Amber
        }

        edge.style = { stroke: edgeColor, strokeWidth: 2 };
        edge.markerEnd = {
            type: MarkerType.ArrowClosed,
            color: edgeColor,
        };

        dagreGraph.setEdge(edge.source, edge.target);
    });

    // Enforce Hierarchy via "invisible" constraints or by leveraging dagre's rank
    // Plan -> ADR -> Story -> Runbook
    // We can't set rank directly on node in dagre easily without using 'ordering'
    // But we can add invisible edges or rely on logic.
    // 
    // Better Approach: 
    // 1. Separate nodes by type
    // 2. Add edges from all Plans to all ADRs (invisible)?
    // 
    // Actually, simply adding constraints to the graph structure works best.

    // Let's modify the graph logic to force ranks if possible. 
    // Since dagre doesn't support explicit rank assignment easily in this interface,
    // we will sort them by Y-coordinate POST-layout or PRE-layout?
    //
    // Alternative: We manually set the Y coordinate based on type!
    // And let dagre only solve X.

    // However, dagre.layout() overwrites x and y.

    // Let's rely on adding High-Level constraint edges for the hierarchy
    // Plan -> ADR
    // ADR -> Story
    // Story -> Runbook

    // We will add these as "weight: 0, minlen: 1" edges to the dagre graph,
    // but not return them to ReactFlow.

    const types = ['plan', 'adr', 'story', 'runbook'];

    nodes.forEach(nodeA => {
        const typeA = nodeA.data?.type?.toLowerCase();
        const rankA = types.indexOf(typeA);

        if (rankA === -1) return;

        // Find next level nodes and link them to force hierarchy
        if (rankA < types.length - 1) {
            // Just linking to *any* node of next rank is messy.
            // Instead, let's just use the natural edges and assume the user links them correctly?
            // The user said: "They should all be linked accordingly".
            // If links fail, we can force it.
        }
    });

    // Strategy 2: Grouping (Compound Graph).
    // Too complex for now.

    // Strategy 3: Just run layout, then OVERRIDE Y-position based on Type!
    // This is the cleanest for "Layers".

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);

        // Hierarchical Override
        let forcedY = nodeWithPosition.y;
        const type = node.data?.type?.toLowerCase();

        if (direction === 'TB') {
            const layerHeight = 150; // Gap between layers
            if (type === 'plan') forcedY = 0;
            if (type === 'adr') forcedY = 1 * layerHeight;
            if (type === 'story') forcedY = 2 * layerHeight;
            if (type === 'runbook') forcedY = 3 * layerHeight;

            // We keep the X from dagre (optimization), but force Y to layer.
            node.position = {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: forcedY
            };
        } else {
            // Default behavior for LR or other
            node.position = {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            };
        }

        node.targetPosition = isHorizontal ? Position.Left : Position.Top;
        node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;

        return node;
    });

    return { nodes, edges };
};

const nodeTypes = {
    custom: CustomNode,
};

function CustomNode({ data }: NodeProps) {
    let borderColor = 'border-gray-500';
    let bgColor = 'bg-gray-800';

    switch (data.type?.toLowerCase()) {
        case 'story':
            borderColor = 'border-blue-500';
            bgColor = 'bg-blue-900/50';
            break;
        case 'plan':
            borderColor = 'border-green-500';
            bgColor = 'bg-green-900/50';
            break;
        case 'runbook':
            borderColor = 'border-purple-500';
            bgColor = 'bg-purple-900/50';
            break;
        case 'adr':
            borderColor = 'border-amber-500';
            bgColor = 'bg-amber-900/50';
            break;
    }

    return (
        <div className={`px-4 py-2 shadow-md rounded-md border-2 ${borderColor} ${bgColor} min-w-[150px]`}>
            <Handle type="target" position={Position.Top} className="w-16 !bg-gray-500" />
            <div className="flex flex-col">
                <div className="text-xs font-bold text-gray-300 uppercase">{data.type}</div>
                <div className="text-sm font-bold text-white">{data.label}</div>
                <div className="text-[10px] text-gray-400">{data.status}</div>
            </div>
            <Handle type="source" position={Position.Bottom} className="w-16 !bg-gray-500" />
        </div>
    );
}

export function EstateGraph({ nodes: initialNodes, edges: initialEdges }: EstateGraphProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
            initialNodes,
            initialEdges
        );
        setNodes([...layoutedNodes]);
        setEdges([...layoutedEdges]);
    }, [initialNodes, initialEdges, setNodes, setEdges]);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    return (
        <div className="h-[600px] bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
            >
                <Background color="#333" gap={16} />
                <Controls className="bg-gray-800 border-gray-700 fill-gray-200" />
                <MiniMap
                    nodeColor={(n) => {
                        if (n.data?.type === 'story') return '#3b82f6';
                        if (n.data?.type === 'plan') return '#10b981';
                        if (n.data?.type === 'runbook') return '#8b5cf6';
                        if (n.data?.type === 'adr') return '#f59e0b';
                        return '#eee';
                    }}
                    style={{ backgroundColor: '#111' }}
                />
            </ReactFlow>
        </div>
    );
}
