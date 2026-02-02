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

import unittest
from agent.core.net_utils import check_ssl_error, SSL_ERROR_MESSAGE

class TestNetUtils(unittest.TestCase):
    def test_check_ssl_error_matches(self):
        # Create exceptions that simulate real SSL errors
        exceptions = [
            Exception("Simulated CERTIFICATE_VERIFY_FAILED error"),
            Exception("requests.exceptions.SSLError: HTTPSConnectionPool... sslyze SSLCertVerificationError"),
            Exception("urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:1007)>")
        ]
        
        for e in exceptions:
            msg = check_ssl_error(e, url="example.com")
            self.assertIsNotNone(msg)
            self.assertIn(SSL_ERROR_MESSAGE, msg)
            self.assertIn("example.com", msg)

    def test_check_ssl_error_no_match(self):
        # Exceptions that are NOT SSL errors
        exceptions = [
            Exception("Http Error 404: Not Found"),
            Exception("ConnectionTimeout"),
            Exception("DNS lookup failed"),
            ValueError("Some other error")
        ]
        
        for e in exceptions:
            msg = check_ssl_error(e, url="example.com")
            self.assertIsNone(msg)

if __name__ == "__main__":
    unittest.main()
