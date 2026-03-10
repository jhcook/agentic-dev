"""Onboarding step library for the Agent CLI."""

from .steps import (
    check_dependencies,
    check_github_auth,
    ensure_agent_directory,
    ensure_gitignore,
    configure_api_keys,
    configure_agent_settings,
    select_default_model,
    configure_voice_settings,
    configure_notion_settings,
    configure_mcp_settings,
    setup_frontend,
    run_verification,
    display_next_steps,
)

__all__ = [
    "check_dependencies",
    "check_github_auth",
    "ensure_agent_directory",
    "ensure_gitignore",
    "configure_api_keys",
    "configure_agent_settings",
    "select_default_model",
    "configure_voice_settings",
    "configure_notion_settings",
    "configure_mcp_settings",
    "setup_frontend",
    "run_verification",
    "display_next_steps",
]
