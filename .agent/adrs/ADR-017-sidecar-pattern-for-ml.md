# ADR-017: Sidecar Pattern for ML Inference

## Status
Accepted

## Context
The main backend service runs on Python 3.14, which currently has compatibility issues with the required ONNX Runtime libraries needed for the AI Room Suggestions feature. We need a way to run the ML inference without downgrading or destabilizing the main backend.

## Decision
We will implement a **Sidecar Pattern** by deploying a separate, lightweight service (`inspected-inference`) dedicated to hosting the ML model and running inference.

- **Stack**: Python 3.11 (or compatible version), FastAPI, ONNX Runtime.
- **Communication**: REST API (Synchronous) over local network (or private VPC). The main backend will act as a gateway/proxy.
- **Scope**: Strictly limited to stateless inference tasks.

## Consequences
### Positive
- **Isolation**: ML dependencies do not pollute the main backend.
- **Scalability**: The inference service can be scaled independently based on CPU/GPU load.
- **Stability**: Crashes or memory leaks in the ML runtime will not bring down the core API.

### Negative
- **Complexity**: Adds another container/service to manage and deploy.
- **Latency**: Introduces a small network hop overhead (mitigated by local networking).
