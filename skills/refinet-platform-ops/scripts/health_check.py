#!/usr/bin/env python3
"""
REFINET Cloud Platform Health Check
Runs all subsystem checks, formats report, emails admin if issues found.

Usage:
    python health_check.py                    # Check and print
    python health_check.py --email            # Check and email admin
    python health_check.py --email --always   # Email even if healthy
"""

import asyncio
import json
import os
import sys
import smtplib
import sqlite3
import shutil
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

try:
    import httpx
except ImportError:
    print("[ops] Installing httpx...")
    os.system(f"{sys.executable} -m pip install httpx -q")
    import httpx


API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")
BITNET_HOST = os.getenv("BITNET_HOST", "http://localhost:8080")


async def check_subsystem(client, name, method, url, **kwargs):
    """Check a single subsystem. Returns (name, result_dict)."""
    try:
        if method == "GET":
            r = await client.get(url, **kwargs)
        else:
            r = await client.post(url, **kwargs)
        return name, {
            "ok": 200 <= r.status_code < 300,
            "status_code": r.status_code,
            "latency_ms": round(r.elapsed.total_seconds() * 1000, 1)
        }
    except Exception as e:
        return name, {"ok": False, "error": str(e)[:200]}


async def run_all_checks():
    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        checks = await asyncio.gather(
            check_subsystem(client, "api", "GET", f"{API_BASE}/health"),
            check_subsystem(client, "bitnet", "POST", f"{BITNET_HOST}/v1/chat/completions",
                json={"model": "bitnet-b1.58-2b", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}),
            return_exceptions=True
        )
        for item in checks:
            if isinstance(item, tuple):
                results[item[0]] = item[1]
            else:
                results["unknown"] = {"ok": False, "error": str(item)}

    # Database check (sync)
    try:
        db_path = os.getenv("DATABASE_PATH", "public.db")
        if Path(db_path).exists():
            conn = sqlite3.connect(db_path, timeout=5)
            conn.execute("SELECT 1")
            conn.close()
            results["database"] = {"ok": True}
        else:
            results["database"] = {"ok": False, "error": f"DB not found: {db_path}"}
    except Exception as e:
        results["database"] = {"ok": False, "error": str(e)[:200]}

    # SMTP check
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "127.0.0.1"), int(os.getenv("SMTP_PORT", "8025")), timeout=5) as s:
            s.noop()
        results["smtp"] = {"ok": True}
    except Exception as e:
        results["smtp"] = {"ok": False, "error": str(e)[:200]}

    # Disk check
    total, used, free = shutil.disk_usage("/")
    results["disk"] = {
        "ok": (free / total) > 0.10,
        "total_gb": round(total / (1024**3), 1),
        "free_gb": round(free / (1024**3), 1),
        "used_pct": round((used / total) * 100, 1)
    }

    # Memory check (Linux only)
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        meminfo = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                meminfo[parts[0].strip()] = parts[1].strip()
        total_mem = int(meminfo.get("MemTotal", "0 kB").split()[0])
        avail_mem = int(meminfo.get("MemAvailable", "0 kB").split()[0])
        results["memory"] = {
            "ok": (avail_mem / total_mem) > 0.15 if total_mem > 0 else False,
            "total_mb": round(total_mem / 1024),
            "available_mb": round(avail_mem / 1024),
            "used_pct": round((1 - avail_mem / total_mem) * 100, 1) if total_mem > 0 else 0
        }
    except FileNotFoundError:
        results["memory"] = {"ok": True, "note": "Non-Linux — skipped"}

    # Agent queue depth check
    try:
        db_path = os.getenv("DATABASE_PATH", "public.db")
        if Path(db_path).exists():
            conn = sqlite3.connect(db_path, timeout=5)
            row = conn.execute("SELECT COUNT(*) FROM agent_tasks WHERE status = 'pending'").fetchone()
            pending = row[0] if row else 0
            conn.close()
            results["agent_queue"] = {
                "ok": pending < 50,
                "pending_tasks": pending,
                "warning": "Queue depth > 200" if pending >= 200 else ("Queue depth > 50" if pending >= 50 else None),
            }
    except Exception as e:
        results["agent_queue"] = {"ok": True, "note": f"Skipped: {str(e)[:100]}"}

    # Memory storage growth check
    try:
        memory_dir = Path(os.getenv("REFINET_ROOT", ".")) / "memory"
        large_files = []
        if memory_dir.exists():
            for subdir in ("episodic", "semantic", "procedural"):
                d = memory_dir / subdir
                if d.exists():
                    for f in d.iterdir():
                        if f.is_file() and f.stat().st_size > 100 * 1024 * 1024:
                            large_files.append(f"{subdir}/{f.name}: {f.stat().st_size // (1024*1024)}MB")
        results["memory_storage"] = {
            "ok": len(large_files) == 0,
            "large_files": large_files if large_files else None,
        }
    except Exception as e:
        results["memory_storage"] = {"ok": True, "note": f"Skipped: {str(e)[:100]}"}

    # Embedding index health check
    try:
        db_path = os.getenv("DATABASE_PATH", "public.db")
        if Path(db_path).exists():
            conn = sqlite3.connect(db_path, timeout=5)
            total_row = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()
            embedded_row = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE embedding IS NOT NULL").fetchone()
            conn.close()
            total = total_row[0] if total_row else 0
            embedded = embedded_row[0] if embedded_row else 0
            missing_pct = ((total - embedded) / total * 100) if total > 0 else 0
            results["embedding_index"] = {
                "ok": missing_pct <= 10,
                "total_chunks": total,
                "embedded": embedded,
                "missing_pct": round(missing_pct, 1),
            }
    except Exception as e:
        results["embedding_index"] = {"ok": True, "note": f"Skipped: {str(e)[:100]}"}

    return results


