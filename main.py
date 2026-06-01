"""
InfraGPT CLI — Rich-formatted terminal interface.

Usage:
  python main.py --scenario pod-crash
  python main.py --scenario disk-pressure
  python main.py --scenario tf-drift
  python main.py --list-scenarios
  python main.py  # interactive mode
"""

import json
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

SCENARIOS_FILE = Path(__file__).parent / "scenarios" / "sample_incidents.json"
console = Console()

SEVERITY_COLORS = {
    "CRITICAL": "bold red",
    "HIGH": "bold orange1",
    "MEDIUM": "bold yellow",
    "LOW": "bold green",
}

AGENT_COLORS = {
    "triage": "cyan",
    "remediation": "magenta",
    "orchestrator": "blue",
}


def load_scenarios() -> dict:
    with open(SCENARIOS_FILE) as f:
        return json.load(f)


def print_banner():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🤖 InfraGPT[/bold cyan] — [white]Multi-Agent DevOps Incident Response Pipeline[/white]\n"
        "[dim]Triage Agent + Remediation Agent + Report Agent + Persistent Memory[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()


def render_event(event: dict):
    """Render a single streaming event from the orchestrator."""
    etype = event.get("type", "")
    agent = event.get("agent", "")
    color = AGENT_COLORS.get(agent, "white")

    if etype == "start":
        console.print(Rule(f"[bold blue]{event['msg']}[/bold blue]", style="blue"))

    elif etype == "phase":
        phase = event["phase"].upper()
        icons = {"triage": "🔍", "remediation": "🔧", "report": "📊"}
        icon = icons.get(event["phase"], "⚡")
        console.print()
        console.print(Rule(f"{icon} [bold {color}]PHASE: {phase} AGENT[/bold {color}]", style=color))

    elif etype == "status":
        console.print(f"  [dim]{event['msg']}[/dim]")

    elif etype == "memory_query":
        count = event["similar_count"]
        total = event["memory_count"]
        if count == 0:
            console.print(Panel(
                f"[dim]Memory contains {total} incident(s). No similar incidents found — fresh analysis.[/dim]",
                title="[bold cyan]🧠 Memory[/bold cyan]",
                border_style="cyan dim",
            ))
        else:
            lines = [f"[bold cyan]🧠 Memory — {count} similar incident(s) found[/bold cyan] (total in store: {total})\n"]
            for i, inc in enumerate(event["similar_incidents"][:2], 1):
                lines.append(
                    f"  [{i}] [yellow]{inc['incident_id']}[/yellow] | "
                    f"severity=[bold]{inc['severity']}[/bold] | "
                    f"similarity={inc['similarity']:.0%}\n"
                    f"      {inc['document'][:120]}..."
                )
            console.print(Panel("\n".join(lines), border_style="cyan", padding=(0, 1)))

    elif etype == "react_step":
        step = event["step"]
        num = step["step_num"]
        thought = step["thought"]
        action = step["action"]
        obs = step["observation"]
        is_final = step["is_final"]

        console.print()
        console.print(f"  [bold white]Step {num}[/bold white] " + "─" * 55)
        console.print(f"  [bold cyan]💭 Thought :[/bold cyan] {thought}")

        if is_final:
            console.print(f"  [bold green]🏁 Action  :[/bold green] FINISH — synthesizing diagnosis")
        else:
            # Tool emoji
            tool_emojis = {
                "kubectl_get_pods": "📦", "kubectl_describe_pod": "🔍",
                "kubectl_get_logs": "📜", "check_node_cpu": "⚡",
                "check_disk": "💾", "check_node_memory": "🧠",
                "terraform_plan": "🔧", "terraform_apply_preview": "✅",
            }
            em = tool_emojis.get(action, "⚙️")
            console.print(f"  [bold yellow]⚡ Action  :[/bold yellow] {em} {action}()")

            # Summarize observation
            summary = _summarize_obs(action, obs)
            status_color = "red" if obs.get("status") == "CRITICAL" else "green" if obs.get("status") == "NORMAL" else "yellow"
            console.print(f"  [bold {status_color}]👁  Obs     :[/bold {status_color}] {summary}")

    elif etype == "diagnosis":
        d = event["diagnosis"]
        obj = event.get("object")
        sev_color = SEVERITY_COLORS.get(d["severity"], "white")
        console.print()
        t = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 1))
        t.add_column("Key", style="bold cyan", width=22)
        t.add_column("Value")
        t.add_row("Severity", f"[{sev_color}]{d['severity']}[/{sev_color}]")
        t.add_row("Root Cause", d["root_cause"])
        t.add_row("Confidence", f"{d['confidence']:.0%}")
        t.add_row("ReAct Steps", str(d["react_steps_count"]))
        t.add_row("Similar Incidents", str(d["similar_incidents_count"]))
        if obj and obj.affected_components:
            t.add_row("Affected", ", ".join(obj.affected_components))
        console.print(Panel(t, title="[bold cyan]📋 TRIAGE DIAGNOSIS[/bold cyan]", border_style="cyan"))

        # Print findings list
        if obj and obj.findings:
            console.print("\n  [bold cyan]🔍 Findings:[/bold cyan]")
            for f in obj.findings:
                console.print(f"    [yellow]▸[/yellow] {f}")

    elif etype == "runbook_search":
        rbs = event.get("runbooks", [])
        if rbs:
            rb_text = "\n\n".join(f"• {rb[:200]}..." for rb in rbs)
            console.print(Panel(rb_text, title="[bold magenta]📚 Runbook Matches[/bold magenta]",
                                border_style="magenta dim", padding=(0, 1)))

    elif etype == "tool_result":
        tool = event["tool"]
        result = event["result"]
        console.print(f"  [bold magenta]🔧 {tool}:[/bold magenta] {result.get('status', result.get('exit_code', ''))}")

    elif etype == "plan":
        plan = event["plan"]
        risk_color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red"}.get(plan["risk_level"], "white")
        console.print()

        # Summary panel
        console.print(Panel(
            f"[bold]{plan['summary']}[/bold]\n\n"
            f"[dim]Risk Level: [bold {risk_color}]{plan['risk_level']}[/bold {risk_color}]  |  "
            f"ETA: ~{plan['estimated_resolution_mins']} min[/dim]",
            title="[bold magenta]🔧 REMEDIATION PLAN[/bold magenta]",
            border_style="magenta",
        ))

        # Immediate steps
        console.print("\n  [bold magenta]⚡ Immediate Steps:[/bold magenta]")
        for step in plan["immediate_steps"]:
            console.print(f"    {step}")

        # Terraform changes
        if plan.get("terraform_changes"):
            console.print("\n  [bold yellow]🏗️  Terraform Changes:[/bold yellow]")
            for ch in plan["terraform_changes"]:
                console.print(f"    [cyan]{ch['resource']}[/cyan]")
                console.print(f"      change : {ch['change']}")
                console.print(f"      risk   : [green]{ch['risk']}[/green]")

        # Terraform snippet
        if event.get("terraform_snippet"):
            from rich.syntax import Syntax
            console.print()
            console.print(Syntax(event["terraform_snippet"], "hcl", theme="monokai",
                                  line_numbers=False, padding=(1, 2)))

        # Prevention
        console.print("\n  [bold green]🛡️  Prevention:[/bold green]")
        for p in plan["prevention"]:
            console.print(f"    • {p}")

    elif etype == "memory_saved":
        console.print()
        console.print(Panel(
            f"[bold green]✅ Incident saved to persistent memory[/bold green]\n"
            f"   ID: [yellow]{event['incident_id']}[/yellow]  |  "
            f"Total incidents in store: [cyan]{event['total_incidents']}[/cyan]",
            border_style="green dim",
        ))

    elif etype == "report":
        rpt = event["report"]
        console.print()
        t = Table(box=box.ROUNDED, border_style="green", show_header=False, padding=(0, 1))
        t.add_column("Key", style="bold green", width=22)
        t.add_column("Value")
        t.add_row("Incident ID", f"[yellow]{rpt['incident_id']}[/yellow]")
        t.add_row("Generated", rpt["generated_at"])
        t.add_row("Severity", f"[bold]{rpt['severity']}[/bold]")
        t.add_row("Impact", rpt["impact"][:120] + "...")
        console.print(Panel(t, title="[bold green]📊 INCIDENT REPORT[/bold green]", border_style="green"))
        console.print("\n  [bold green]Executive Summary:[/bold green]")
        console.print(f"    {rpt['executive_summary'][:300]}...")
        console.print("\n  [bold green]📊 Slack Alert:[/bold green]")
        console.print(Panel(event.get("slack_alert", ""), border_style="blue dim", padding=(0, 1)))
        if event.get("timeline"):
            console.print("\n  [bold green]📅 Timeline:[/bold green]")
            for tl in event["timeline"][:5]:
                console.print(f"    [dim]{tl}[/dim]")

    elif etype == "done":
        console.print()
        console.print(Rule("[bold green]✅ All 3 Agents Complete[/bold green]", style="green"))
        console.print()


