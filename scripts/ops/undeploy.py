#!/usr/bin/env python3
"""Stop and remove a deployed Docker service."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "undeploy",
    "description": "Stop and remove a deployed Docker service",
    "category": "ops",
    "requires_admin": True,
}


def run_docker(cmd, label, timeout=30):
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
    remove_volumes = args.get("remove_volumes", False)
    remove_image = args.get("remove_image", False)

    if not service_name:
        print("ERROR: service_name is required")
        print('Usage: SCRIPT_ARGS=\'{"service_name":"my-api"}\' python scripts/ops/undeploy.py')
        print('  Optional: "remove_volumes":true, "remove_image":true')
        sys.exit(1)

    container_name = f"groot-{service_name}"

    print(f"=== Undeploy Service ===")
    print(f"  Service: {service_name}")
    print(f"  Container: {container_name}")
    print()

    # Step 1: Check if container exists
    print("--- Container Info ---")
    ok, inspect_out = run_docker(
        ["inspect", "--format",
         "Status: {{.State.Status}}\nImage: {{.Config.Image}}\nCreated: {{.Created}}",
         container_name],
        "inspect",
        timeout=10,
    )

    if not ok:
        print(f"\n  Container '{container_name}' not found.")
        # Try listing groot containers to help user
        ok, ps_out = run_docker(
            ["ps", "-a", "--filter", "label=groot.service", "--format",
             "{{.Names}}\t{{.Status}}\t{{.Image}}"],
            "list",
            timeout=10,
        )
        if ok and ps_out:
            print("\n  Available GROOT services:")
            for line in ps_out.split("\n"):
                print(f"    {line}")
        sys.exit(1)

    print(f"    {inspect_out}")

    # Capture image name before removal
    image_name = ""
    ok, img = run_docker(
        ["inspect", "--format", "{{.Config.Image}}", container_name],
        "get-image",
        timeout=10,
    )
    if ok:
        image_name = img.strip()

    # Step 2: Stop container
    print("\n--- Stopping ---")
    ok, status = run_docker(
        ["inspect", "--format", "{{.State.Status}}", container_name],
        "status",
        timeout=10,
    )

    if ok and status == "running":
        ok, _ = run_docker(["stop", container_name], "stop", timeout=30)
        if ok:
            print("    Container stopped")
        else:
            print("    Warning: Failed to stop gracefully, force killing...")
            run_docker(["kill", container_name], "kill", timeout=10)
    else:
        print(f"    Container already stopped (status: {status})")

    # Step 3: Remove container
    print("\n--- Removing ---")
    rm_cmd = ["rm"]
    if remove_volumes:
        rm_cmd.append("-v")
    rm_cmd.append(container_name)

    ok, _ = run_docker(rm_cmd, "remove")
    if ok:
        print("    Container removed")
    else:
        print("    Warning: Failed to remove container")

    # Step 4: Remove image (optional)
    if remove_image and image_name:
        print("\n--- Image Cleanup ---")
        ok, _ = run_docker(["rmi", image_name], "remove-image", timeout=30)
        if ok:
            print(f"    Image {image_name} removed")
        else:
            print(f"    Warning: Could not remove image (may be used by other containers)")

    # Step 5: Verify
    print("\n--- Verification ---")
    ok, _ = run_docker(["inspect", container_name], "verify", timeout=10)
    if not ok:
        print(f"    Container '{container_name}' successfully removed")
    else:
        print(f"    WARNING: Container '{container_name}' still exists")

    print(f"\nUndeploy complete for service '{service_name}'")


if __name__ == "__main__":
    main()