def format_report(results):
    all_ok = all(r.get("ok", False) for r in results.values())
    status = "✅ ALL SYSTEMS OPERATIONAL" if all_ok else "🚨 ISSUES DETECTED"

    lines = [status, "=" * 40]
    for name, data in results.items():
        icon = "✅" if data.get("ok") else "❌"
        detail = ""
        if "latency_ms" in data:
            detail = f" ({data['latency_ms']}ms)"
        elif "error" in data:
            detail = f" — {data['error']}"
        elif "used_pct" in data:
            detail = f" ({data['used_pct']}% used)"
        lines.append(f"  {icon} {name}{detail}")

    return "\n".join(lines), all_ok


def send_email(subject, html_body, text_body):
    admin = os.getenv("ADMIN_EMAIL")
    if not admin:
        print("[ops] ADMIN_EMAIL not set — skipping email")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = os.getenv("MAIL_FROM", "groot@refinet.io")
    msg["To"] = admin
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "127.0.0.1"), int(os.getenv("SMTP_PORT", "8025"))) as server:
            server.send_message(msg)
        print(f"[ops] Email sent to {admin}")
    except Exception as e:
        print(f"[ops] Email failed: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="REFINET Platform Health Check")
    parser.add_argument("--email", action="store_true", help="Send email report on failure (or always with --always)")
    parser.add_argument("--always", action="store_true", help="Send email even when all checks pass")
    args = parser.parse_args()

    results = asyncio.run(run_all_checks())
    report_text, all_ok = format_report(results)
    print(report_text)

    should_email = args.email
    always_email = args.always

    if should_email and (not all_ok or always_email):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        status = "All Systems Operational" if all_ok else "Issues Detected"
        subject = f"[REFINET HEALTH] {status} — {ts}"

        # Build HTML (inline for email compatibility)
        rows = ""
        for name, data in results.items():
            ok = data.get("ok", False)
            icon = "✅" if ok else "❌"
            detail = ""
            if "latency_ms" in data:
                detail = f"{data['latency_ms']}ms"
            elif "error" in data:
                detail = f"<span style='color:#ff6b6b'>{data['error'][:80]}</span>"
            elif "used_pct" in data:
                detail = f"{data['used_pct']}% used"
            rows += f"<tr><td style='padding:6px'>{icon}</td><td style='padding:6px'><b>{name}</b></td><td style='padding:6px'>{detail}</td></tr>"

        html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0;font-size:18px">🌱 REFINET Cloud — Health Report</h2>
            <p style="margin:4px 0 0;font-size:12px;color:#888">{ts}</p>
          </div>
          <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
            <table style="width:100%;border-collapse:collapse">{rows}</table>
          </div>
        </div>
        """
        send_email(subject, html, report_text)

    # Write result for automation consumption
    print(json.dumps(results, indent=2))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
