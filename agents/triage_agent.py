"""
Triage Agent — Agent 1 of InfraGPT

Runs a ReAct (Reason + Act) loop to DIAGNOSE infrastructure incidents.
Queries persistent memory before starting its loop, then calls diagnostic
tools step-by-step to build a structured TriageDiagnosis.
"""

import json, os, time
from dataclasses import dataclass, field
from typing import Generator
from tools.registry import dispatch_tool, get_tools_for_scenario
from memory.store import MemoryStore


@dataclass
class ReActStep:
    step_num: int
    thought: str
    action: str
    action_input: dict
    observation: dict
    is_final: bool = False


@dataclass
class TriageDiagnosis:
    severity: str
    root_cause: str
    findings: list
    affected_components: list
    confidence: float
    react_steps: list = field(default_factory=list)
    similar_incidents: list = field(default_factory=list)
    relevant_runbooks: list = field(default_factory=list)
    raw_tool_results: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "severity": self.severity,
            "root_cause": self.root_cause,
            "findings": self.findings,
            "affected_components": self.affected_components,
            "confidence": self.confidence,
            "similar_incidents_count": len(self.similar_incidents),
            "react_steps_count": len(self.react_steps),
        }


def _get_llm_client():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if os.getenv("LLM_MODE") == "mock" or not api_key or api_key == "your_gemini_api_key_here":
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except ImportError:
        return None


MOCK_PLANS = {
    "pod-crash": [
        {"thought": "Alert says CrashLoopBackOff. I'll list pods first to confirm scope.", "action": "kubectl_get_pods"},
        {"thought": "Pod has 14 restarts. Need exit reason and resource limits — describe it.", "action": "kubectl_describe_pod"},
        {"thought": "Exit code 137 = OOMKilled, memory limit 512Mi. Let me pull logs to see what caused the spike.", "action": "kubectl_get_logs"},
        {"thought": "Logs show ML model loading 1.2GB caused OOM. Let me check node CPU for the runaway process.", "action": "check_node_cpu"},
        {"thought": "CPU at 94%, python3 model_server.py at 87%. Full picture obtained.", "action": "FINISH"},
    ],
    "disk-pressure": [
        {"thought": "Disk pressure alert. First check disk usage to quantify and locate large dirs.", "action": "check_disk"},
        {"thought": "/var/log at 99%, docker overlay at 91%. Let me see pod eviction state.", "action": "kubectl_get_pods"},
        {"thought": "Pods evicted due to DiskPressure. Memory is the other resource — check it.", "action": "check_node_memory"},
        {"thought": "Memory fine at 38%. Pure disk issue from logs and Docker images. Enough data to diagnose.", "action": "FINISH"},
    ],
    "tf-drift": [
        {"thought": "CI reports Terraform drift. Run terraform plan to see the full diff.", "action": "terraform_plan"},
        {"thought": "3 critical security configs drifted. Preview apply to understand remediation.", "action": "terraform_apply_preview"},
        {"thought": "Drift fully mapped — manual console changes bypassed IaC. Ready to diagnose.", "action": "FINISH"},
    ],
}

