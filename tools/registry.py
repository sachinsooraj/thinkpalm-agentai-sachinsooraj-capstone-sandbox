"""
Tool Registry — central dispatcher for all InfraGPT tools.

The LLM calls tools by name; this module resolves the call,
executes the mock implementation, and returns structured results.
"""

import json
from typing import Any, Callable
from tools.kubectl_tools import kubectl_get_pods, kubectl_describe_pod, kubectl_get_logs
from tools.system_tools import check_node_cpu, check_disk, check_node_memory
from tools.terraform_tools import terraform_plan, terraform_apply_preview


# ------------------------------------------------------------------ #
#  Tool metadata — used to build the LLM function-calling schema
# ------------------------------------------------------------------ #

TOOL_REGISTRY: dict[str, dict] = {
    "kubectl_get_pods": {
        "fn": kubectl_get_pods,
        "description": "List all pods in a Kubernetes namespace. Returns status, restart count, and scheduling info.",
        "parameters": {
            "namespace": "Kubernetes namespace to query (e.g. 'production')",
            "pod": "Target pod name (optional, for filtering)",
        },
        "category": "kubernetes",
        "emoji": "📦",
    },
    "kubectl_describe_pod": {
        "fn": kubectl_describe_pod,
        "description": "Describe a specific pod: shows events, exit codes, resource limits, conditions.",
        "parameters": {
            "pod": "Name of the pod to describe",
            "namespace": "Kubernetes namespace",
        },
        "category": "kubernetes",
        "emoji": "🔍",
    },
    "kubectl_get_logs": {
        "fn": kubectl_get_logs,
        "description": "Get the last container logs (--previous) from a crashed pod.",
        "parameters": {
            "pod": "Name of the pod",
            "namespace": "Kubernetes namespace",
        },
        "category": "kubernetes",
        "emoji": "📜",
    },
    "check_node_cpu": {
        "fn": check_node_cpu,
        "description": "Check CPU utilization on a node. Returns usage%, status, and top processes.",
        "parameters": {
            "node": "Node hostname to check (e.g. 'node-01')",
        },
        "category": "system",
        "emoji": "⚡",
    },
    "check_disk": {
        "fn": check_disk,
        "description": "Check filesystem disk usage on a node. Returns usage%, free space, and large directories.",
        "parameters": {
            "node": "Node hostname to check",
        },
        "category": "system",
        "emoji": "💾",
    },
    "check_node_memory": {
        "fn": check_node_memory,
        "description": "Check RAM utilization on a node. Returns used/free GB and status.",
        "parameters": {
            "node": "Node hostname to check",
        },
        "category": "system",
        "emoji": "🧠",
    },
    "terraform_plan": {
        "fn": terraform_plan,
        "description": "Run terraform plan to detect infrastructure drift between state and actual resources.",
        "parameters": {},
        "category": "terraform",
        "emoji": "🔧",
    },
    "terraform_apply_preview": {
        "fn": terraform_apply_preview,
        "description": "Preview terraform apply changes (dry-run). Shows what would change without applying.",
        "parameters": {},
        "category": "terraform",
        "emoji": "✅",
    },
}


def dispatch_tool(tool_name: str, ctx: dict) -> dict:
    """
    Dispatch a tool call by name, injecting the incident context.

    Args:
        tool_name: Name of the tool to call (must be in TOOL_REGISTRY)
        ctx: Incident context dict (node, pod, namespace, scenario_id, etc.)

    Returns:
        Tool result dict with 'tool' key indicating the tool called.
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "tool": tool_name,
            "error": f"Unknown tool '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}",
        }

    fn: Callable = TOOL_REGISTRY[tool_name]["fn"]
    try:
        return fn(ctx)
    except Exception as e:
        return {"tool": tool_name, "error": str(e)}


def get_tool_descriptions() -> str:
    """Return a formatted string describing all available tools (for LLM prompts)."""
    lines = []
    for name, info in TOOL_REGISTRY.items():
        params = ", ".join(f"{k}: {v}" for k, v in info["parameters"].items())
        lines.append(f"  {info['emoji']} {name}({params})\n     → {info['description']}")
    return "\n\n".join(lines)


def get_tools_for_scenario(scenario_id: str) -> list[str]:
    """Return the recommended tool sequence for a given scenario."""
    sequences = {
        "pod-crash": [
            "kubectl_get_pods",
            "kubectl_describe_pod",
            "kubectl_get_logs",
            "check_node_cpu",
            "check_node_memory",
        ],
        "disk-pressure": [
            "check_disk",
            "kubectl_get_pods",
            "check_node_cpu",
            "check_node_memory",
        ],
        "tf-drift": [
            "terraform_plan",
            "terraform_apply_preview",
            "check_node_cpu",
        ],
    }
    return sequences.get(scenario_id, list(TOOL_REGISTRY.keys())[:4])


class ToolRegistry:
    """Convenience class wrapping the module-level functions."""

    dispatch = staticmethod(dispatch_tool)
    descriptions = staticmethod(get_tool_descriptions)
    for_scenario = staticmethod(get_tools_for_scenario)
    all_tools = TOOL_REGISTRY
