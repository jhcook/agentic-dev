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

import typer

from agent.commands.onboard import app as onboard_app

app = typer.Typer()
app.add_typer(onboard_app, name="onboard")


@app.callback()
def cli() -> None:
    """A CLI for managing and interacting with the AI agent."""
    pass


if __name__ == "__main__":
    app()