def _summarize_obs(tool: str, obs: dict) -> str:
    """One-line summary of a tool observation."""
    if "error" in obs:
        return f"[red]ERROR: {obs['error']}[/red]"
    summaries = {
        "kubectl_get_pods": lambda o: f"{o.get('pod_count', 0)} pods — status: {', '.join(set(p['status'] for p in o.get('pods', [])))}",
        "kubectl_describe_pod": lambda o: f"Exit: {o.get('last_state', {}).get('reason', 'N/A')} (code {o.get('last_state', {}).get('exit_code', '?')}) | restarts: {o.get('restarts', 0)}",
        "kubectl_get_logs": lambda o: f"{o.get('line_count', 0)} log lines — last: {o.get('lines', [''])[- 1][:80]}",
        "check_node_cpu": lambda o: f"CPU {o.get('usage_percent', 0)}% [{o.get('status', '?')}] — top: {o.get('top_processes', [{}])[0].get('cmd', '?')[:40]}",
        "check_disk": lambda o: f"Disk {o.get('use_percent', 0)}% used, {o.get('free_gb', 0)}GB free [{o.get('status', '?')}]",
        "check_node_memory": lambda o: f"RAM {o.get('use_percent', 0)}% — {o.get('used_gb', 0)}/{o.get('total_gb', 0)}GB [{o.get('status', '?')}]",
        "terraform_plan": lambda o: f"Drift={'YES' if o.get('drift_detected') else 'NO'} — {o.get('change_count', 0)} resource(s) changed",
        "terraform_apply_preview": lambda o: f"{o.get('status', '?')} — {o.get('resources_to_change', 0)} resource(s) to apply",
    }
    fn = summaries.get(tool)
    try:
        return fn(obs) if fn else str(obs)[:120]
    except Exception:
        return str(obs)[:120]


