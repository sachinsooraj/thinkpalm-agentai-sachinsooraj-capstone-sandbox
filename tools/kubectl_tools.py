"""
Mock kubectl tool implementations for InfraGPT.

All tools return realistic simulated data — no real cluster is required.
Scenario context (node, pod, namespace) is injected via the ctx dict.
"""

import random
from datetime import datetime, timedelta


def kubectl_get_pods(ctx: dict) -> dict:
    """Simulate: kubectl get pods -n <namespace>"""
    namespace = ctx.get("namespace", "production")
    pod = ctx.get("pod", "api-server-7d9f")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "pod-crash":
        pods = [
            {
                "name": pod,
                "namespace": namespace,
                "status": "CrashLoopBackOff",
                "restarts": 14,
                "age": "2h",
                "ready": "0/1",
                "node": ctx.get("node", "node-01"),
            },
            {
                "name": "api-server-7d9f-prev",
                "namespace": namespace,
                "status": "Completed",
                "restarts": 0,
                "age": "3h",
                "ready": "0/1",
                "node": ctx.get("node", "node-01"),
            },
            {
                "name": "redis-cache-5f8b",
                "namespace": namespace,
                "status": "Running",
                "restarts": 0,
                "age": "5d",
                "ready": "1/1",
                "node": "node-02",
            },
        ]
    elif scenario == "disk-pressure":
        pods = [
            {
                "name": pod,
                "namespace": namespace,
                "status": "Evicted",
                "restarts": 0,
                "age": "30m",
                "ready": "0/1",
                "node": ctx.get("node", "node-02"),
                "reason": "Evicted due to DiskPressure",
            },
            {
                "name": "metrics-server-9c2d",
                "namespace": "kube-system",
                "status": "Pending",
                "restarts": 0,
                "age": "15m",
                "ready": "0/1",
                "node": "Unschedulable",
                "reason": "0/3 nodes available: 1 node(s) had taints: node.kubernetes.io/disk-pressure",
            },
        ]
    else:
        pods = [
            {
                "name": pod,
                "namespace": namespace,
                "status": "Running",
                "restarts": 0,
                "age": "1d",
                "ready": "1/1",
                "node": ctx.get("node", "node-01"),
            }
        ]

    return {
        "tool": "kubectl_get_pods",
        "namespace": namespace,
        "pod_count": len(pods),
        "pods": pods,
    }


def kubectl_describe_pod(ctx: dict) -> dict:
    """Simulate: kubectl describe pod <pod> -n <namespace>"""
    pod = ctx.get("pod", "api-server-7d9f")
    namespace = ctx.get("namespace", "production")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "pod-crash":
        last_state = {
            "exit_code": 137,
            "reason": "OOMKilled",
            "message": "Container exceeded memory limit of 512Mi",
            "started_at": (datetime.utcnow() - timedelta(minutes=8)).isoformat(),
            "finished_at": (datetime.utcnow() - timedelta(minutes=7)).isoformat(),
        }
        conditions = ["PodScheduled=True", "Initialized=True", "Ready=False", "ContainersReady=False"]
        events = [
            "Warning BackOff: Back-off restarting failed container",
            "Warning OOMKilling: Memory cgroup out of memory: Kill process 18432",
            "Normal Pulling: Pulling image api-server:v2.3.1",
        ]
        resources = {"requests": {"cpu": "200m", "memory": "256Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}
    elif scenario == "disk-pressure":
        last_state = {
            "exit_code": 1,
            "reason": "Error",
            "message": "Evicted: The node was low on resource: ephemeral-storage",
        }
        conditions = ["PodScheduled=True", "Initialized=True", "Ready=False"]
        events = [
            "Warning Evicted: The node had condition: DiskPressure",
            "Warning FreeDiskSpaceFailed: failed to garbage collect required amount of images",
        ]
        resources = {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "200m", "memory": "256Mi"}}
    else:
        last_state = {}
        conditions = ["PodScheduled=True", "Ready=True"]
        events = ["Normal Started: Container started"]
        resources = {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}

    return {
        "tool": "kubectl_describe_pod",
        "pod": pod,
        "namespace": namespace,
        "restarts": 14 if scenario == "pod-crash" else 0,
        "last_state": last_state,
        "conditions": conditions,
        "events": events,
        "resources": resources,
        "image": "api-server:v2.3.1",
    }


def kubectl_get_logs(ctx: dict) -> dict:
    """Simulate: kubectl logs <pod> --previous"""
    pod = ctx.get("pod", "api-server-7d9f")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "pod-crash":
        lines = [
            "2026-05-27T09:41:02Z INFO  Starting api-server v2.3.1",
            "2026-05-27T09:41:05Z INFO  Connected to PostgreSQL at postgres:5432",
            "2026-05-27T09:41:10Z INFO  Loading ML model weights (1.2GB)...",
            "2026-05-27T09:41:18Z WARN  Memory usage at 85% (436Mi/512Mi)",
            "2026-05-27T09:41:22Z ERROR Prediction batch size 2048 too large, OOM imminent",
            "2026-05-27T09:41:23Z FATAL OOMKilled — process terminated by kernel",
        ]
    elif scenario == "disk-pressure":
        lines = [
            "2026-05-27T09:30:01Z INFO  log-collector starting",
            "2026-05-27T09:30:05Z WARN  /var/log partition at 94%",
            "2026-05-27T09:35:00Z ERROR Failed to write log file: No space left on device",
            "2026-05-27T09:35:01Z FATAL Exiting: disk full",
        ]
    else:
        lines = [
            "2026-05-27T09:00:00Z INFO  Service started normally",
            "2026-05-27T09:00:10Z INFO  Health check passed",
        ]

    return {
        "tool": "kubectl_get_logs",
        "pod": pod,
        "lines": lines,
        "line_count": len(lines),
    }