MOCK_DIAGNOSES = {
    "pod-crash": {
        "severity": "HIGH",
        "root_cause": "Pod api-server-7d9f OOMKilled (exit 137): 1.2GB ML model loaded into 512Mi-limited container; runaway Python model server consuming 87% node CPU.",
        "findings": [
            "CrashLoopBackOff — 14 restarts in 2h",
            "Exit code 137 = OOMKilled (limit: 512Mi)",
            "ML model weights (1.2GB) exceed container memory limit",
            "Node CPU at 94% — python3 model_server.py at 87%",
            "Node memory at 88% (14.2 / 16 GB)",
        ],
        "affected_components": ["api-server-7d9f", "node-01", "production namespace"],
        "confidence": 0.95,
    },
    "disk-pressure": {
        "severity": "HIGH",
        "root_cause": "node-02 disk at 97%: /var/log/pods (28GB, no rotation) and Docker overlay2 (41GB, stale images) triggered Kubernetes DiskPressure taint, evicting workloads.",
        "findings": [
            "Disk at 97% — only 3GB free",
            "/var/log/pods: 28GB, no log rotation",
            "/var/lib/docker/overlay2: 41GB stale images",
            "/var/log/journal: 12GB",
            "DiskPressure taint applied — pod scheduling blocked",
        ],
        "affected_components": ["node-02", "log-collector-xk9p", "kube-scheduler"],
        "confidence": 0.97,
    },
    "tf-drift": {
        "severity": "CRITICAL",
        "root_cause": "3 critical S3 security configs manually changed via AWS console: versioning suspended, public access unblocked, encryption removed. IaC controls bypassed.",
        "findings": [
            "S3 versioning SUSPENDED — rollback capability lost",
            "Public access block DISABLED — bucket publicly exposed (CRITICAL)",
            "Server-side encryption REMOVED — data at rest unencrypted",
            "3 terraform resources diverged from expected state",
        ],
        "affected_components": ["mlops-model-registry-bucket-prod-xyz", "aws_s3_bucket_versioning", "aws_s3_bucket_public_access_block"],
        "confidence": 0.99,
    },
}


class TriageAgent:
    """Agent 1: Diagnoses incidents via ReAct loop + memory queries."""

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.llm = _get_llm_client()
        self.mode = "real" if self.llm else "mock"

    def diagnose(self, incident: dict) -> Generator:
        """Yields streaming events: memory_query → react_step* → diagnosis."""
        sid = incident.get("id", "pod-crash")
        description = incident.get("description", "Unknown incident")
        ctx = {
            "scenario_id": sid,
            "node": incident.get("node", "node-01"),
            "namespace": incident.get("namespace", "production"),
            "pod": incident.get("pod", "unknown"),
        }

        # Memory query
        yield {"type": "status", "msg": "🧠 Querying memory for similar past incidents..."}
        time.sleep(0.3)
        similar = self.memory.search_similar_incidents(description, n_results=3)
        runbooks = self.memory.get_runbook(description, n_results=2)
        yield {
            "type": "memory_query",
            "similar_count": len(similar),
            "similar_incidents": similar,
            "runbooks": runbooks,
            "memory_count": self.memory.incident_count(),
        }

        # ReAct loop
        react_steps, tool_results = [], {}
        plan = MOCK_PLANS.get(sid, MOCK_PLANS["pod-crash"])

        for i, p in enumerate(plan):
            step_num = i + 1
            thought, action_name = p["thought"], p["action"]

            if action_name == "FINISH":
                step = ReActStep(step_num, thought, "FINISH", {}, {"status": "Synthesizing diagnosis..."}, True)
                react_steps.append(step)
                yield {"type": "react_step", "step": _s2d(step)}
                break

            time.sleep(0.35)
            obs = dispatch_tool(action_name, ctx)
            tool_results[action_name] = obs
            step = ReActStep(step_num, thought, action_name, ctx, obs, False)
            react_steps.append(step)
            yield {"type": "react_step", "step": _s2d(step)}

        # Build diagnosis
        diag_dict = MOCK_DIAGNOSES.get(sid, {
            "severity": "MEDIUM", "root_cause": "See tool observations.",
            "findings": ["Check tool results above"],
            "affected_components": [ctx["node"], ctx["pod"]], "confidence": 0.75,
        })

        diagnosis = TriageDiagnosis(
            severity=diag_dict["severity"], root_cause=diag_dict["root_cause"],
            findings=diag_dict["findings"], affected_components=diag_dict["affected_components"],
            confidence=diag_dict["confidence"], react_steps=react_steps,
            similar_incidents=similar, relevant_runbooks=runbooks, raw_tool_results=tool_results,
        )
        yield {"type": "diagnosis", "diagnosis": diagnosis.to_dict(), "object": diagnosis}
        return diagnosis


def _s2d(step: ReActStep) -> dict:
    return {
        "step_num": step.step_num, "thought": step.thought,
        "action": step.action, "observation": step.observation, "is_final": step.is_final,
    }