# ─────────────────────────────────────────────────────────── CLI ──

@click.command()
@click.option("--scenario", "-s", default=None, help="Scenario ID: pod-crash | disk-pressure | tf-drift")
@click.option("--list-scenarios", "-l", is_flag=True, help="List all available scenarios")
@click.option("--incident", "-i", default=None, help="Free-text incident description (uses pod-crash template)")
def main(scenario, list_scenarios, incident):
    """InfraGPT — Multi-Agent DevOps Incident Response CLI."""
    print_banner()
    scenarios = load_scenarios()

    if list_scenarios:
        t = Table(title="Available Scenarios", box=box.ROUNDED, border_style="cyan")
        t.add_column("ID", style="bold cyan")
        t.add_column("Title")
        t.add_column("Severity", style="bold")
        for sid, s in scenarios.items():
            t.add_row(sid, f"{s['emoji']} {s['title']}", s["severity_hint"])
        console.print(t)
        console.print("\nRun: [bold cyan]python main.py --scenario pod-crash[/bold cyan]")
        return

    # Resolve incident
    if incident:
        chosen = dict(scenarios["pod-crash"])  # use pod-crash template
        chosen["description"] = incident
        chosen["title"] = f"Custom: {incident[:50]}"
    elif scenario:
        if scenario not in scenarios:
            console.print(f"[red]Unknown scenario '{scenario}'. Run --list-scenarios to see options.[/red]")
            sys.exit(1)
        chosen = scenarios[scenario]
    else:
        # Interactive
        console.print("[bold]Available scenarios:[/bold]")
        for i, (sid, s) in enumerate(scenarios.items(), 1):
            console.print(f"  [{i}] [cyan]{sid}[/cyan] — {s['emoji']} {s['title']}")
        console.print()
        choice = console.input("[bold]Enter scenario ID or number[/bold] (default: pod-crash): ").strip()
        if not choice:
            choice = "pod-crash"
        if choice.isdigit():
            sid_list = list(scenarios.keys())
            choice = sid_list[int(choice) - 1] if 0 < int(choice) <= len(sid_list) else "pod-crash"
        chosen = scenarios.get(choice, scenarios["pod-crash"])

    # Run pipeline
    from agents.orchestrator import Orchestrator
    orch = Orchestrator()

    console.print(f"\n[bold]Incident:[/bold] {chosen.get('emoji', '🚨')} [white]{chosen['description']}[/white]\n")

    with console.status("[bold cyan]Running InfraGPT pipeline...[/bold cyan]", spinner="dots"):
        time.sleep(0.3)  # let status render

    # Stream events
    for event in orch.run(chosen):
        render_event(event)


if __name__ == "__main__":
    main()
