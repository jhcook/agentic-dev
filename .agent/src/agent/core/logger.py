import logging
from pathlib import Path

# Configure default logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler(sys.stdout) # Don't log to stdout as it interferes with pipeable output
    ]
)

# Create a custom logger
logger = logging.getLogger("agent")

# Add file handler if needed (e.g. to .agent/logs/agent.log)
log_dir = Path(".agent/logs")
log_dir.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_dir / "agent.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def get_logger(name: str):
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"agent.{name}")
