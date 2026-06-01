"""
Remediation Agent — Agent 2 of InfraGPT

Receives the TriageDiagnosis from the Triage Agent and proposes
a concrete remediation plan, including:
  - Immediate mitigation steps (kubectl commands)
  - Terraform fixes (for IaC drift scenarios)
  - Long-term prevention recommendations
  - Auto-generated runbook entry (saved to memory)
"""

import json, os, time
from dataclasses import dataclass, field
from typing import Generator
from tools.registry import dispatch_tool
from memory.store import MemoryStore


@dataclass
class RemediationPlan:
    summary: str
    severity: str
    immediate_steps: list
    terraform_changes: list
    prevention: list
    runbook_entry: str
    estimated_resolution_mins: int
    risk_level: str        # LOW / MEDIUM / HIGH

    def to_dict(self):
        return {
            "summary": self.summary,
            "severity": self.severity,
            "immediate_steps": self.immediate_steps,
            "terraform_changes": self.terraform_changes,
            "prevention": self.prevention,
            "runbook_entry": self.runbook_entry,
            "estimated_resolution_mins": self.estimated_resolution_mins,
            "risk_level": self.risk_level,
        }


# ── Scenario-specific remediation playbooks ────────────────────────

MOCK_REMEDIATIONS = {
    "pod-crash": {
        "summary": "Increase container memory limit and reduce ML model batch size to prevent OOM recurrence.",
        "severity": "HIGH",
        "immediate_steps": [
            "🛑  Kill runaway process: kubectl exec node-01 -- kill -9 18432",
            "📋  Check current state: kubectl describe pod api-server-7d9f -n production",
            "🔄  Patch memory limit to 2Gi:\n    kubectl patch deployment api-server -n production -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"api-server\",\"resources\":{\"limits\":{\"memory\":\"2Gi\"},\"requests\":{\"memory\":\"1Gi\"}}}]}}}}'",
            "🔃  Roll out restart: kubectl rollout restart deployment/api-server -n production",
            "👁️   Watch rollout: kubectl rollout status deployment/api-server -n production",
        ],
        "terraform_changes": [],
        "prevention": [
            "Add HPA (Horizontal Pod Autoscaler) targeting 70% memory utilization",
            "Implement model lazy-loading or streaming weights instead of full load at startup",
            "Add liveness/readiness probes with memory-aware thresholds",
            "Set up Prometheus alert at 80% container memory usage",
            "Consider splitting model serving into dedicated GPU-enabled pods",
        ],
        "runbook_entry": (
            "OOMKilled Pod Remediation (api-server): "
            "Patch deployment memory limit from 512Mi to 2Gi. "
            "Root cause was ML model weight loading (1.2GB) exceeding container limit. "
            "Use kubectl patch or edit deployment spec. Add HPA for future scaling."
        ),
        "estimated_resolution_mins": 10,
        "risk_level": "LOW",
        "terraform_snippet": None,
    },
    "disk-pressure": {
        "summary": "Free disk space immediately via log rotation and Docker prune, then add automated retention policies.",
        "severity": "HIGH",
        "immediate_steps": [
            "📦  Remove stale Docker images: docker system prune -af --volumes (on node-02)",
            "🗒️   Rotate and vacuum journal: journalctl --vacuum-size=500M",
            "🗑️   Clean evicted pods: kubectl delete pod --field-selector=status.phase==Failed --all-namespaces",
            "📂  Compress old logs: find /var/log/pods -name '*.log' -mtime +1 | xargs gzip",
            "📊  Verify recovery: df -h && kubectl describe node node-02 | grep -A5 Conditions",
        ],
        "terraform_changes": [],
        "prevention": [
            "Add logrotate config for /var/log/pods (daily, maxsize 100MB, rotate 7)",
            "Schedule weekly: docker system prune -af via CronJob in kube-system",
            "Configure node ephemeral-storage eviction thresholds in kubelet: --eviction-hard=nodefs.available<15%",
            "Add Prometheus disk alert at 75% usage (before DiskPressure taint)",
            "Consider PersistentVolume for application logs instead of node filesystem",
        ],
        "runbook_entry": (
            "Disk Pressure Remediation (node-02): "
            "Run docker system prune + journalctl vacuum. "
            "Root cause: 28GB pod logs + 41GB stale Docker images. "
            "Add logrotate and weekly prune CronJob to prevent recurrence."
        ),
        "estimated_resolution_mins": 20,
        "risk_level": "LOW",
        "terraform_snippet": None,
    },
    "tf-drift": {
        "summary": "Immediately apply Terraform to restore all 3 drifted security configurations; enforce IaC-only access policy.",
        "severity": "CRITICAL",
        "immediate_steps": [
            "🔒  URGENT — block all public access now:\n    aws s3api put-public-access-block --bucket mlops-model-registry-bucket-prod-xyz --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true",
            "🔐  Re-enable encryption:\n    aws s3api put-bucket-encryption --bucket mlops-model-registry-bucket-prod-xyz --server-side-encryption-configuration '{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'",
            "✅  Apply Terraform to restore full state:\n    terraform apply -auto-approve",
            "🔍  Verify state matches: terraform plan (should show: No changes)",
            "📋  Audit CloudTrail for who made manual changes: aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=mlops-model-registry-bucket-prod-xyz",
        ],
        "terraform_changes": [
            {
                "resource": "aws_s3_bucket_versioning.model_registry",
                "change": 'status: "Suspended" → "Enabled"',
                "risk": "SAFE — re-enables version history",
            },
            {
                "resource": "aws_s3_bucket_public_access_block.model_registry",
                "change": "block_public_acls: false → true",
                "risk": "SAFE — closes public exposure",
            },
            {
                "resource": "aws_s3_bucket_server_side_encryption_configuration.model_registry",
                "change": "sse_algorithm: none → AES256",
                "risk": "SAFE — re-enables encryption at rest",
            },
        ],
        "prevention": [
            "Add AWS SCP (Service Control Policy) denying manual S3 config changes in prod",
            "Enable AWS Config rule: s3-bucket-public-read-prohibited, s3-bucket-ssl-requests-only",
            "Add terraform plan -detailed-exitcode to CI: fail pipeline on any drift",
            "Set up Terraform Cloud with Sentinel policy enforcement",
            "Grant IAM: deny s3:PutBucketAcl for all roles except terraform-ci-role",
        ],
        "runbook_entry": (
            "Terraform Drift Remediation (S3 model registry): "
            "terraform apply restores versioning, encryption, public access block. "
            "Root cause: manual AWS console changes. "
            "Enforce IaC-only via SCP + AWS Config drift detection."
        ),
        "estimated_resolution_mins": 15,
        "risk_level": "MEDIUM",
        "terraform_snippet": """
# Terraform fix — paste in main.tf if drift reoccurs

resource "aws_s3_bucket_versioning" "model_registry" {
  bucket = aws_s3_bucket.model_registry.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "model_registry" {
  bucket                  = aws_s3_bucket.model_registry.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
""".strip(),
    },
}


