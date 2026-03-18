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

import logging

# Suppress noisy third-party loggers at module level — before any model can load.
# configure_logging() reinforces this, but the model may load before the CLI
# parses verbosity flags, so we must act at import time too.
for _noisy in (
    "huggingface_hub",
    "sentence_transformers",
    "transformers",
    "transformers.modeling_utils",
    "transformers.trainer",
    "transformers.utils",
):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

# transformers ships its own logging wrapper (transformers.utils.logging) which is
# independent of Python's logging hierarchy — setLevel above does not reach it.
# Must use the library's own API to suppress the "layers were not sharded" noise.
try:
    import transformers as _transformers
    _transformers.logging.set_verbosity_error()
except Exception:
    pass
try:
    import sentence_transformers as _st  # noqa: F401
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
except Exception:
    pass



# Configure default logging (Default to WARNING to be quiet)
# We do NOT call basicConfig here to avoid side effects on import.
# Instead, we provide a setup function.

_BASE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_TRACE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [trace_id=%(trace_id)s span_id=%(span_id)s] - %(message)s'


class OTelFilter(logging.Filter):
    """Inject OpenTelemetry trace context into log records.

    Sets ``has_trace``, ``trace_id``, and ``span_id`` on every record so
    the :class:`TraceAwareFormatter` can decide whether to render them.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                record.trace_id = trace.format_trace_id(ctx.trace_id)
                record.span_id = trace.format_span_id(ctx.span_id)
                record.has_trace = True
            else:
                record.trace_id = ""
                record.span_id = ""
                record.has_trace = False
        except ImportError:
            record.trace_id = ""
            record.span_id = ""
            record.has_trace = False
        return True


class TraceAwareFormatter(logging.Formatter):
    """Conditionally include trace context in log output.

    When an active OpenTelemetry span is recording, the formatter appends
    ``[trace_id=... span_id=...]`` to the log line. Otherwise, the trace
    fields are omitted entirely to keep logs clean.
    """

    def __init__(self, datefmt: str | None = None) -> None:
        # Initialise with the base format; we swap dynamically in format()
        super().__init__(fmt=_BASE_FORMAT, datefmt=datefmt)
        self._trace_formatter = logging.Formatter(fmt=_TRACE_FORMAT, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        if getattr(record, 'has_trace', False):
            return self._trace_formatter.format(record)
        return super().format(record)


# Guard flag to prevent adding duplicate file handlers.
_file_handler_added = False


def configure_logging(verbosity: int = 0) -> None:
    """
    Configure logging based on verbosity level.

    0 = WARNING (default)
    1 = INFO (-v)
    2 = DEBUG (Agent DEBUG, Libraries WARNING) (-vv)
    3 = DEBUG (Full DEBUG) (-vvv)
    """
    # Default: Root WARNING
    root_level = logging.WARNING
    agent_level = logging.WARNING
    
    if verbosity == 1:
        # -v: Agent INFO, Root WARNING
        agent_level = logging.INFO
    elif verbosity == 2:
        # -vv: Agent DEBUG, Root WARNING (keep libraries quiet)
        agent_level = logging.DEBUG
        root_level = logging.WARNING
    elif verbosity >= 3:
        # -vvv: Everything DEBUG
        agent_level = logging.DEBUG
        root_level = logging.DEBUG

    # Remove existing handlers to avoid duplicates
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(OTelFilter())
    stream_handler.setFormatter(TraceAwareFormatter())

    logging.basicConfig(
        level=root_level,
        handlers=[stream_handler]
    )
    
    # Set Agent level explicitly if different from root
    logging.getLogger("agent").setLevel(agent_level)

    # Lazy file handler: create logs dir and attach handler only when
    # configure_logging is called AND the .agent project directory exists.
    global _file_handler_added
    if not _file_handler_added:
        from agent.core.config import config
        if config.agent_dir.exists():
            log_dir = config.logs_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "agent.log")
            file_handler.setFormatter(TraceAwareFormatter())
            file_handler.addFilter(OTelFilter())
            logging.getLogger("agent").addHandler(file_handler)
            _file_handler_added = True

    # Suppress verbose third-party loggers globally
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    logging.getLogger("backoff").setLevel(logging.ERROR)

# Create a custom logger (no file handler at import time)
logger = logging.getLogger("agent")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"agent.{name}")
