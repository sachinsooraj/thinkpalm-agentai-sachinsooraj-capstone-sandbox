"""
Mock Terraform tool implementations for InfraGPT.
Simulates terraform plan output for drift detection scenarios.
"""

from datetime import datetime


def terraform_plan(ctx: dict) -> dict:
    """Simulate: terraform plan — detect infrastructure drift."""
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "tf-drift":
        changes = [
            {
                "action": "update",
                "resource": "aws_s3_bucket_versioning.model_registry",
                "attribute": "versioning_configuration.status",
                "expected": "Enabled",
                "actual": "Suspended",
                "risk": "HIGH — model rollback disabled",
            },
            {
                "action": "update",
                "resource": "aws_s3_bucket_public_access_block.model_registry",
                "attribute": "block_public_acls",
                "expected": "true",
                "actual": "false",
                "risk": "CRITICAL — bucket publicly accessible",
            },
            {
                "action": "update",
                "resource": "aws_s3_bucket_server_side_encryption_configuration.model_registry",
                "attribute": "rule.apply_server_side_encryption_by_default.sse_algorithm",
                "expected": "AES256",
                "actual": "none",
                "risk": "HIGH — data at rest unencrypted",
            },
        ]
        drift_detected = True
        change_count = len(changes)
        exit_code = 2  # terraform convention: 2 = changes present

        terraform_output = """
# Terraform Plan Output

aws_s3_bucket_versioning.model_registry will be updated in-place
  ~ resource "aws_s3_bucket_versioning" "model_registry" {
      ~ versioning_configuration {
          ~ status = "Suspended" -> "Enabled"
        }
    }

aws_s3_bucket_public_access_block.model_registry will be updated in-place
  ~ resource "aws_s3_bucket_public_access_block" "model_registry" {
      ~ block_public_acls   = false -> true
      ~ block_public_policy = false -> true
    }

aws_s3_bucket_server_side_encryption_configuration.model_registry will be updated
  ~ resource "..." {
      + sse_algorithm = "AES256"
    }

Plan: 0 to add, 3 to change, 0 to destroy.
""".strip()

    else:
        changes = []
        drift_detected = False
        change_count = 0
        exit_code = 0
        terraform_output = "No changes. Infrastructure is up-to-date."

    return {
        "tool": "terraform_plan",
        "drift_detected": drift_detected,
        "change_count": change_count,
        "exit_code": exit_code,
        "changes": changes,
        "plan_output": terraform_output,
        "timestamp": datetime.utcnow().isoformat(),
    }


def terraform_apply_preview(ctx: dict) -> dict:
    """Preview what terraform apply would do (dry-run safe)."""
    plan = terraform_plan(ctx)

    if not plan["drift_detected"]:
        return {"tool": "terraform_apply_preview", "status": "NO_CHANGES", "message": "Nothing to apply."}

    return {
        "tool": "terraform_apply_preview",
        "status": "READY_TO_APPLY",
        "resources_to_change": plan["change_count"],
        "apply_command": "terraform apply -auto-approve",
        "estimated_duration": "~45 seconds",
        "rollback_command": "terraform apply -target=<resource> (revert manually)",
        "changes": plan["changes"],
    }
