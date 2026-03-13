# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Telemetry instrumentation for verification workflows.

Follows ADR-058: Telemetry and Instrumentation Schema.
"""

import time
from typing import Dict, Any
from opentelemetry import trace, metrics
from agent.core.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

duration_histogram = meter.create_histogram(
    "verification.execution_duration_ms",
    description="Total execution time for the verification workflow",
    unit="ms"
)

class VerificationTelemetry:
    """Helper to track and emit verification metrics."""
    
    def __init__(self, workflow_type: str):
        """
        Initialize telemetry tracker.
        
        Args:
            workflow_type: The type of verification.
        """
        self.workflow_type = workflow_type
        self.start_time = 0.0
        
    def start(self) -> None:
        """Start tracking duration."""
        self.start_time = time.perf_counter()
        
    def emit(self, status: str, metadata: Dict[str, Any] = None) -> None:
        """
        Emit metrics to OpenTelemetry.
        
        Args:
            status: Final status ('Success', 'Failed').
            metadata: Additional non-PII attributes.
        """
        if metadata is None:
            metadata = {}
            
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        attributes = {
            "workflow_type": self.workflow_type,
            "status": status,
            **metadata
        }
        
        duration_histogram.record(duration_ms, attributes)
        
        logger.info(
            "Verification telemetry emitted",
            extra={
                "duration_ms": duration_ms,
                "status": status,
                "workflow": self.workflow_type
            }
        )
