# 🤖 InfraGPT — Multi-Agent DevOps Incident Response Pipeline

> **Capstone Flagship Project** · Triage Agent + Remediation Agent + Persistent Memory (ChromaDB) + Streamlit UI + CLI

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/streamlit-1.35+-red.svg)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/memory-ChromaDB-green.svg)](https://trychroma.com)
[![LLM](https://img.shields.io/badge/LLM-Gemini%201.5%20Flash-orange.svg)](https://ai.google.dev)

---

## 🎯 What It Does

InfraGPT is an **end-to-end agentic pipeline** that autonomously diagnoses and remediates DevOps/infrastructure incidents. When a production alert fires, InfraGPT:

1. **Queries memory** (ChromaDB) for similar past incidents before starting analysis
2. Runs **Triage Agent** — a ReAct (Reason+Act) loop that calls diagnostic tools step-by-step
3. Hands diagnosis to **Remediation Agent** — generates concrete fix steps, Terraform patches, and prevention recommendations
4. **Saves** the incident + fix to persistent memory so future runs are smarter

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────┐
│           Streamlit UI  /  CLI               │
└──────────────────┬───────────────────────────┘
                   │
          ┌────────▼────────┐
          │  Orchestrator   │  routes + streams all events
          └──┬──────────┬───┘
             │          │
   ┌──────────▼──┐  ┌───▼──────────────┐
   │ 🔍 TRIAGE   │  │ 🔧 REMEDIATION   │
   │   AGENT     │  │    AGENT         │
   │  (diagnose) │  │ (fix + Terraform) │
   └──────┬──────┘  └───────┬──────────┘
          │                 │
   ┌──────▼─────────────────▼──────────┐
   │          TOOL REGISTRY            │
   │ kubectl_get_pods  check_disk      │
   │ kubectl_describe  check_node_cpu  │
   │ kubectl_get_logs  check_node_mem  │
   │ terraform_plan    terraform_apply │
   └──────────────────┬────────────────┘
                      │
   ┌──────────────────▼────────────────┐
   │     MEMORY LAYER (ChromaDB)       │
   │  incident_history + runbook_kb    │
   └───────────────────────────────────┘
```

---

## ✅ Deliverables Checklist

| Requirement | Status | Details |
|---|---|---|
| 2+ Agents | ✅ | Triage Agent + Remediation Agent + Orchestrator |
| Tool-calling | ✅ | 8 tools: kubectl, system, terraform |
| Memory | ✅ | ChromaDB persistent — queries past incidents before diagnosing |
| Working UI | ✅ | Streamlit dark-mode UI with streaming |
| Working CLI | ✅ | Rich-formatted terminal with `python main.py` |
| README | ✅ | This file |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/infragpt-capstone.git
cd infragpt-capstone

python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure API Key (optional)

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
# Leave blank to run in mock mode — fully works without any API key
```

Get a free Gemini API key at: https://aistudio.google.com/

### 3. Run — Streamlit UI

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

### 4. Run — CLI

```bash
# List available scenarios
python main.py --list-scenarios

# Run a specific scenario
python main.py --scenario pod-crash
python main.py --scenario disk-pressure
python main.py --scenario tf-drift

# Custom incident description
python main.py --incident "High memory usage on node-03, pods are being evicted"

# Interactive mode
python main.py
```

---

## 🧠 Memory Demonstration

Memory is **persistent across runs** (stored in `./chroma_data/`):

```bash
# First run — no past incidents
python main.py --scenario pod-crash
# Output: "Memory contains 0 incidents. No similar incidents found."

# Second run — memory recalls the previous incident
python main.py --scenario pod-crash
# Output: "Found 1 similar incident: inc-a3f9b2c1 | severity=HIGH | similarity=97%"
```

The Remediation Agent also searches a **pre-seeded runbook knowledge base** (5 runbooks covering OOMKilled, CrashLoop, DiskPressure, CPU spike, Terraform drift).

---

## 📋 Demo Scenarios

| Scenario ID | Title | What Triage Finds | Remediation Proposes |
|---|---|---|---|
| `pod-crash` | API Pod CrashLoopBackOff | OOMKilled (exit 137), 14 restarts, 94% CPU | Patch memory limit 512Mi→2Gi, kubectl rollout restart |
| `disk-pressure` | Node Disk Pressure Critical | 97% disk, 28GB pod logs, 41GB Docker images | docker prune + log rotation CronJob |
| `tf-drift` | Terraform State Drift | 3 S3 security misconfigs (public access, encryption) | terraform apply + AWS SCP enforcement |

---

## 📁 Project Structure

```
capstone/
├── app.py                     # Streamlit UI
├── main.py                    # CLI entrypoint
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── orchestrator.py        # Routes incidents, coordinates agents
│   ├── triage_agent.py        # ReAct loop + tool-calling + memory query
│   └── remediation_agent.py   # Fix plan + Terraform + runbook save
│
├── tools/
│   ├── registry.py            # Central tool dispatcher
│   ├── kubectl_tools.py       # Mock kubectl get/describe/logs
│   ├── system_tools.py        # Mock CPU/disk/memory checks
│   └── terraform_tools.py     # Mock terraform plan/apply
│
├── memory/
│   └── store.py               # ChromaDB wrapper (2 collections)
│
├── scenarios/
│   └── sample_incidents.json  # Pre-built demo scenarios
│
└── chroma_data/               # Auto-created — persistent memory store
```

---

## 🔧 Tech Stack

| Component | Technology |
|---|---|
| LLM | Google Gemini 1.5 Flash (+ deterministic mock fallback) |
| Memory | ChromaDB (persistent on-disk vector store) |
| UI | Streamlit |
| CLI | Click + Rich |
| Tools | Mock kubectl, system, Terraform implementations |
| Language | Python 3.11+ |

---

## 🔑 Mock Mode (No API Key Required)

All scenarios work **100% without any API key** using a deterministic mock reasoning engine. The agent behavior, tool calls, observations, and diagnoses are all realistic and scenario-specific — perfect for demos and Loom recordings.

To force mock mode even if a key is present:
```bash
LLM_MODE=mock python main.py --scenario pod-crash
```

---

## 📹 Loom Walkthrough

> Link: [Add your Loom link here]

The walkthrough demonstrates:
1. CLI run showing full ReAct trace
2. Memory empty on first run → populated after
3. Second run showing memory recall
4. Streamlit UI with both agent panels
5. Terraform drift scenario with IaC fix preview

---

## 🧩 Extending InfraGPT

**Add a real LLM**: Set `GEMINI_API_KEY` in `.env` — the agent automatically switches from mock to Gemini reasoning.

**Add a new tool**: Create a function in `tools/kubectl_tools.py` or `tools/system_tools.py`, register it in `tools/registry.py`.

**Add a new scenario**: Add an entry to `scenarios/sample_incidents.json` and corresponding entries in `MOCK_PLANS` / `MOCK_DIAGNOSES` / `MOCK_REMEDIATIONS` in the agent files.

---

*Built with Python · Streamlit · ChromaDB · Google Gemini · Rich*
