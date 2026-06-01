"""
InfraGPT -- Streamlit UI
Premium dark-mode multi-agent DevOps incident response dashboard.
"""

import json
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InfraGPT | Multi-Agent DevOps Pipeline",
    page_icon="robot",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0d1117; color: #e6edf3; }
section[data-testid="stSidebar"] { background: #161b22 !important; border-right: 1px solid #30363d; }

/* Metric boxes */
.metric-box {
    background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 18px 16px;
    text-align: center;
    transition: border-color 0.2s;
}
.metric-box:hover { border-color: #58a6ff; }
.metric-val { font-size: 2rem; font-weight: 700; color: #58a6ff; }
.metric-lbl { font-size: 0.75rem; color: #8b949e; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }

/* Agent badges */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-triage    { background: #0d419d; color: #79c0ff; border: 1px solid #1f6feb; }
.badge-remediation { background: #6e40c9; color: #d2a8ff; border: 1px solid #8957e5; }
.badge-report    { background: #1a3a2a; color: #56d364; border: 1px solid #238636; }
.badge-orch      { background: #1a4a1a; color: #56d364; border: 1px solid #238636; }

/* Step cards */
.step-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-left: 3px solid #58a6ff;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 8px 0;
    font-size: 0.85rem;
}
.step-card.final { border-left-color: #56d364; }
.step-thought { color: #79c0ff; font-style: italic; margin-bottom: 6px; }
.step-action  { color: #f0883e; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; }
.step-obs     { color: #8b949e; margin-top: 6px; font-size: 0.8rem; }

/* Severity badges */
.sev-CRITICAL { background:#4c1515; color:#ff7b7b; border:1px solid #da3633; border-radius:6px; padding:2px 10px; font-weight:700; }
.sev-HIGH     { background:#3a2000; color:#ffa657; border:1px solid #d29922; border-radius:6px; padding:2px 10px; font-weight:700; }
.sev-MEDIUM   { background:#2a2200; color:#e3b341; border:1px solid #9e6a03; border-radius:6px; padding:2px 10px; font-weight:700; }
.sev-LOW      { background:#102010; color:#56d364; border:1px solid #238636; border-radius:6px; padding:2px 10px; font-weight:700; }

/* Info/memory cards */
.memory-card {
    background: #0d2137;
    border: 1px solid #1f6feb;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 6px 0;
    font-size: 0.83rem;
}
.runbook-card {
    background: #1a0d2e;
    border: 1px solid #6e40c9;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 6px 0;
    font-size: 0.83rem;
    color: #c9b1ff;
}

/* Plan step */
.plan-step {
    background: #161b22;
    border: 1px solid #30363d;
    border-left: 3px solid #f0883e;
    border-radius: 6px;
    padding: 8px 14px;
    margin: 5px 0;
    font-size: 0.83rem;
    color: #e6edf3;
}
.prevention-step {
    background: #102010;
    border: 1px solid #238636;
    border-radius: 6px;
    padding: 8px 14px;
    margin: 5px 0;
    font-size: 0.83rem;
    color: #7ee787;
}
.tf-change {
    background: #1a1400;
    border: 1px solid #9e6a03;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 5px 0;
    font-size: 0.82rem;
    font-family: 'JetBrains Mono', monospace;
}
.memory-saved {
    background: #0a2a0a;
    border: 1px solid #238636;
    border-radius: 8px;
    padding: 12px 14px;
    color: #56d364;
    font-size: 0.85rem;
}
.finding-item {
    padding: 4px 0;
    color: #e6edf3;
    font-size: 0.83rem;
}
.section-header {
    color: #58a6ff;
    font-weight: 600;
    font-size: 0.88rem;
    margin: 10px 0 4px 0;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* Divider */
hr { border-color: #30363d !important; }

/* Sidebar elements */
.stSelectbox > div { background: #0d1117 !important; color: #e6edf3 !important; }
h1, h2, h3 { color: #e6edf3 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _obs_summary(tool: str, obs: dict) -> str:
    summaries = {
        "kubectl_get_pods":    lambda o: f"{o.get('pod_count',0)} pods | status: {', '.join(set(p['status'] for p in o.get('pods',[])))}",
        "kubectl_describe_pod":lambda o: f"Exit: {o.get('last_state',{}).get('reason','?')} (code {o.get('last_state',{}).get('exit_code','?')}) | restarts: {o.get('restarts',0)}",
        "kubectl_get_logs":    lambda o: f"{o.get('line_count',0)} lines | last: {o.get('lines',[''])[-1][:70]}",
        "check_node_cpu":      lambda o: f"CPU {o.get('usage_percent',0)}% [{o.get('status','?')}] | top: {o.get('top_processes',[{}])[0].get('cmd','?')[:40]}",
        "check_disk":          lambda o: f"Disk {o.get('use_percent',0)}% | {o.get('free_gb',0)}GB free [{o.get('status','?')}]",
        "check_node_memory":   lambda o: f"RAM {o.get('use_percent',0)}% | {o.get('used_gb',0)}/{o.get('total_gb',0)}GB [{o.get('status','?')}]",
        "terraform_plan":      lambda o: f"Drift={'YES' if o.get('drift_detected') else 'NO'} | {o.get('change_count',0)} resource(s) changed",
        "terraform_apply_preview": lambda o: f"{o.get('status','?')} | {o.get('resources_to_change',0)} resource(s) to apply",
    }
    fn = summaries.get(tool)
    try:
        return fn(obs) if fn else str(obs)[:100]
    except Exception:
        return str(obs)[:100]


TOOL_EMOJI = {
    "kubectl_get_pods": "📦", "kubectl_describe_pod": "🔍",
    "kubectl_get_logs": "📜", "check_node_cpu": "⚡",
    "check_disk": "💾", "check_node_memory": "🧠",
    "terraform_plan": "🔧", "terraform_apply_preview": "✅",
}

SEV_CLASS = {"CRITICAL": "sev-CRITICAL", "HIGH": "sev-HIGH", "MEDIUM": "sev-MEDIUM", "LOW": "sev-LOW"}
RISK_COLOR = {"LOW": "#56d364", "MEDIUM": "#e3b341", "HIGH": "#ff7b7b"}


@st.cache_data
def load_scenarios():
    path = Path(__file__).parent / "scenarios" / "sample_incidents.json"
    with open(path) as f:
        return json.load(f)


# ── Sidebar ────────────────────────────────────────────────────────────────────
scenarios = load_scenarios()

with st.sidebar:
    st.markdown("## 🤖 InfraGPT")
    st.markdown(
        "<span class='badge badge-triage'>Triage Agent</span> &nbsp; "
        "<span class='badge badge-remediation'>Remediation Agent</span> &nbsp; "
        "<span class='badge badge-report'>Report Agent</span>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("### 🚨 Select Incident")

    sid = st.selectbox(
        "Scenario",
        options=list(scenarios.keys()),
        format_func=lambda k: f"{scenarios[k]['emoji']} {scenarios[k]['title']}",
        label_visibility="collapsed",
    )
    custom_desc = st.text_area(
        "Custom description (optional)",
        placeholder="e.g. Memory spike on node-03, pods evicted...",
        height=80,
    )
    run_btn = st.button("🚀 Run InfraGPT Pipeline", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ℹ️ Architecture")
    st.markdown("""
```
CLI / Streamlit UI
       |
   Orchestrator
   /          \\
Triage      Remediation
Agent         Agent
   \\          /
  Tool Registry
  (kubectl, tf, sys)
       |
  Memory (ChromaDB)
```
""")
    st.markdown("### 🛠️ 8 Tools Available")
    tools_list = [
        ("📦", "kubectl_get_pods"), ("🔍", "kubectl_describe_pod"),
        ("📜", "kubectl_get_logs"), ("⚡", "check_node_cpu"),
        ("💾", "check_disk"), ("🧠", "check_node_memory"),
        ("🔧", "terraform_plan"), ("✅", "terraform_apply_preview"),
    ]
    for em, t in tools_list:
        st.markdown(f"<small>{em} {t}</small>", unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🤖 InfraGPT — Multi-Agent Incident Response")
st.markdown(
    "<span class='badge badge-triage'>🔍 Triage Agent</span> &nbsp;"
    "<span class='badge badge-remediation'>🔧 Remediation Agent</span> &nbsp;"
    "<span class='badge badge-report'>📊 Report Agent</span> &nbsp;"
    "<span class='badge badge-orch'>⚡ Persistent Memory</span>",
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
mem_count  = st.session_state.get("mem_total", 0)
step_count = st.session_state.get("steps_count", 0)
with m1: st.markdown("<div class='metric-box'><div class='metric-val'>3</div><div class='metric-lbl'>Active Agents</div></div>", unsafe_allow_html=True)
with m2: st.markdown("<div class='metric-box'><div class='metric-val'>8</div><div class='metric-lbl'>Tools Available</div></div>", unsafe_allow_html=True)
with m3: st.markdown(f"<div class='metric-box'><div class='metric-val'>{mem_count}</div><div class='metric-lbl'>Memory Incidents</div></div>", unsafe_allow_html=True)
with m4: st.markdown(f"<div class='metric-box'><div class='metric-val'>{step_count}</div><div class='metric-lbl'>ReAct Steps Run</div></div>", unsafe_allow_html=True)

st.markdown("---")

if not run_btn:
    st.info("👈 Select a scenario in the sidebar and click **Run InfraGPT Pipeline** to start.")
    st.stop()

# ── Resolve incident ───────────────────────────────────────────────────────────
incident = dict(scenarios[sid])
if custom_desc.strip():
    incident["description"] = custom_desc.strip()
    incident["title"] = f"Custom: {custom_desc.strip()[:50]}"

st.markdown(f"### 🚨 Incident: {incident.get('emoji','🔴')} {incident['title']}")
st.markdown(
    f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px;"
    f"color:#8b949e;font-size:0.88rem'>{incident['description']}</div>",
    unsafe_allow_html=True,
)
st.markdown("")

# ── Two-column layout ──────────────────────────────────────────────────────────
col_triage, col_remediation = st.columns(2, gap="medium")

with col_triage:
    st.markdown("<span class='badge badge-triage' style='font-size:0.95rem;padding:4px 12px'>🔍 TRIAGE AGENT</span>", unsafe_allow_html=True)
    triage_placeholder = st.empty()

with col_remediation:
    st.markdown("<span class='badge badge-remediation' style='font-size:0.95rem;padding:4px 12px'>🔧 REMEDIATION AGENT</span>", unsafe_allow_html=True)
    remediation_placeholder = st.empty()

st.markdown("---")
mem_placeholder = st.empty()

# ── Report Agent panel (below the 2-col layout) ───────────────────────────────
st.markdown("")
st.markdown("<span class='badge badge-report' style='font-size:0.95rem;padding:4px 12px'>📊 REPORT AGENT</span>", unsafe_allow_html=True)
report_placeholder = st.empty()

# ── Streaming state ────────────────────────────────────────────────────────────
from agents.orchestrator import Orchestrator

orch = Orchestrator()
progress = st.progress(0, text="Starting pipeline...")

triage_html      = ""
remediation_html = ""
report_html      = ""
current_step     = 0
mem_total        = 0
final_plan       = None
final_diagnosis  = None
final_tf_snippet = None
final_report_obj = None

TOTAL_STEPS = 14  # approximate

def pct(n): return min(int(n / TOTAL_STEPS * 100), 99)


def render_triage(html):
    triage_placeholder.markdown(html, unsafe_allow_html=True)


def render_remediation(html):
    remediation_placeholder.markdown(html, unsafe_allow_html=True)


# ── Event loop ─────────────────────────────────────────────────────────────────
for event in orch.run(incident):
    etype = event.get("type", "")
    agent = event.get("agent", "")

    # ── start / phase ──
    if etype == "start":
        progress.progress(2, text=event["msg"])

    elif etype == "phase":
        current_step += 1
        progress.progress(pct(current_step), text=event["msg"])

    # ── status ──
    elif etype == "status":
        if agent == "triage":
            triage_html += f"<div style='color:#8b949e;font-size:0.82rem;padding:4px 0'>{event['msg']}</div>"
            render_triage(triage_html)
        elif agent == "remediation":
            remediation_html += f"<div style='color:#8b949e;font-size:0.82rem;padding:4px 0'>{event['msg']}</div>"
            render_remediation(remediation_html)
        else:
            report_html += f"<div style='color:#8b949e;font-size:0.82rem;padding:4px 0'>{event['msg']}</div>"
            report_placeholder.markdown(report_html, unsafe_allow_html=True)
        current_step += 1
        progress.progress(pct(current_step), text=event["msg"])

    # ── memory_query ──
    elif etype == "memory_query":
        count = event["similar_count"]
        total = event["memory_count"]
        if count == 0:
            triage_html += (
                "<div class='memory-card'>"
                f"<b style='color:#58a6ff'>🧠 Memory</b><br>"
                f"<span style='color:#8b949e'>Store has {total} incident(s). No similar past incidents — fresh analysis.</span>"
                "</div>"
            )
        else:
            triage_html += f"<div class='memory-card'><b style='color:#58a6ff'>🧠 Memory — {count} similar incident(s)</b> (total: {total})<br>"
            for inc in event["similar_incidents"][:2]:
                triage_html += (
                    f"<div style='margin-top:6px;font-size:0.8rem'>"
                    f"<span style='color:#e3b341'>{inc['incident_id']}</span> | "
                    f"sev=<b>{inc['severity']}</b> | sim={inc['similarity']:.0%}<br>"
                    f"<span style='color:#8b949e'>{inc['document'][:100]}...</span>"
                    f"</div>"
                )
            triage_html += "</div>"
        render_triage(triage_html)
        current_step += 1
        progress.progress(pct(current_step), text="Memory queried")

    # ── react_step ──
    elif etype == "react_step":
        step = event["step"]
        is_final = step["is_final"]
        card_class = "step-card final" if is_final else "step-card"
        em = TOOL_EMOJI.get(step["action"], "⚙️")
        action_str = "FINISH — synthesizing diagnosis" if is_final else f"{em} {step['action']}()"
        obs_str = "" if is_final else f"<div class='step-obs'>👁 {_obs_summary(step['action'], step['observation'])}</div>"

        triage_html += (
            f"<div class='{card_class}'>"
            f"<div class='step-thought'>💭 {step['thought']}</div>"
            f"<div class='step-action'>⚡ {action_str}</div>"
            f"{obs_str}"
            f"</div>"
        )
        render_triage(triage_html)
        current_step += 1
        progress.progress(pct(current_step), text=f"ReAct step {step['step_num']}: {step['action']}")

    # ── diagnosis ──
    elif etype == "diagnosis":
        d = event["diagnosis"]
        obj = event.get("object")
        sev_cls = SEV_CLASS.get(d["severity"], "sev-MEDIUM")
        final_diagnosis = d
        if obj:
            final_diagnosis["findings"] = obj.findings
            final_diagnosis["affected_components"] = obj.affected_components

        triage_html += (
            f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:14px;margin-top:10px'>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>"
            f"<b style='color:#58a6ff'>📋 DIAGNOSIS</b>"
            f"<span class='{sev_cls}'>{d['severity']}</span>"
            f"</div>"
            f"<div style='font-size:0.84rem;color:#e6edf3;margin-bottom:8px'>{d['root_cause']}</div>"
            f"<div style='font-size:0.78rem;color:#8b949e'>Confidence: {d['confidence']:.0%} | "
            f"ReAct steps: {d['react_steps_count']} | Similar: {d['similar_incidents_count']}</div>"
        )
        if obj and obj.findings:
            triage_html += "<div class='section-header' style='margin-top:10px'>Findings</div>"
            for f in obj.findings:
                triage_html += f"<div class='finding-item'>&#9658; {f}</div>"
        triage_html += "</div>"
        render_triage(triage_html)
        current_step += 1
        progress.progress(pct(current_step), text="Triage complete")

    # ── runbook_search ──
    elif etype == "runbook_search":
        rbs = event.get("runbooks", [])
        if rbs:
            remediation_html += "<div class='section-header'>📚 Runbook Matches</div>"
            for rb in rbs[:2]:
                remediation_html += f"<div class='runbook-card'>{rb[:220]}...</div>"
            render_remediation(remediation_html)

    # ── tool_result (terraform) ──
    elif etype == "tool_result":
        result = event["result"]
        remediation_html += (
            f"<div style='background:#161b22;border:1px solid #30363d;border-radius:6px;"
            f"padding:8px 12px;margin:6px 0;font-size:0.8rem;color:#f0883e'>"
            f"🔧 {event['tool']}: {result.get('status', result.get('exit_code', str(result)[:60]))}"
            f"</div>"
        )
        render_remediation(remediation_html)

    # ── plan ──
    elif etype == "plan":
        plan = event["plan"]
        final_plan = plan
        final_tf_snippet = event.get("terraform_snippet")
        risk_c = RISK_COLOR.get(plan["risk_level"], "#8b949e")

        remediation_html += (
            f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:14px;margin-top:10px'>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>"
            f"<b style='color:#d2a8ff'>🔧 REMEDIATION PLAN</b>"
            f"<span style='color:{risk_c};font-size:0.78rem;font-weight:600'>Risk: {plan['risk_level']}</span>"
            f"<span style='color:#8b949e;font-size:0.78rem'>ETA: ~{plan['estimated_resolution_mins']} min</span>"
            f"</div>"
            f"<div style='font-size:0.84rem;color:#e6edf3;margin-bottom:10px'>{plan['summary']}</div>"
            f"<div class='section-header'>Immediate Steps</div>"
        )
        for step in plan["immediate_steps"]:
            remediation_html += f"<div class='plan-step'>{step}</div>"

        if plan.get("terraform_changes"):
            remediation_html += "<div class='section-header' style='margin-top:10px'>Terraform Changes</div>"
            for ch in plan["terraform_changes"]:
                remediation_html += (
                    f"<div class='tf-change'>"
                    f"<span style='color:#f0883e'>{ch['resource']}</span><br>"
                    f"<span style='color:#e6edf3'>{ch['change']}</span><br>"
                    f"<span style='color:#56d364;font-size:0.78rem'>{ch['risk']}</span>"
                    f"</div>"
                )

        remediation_html += "<div class='section-header' style='margin-top:10px'>Prevention</div>"
        for p in plan["prevention"]:
            remediation_html += f"<div class='prevention-step'>&#9655; {p}</div>"
        remediation_html += "</div>"
        render_remediation(remediation_html)
        current_step += 1
        progress.progress(pct(current_step), text="Remediation plan built")

    # ── memory_saved ──
    elif etype == "memory_saved":
        mem_total = event["total_incidents"]
        mem_placeholder.markdown(
            f"<div class='memory-saved'>"
            f"✅ Incident saved to persistent memory &nbsp;|&nbsp; "
            f"ID: <code>{event['incident_id']}</code> &nbsp;|&nbsp; "
            f"Total in store: <b>{mem_total}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.session_state["mem_total"]    = mem_total
        st.session_state["steps_count"] = current_step

    # ── report ──
    elif etype == "report" and agent == "report":
        rpt = event["report"]
        final_report_obj = event.get("object")
        timeline_items = "".join(
            f"<div style='font-size:0.8rem;color:#8b949e;padding:3px 0;border-left:2px solid #30363d;padding-left:8px;margin:3px 0'>{tl}</div>"
            for tl in event.get("timeline", [])
        )
        slack_escaped = event.get("slack_alert", "").replace("<", "&lt;").replace(">", "&gt;")
        report_html += (
            f"<div style='background:#0d1117;border:1px solid #238636;border-radius:10px;padding:14px;margin-top:8px'>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>"
            f"<b style='color:#56d364'>📊 INCIDENT REPORT</b>"
            f"<code style='font-size:0.78rem;color:#e3b341'>{rpt['incident_id']}</code>"
            f"<span style='color:#8b949e;font-size:0.78rem'>{rpt['generated_at']}</span>"
            f"</div>"
            f"<div class='section-header'>Executive Summary</div>"
            f"<div style='font-size:0.84rem;color:#e6edf3;line-height:1.5'>{rpt['executive_summary']}</div>"
            f"<div class='section-header' style='margin-top:10px'>Impact</div>"
            f"<div style='font-size:0.83rem;color:#ffa657'>{rpt['impact']}</div>"
            f"<div class='section-header' style='margin-top:10px'>Incident Timeline</div>"
            f"{timeline_items}"
            f"<div class='section-header' style='margin-top:10px'>📣 Slack Alert (copy-paste ready)</div>"
            f"<pre style='background:#161b22;border:1px solid #30363d;border-radius:6px;padding:10px;"
            f"font-size:0.78rem;color:#79c0ff;white-space:pre-wrap'>{slack_escaped}</pre>"
            f"</div>"
        )
        report_placeholder.markdown(report_html, unsafe_allow_html=True)
        current_step += 1
        progress.progress(pct(current_step), text=f"Report {rpt['incident_id']} generated")

    # ── done ──
    elif etype == "done":
        progress.progress(100, text="✅ All 3 agents complete!")

# ── Post-run extras ────────────────────────────────────────────────────────────
if final_diagnosis:
    with st.expander("📋 Full Triage Findings", expanded=False):
        for f in final_diagnosis.get("findings", []):
            st.markdown(f"<div class='finding-item'>&#9658; {f}</div>", unsafe_allow_html=True)

if final_tf_snippet:
    with st.expander("🔧 Terraform Fix Snippet", expanded=False):
        st.code(final_tf_snippet, language="hcl")

if final_plan or final_diagnosis:
    report = {
        "incident": incident.get("title"),
        "diagnosis": final_diagnosis,
        "plan": final_plan,
    }
    st.download_button(
        label="📥 Download Incident Report (JSON)",
        data=json.dumps(report, indent=2),
        file_name=f"infragpt_{incident.get('id','incident')}_report.json",
        mime="application/json",
    )
