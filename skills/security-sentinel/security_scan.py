#!/usr/bin/env python3
"""
REFINET Security Sentinel — Autonomous Defense Scanner
Runs auth anomaly detection, rate limit analysis, TLS monitoring,
wallet forensics, and BYOK gate validation. Emails admin security briefing.

Usage:
    python security_scan.py                          # Full scan, print report
    python security_scan.py --email                  # Full scan + email admin
    python security_scan.py --tls-only               # TLS cert check only
    python security_scan.py --gate-only              # BYOK gate validation only
    python security_scan.py --wallet 0xabc...        # Forensics on specific wallet
"""

import json
import os
import sys
import ssl
import socket
import sqlite3
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "public.db")
API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")
TLS_HOSTNAMES = ["api.refinet.io", "app.refinet.io"]


def get_db():
    if not Path(DB_PATH).exists():
        print(f"[security] DB not found: {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH, timeout=10)


ANOMALY_RULES = {
    "siwe_brute_force": {
        "severity": "HIGH",
        "description": "5+ failed SIWE sigs from same IP (1h)",
        "query": """SELECT ip_address, COUNT(*) as fails FROM audit_log
            WHERE event_type='auth.siwe.fail' AND timestamp > datetime('now','-1 hour')
            GROUP BY ip_address HAVING fails >= 5"""
    },
    "totp_brute_force": {
        "severity": "CRITICAL",
        "description": "3+ TOTP failures for same user (30min)",
        "query": """SELECT user_id, wallet_address, COUNT(*) as fails FROM audit_log
            WHERE event_type='auth.totp.fail' AND timestamp > datetime('now','-30 minutes')
            GROUP BY user_id HAVING fails >= 3"""
    },
    "credential_stuffing": {
        "severity": "CRITICAL",
        "description": "3+ users, 10+ attempts from same IP (1h)",
        "query": """SELECT ip_address, COUNT(DISTINCT COALESCE(user_id,wallet_address)) as users,
            COUNT(*) as attempts FROM audit_log
            WHERE event_type IN ('auth.login.fail','auth.siwe.fail') AND timestamp > datetime('now','-1 hour')
            GROUP BY ip_address HAVING users >= 3 AND attempts >= 10"""
    },
    "expired_jwt_reuse": {
        "severity": "MEDIUM",
        "description": "3+ expired token attempts per user/IP (1h)",
        "query": """SELECT user_id, ip_address, COUNT(*) as reuses FROM audit_log
            WHERE event_type='auth.token.expired' AND timestamp > datetime('now','-1 hour')
            GROUP BY user_id, ip_address HAVING reuses >= 3"""
    },
    "api_key_abuse": {
        "severity": "HIGH",
        "description": "10+ rate limit hits for same key (1h)",
        "query": """SELECT json_extract(details,'$.api_key_id') as kid, COUNT(*) as hits FROM audit_log
            WHERE event_type='rate_limit.hit' AND json_extract(details,'$.api_key_id') IS NOT NULL
            AND timestamp > datetime('now','-1 hour') GROUP BY kid HAVING hits >= 10"""
    },
    "rapid_key_creation": {
        "severity": "HIGH",
        "description": "3+ API keys created by same user (1h)",
        "query": """SELECT user_id, COUNT(*) as made FROM audit_log
            WHERE event_type='keys.create' AND timestamp > datetime('now','-1 hour')
            GROUP BY user_id HAVING made >= 3"""
    }
}


def run_anomaly_detection(db):
    detections = []
    if not db:
        return detections
    for name, rule in ANOMALY_RULES.items():
        try:
            rows = db.execute(rule["query"]).fetchall()
            if rows:
                detections.append({"rule": name, "severity": rule["severity"],
                    "description": rule["description"], "matches": len(rows),
                    "sample": str(rows[:3])[:200]})
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                detections.append({"rule": name, "severity": "ERROR",
                    "description": str(e)[:80], "matches": 0})
    return detections


def analyze_rate_limits(db):
    if not db:
        return {"hits_24h": 0, "classification": "NO_DB"}
    try:
        hits = db.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='rate_limit.hit' AND timestamp > datetime('now','-24 hours')").fetchone()[0]
        top = db.execute("SELECT ip_address, COUNT(*) as h FROM audit_log WHERE event_type='rate_limit.hit' AND timestamp > datetime('now','-24 hours') GROUP BY ip_address ORDER BY h DESC LIMIT 5").fetchall()
        top_ips = [{"ip": r[0], "hits": r[1]} for r in top]
        if hits > 100 and top_ips:
            pct = top_ips[0]["hits"] / hits * 100
            cls = "LIKELY_ABUSE" if pct > 50 else "TRAFFIC_SPIKE"
        else:
            cls, pct = "NORMAL", 0
        return {"hits_24h": hits, "top_ips": top_ips, "classification": cls}
    except sqlite3.OperationalError:
        return {"hits_24h": 0, "classification": "TABLE_MISSING"}


def check_tls(hostname, port=443):
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(10)
            s.connect((hostname, port))
            cert = s.getpeercert()
        exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (exp - datetime.now(timezone.utc)).days
        issuer = dict(x[0] for x in cert.get("issuer", []))
        lvl = "CRITICAL" if days <= 7 else "HIGH" if days <= 14 else "MEDIUM" if days <= 30 else "OK"
        return {"hostname": hostname, "valid": days > 0, "days_remaining": days,
                "expires": exp.isoformat(), "issuer": issuer.get("organizationName", "?"), "alert_level": lvl}
    except Exception as e:
        return {"hostname": hostname, "valid": False, "error": str(e)[:200], "alert_level": "CRITICAL", "days_remaining": -1}


def wallet_forensics(db, wallet=None, hours=24):
    if not db:
        return []
    try:
        if wallet:
            w, p = "WHERE wallet_address=? AND timestamp>datetime('now',?)", (wallet, f'-{hours} hours')
        else:
            w, p = "WHERE wallet_address IS NOT NULL AND timestamp>datetime('now',?)", (f'-{hours} hours',)
        rows = db.execute(f"""SELECT wallet_address, COUNT(*) as reqs, COUNT(DISTINCT endpoint) as ep,
            COUNT(DISTINCT ip_address) as ips,
            SUM(CASE WHEN status_code>=400 THEN 1 ELSE 0 END) as errs,
            SUM(CASE WHEN event_type='rate_limit.hit' THEN 1 ELSE 0 END) as rl
            FROM audit_log {w} GROUP BY wallet_address ORDER BY reqs DESC LIMIT 20""", p).fetchall()
    except sqlite3.OperationalError:
        return []
    results = []
    for r in rows:
        anomalies = []
        if r[2] > 50: anomalies.append({"type": "endpoint_sweep", "severity": "HIGH"})
        if r[3] > 5: anomalies.append({"type": "multi_ip", "severity": "MEDIUM"})
        if r[1] > 10 and r[4] / r[1] > 0.3: anomalies.append({"type": "high_errors", "severity": "MEDIUM"})
        if r[5] > 3: anomalies.append({"type": "rate_abuse", "severity": "HIGH"})
        results.append({"wallet": r[0][:12]+"...", "requests": r[1], "endpoints": r[2],
            "ips": r[3], "errors": r[4], "rate_hits": r[5], "anomalies": anomalies})
    return results


def validate_gate():
    res = {"tests": [], "all_passed": True}
    try:
        import httpx
        for ep, nm in [("/keys/create", "keys"), ("/provider-keys/", "provider")]:
            try:
                r = httpx.request("POST" if "create" in ep else "GET", f"{API_BASE}{ep}", timeout=10)
                ok = r.status_code in (401, 403)
                res["tests"].append({"name": nm, "passed": ok, "status": r.status_code})
                if not ok: res["all_passed"] = False
            except Exception as e:
                res["tests"].append({"name": nm, "passed": False, "error": str(e)[:80]})
                res["all_passed"] = False
    except ImportError:
        res["tests"].append({"name": "httpx", "passed": False, "error": "not installed"})
        res["all_passed"] = False
    return res


def format_report(anomalies, rates, tls_list, wallets, gate):
    threats = sum(1 for a in anomalies if a["severity"] in ("CRITICAL", "HIGH"))
    status = f"THREATS ({threats})" if threats else "CLEAR"
    lines = [f"Security: {status}", "=" * 40]
    for a in anomalies:
        lines.append(f"  [{a['severity']}] {a['rule']}: {a['matches']} matches")
    lines.append(f"  Rate limits: {rates.get('hits_24h',0)} hits ({rates.get('classification','?')})")
    for t in tls_list:
        lines.append(f"  TLS {t['hostname']}: {t.get('days_remaining','?')}d ({t.get('alert_level','?')})")
    lines.append(f"  Wallet flags: {sum(len(w.get('anomalies',[])) for w in wallets)}")
    lines.append(f"  BYOK gate: {'PASS' if gate.get('all_passed') else 'FAIL'}")
    text = "\n".join(lines)

    sc = {"CRITICAL":"#ff4444","HIGH":"#ff6b6b","MEDIUM":"#ffd93d","OK":"#00d4aa"}
    arows = "".join(f"<tr><td style='padding:6px;color:{sc.get(a['severity'],'#888')};font-weight:bold'>{a['severity']}</td><td style='padding:6px'>{a['rule']}</td><td style='padding:6px'>{a['matches']}</td></tr>" for a in anomalies)
    trows = "".join(f"<tr><td style='padding:6px;color:{sc.get(t.get('alert_level'),'#888')}'>{t.get('alert_level','?')}</td><td style='padding:6px'>{t['hostname']}</td><td style='padding:6px'>{t.get('days_remaining','?')}d</td></tr>" for t in tls_list)
    gc = "#00d4aa" if gate.get("all_passed") else "#ff4444"
    html = f"""<div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0;border-bottom:2px solid {'#ff4444' if threats else '#00d4aa'}">
        <h2 style="margin:0;font-size:18px">Security Sentinel — {status}</h2>
        <p style="margin:4px 0 0;font-size:12px;color:#888">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p></div>
      <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
        <h4 style="margin:0 0 8px">Auth anomalies</h4>
        {'<table style="width:100%;border-collapse:collapse">'+arows+'</table>' if anomalies else '<p style="color:#00d4aa">None</p>'}
        <h4 style="margin:16px 0 8px">Rate limits</h4><p style="color:#ccc">{rates.get('hits_24h',0)} hits — {rates.get('classification','?')}</p>
        <h4 style="margin:16px 0 8px">TLS</h4><table style="width:100%;border-collapse:collapse">{trows}</table>
        <h4 style="margin:16px 0 8px">Wallets</h4><p style="color:#ccc">{sum(len(w.get('anomalies',[])) for w in wallets)} flags</p>
        <h4 style="margin:16px 0 8px">BYOK gate</h4><p style="color:{gc};font-weight:bold">{'PASS' if gate.get('all_passed') else 'FAIL'}</p>
        <hr style="border:none;border-top:1px solid #333;margin:16px 0"><p style="font-size:11px;color:#666">GROOT Security Sentinel</p></div></div>"""
    return text, html


def send_email(subject, html, text):
    admin = os.getenv("ADMIN_EMAIL")
    if not admin: return
    msg = MIMEMultipart("alternative")
    msg["From"] = os.getenv("MAIL_FROM", "groot@refinet.io")
    msg["To"] = admin
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST","127.0.0.1"), int(os.getenv("SMTP_PORT","8025"))) as s:
            s.send_message(msg)
        print(f"[security] Email sent to {admin}")
    except Exception as e:
        print(f"[security] Email failed: {e}")


def main():
    db = get_db()
    wallet_arg = None
    for i, a in enumerate(sys.argv):
        if a == "--wallet" and i+1 < len(sys.argv): wallet_arg = sys.argv[i+1]

    if "--tls-only" in sys.argv:
        for t in [check_tls(h) for h in TLS_HOSTNAMES]: print(json.dumps(t, indent=2))
        sys.exit(0)
    if "--gate-only" in sys.argv:
        g = validate_gate(); print(json.dumps(g, indent=2)); sys.exit(0 if g["all_passed"] else 1)

    anomalies = run_anomaly_detection(db)
    rates = analyze_rate_limits(db)
    tls = [check_tls(h) for h in TLS_HOSTNAMES]
    wallets = wallet_forensics(db, wallet=wallet_arg)
    gate = validate_gate()

    text, html = format_report(anomalies, rates, tls, wallets, gate)
    print(text)

    if "--email" in sys.argv:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        th = sum(1 for a in anomalies if a["severity"] in ("CRITICAL","HIGH"))
        send_email(f"[REFINET SECURITY] {'THREATS' if th else 'Clear'} — {ts}", html, text)

    crit = any(a["severity"]=="CRITICAL" for a in anomalies)
    tls_crit = any(t.get("alert_level")=="CRITICAL" for t in tls)
    if db: db.close()
    sys.exit(1 if (crit or tls_crit or not gate.get("all_passed",True)) else 0)


if __name__ == "__main__":
    main()
