#!/usr/bin/env python3
"""Deploy static files to a local serve directory."""

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "deploy_static",
    "description": "Deploy static files to a local serve directory",
    "category": "ops",
    "requires_admin": True,
}

# Default base directory for serving static deployments
DEFAULT_SERVE_ROOT = os.environ.get("GROOT_STATIC_ROOT", "/var/www/groot-static")


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    source_dir = args.get("source_dir", "")
    target_name = args.get("target_name", "")
    serve_root = args.get("serve_root", DEFAULT_SERVE_ROOT)
    clean = args.get("clean", False)

    if not source_dir or not target_name:
        print("ERROR: source_dir and target_name are required")
        print('Usage: SCRIPT_ARGS=\'{"source_dir":"/path/to/dist","target_name":"my-app"}\' python scripts/ops/deploy_static.py')
        print('  Optional: "serve_root":"/var/www", "clean":true')
        sys.exit(1)

    if not os.path.isdir(source_dir):
        print(f"ERROR: Source directory does not exist: {source_dir}")
        sys.exit(1)

    # Sanitize target name
    target_name = target_name.replace(" ", "-").replace("/", "-").replace("..", "").lower()
    target_path = os.path.join(serve_root, target_name)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{target_path}.backup-{timestamp}"

    print(f"=== Static File Deployment ===")
    print(f"  Source: {source_dir}")
    print(f"  Target: {target_path}")
    print()

    # Count source files
    source_files = 0
    source_size = 0
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            source_files += 1
            fp = os.path.join(root, f)
            try:
                source_size += os.path.getsize(fp)
            except OSError:
                pass

    print(f"  Source files: {source_files}")
    print(f"  Source size: {source_size / 1024 / 1024:.2f} MB")
    print()

    if source_files == 0:
        print("ERROR: Source directory is empty")
        sys.exit(1)

    try:
        # Create serve root if needed
        os.makedirs(serve_root, exist_ok=True)

        # Backup existing deployment
        if os.path.exists(target_path):
            print(f"  Backing up existing deployment to {backup_path}")
            shutil.move(target_path, backup_path)

        # Clean or copy
        if clean and os.path.exists(target_path):
            shutil.rmtree(target_path)

        # Deploy files
        print("  Copying files...")
        shutil.copytree(source_dir, target_path, dirs_exist_ok=True)

        # Verify deployment
        deployed_files = 0
        deployed_size = 0
        for root, dirs, files in os.walk(target_path):
            for f in files:
                deployed_files += 1
                fp = os.path.join(root, f)
                try:
                    deployed_size += os.path.getsize(fp)
                except OSError:
                    pass

        print()
        print(f"  Deployed: {deployed_files} files ({deployed_size / 1024 / 1024:.2f} MB)")
        print(f"  Location: {target_path}")

        # Check for index.html
        index_path = os.path.join(target_path, "index.html")
        if os.path.isfile(index_path):
            print(f"  Entry point: {index_path}")
        else:
            print("  Warning: No index.html found in deployed files")

        # Cleanup old backup if deploy succeeded
        if os.path.exists(backup_path):
            print(f"\n  Previous version backed up at: {backup_path}")
            print("  Run cleanup to remove old backups when ready.")

        print("\nDeployment successful!")

    except PermissionError as e:
        print(f"ERROR: Permission denied: {e}")
        print("  Try running with appropriate permissions or change serve_root.")
        # Restore backup if exists
        if os.path.exists(backup_path) and not os.path.exists(target_path):
            shutil.move(backup_path, target_path)
            print("  Restored previous deployment from backup.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Deployment failed: {e}")
        # Restore backup if exists
        if os.path.exists(backup_path) and not os.path.exists(target_path):
            shutil.move(backup_path, target_path)
            print("  Restored previous deployment from backup.")
        sys.exit(1)


if __name__ == "__main__":
    main()
