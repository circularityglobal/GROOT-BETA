---
name: analyze-telemetry
description: Analyze IoT device telemetry for anomalies and threshold violations
version: "1.0"
trigger: auto
agent: device-monitor
input: { device_id: string, readings: dict }
output: { anomaly: boolean, severity: string, recommendation: string }
---

# Analyze Telemetry

Evaluate incoming device telemetry against configured thresholds
and historical patterns.

## Steps
1. Compare readings against known safe ranges
2. Check for sudden changes or trend deviations
3. Classify severity: normal, warning, critical
4. Generate recommendation if anomaly detected
5. Dispatch alert if severity is critical
