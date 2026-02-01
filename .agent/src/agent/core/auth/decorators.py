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

from functools import wraps
import typer
from agent.core.auth.credentials import validate_credentials
from agent.core.auth.errors import MissingCredentialsError

def with_creds(func):
    """
    Decorator to ensure that credentials are set before running a function.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            validate_credentials()
        except MissingCredentialsError as e:
            print(e)
            raise typer.Exit(code=1)
        return func(*args, **kwargs)
    return wrapper
