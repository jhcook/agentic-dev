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

import { useEffect, useRef } from 'react';

interface WaveformVisualizerProps {
    audioData: Float32Array | null;
    isActive: boolean;
}

export function WaveformVisualizer({ audioData, isActive }: WaveformVisualizerProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationFrameRef = useRef<number | null>(null);

    useEffect(() => {
        if (!canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d')!;
        const { width, height } = canvas;

        const draw = () => {
            // Clear
            ctx.fillStyle = '#1f2937'; // dark:bg-gray-800
            ctx.fillRect(0, 0, width, height);

            if (audioData && audioData.length > 0) {
                // Draw waveform
                ctx.strokeStyle = isActive ? '#3b82f6' : '#6b7280'; // blue-500 or gray-500
                ctx.lineWidth = 2;
                ctx.beginPath();

                const step = Math.ceil(audioData.length / width);
                const amp = height / 2;

                for (let i = 0; i < width; i++) {
                    const slice = audioData.slice(i * step, (i + 1) * step);
                    if (slice.length === 0) continue;

                    const min = Math.min(...Array.from(slice));
                    const max = Math.max(...Array.from(slice));

                    ctx.moveTo(i, (1 + min) * amp);
                    ctx.lineTo(i, (1 + max) * amp);
                }

                ctx.stroke();
            } else {
                // Draw center line when no audio
                ctx.strokeStyle = '#374151'; // gray-700
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0, height / 2);
                ctx.lineTo(width, height / 2);
                ctx.stroke();
            }

            animationFrameRef.current = requestAnimationFrame(draw);
        };

        draw();

        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [audioData, isActive]);

    return (
        <canvas
            ref={canvasRef}
            width={800}
            height={200}
            className="w-full h-48 bg-gray-800 rounded-lg"
            aria-label="Audio waveform visualization"
        />
    );
}
