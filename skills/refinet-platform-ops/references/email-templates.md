# REFINET Admin Email Templates

Use these templates for each alert category. All templates use inline CSS for maximum email client compatibility.

## Base Template (wrap all alerts in this)

```python
def build_email_html(category: str, subject: str, body_content: str, timestamp: str = None) -> str:
    from datetime import datetime, timezone
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a1a;">
      <div style="background: #1a1a2e; color: #e0e0e0; padding: 16px 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #00d4aa;">
        <h2 style="margin: 0; font-size: 18px;">🌱 REFINET Cloud — {category}</h2>
        <p style="margin: 4px 0 0; font-size: 12px; color: #888;">{ts}</p>
      </div>
      <div style="background: #16213e; color: #e0e0e0; padding: 20px; border-radius: 0 0 8px 8px;">
        <h3 style="margin: 0 0 12px; color: #00d4aa;">{subject}</h3>
        {body_content}
        <hr style="border: none; border-top: 1px solid #333; margin: 16px 0;">
        <p style="font-size: 11px; color: #666; margin: 0;">
          Sent by GROOT Platform Ops Agent · 
          <a href="https://app.refinet.io" style="color: #00d4aa; text-decoration: none;">app.refinet.io</a>
        </p>
      </div>
    </div>
    """
```

## HEALTH Alert

```python
def health_alert_body(results: dict) -> str:
    rows = ""
    for subsystem, data in results.items():
        ok = data.get("ok", False)
        icon = "✅" if ok else "❌"
        detail = ""
        if "latency_ms" in data:
            detail = f"{data['latency_ms']:.0f}ms"
        elif "error" in data:
            detail = f"<span style='color:#ff6b6b'>{data['error'][:80]}</span>"
        elif "used_pct" in data:
            pct = data["used_pct"]
            color = "#ff6b6b" if pct > 90 else "#ffd93d" if pct > 75 else "#00d4aa"
            detail = f"<span style='color:{color}'>{pct}% used</span>"
        rows += f"""
        <tr style="border-bottom: 1px solid #2a2a4a;">
          <td style="padding: 8px;">{icon}</td>
          <td style="padding: 8px;"><b>{subsystem}</b></td>
          <td style="padding: 8px;">{detail}</td>
        </tr>"""
    
    return f"""
    <table style="width: 100%; border-collapse: collapse; color: #e0e0e0;">
      <tr style="border-bottom: 2px solid #333;">
        <th style="padding: 8px; text-align: left;">Status</th>
        <th style="padding: 8px; text-align: left;">Subsystem</th>
        <th style="padding: 8px; text-align: left;">Detail</th>
      </tr>
      {rows}
    </table>
    """
```

## SECURITY Alert

```python
def security_alert_body(event_type: str, details: dict) -> str:
    return f"""
    <div style="background: #2a1a1a; border-left: 4px solid #ff4444; padding: 12px; margin: 8px 0; border-radius: 4px;">
      <p style="margin: 0; color: #ff6b6b;"><b>⚠️ {event_type}</b></p>
    </div>
    <table style="width: 100%; color: #e0e0e0; margin-top: 12px;">
      {''.join(f'<tr><td style="padding: 4px 8px; color: #888;">{k}</td><td style="padding: 4px 8px;">{v}</td></tr>' for k, v in details.items())}
    </table>
    <p style="color: #888; font-size: 13px; margin-top: 12px;">
      Review the full audit log at <a href="https://api.refinet.io/admin/audit-log" style="color: #00d4aa;">api.refinet.io/admin/audit-log</a>
    </p>
    """
```

## DAILY SUMMARY

```python
def daily_summary_body(stats: dict) -> str:
    return f"""
    <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
      <div style="flex: 1; min-width: 120px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('requests', 0)}</div>
        <div style="font-size: 12px; color: #888;">Requests</div>
      </div>
      <div style="flex: 1; min-width: 120px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('agents_run', 0)}</div>
        <div style="font-size: 12px; color: #888;">Agent Runs</div>
      </div>
      <div style="flex: 1; min-width: 120px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('contracts', 0)}</div>
        <div style="font-size: 12px; color: #888;">New Contracts</div>
      </div>
      <div style="flex: 1; min-width: 120px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: {('#ff6b6b' if stats.get('errors', 0) > 0 else '#00d4aa')}; font-weight: bold;">{stats.get('errors', 0)}</div>
        <div style="font-size: 12px; color: #888;">Errors</div>
      </div>
    </div>
    <p style="color: #ccc; font-size: 14px;">
      Uptime: <b style="color: #00d4aa;">{stats.get('uptime_pct', '—')}%</b> · 
      Avg latency: <b>{stats.get('avg_latency_ms', '—')}ms</b> · 
      Active users: <b>{stats.get('active_users', 0)}</b>
    </p>
    """
```
