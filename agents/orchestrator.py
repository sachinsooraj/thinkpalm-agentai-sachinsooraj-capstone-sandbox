"""
Orchestrator — coordinates Triage Agent and Remediation Agent.

Flow:
  1. Accepts incident (from CLI or Streamlit UI)
  2. Dispatches to TriageAgent → streams diagnosis steps
  3. Passes TriageDiagnosis → RemediationAgent → streams fix plan
  4. Yields all events with agent labels for UI rendering
"""

import time
from memory.store import MemoryStore
from agents.triage_agent import TriageAgent
from agents.remediation_agent import RemediationAgent


class Orchestrator:
    """Routes incidents through Triage → Remediation, streams all events."""

    def __init__(self):
        self.memory = MemoryStore()
        self.triage = TriageAgent(memory=self.memory)
        self.remediation = RemediationAgent(memory=self.memory)

    def run(self, incident: dict):
        """
        Generator: yields all events from both agents with 'agent' label.

        Event types:
          status       : simple status string from an agent
          memory_query : results of memory search (pre-triage)
          react_step   : one ReAct step (Thought→Action→Observation)
          diagnosis    : final TriageDiagnosis dict
          runbook_search: remediation runbook matches
          tool_result  : tool output used in remediation
          plan         : final RemediationPlan dict
          memory_saved : confirmation incident stored in memory
          done         : pipeline complete
        """
        yield {"agent": "orchestrator", "type": "start",
               "msg": f"🚀 InfraGPT pipeline started for: {incident.get('title', incident.get('id', 'incident'))}"}

        # ── Phase 1: Triage ──────────────────────────────────────────
        yield {"agent": "orchestrator", "type": "phase",
               "phase": "triage", "msg": "🔍 Handing off to Triage Agent..."}

        diagnosis_obj = None
        for event in self.triage.diagnose(incident):
            event["agent"] = "triage"
            if event["type"] == "diagnosis":
                diagnosis_obj = event["object"]
            yield event

        if diagnosis_obj is None:
            yield {"agent": "orchestrator", "type": "error", "msg": "Triage failed to produce a diagnosis."}
            return

        # ── Phase 2: Remediation ─────────────────────────────────────
        yield {"agent": "orchestrator", "type": "phase",
               "phase": "remediation", "msg": "🔧 Handing off to Remediation Agent..."}
        time.sleep(0.2)

        for event in self.remediation.remediate(incident, diagnosis_obj):
            event["agent"] = "remediation"
            yield event

        yield {"agent": "orchestrator", "type": "done",
               "msg": "✅ Pipeline complete. Incident diagnosed and remediated."}
