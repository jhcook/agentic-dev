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
from typing import Optional

logger = logging.getLogger(__name__)

SSL_ERROR_MESSAGE = (
    "❌ SSL Verification Failed.\n"
    "This is likely due to a corporate proxy interfering with the connection.\n"
    "ACTION REQUIRED: Ensure the target domain is whitelisted in your proxy configuration "
    "or install the proxy's CA certificate locally."
)

def check_ssl_error(e: Exception, url: str = "target") -> Optional[str]:
    """
    Checks if an exception is an SSL verification failure and returns a standardized error message.
    
    Args:
        e: The exception to check.
        url: The URL being accessed (for context).
        
    Returns:
        str: The standardized error message if it's an SSL error, else None.
    """
    error_str = str(e)
    
    # Common SSL error indicators across libraries (urllib, requests, httpx)
    ssl_indicators = [
        "CERTIFICATE_VERIFY_FAILED",
        "SSLCertVerificationError", 
        "SSLError",
        "certificate verify failed"
    ]
    
    if any(indicator in error_str for indicator in ssl_indicators):
        msg = f"{SSL_ERROR_MESSAGE}\nTarget: {url}"
        return msg
        
    return None
