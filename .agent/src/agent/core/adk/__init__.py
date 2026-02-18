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
ADK Multi-Agent Governance Panel.

This package implements multi-agent orchestration for the governance council
using Google's Agent Development Kit (ADK). It wraps the existing AIService
through a vendor-agnostic adapter and maps governance roles to ADK agents
with read-only tool access.
"""
