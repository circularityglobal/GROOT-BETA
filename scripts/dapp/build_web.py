#!/usr/bin/env python3
"""Build a web project using npm install + npm run build."""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "build_web",
    "description": "Build a web project (npm install + npm run build)",
    "category": "dapp",
    "requires_admin": False,
}


def run_command(cmd, cwd, label, timeout=300):
    """Run a command and print its output."""
    print(f"\n--- {label} ---")
    print(f"  Running: {' '.join(cmd)}")
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        elapsed = time.time() - start

        if result.stdout.strip():
            # Print last 30 lines of stdout to avoid overwhelming output
            lines = result.stdout.strip().split("\n")
            if len(lines) > 30:
                print(f"  ... ({len(lines) - 30} lines omitted)")
                for line in lines[-30:]:
                    print(f"  {line}")
            else:
                for line in lines:
                    print(f"  {line}")

        if result.returncode != 0:
            print(f"\n  FAILED (exit {result.returncode}, {elapsed:.1f}s)")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n")[-20:]:
                    print(f"  STDERR: {line}")
            return False

        print(f"  OK ({elapsed:.1f}s)")
        return True

    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return False
    except FileNotFoundError:
        print(f"  ERROR: {cmd[0]} not found in PATH")
        return False


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    project_path = args.get("project_path", "")
    skip_install = args.get("skip_install", False)
    build_script = args.get("build_script", "build")

    if not project_path:
        print("ERROR: project_path is required")
        print('Usage: SCRIPT_ARGS=\'{"project_path":"/path/to/project"}\' python scripts/dapp/build_web.py')
        print('  Optional: "skip_install":true, "build_script":"build:prod"')
        sys.exit(1)

    if not os.path.isdir(project_path):
        print(f"ERROR: {project_path} is not a directory")
        sys.exit(1)

    package_json = os.path.join(project_path, "package.json")
    if not os.path.isfile(package_json):
        print(f"ERROR: No package.json found in {project_path}")
        sys.exit(1)

    print(f"=== Web Project Build ===")
    print(f"  Project: {project_path}")

    # Read package.json for info
    try:
        with open(package_json) as f:
            pkg = json.load(f)
        print(f"  Name: {pkg.get('name', 'unknown')}")
        print(f"  Version: {pkg.get('version', 'unknown')}")
        available_scripts = list(pkg.get("scripts", {}).keys())
        print(f"  Scripts: {', '.join(available_scripts)}")
    except Exception as e:
        print(f"  Warning: Could not parse package.json: {e}")

    success = True

    # Step 1: npm install
    if not skip_install:
        if not run_command(["npm", "install"], project_path, "npm install", timeout=180):
            success = False

    # Step 2: npm run build
    if success:
        if not run_command(["npm", "run", build_script], project_path, f"npm run {build_script}", timeout=300):
            success = False

    print()
    if success:
        # Check for build output
        common_output_dirs = ["dist", "build", "out", ".next", "public"]
        for d in common_output_dirs:
            output_dir = os.path.join(project_path, d)
            if os.path.isdir(output_dir):
                file_count = sum(len(f) for _, _, f in os.walk(output_dir))
                print(f"  Build output: {d}/ ({file_count} files)")
                break

        print("\nBuild completed successfully!")
    else:
        print("\nBuild FAILED. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
