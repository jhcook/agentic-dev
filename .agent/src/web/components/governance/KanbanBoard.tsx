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

import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    type DragEndEvent,
    useDroppable
} from '@dnd-kit/core';
import {
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface Artifact {
    id: string;
    type: string;
    title: string;
    status: string;
}

interface KanbanBoardProps {
    artifacts: Artifact[];
    onStatusChange: (id: string, newStatus: string) => void;
}

function SortableItem({ id, title }: { id: string, title: string, type: string }) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
    } = useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    return (
        <div ref={setNodeRef} style={style} {...attributes} {...listeners} className="bg-gray-800 p-3 rounded mb-2 border border-gray-700 hover:border-blue-500 cursor-grab active:cursor-grabbing">
            <div className="flex justify-between items-start">
                <span className="font-medium text-sm text-gray-200">{title}</span>
                <span className="text-[10px] uppercase bg-gray-700 px-1.5 py-0.5 rounded text-gray-400">{id}</span>
            </div>
        </div>
    );
}

function Column({ id, title, items }: { id: string, title: string, items: Artifact[] }) {
    const { setNodeRef } = useDroppable({
        id: id,
    });

    return (
        <div ref={setNodeRef} className="flex-1 bg-gray-900/50 rounded-lg p-4 border border-gray-800 min-h-[400px]">
            <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase tracking-wider">{title} <span className="text-gray-600">({items.length})</span></h3>
            <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
                {items.map(item => (
                    <SortableItem key={item.id} id={item.id} title={item.title} type={item.type} />
                ))}
            </SortableContext>
            {items.length === 0 && <div className="text-center text-gray-700 text-xs py-10 border-2 border-dashed border-gray-800 rounded">No Items</div>}
        </div>
    );
}

export function KanbanBoard({ artifacts, onStatusChange }: KanbanBoardProps) {
    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const normalizeStatus = (s: string) => s.toUpperCase().trim();

    const openItems = artifacts.filter(a => {
        const s = normalizeStatus(a.status);
        return s === 'OPEN' || s === 'DRAFT' || s === 'UNKNOWN';
    });

    const plannedItems = artifacts.filter(a => {
        const s = normalizeStatus(a.status);
        return s === 'PLANNED' || s === 'PROPOSED' || s === 'IN_PROGRESS';
    });

    const committedItems = artifacts.filter(a => {
        const s = normalizeStatus(a.status);
        return s === 'COMMITTED' || s === 'ACCEPTED' || s === 'IMPLEMENTED' || s === 'DONE';
    });

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (!over) return;

        // Find which column the item was dropped into
        // The Droppable ID corresponds to the status
        const status = over.id as string;

        // Find the item
        const item = artifacts.find(a => a.id === active.id);

        if (item && item.status !== status) {
            onStatusChange(item.id, status);
        }
    };

    return (
        <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
        >
            <div className="flex gap-6 h-full overflow-x-auto pb-4">
                <Column id="OPEN" title="Open / Draft" items={openItems} />
                <Column id="PROPOSED" title="Proposed / Planned" items={plannedItems} />
                <Column id="ACCEPTED" title="Committed / Accepted" items={committedItems} />
            </div>
        </DndContext>
    );
}
