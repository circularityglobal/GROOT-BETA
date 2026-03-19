#!/usr/bin/env python3
"""Deploy a service via Docker."""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "deploy_service",
    "description": "Deploy a service via Docker container",
    "category": "ops",
    "requires_admin": True,
}


def run_docker(cmd, label, timeout=120):
    """Run a docker command and return (success, stdout)."""
    print(f"  [{label}] docker {' '.join(cmd)}")
    try:
        result = subprocess.run(
            ["docker"] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            print(f"    FAILED: {result.stderr.strip()}")
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT after {timeout}s")
        return False, "timeout"
    except FileNotFoundError:
        print("    ERROR: docker is not installed or not in PATH")
        return False, "docker not found"


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    service_name = args.get("service_name", "")
    image_tag = args.get("image_tag", "")
    ports = args.get("ports", [])           # e.g., ["8080:80", "443:443"]
    env_vars = args.get("env_vars", {})     # e.g., {"NODE_ENV": "production"}
    volumes = args.get("volumes", [])       # e.g., ["/data:/app/data"]
    network = args.get("network", "groot-net")
    restart_policy = args.get("restart_policy", "unless-stopped")
    memory_limit = args.get("memory_limit", "512m")

    if not service_name or not image_tag:
        print("ERROR: service_name and image_tag are required")
        print('Usage: SCRIPT_ARGS=\'{"service_name":"my-api","image_tag":"myapp:latest"}\' python scripts/ops/deploy_service.py')
        print('  Optional: "ports":["8080:80"], "env_vars":{"KEY":"VAL"}, "volumes":["/data:/app/data"]')
        print('  Optional: "network":"groot-net", "restart_policy":"unless-stopped", "memory_limit":"512m"')
        sys.exit(1)

    container_name = f"groot-{service_name}"

    print(f"=== Docker Service Deployment ===")
    print(f"  Service: {service_name}")
    print(f"  Container: {container_name}")
    print(f"  Image: {image_tag}")
    if ports:
        print(f"  Ports: {', '.join(ports)}")
    if volumes:
        print(f"  Volumes: {', '.join(volumes)}")
    print(f"  Network: {network}")
    print(f"  Memory: {memory_limit}")
    print()

    # Step 1: Check if Docker is available
    print("--- Pre-flight ---")
    ok, version = run_docker(["--version"], "version")
    if not ok:
        print("ERROR: Docker is not available")
        sys.exit(1)
    print(f"    {version}")

    # Step 2: Create network if needed
    run_docker(["network", "create", network], "network", timeout=10)
    # Ignore error if network already exists

    # Step 3: Stop and remove existing container
    print("\n--- Cleanup ---")
    ok, _ = run_docker(["inspect", container_name], "inspect", timeout=10)
    if ok:
        print(f"  Existing container found, stopping...")
        run_docker(["stop", container_name], "stop", timeout=30)
        run_docker(["rm", container_name], "remove", timeout=10)
    else:
        print(f"  No existing container '{container_name}'")

    # Step 4: Pull image if it looks like a registry image
    print("\n--- Image ---")
    if ":" in image_tag and "/" in image_tag:
        ok, _ = run_docker(["pull", image_tag], "pull", timeout=300)
        if not ok:
            print("WARNING: Could not pull image, trying local image")

    # Step 5: Build run command
    print("\n--- Deploy ---")
    run_cmd = [
        "run", "-d",
        "--name", container_name,
        "--network", network,
        "--restart", restart_policy,
        "--memory", memory_limit,
        "--label", f"groot.service={service_name}",
        "--label", f"groot.deployed={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
    ]

    for port in ports:
        run_cmd.extend(["-p", port])

    for key, value in env_vars.items():
        run_cmd.extend(["-e", f"{key}={value}"])

    for vol in volumes:
        run_cmd.extend(["-v", vol])

    run_cmd.append(image_tag)

    ok, container_id = run_docker(run_cmd, "start", timeout=60)
    if not ok:
        print("\nERROR: Failed to start container")
        sys.exit(1)

    print(f"    Container ID: {container_id[:12]}")

    # Step 6: Verify container is running
    time.sleep(2)
    ok, status = run_docker(
        ["inspect", "--format", "{{.State.Status}}", container_name],
        "verify",
        timeout=10,
    )

    if ok and status == "running":
        print(f"\n  Container status: RUNNING")

        # Show port mappings
        ok, port_info = run_docker(
            ["port", container_name],
            "ports",
            timeout=10,
        )
        if ok and port_info:
            print(f"  Port mappings:")
            for line in port_info.split("\n"):
                print(f"    {line}")

        print(f"\nDeployment successful!")
        print(f"  Container: {container_name}")
        print(f"  Manage: docker logs {container_name}")
    else:
        print(f"\n  Container status: {status if ok else 'UNKNOWN'}")
        # Show logs for debugging
        ok, logs = run_docker(["logs", "--tail", "20", container_name], "logs", timeout=10)
        if ok and logs:
            print(f"\n  Recent logs:")
            for line in logs.split("\n"):
                print(f"    {line}")
        print("\nWARNING: Container may not be running properly. Check logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
