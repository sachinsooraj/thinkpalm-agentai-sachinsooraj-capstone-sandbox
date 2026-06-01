"""
ChromaDB-backed persistent memory store for InfraGPT.

Uses a custom offline embedding function (TF-IDF-style hash vectors)
so NO internet access or model downloads are needed.

Two collections:
  - incident_history : stores past incidents + their diagnoses
  - runbook_knowledge: stores remediation steps (runbooks)
"""

import json
import uuid
import hashlib
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import chromadb


CHROMA_PATH = Path(__file__).parent.parent / "chroma_data"

# ── Offline embedding function ────────────────────────────────────────────────
# Uses a simple bag-of-words TF projection into a fixed 128-d space.
# No downloads, no network, fully deterministic.
DIM = 128
STOPWORDS = {"the", "a", "an", "is", "it", "in", "of", "to", "and", "or", "for", "on", "at", "by", "with"}

def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]

def _hash_embed(text: str) -> list[float]:
    """Hash each token into a DIM-dimensional vector and sum."""
    tokens = _tokenize(text)
    vec = [0.0] * DIM
    for tok in tokens:
        digest = hashlib.sha256(tok.encode()).digest()
        for i in range(DIM):
            byte = digest[i % 32]
            vec[i] += (byte / 255.0) * 2 - 1  # map to [-1, 1]
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class OfflineEmbeddingFn:
    """ChromaDB-compatible embedding function — no network required."""

    def name(self) -> str:
        return "offline-hash-embed"

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [_hash_embed(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return [_hash_embed(text) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        if isinstance(input, str):
            return [_hash_embed(input)]
        return [_hash_embed(text) for text in input]


_EMBED_FN = OfflineEmbeddingFn()


class MemoryStore:
    """Persistent vector memory backed by ChromaDB (on-disk, offline-safe)."""

    def __init__(self, persist_path: str | None = None):
        path = persist_path or str(CHROMA_PATH)
        self.client = chromadb.PersistentClient(path=path)

        self.incidents = self.client.get_or_create_collection(
            name="incident_history",
            embedding_function=_EMBED_FN,
            metadata={"hnsw:space": "cosine"},
        )
        self.runbooks = self.client.get_or_create_collection(
            name="runbook_knowledge",
            embedding_function=_EMBED_FN,
            metadata={"hnsw:space": "cosine"},
        )
        self._seed_runbooks()

    # ── Incident Memory ────────────────────────────────────────────────────────

    def save_incident(
        self,
        description: str,
        diagnosis: dict,
        remediation: dict,
        scenario_id: str = "",
    ) -> str:
        """Persist a completed incident. Returns incident ID."""
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.utcnow().isoformat()

        document = (
            f"INCIDENT: {description}\n"
            f"ROOT_CAUSE: {diagnosis.get('root_cause', '')}\n"
            f"SEVERITY: {diagnosis.get('severity', '')}\n"
            f"FIX: {remediation.get('summary', '')}"
        )

        self.incidents.add(
            documents=[document],
            metadatas=[{
                "incident_id": incident_id,
                "timestamp": timestamp,
                "scenario_id": scenario_id,
                "severity": diagnosis.get("severity", "UNKNOWN"),
                "diagnosis_json": json.dumps(diagnosis),
                "remediation_json": json.dumps(remediation),
            }],
            ids=[incident_id],
        )
        return incident_id

    def search_similar_incidents(self, query: str, n_results: int = 3) -> list[dict]:
        """Return up to n_results past incidents similar to query."""
        count = self.incidents.count()
        if count == 0:
            return []

        results = self.incidents.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )

        hits = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            similarity = round(max(0.0, 1 - distance), 3)
            hits.append({
                "incident_id": meta["incident_id"],
                "timestamp": meta["timestamp"],
                "severity": meta["severity"],
                "document": doc,
                "similarity": similarity,
                "diagnosis": json.loads(meta.get("diagnosis_json", "{}")),
                "remediation": json.loads(meta.get("remediation_json", "{}")),
            })
        return hits

    def incident_count(self) -> int:
        return self.incidents.count()

    # ── Runbook Knowledge Base ─────────────────────────────────────────────────

    def _seed_runbooks(self):
        """Pre-seed runbook knowledge (idempotent)."""
        if self.runbooks.count() > 0:
            return

        runbooks = [
            {
                "id": "rb-oomkilled",
                "text": (
                    "OOMKilled Pod Runbook: Pod terminated due to memory limit breach. "
                    "Steps: 1) kubectl top pod to confirm memory usage. "
                    "2) Increase resources.limits.memory in Deployment spec. "
                    "3) Consider HPA for dynamic scaling. "
                    "4) Add memory profiling to identify leaks."
                ),
                "tags": "oomkilled memory pod kubernetes",
            },
            {
                "id": "rb-crashloop",
                "text": (
                    "CrashLoopBackOff Runbook: Pod repeatedly restarting. "
                    "Steps: 1) kubectl logs <pod> --previous to see crash reason. "
                    "2) kubectl describe pod to check events and exit codes. "
                    "3) Common causes: OOMKilled, bad config, missing env vars, failed health checks. "
                    "4) Fix root cause, then kubectl rollout restart deployment."
                ),
                "tags": "crashloop pod restart kubernetes",
            },
            {
                "id": "rb-disk-pressure",
                "text": (
                    "Disk Pressure Runbook: Node disk usage critical (>90%). "
                    "Steps: 1) du -sh /* to find large directories. "
                    "2) journalctl --vacuum-size=500M to trim logs. "
                    "3) docker system prune -af to remove stale images. "
                    "4) kubectl delete pod --field-selector=status.phase==Failed to clean evicted pods. "
                    "5) Add log rotation via logrotate config."
                ),
                "tags": "disk pressure storage node eviction",
            },
            {
                "id": "rb-cpu-spike",
                "text": (
                    "CPU Spike Runbook: Node CPU >80%. "
                    "Steps: 1) top -c to identify runaway process. "
                    "2) kubectl top pod --all-namespaces to pinpoint workload. "
                    "3) Check for missing resource limits (resources.limits.cpu). "
                    "4) Scale horizontally via kubectl scale or HPA. "
                    "5) Investigate for infinite loops or throttling."
                ),
                "tags": "cpu spike performance throttle kubernetes",
            },
            {
                "id": "rb-tf-drift",
                "text": (
                    "Terraform Drift Runbook: Infrastructure state diverged from code. "
                    "Steps: 1) terraform plan to see diff. "
                    "2) Review unexpected changes — manual edits in console? "
                    "3) terraform apply -target=<resource> to reconcile. "
                    "4) Add drift detection to CI: terraform plan -detailed-exitcode. "
                    "5) Enable AWS Config or equivalent for drift alerts."
                ),
                "tags": "terraform drift iac state reconcile aws",
            },
        ]

        self.runbooks.add(
            documents=[r["text"] for r in runbooks],
            metadatas=[{"tags": r["tags"]} for r in runbooks],
            ids=[r["id"] for r in runbooks],
        )

    def get_runbook(self, query: str, n_results: int = 2) -> list[str]:
        """Retrieve the most relevant runbooks for a given query."""
        count = self.runbooks.count()
        if count == 0:
            return []

        results = self.runbooks.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        return results["documents"][0]
