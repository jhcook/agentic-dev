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

import yaml
import glob

journey_files = glob.glob("cache/journeys/**/*.yaml", recursive=True)

for jrn_file in journey_files:
    with open(jrn_file, "r") as f:
        data = yaml.safe_load(f)
    if "implementation" not in data or ("files" in data.get("implementation", {}) and not data["implementation"]["files"]):
        print(f"Journey {jrn_file} needs backfilling")