class RemediationAgent:
    """Agent 2: Proposes fixes based on the Triage diagnosis, saves runbook to memory."""

    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def remediate(self, incident: dict, diagnosis) -> Generator:
        """Yields streaming events: tool_check → plan → runbook_saved."""
        sid = incident.get("id", "pod-crash")

        yield {"type": "status", "msg": "🔧 Remediation Agent received diagnosis — building action plan..."}
        time.sleep(0.4)

        # Check relevant runbooks from memory
        yield {"type": "status", "msg": "📚 Searching runbook knowledge base..."}
        runbooks = self.memory.get_runbook(diagnosis.root_cause, n_results=2)
        time.sleep(0.3)
        yield {"type": "runbook_search", "runbooks": runbooks}

        # For terraform scenario, also call the tool to show live plan
        if sid == "tf-drift":
            yield {"type": "status", "msg": "🔧 Running terraform apply preview..."}
            time.sleep(0.4)
            ctx = {"scenario_id": sid, "node": incident.get("node", "node-01")}
            apply_preview = dispatch_tool("terraform_apply_preview", ctx)
            yield {"type": "tool_result", "tool": "terraform_apply_preview", "result": apply_preview}

        # Build remediation plan
        time.sleep(0.3)
        raw = MOCK_REMEDIATIONS.get(sid, {
            "summary": "Review tool observations and apply standard runbook steps.",
            "severity": diagnosis.severity,
            "immediate_steps": ["Review diagnosis findings", "Apply relevant runbook", "Monitor after fix"],
            "terraform_changes": [],
            "prevention": ["Add monitoring alerts", "Review resource limits"],
            "runbook_entry": f"Incident remediated: {diagnosis.root_cause[:120]}",
            "estimated_resolution_mins": 30,
            "risk_level": "MEDIUM",
        })

        plan = RemediationPlan(
            summary=raw["summary"],
            severity=raw["severity"],
            immediate_steps=raw["immediate_steps"],
            terraform_changes=raw.get("terraform_changes", []),
            prevention=raw["prevention"],
            runbook_entry=raw["runbook_entry"],
            estimated_resolution_mins=raw["estimated_resolution_mins"],
            risk_level=raw["risk_level"],
        )

        yield {"type": "plan", "plan": plan.to_dict(), "object": plan,
               "terraform_snippet": raw.get("terraform_snippet")}

        # Save to memory
        yield {"type": "status", "msg": "💾 Saving incident + fix to persistent memory..."}
        time.sleep(0.2)
        inc_id = self.memory.save_incident(
            description=incident.get("description", ""),
            diagnosis=diagnosis.to_dict(),
            remediation=plan.to_dict(),
            scenario_id=sid,
        )
        yield {"type": "memory_saved", "incident_id": inc_id, "total_incidents": self.memory.incident_count()}
