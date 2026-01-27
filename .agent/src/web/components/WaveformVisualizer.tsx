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
    analyserRef: React.RefObject<AnalyserNode | null>;
    isActive: boolean;
}

export function WaveformVisualizer({ analyserRef, isActive }: WaveformVisualizerProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const animationFrameRef = useRef<number | null>(null);

    useEffect(() => {
        if (!canvasRef.current || !containerRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d', { alpha: false })!; // Optimization: no alpha where possible

        const resize = () => {
            if (containerRef.current) {
                canvas.width = containerRef.current.clientWidth * window.devicePixelRatio;
                canvas.height = containerRef.current.clientHeight * window.devicePixelRatio;
            }
        };

        window.addEventListener('resize', resize);
        resize();

        // Persistent data array for frequencies
        const dataArray = new Uint8Array(1024); // Matches 2048 fftSize

        const draw = () => {
            const width = canvas.width;
            const height = canvas.height;

            // Clear background
            ctx.fillStyle = '#121216';
            ctx.fillRect(0, 0, width, height);

            const analyser = analyserRef.current;

            if (analyser && isActive) {
                analyser.getByteFrequencyData(dataArray);

                // Focus on frequencies up to ~10kHz (roughly 40% of the 24kHz window)
                const zoomFactor = 0.4;
                const dataLen = Math.floor(dataArray.length * zoomFactor);

                const barWidth = 6 * window.devicePixelRatio;
                const gap = 3 * window.devicePixelRatio;
                const numBars = Math.floor(width / (barWidth + gap));

                const segmentHeight = 3 * window.devicePixelRatio;
                const segmentGap = 1.5 * window.devicePixelRatio;
                const numSegments = Math.floor(height / (segmentHeight + segmentGap));

                for (let i = 0; i < numBars; i++) {
                    const dataIdx = Math.floor((i / numBars) * dataLen);
                    const val = dataArray[dataIdx] / 255.0;

                    const activeSegments = Math.floor(val * numSegments);
                    const x = i * (barWidth + gap);

                    for (let j = 0; j < numSegments; j++) {
                        const y = height - (j + 1) * (segmentHeight + segmentGap);

                        const ratio = j / numSegments;
                        let color = '#22c55e'; // Green-500
                        if (ratio > 0.8) color = '#ef4444'; // Red-500
                        else if (ratio > 0.6) color = '#eab308'; // Yellow-500

                        if (j < activeSegments) {
                            ctx.fillStyle = color;
                        } else {
                            ctx.fillStyle = 'rgba(30, 41, 59, 0.3)';
                        }

                        ctx.fillRect(x, y, barWidth, segmentHeight);
                    }
                }
            } else {
                // Dim "quiet" state with a simple line
                ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0, height - 10);
                ctx.lineTo(width, height - 10);
                ctx.stroke();
            }

            animationFrameRef.current = requestAnimationFrame(draw);
        };

        draw();

        return () => {
            window.removeEventListener('resize', resize);
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [analyserRef, isActive]); // Only rerun if analyser target changes (rare) or isActive toggle

    return (
        <div ref={containerRef} className="w-full h-full">
            <canvas
                ref={canvasRef}
                className="w-full h-full"
                aria-label="Audio frequency visualizer"
            />
        </div>
    );
}
