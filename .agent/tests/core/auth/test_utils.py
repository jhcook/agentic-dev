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

from agent.core.auth.utils import validate_password_strength

def test_validate_password_strength_valid() -> None:
    is_valid, msg = validate_password_strength("Valid1Password!")
    assert is_valid is True
    assert msg == ""

def test_validate_password_strength_too_short() -> None:
    is_valid, msg = validate_password_strength("Short1!")
    assert is_valid is False
    assert "at least 12 characters" in msg

def test_validate_password_strength_no_upper() -> None:
    is_valid, msg = validate_password_strength("nouppercase123!")
    assert is_valid is False
    assert "uppercase" in msg

def test_validate_password_strength_no_lower() -> None:
    is_valid, msg = validate_password_strength("NOLOWERCASE123!")
    assert is_valid is False
    assert "lowercase" in msg

def test_validate_password_strength_no_digit() -> None:
    is_valid, msg = validate_password_strength("NoDigitPassword!")
    assert is_valid is False
    assert "numbers" in msg
