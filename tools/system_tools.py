"""
Mock system-level tool implementations for InfraGPT.
Covers: CPU, disk, memory, network checks on nodes.
"""

from datetime import datetime


def check_node_cpu(ctx: dict) -> dict:
    """Simulate: top / mpstat — node CPU utilization."""
    node = ctx.get("node", "node-01")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "pod-crash":
        usage_percent = 94
        top_processes = [
            {"pid": 18432, "cmd": "python3 model_server.py", "cpu_pct": 87.2, "mem_pct": 78.4},
            {"pid": 1823, "cmd": "kubelet", "cpu_pct": 3.1, "mem_pct": 1.2},
            {"pid": 2991, "cmd": "containerd", "cpu_pct": 2.4, "mem_pct": 0.9},
        ]
        status = "CRITICAL"
        threshold = 80
    elif scenario == "disk-pressure":
        usage_percent = 42
        top_processes = [
            {"pid": 7821, "cmd": "log-collector", "cpu_pct": 38.1, "mem_pct": 12.3},
            {"pid": 1823, "cmd": "kubelet", "cpu_pct": 2.8, "mem_pct": 1.1},
        ]
        status = "NORMAL"
        threshold = 80
    else:
        usage_percent = 31
        top_processes = [
            {"pid": 1823, "cmd": "kubelet", "cpu_pct": 15.2, "mem_pct": 3.1},
            {"pid": 2991, "cmd": "containerd", "cpu_pct": 10.4, "mem_pct": 1.8},
        ]
        status = "NORMAL"
        threshold = 80

    return {
        "tool": "check_node_cpu",
        "node": node,
        "usage_percent": usage_percent,
        "threshold": threshold,
        "status": status,
        "top_processes": top_processes,
        "timestamp": datetime.utcnow().isoformat(),
    }


def check_disk(ctx: dict) -> dict:
    """Simulate: df -h — filesystem usage on a node."""
    node = ctx.get("node", "node-01")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "disk-pressure":
        use_percent = 97
        used_gb = 97
        total_gb = 100
        free_gb = 3
        status = "CRITICAL"
        mount_details = [
            {"mount": "/", "used_pct": 97, "free_gb": 3, "type": "ext4"},
            {"mount": "/var/log", "used_pct": 99, "free_gb": 0.2, "type": "ext4"},
            {"mount": "/var/lib/docker", "used_pct": 91, "free_gb": 4.5, "type": "overlay2"},
        ]
        large_dirs = [
            "/var/log/pods: 28GB",
            "/var/lib/docker/overlay2: 41GB",
            "/var/log/journal: 12GB",
        ]
    elif scenario == "pod-crash":
        use_percent = 67
        used_gb = 67
        total_gb = 100
        free_gb = 33
        status = "NORMAL"
        mount_details = [
            {"mount": "/", "used_pct": 67, "free_gb": 33, "type": "ext4"},
        ]
        large_dirs = []
    else:
        use_percent = 45
        used_gb = 45
        total_gb = 100
        free_gb = 55
        status = "NORMAL"
        mount_details = [
            {"mount": "/", "used_pct": 45, "free_gb": 55, "type": "ext4"},
        ]
        large_dirs = []

    return {
        "tool": "check_disk",
        "node": node,
        "use_percent": use_percent,
        "used_gb": used_gb,
        "total_gb": total_gb,
        "free_gb": free_gb,
        "status": status,
        "mount_details": mount_details,
        "large_dirs": large_dirs,
        "timestamp": datetime.utcnow().isoformat(),
    }


def check_node_memory(ctx: dict) -> dict:
    """Simulate: free -h — memory utilization on node."""
    node = ctx.get("node", "node-01")
    scenario = ctx.get("scenario_id", "pod-crash")

    if scenario == "pod-crash":
        used_gb = 14.2
        total_gb = 16.0
        free_gb = 1.8
        use_percent = 88
        status = "WARNING"
    elif scenario == "disk-pressure":
        used_gb = 6.1
        total_gb = 16.0
        free_gb = 9.9
        use_percent = 38
        status = "NORMAL"
    else:
        used_gb = 8.0
        total_gb = 16.0
        free_gb = 8.0
        use_percent = 50
        status = "NORMAL"

    return {
        "tool": "check_node_memory",
        "node": node,
        "used_gb": used_gb,
        "total_gb": total_gb,
        "free_gb": free_gb,
        "use_percent": use_percent,
        "status": status,
    }
