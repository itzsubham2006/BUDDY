"""Prompt templates for the agent's LLM calls."""

from __future__ import annotations


def build_system_prompt(agent_name: str, long_term_facts: dict[str, str]) -> str:
    facts_block = ""
    if long_term_facts:
        lines = "\n".join(f"- {k}: {v}" for k, v in long_term_facts.items())
        facts_block = f"\n\nKnown user preferences:\n{lines}"

    return (
        f"You are {agent_name}, a concise personal desktop voice assistant running "
        "locally on the user's Windows computer.\n\n"
        "Rules:\n"
        "1. If the user's request maps to one of the available tools, call that tool. "
        "Do not describe the tool call in prose — invoke it.\n"
        "2. If no tool applies, answer directly in one or two short sentences. "
        "You are spoken aloud, so avoid long answers, markdown, or lists.\n"
        "3. Never claim to have performed an action you did not actually call a tool for.\n"
        "4. You do not have the ability to run arbitrary shell commands or bypass "
        "the permission system — do not imply otherwise.\n"
        "5. Keep responses short and natural, as if speaking out loud."
        f"{facts_block}"
    )


def build_confirmation_summary(tool_name: str, arguments: dict) -> str:
    """Plain-language summary of a pending sensitive action, for confirmation prompts."""
    arg_desc = ", ".join(f"{k}={v}" for k, v in arguments.items()) if arguments else ""
    if arg_desc:
        return f"I'm about to run '{tool_name}' with {arg_desc}."
    return f"I'm about to run '{tool_name}'."
