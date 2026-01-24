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

/**
 * AudioWorklet processor for downsampling audio to 16kHz PCM.
 * Runs in a separate thread to maintain <20ms latency requirement.
 */
class AudioDownsamplerProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.targetSampleRate = 16000;
        this.buffer = [];
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const inputData = input[0]; // Mono channel
        const inputSampleRate = sampleRate; // Global from AudioWorkletGlobalScope
        const ratio = inputSampleRate / this.targetSampleRate;

        // Simple downsampling (take every Nth sample)
        for (let i = 0; i < inputData.length; i += ratio) {
            this.buffer.push(inputData[Math.floor(i)]);
        }

        // Send chunks of ~100ms (1600 samples at 16kHz)
        while (this.buffer.length >= 1600) {
            const chunk = this.buffer.splice(0, 1600);
            const pcm16 = new Int16Array(chunk.length);

            // Convert float32 [-1, 1] to int16 [-32768, 32767]
            for (let i = 0; i < chunk.length; i++) {
                pcm16[i] = Math.max(-1, Math.min(1, chunk[i])) * 0x7FFF;
            }

            // Transfer ownership for zero-copy
            this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
        }

        return true; // Keep processor alive
    }
}

registerProcessor('audio-downsampler', AudioDownsamplerProcessor);
