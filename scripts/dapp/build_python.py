#!/usr/bin/env python3
"""Build a Python project: install dependencies and run tests."""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "build_python",
    "description": "Build a Python project (pip install -r requirements.txt + pytest)",
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
    skip_tests = args.get("skip_tests", False)
    python_bin = args.get("python", "python3")

    if not project_path:
        print("ERROR: project_path is required")
        print('Usage: SCRIPT_ARGS=\'{"project_path":"/path/to/project"}\' python scripts/dapp/build_python.py')
        print('  Optional: "skip_install":true, "skip_tests":true, "python":"python3.11"')
        sys.exit(1)

    if not os.path.isdir(project_path):
        print(f"ERROR: {project_path} is not a directory")
        sys.exit(1)

    print(f"=== Python Project Build ===")
    print(f"  Project: {project_path}")

    # Detect project type
    has_requirements = os.path.isfile(os.path.join(project_path, "requirements.txt"))
    has_setup_py = os.path.isfile(os.path.join(project_path, "setup.py"))
    has_pyproject = os.path.isfile(os.path.join(project_path, "pyproject.toml"))
    has_pipfile = os.path.isfile(os.path.join(project_path, "Pipfile"))

    detected = []
    if has_requirements:
        detected.append("requirements.txt")
    if has_setup_py:
        detected.append("setup.py")
    if has_pyproject:
        detected.append("pyproject.toml")
    if has_pipfile:
        detected.append("Pipfile")

    print(f"  Detected: {', '.join(detected) if detected else 'no known config files'}")

    # Check for test directories
    test_dirs = ["tests", "test", "spec"]
    found_tests = [d for d in test_dirs if os.path.isdir(os.path.join(project_path, d))]
    has_tests = bool(found_tests)
    if found_tests:
        print(f"  Test dirs: {', '.join(found_tests)}")

    success = True

    # Step 1: Install dependencies
    if not skip_install:
        if has_requirements:
            if not run_command(
                [python_bin, "-m", "pip", "install", "-r", "requirements.txt"],
                project_path,
                "Install requirements",
                timeout=180,
            ):
                success = False
        elif has_pyproject:
            if not run_command(
                [python_bin, "-m", "pip", "install", "-e", "."],
                project_path,
                "Install from pyproject.toml",
                timeout=180,
            ):
                success = False
        elif has_setup_py:
            if not run_command(
                [python_bin, "-m", "pip", "install", "-e", "."],
                project_path,
                "Install from setup.py",
                timeout=180,
            ):
                success = False
        else:
            print("\n  No dependency file found, skipping install.")

    # Step 2: Run tests
    if success and not skip_tests:
        if has_tests or has_pyproject:
            if not run_command(
                [python_bin, "-m", "pytest", "-v", "--tb=short"],
                project_path,
                "Run tests (pytest)",
                timeout=300,
            ):
                success = False
        else:
            print("\n  No test directory found, skipping tests.")

    # Step 3: Syntax check (quick validation)
    if success:
        print("\n--- Syntax Check ---")
        py_files = []
        for root, dirs, files in os.walk(project_path):
            # Skip common non-source directories
            rel = os.path.relpath(root, project_path)
            skip = {"venv", ".venv", "__pycache__", ".git", "node_modules", ".tox", "dist"}
            if any(part in skip for part in rel.split(os.sep)):
                continue
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))

        errors = 0
        for pf in py_files:
            try:
                with open(pf) as fh:
                    compile(fh.read(), pf, "exec")
            except SyntaxError as e:
                errors += 1
                rel_path = os.path.relpath(pf, project_path)
                print(f"  SyntaxError in {rel_path}: {e.msg} (line {e.lineno})")

        if errors:
            print(f"  {errors} file(s) with syntax errors")
        else:
            print(f"  {len(py_files)} Python files OK")

    print()
    if success:
        print("Build completed successfully!")
    else:
        print("Build FAILED. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
