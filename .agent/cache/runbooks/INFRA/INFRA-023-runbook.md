# INFRA-023: Agent Config Command

## State
ACCEPTED

## Goal Description
Provide a Command-Line Interface (CLI) tool for managing and modifying the agent's configuration without requiring manual edits to YAML files. This will include functionality for retrieving (`get`), modifying (`set`), and displaying (`list`) configuration settings, supporting dot-notation for nested keys (e.g. `models.gpt-4o.cost_per_1k_input`). The solution will primarily target `.agent/etc/router.yaml` but be extensible for other YAML configs.

## Panel Review Findings

- **@Architect**:
  - The solution should introduce a `ConfigManager` in `agent/core/config.py` (or `agent/core/config_manager.py` if too large) to handle safe YAML reading/writing.
  - Using dot-notation for keys maps well to nested YAML structures.
  - **Constraint**: Ensure thread-safety or file locking if parallel execution is anticipated, though unlikely for manual CLI usage. `atomic` writes (write to temp, then rename) are recommended.
  - **Validation**: The CLI must ensure it doesn't corrupt the YAML structure.

- **@Security**:
  - **Sensitive Data**: `router.yaml` and other configs may contain API keys (though env vars are preferred). If storing secrets, ensure permissions are restricted (600).
  - The `list` command should optionally mask known sensitive keys (like `api_key`) to prevent shoulder surfing, even if stored in cleartext.
  - Ensure `set` command prevents path traversal if keys are used to construct file paths (unlikely but possible).

- **@QA**:
  - **Test Strategy**: Unit tests for the `ConfigManager` to handle read/write/nested updates.
  - Integration: `env -u VIRTUAL_ENV uv run agent config set ...` followed by `env -u VIRTUAL_ENV uv run agent run ...` (or probing the file) to verify persistence.
  - Edge cases: Setting a key that doesn't exist (should create it? or fail?), setting wrong types (boolean as string).
  - **Rollback**: Automatic backup of the config file before writing is a good safety net.

- **@Docs**:
  - Update `README.md` with the new command syntax.
  - `env -u VIRTUAL_ENV uv run agent config --help` should be self-explanatory.

- **@Compliance**:
  - `router.yaml` defines model usage costs. Changing these via CLI impacts cost tracking. Ensure logs reflect *who* changed the config and *what* changed, for auditing.

- **@Observability**:
  - Log every configuration change (old value -> new value) to `.agent/logs/agent.log`.

---

## Implementation Steps

### Core Logic
#### MODIFY: `agent/core/config.py`
1.  **Enhance `Config` or create `ConfigManager`**:
    -   Add `load_yaml(path)` and `save_yaml(path, data)` methods.
    -   Implement "Atomic Write": write to `path.tmp` then `os.replace`.
    -   Implement `backup_config(path)`: copy to `.agent/backups/`.
    -   Implement `get_value(data, dotted_key)` and `set_value(data, dotted_key, value)`.
2.  **Support for `router.yaml`**:
    -   Identify `.agent/etc/router.yaml` as a managed config file.

### Command-Line Interface (CLI)
#### NEW: `agent/commands/config.py`
1.  **Create `app` (Typer application)**.
2.  **`get` command**:
    -   Args: `key` (optional, if distinct files supported), or just assume global config space. Since we have specific files, maybe `env -u VIRTUAL_ENV uv run agent config get router.models.gpt-4o.tier`.
    -   Logic: Load yaml, traverse keys, print value (JSON or plain).
3.  **`set` command**:
    -   Args: `key`, `value`.
    -   Logic:
        -   Load yaml.
        -   Backup file.
        -   Update value (handle type casting: "true" -> True, number strings to float/int).
        -   Save yaml.
        -   Log change.
4.  **`list` command**:
    -   Args: None (or filter).
    -   Logic: Dump the whole YAML (syntax highlighted).

#### MODIFY: `agent/main.py`
1.  Register `config` subcommand group: `app.add_typer(config.app, name="config")`.

---

## Verification Plan

### Automated Tests
-   **Unit Tests (`tests/commands/test_config.py`)**:
    -   Test `get_value` / `set_value` traversal logic.
    -   Test type inference (string "123" -> int 123, "true" -> bool True).
    -   Test atomic write and backup creation.
-   **Integration Tests**:
    -   Run `env -u VIRTUAL_ENV uv run agent config set models.test_model.tier light`.
    -   Verify content of `.agent/etc/router.yaml`.
    -   Run `env -u VIRTUAL_ENV uv run agent config get models.test_model.tier` -> expect "light".

### Manual Verification
1.  Run `env -u VIRTUAL_ENV uv run agent config list` -> See colorized YAML.
2.  Run `env -u VIRTUAL_ENV uv run agent config set settings.default_tier output_only_test_tier`.
3.  Cat `.agent/etc/router.yaml` -> check change.
4.  Run `env -u VIRTUAL_ENV uv run agent config get settings.default_tier` -> "output_only_test_tier".
5.  Revert change: `env -u VIRTUAL_ENV uv run agent config set settings.default_tier standard`.

---

## Definition of Done
-   [ ] `env -u VIRTUAL_ENV uv run agent config` commands implemented (`get`, `set`, `list`).
-   [ ] Core config logic (atomic write, backups) implemented.
-   [ ] Unit and integration tests passed.
-   [ ] README updated with new command usage.
-   [ ] Governance review (via `env -u VIRTUAL_ENV uv run agent preflight`) passes.