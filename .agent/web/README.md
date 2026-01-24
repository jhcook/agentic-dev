# Agentic Dev - Web Client

This is the React-based management console for the Agentic development platform.

## Features

- **Management Console**: Monitor and control agent processes.
- **Voice Client**: Real-time bidirectional voice interface with barge-in support.

## Voice Client

The Voice Client provides a visual interface for talking to the agent.

### Key Capabilities

- **Real-time Waveform**: Visual feedback for input and output audio.
- **Barge-in (Interrupts)**: Speak over the agent to stop it immediately.
- **Low Latency**: Uses `AudioWorklet` for micro-second processing.

### Browser Compatibility

- **Chrome 66+** (Required for AudioWorklet)
- **Firefox 76+**
- **Safari 14.1+**

### Setup & Running

1. **Ensure Backend is running**:

    ```bash
    agent admin start
    ```

2. **Start Web Client**:

    ```bash
    cd .agent/web
    npm run dev
    ```

3. **Access**: Navigate to `http://localhost:8080`.
4. **Permission**: Click "Enable Microphone" and grant browser permissions.

## Development

### Tech Stack

- **React 18**
- **TypeScript**
- **Vite**
- **TailwindCSS**

### Commands

- `npm run dev`: Start development server.
- `npm run build`: Build for production.
- `npm run lint`: Run ESLint.
- `npm run preview`: Preview production build.
