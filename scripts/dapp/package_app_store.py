#!/usr/bin/env python3
"""Package a project directory into a ZIP for App Store submission."""

import json
import os
import sys
import zipfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "package_app_store",
    "description": "Package a project directory into a ZIP for App Store submission",
    "category": "dapp",
    "requires_admin": False,
}

# Directories and patterns to exclude from packaging
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".pytest_cache", ".mypy_cache", ".eggs",
    "dist", "build", ".next", ".nuxt",
}

EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".egg-info", ".DS_Store",
    ".env", ".env.local", ".env.production",
}

EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db", ".env", ".env.local",
    ".env.production", ".env.development",
}


def should_exclude(rel_path, filename):
    """Check if a file should be excluded from the package."""
    parts = rel_path.split(os.sep)
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True

    if filename in EXCLUDE_FILES:
        return True

    _, ext = os.path.splitext(filename)
    if ext in EXCLUDE_EXTENSIONS:
        return True

    return False


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    project_path = args.get("project_path", "")
    output_name = args.get("output_name", "")
    output_dir = args.get("output_dir", ".")

    if not project_path:
        print("ERROR: project_path is required")
        print('Usage: SCRIPT_ARGS=\'{"project_path":"/path/to/project","output_name":"my-app"}\' python scripts/dapp/package_app_store.py')
        sys.exit(1)

    if not os.path.isdir(project_path):
        print(f"ERROR: {project_path} is not a directory")
        sys.exit(1)

    # Derive output name from directory if not provided
    if not output_name:
        output_name = os.path.basename(os.path.abspath(project_path))

    # Sanitize output name
    output_name = output_name.replace(" ", "-").lower()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    zip_filename = f"{output_name}-{timestamp}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    print(f"=== App Store Packager ===")
    print(f"  Source: {project_path}")
    print(f"  Output: {zip_path}")
    print()

    # Validate the project has required files
    print("--- Validation ---")
    warnings = []

    # Check for a manifest or package descriptor
    has_manifest = False
    manifest_files = ["package.json", "pyproject.toml", "setup.py", "Cargo.toml", "manifest.json"]
    for mf in manifest_files:
        if os.path.isfile(os.path.join(project_path, mf)):
            print(f"  Found: {mf}")
            has_manifest = True

    if not has_manifest:
        warnings.append("No package manifest found (package.json, pyproject.toml, etc.)")

    # Check for README
    readme_files = ["README.md", "README.txt", "README", "readme.md"]
    has_readme = any(os.path.isfile(os.path.join(project_path, rf)) for rf in readme_files)
    if not has_readme:
        warnings.append("No README file found (recommended for App Store listing)")

    # Check for LICENSE
    license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
    has_license = any(os.path.isfile(os.path.join(project_path, lf)) for lf in license_files)
    if not has_license:
        warnings.append("No LICENSE file found (required for App Store submission)")

    if warnings:
        print("\n  Warnings:")
        for w in warnings:
            print(f"    - {w}")
    print()

    # Build the ZIP
    print("--- Packaging ---")
    os.makedirs(output_dir, exist_ok=True)

    file_count = 0
    total_size = 0
    excluded_count = 0

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, dirs, files in os.walk(project_path):
                # Prune excluded directories in-place
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

                for filename in sorted(files):
                    rel_dir = os.path.relpath(root, project_path)
                    rel_path = os.path.join(rel_dir, filename) if rel_dir != "." else filename

                    if should_exclude(rel_path, filename):
                        excluded_count += 1
                        continue

                    full_path = os.path.join(root, filename)

                    try:
                        file_size = os.path.getsize(full_path)
                        # Skip files larger than 50MB
                        if file_size > 50 * 1024 * 1024:
                            warnings.append(f"Skipped large file: {rel_path} ({file_size / 1024 / 1024:.1f} MB)")
                            excluded_count += 1
                            continue

                        archive_name = os.path.join(output_name, rel_path)
                        zf.write(full_path, archive_name)
                        file_count += 1
                        total_size += file_size
                    except (PermissionError, OSError) as e:
                        print(f"  Warning: Could not add {rel_path}: {e}")

        zip_size = os.path.getsize(zip_path)
        compression_ratio = (1 - zip_size / total_size) * 100 if total_size > 0 else 0

        print(f"  Files included: {file_count}")
        print(f"  Files excluded: {excluded_count}")
        print(f"  Source size: {total_size / 1024 / 1024:.2f} MB")
        print(f"  Package size: {zip_size / 1024 / 1024:.2f} MB")
        print(f"  Compression: {compression_ratio:.1f}%")
        print()
        print(f"Package created: {zip_path}")
        print(f"\nReady for App Store submission via POST /app-store/submit")

    except Exception as e:
        print(f"ERROR: Failed to create package: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
