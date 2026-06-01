"""
Orchestrator — coordinates all three InfraGPT agents.

Flow:
  Phase 1 → Triage Agent    (diagnose via ReAct + tools + memory)
  Phase 2 → Remediation Agent (propose fix + Terraform + runbook)
  Phase 3 → Report Agent    (post-mortem + Slack/PagerDuty alert)
"""

import time
from memory.store import MemoryStore
from agents.triage_agent import TriageAgent
from agents.remediation_agent import RemediationAgent
from agents.report_agent import ReportAgent


class Orchestrator:
    """Routes incidents through Triage → Remediation → Report, streaming all events."""

    def __init__(self):
        self.memory = MemoryStore()
        self.triage = TriageAgent(memory=self.memory)
        self.remediation = RemediationAgent(memory=self.memory)
        self.report = ReportAgent(memory=self.memory)

    def run(self, incident: dict):
        """
        Generator yielding all events from all three agents, labelled by 'agent'.

        Event types:
          start         : pipeline kick-off
          phase         : agent handoff announcement
          status        : simple progress message
          memory_query  : results of ChromaDB search (pre-triage)
          react_step    : one ReAct Thought→Action→Observation step
          diagnosis     : final TriageDiagnosis dict
          runbook_search: runbook KB matches (remediation)
          tool_result   : tool output used in remediation
          plan          : final RemediationPlan dict
          memory_saved  : confirmation incident stored in memory
          report        : final IncidentReport dict (post-mortem + alerts)
          done          : pipeline complete
        """
        yield {
            "agent": "orchestrator",
            "type": "start",
            "msg": f"🚀 InfraGPT pipeline started — {incident.get('title', incident.get('id', 'incident'))}",
        }

        # ── Phase 1: Triage ──────────────────────────────────────────────────
        yield {"agent": "orchestrator", "type": "phase",
               "phase": "triage", "msg": "🔍 Handing off to Triage Agent..."}

        diagnosis_obj = None
        for event in self.triage.diagnose(incident):
            event["agent"] = "triage"
            if event["type"] == "diagnosis":
                diagnosis_obj = event.get("object")
            yield event

        if diagnosis_obj is None:
            yield {"agent": "orchestrator", "type": "error", "msg": "Triage failed — aborting."}
            return

        # ── Phase 2: Remediation ─────────────────────────────────────────────
        yield {"agent": "orchestrator", "type": "phase",
               "phase": "remediation", "msg": "🔧 Handing off to Remediation Agent..."}
        time.sleep(0.2)

        plan_obj = None
        for event in self.remediation.remediate(incident, diagnosis_obj):
            event["agent"] = "remediation"
            if event["type"] == "plan":
                plan_obj = event.get("object")
            yield event

        # ── Phase 3: Report ──────────────────────────────────────────────────
        yield {"agent": "orchestrator", "type": "phase",
               "phase": "report", "msg": "📊 Handing off to Report Agent..."}
        time.sleep(0.2)

        for event in self.report.generate_report(incident, diagnosis_obj, plan_obj):
            event["agent"] = "report"
            yield event

        yield {"agent": "orchestrator", "type": "done",
               "msg": "✅ All 3 agents complete. Incident diagnosed, remediated, and reported."}
