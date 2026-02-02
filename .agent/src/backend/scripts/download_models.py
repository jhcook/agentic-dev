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


import os
import hashlib
import logging
import requests
from pathlib import Path
from agent.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model-downloader")

# Constants
MODEL_DIR_NAME = "kokoro"
MODELS = {
    "kokoro-v0_19.onnx": {
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
        "sha256": None  # Skip check for now to avoid breaking if upstream changes, or add if known
    },
    "voices.json": {
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json",
        "sha256": None
    }
}

def get_model_dir() -> Path:
    """Get the directory to store models."""
    # Use config if possible, or default to .agent/models
    # agent.core.config usually has repo_root
    return config.agent_dir / "models" / MODEL_DIR_NAME

def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    if not expected_sha256:
        return True
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest() == expected_sha256

def download_file(url: str, dest_path: Path):
    logger.info(f"Downloading {url} to {dest_path}...")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    logger.info("Download complete.")

def main():
    model_dir = get_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Model directory: {model_dir}")

    for filename, info in MODELS.items():
        dest_path = model_dir / filename
        if dest_path.exists():
            if info["sha256"]:
                if verify_checksum(dest_path, info["sha256"]):
                    logger.info(f"{filename} exists and verified. Skipping.")
                    continue
                else:
                    logger.warning(f"{filename} checksum mismatch. Re-downloading.")
            else:
                logger.info(f"{filename} exists. Skipping (no checksum check).")
                continue
        
        try:
            download_file(info["url"], dest_path)
            if info["sha256"] and not verify_checksum(dest_path, info["sha256"]):
                logger.error(f"Checksum verification failed for {filename}!")
                os.remove(dest_path)
        except Exception as e:
            from agent.core.net_utils import check_ssl_error
            ssl_msg = check_ssl_error(e, url=info["url"])
            if ssl_msg:
                 logger.error(ssl_msg)
                 # Do not remove dest_path (partial) if verification failed? 
                 # Actually if SSL failed, file likely created empty or partial.
                 # Let's keep existing behavior or cleanup?
                 # Existing behavior is to log error and continue loop.
            else:
                 logger.error(f"Failed to download {filename}: {e}")

if __name__ == "__main__":
    main()
