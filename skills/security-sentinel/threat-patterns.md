# REFINET Threat Pattern Catalog

## Detection Queries

Each query runs against the append-only `audit_log` table. The sentinel executes these on schedule and alerts admin when thresholds are breached.

---

### 1. SIWE Brute Force

**Severity**: HIGH
**Window**: 1 hour
**Threshold**: 5+ failed signatures from same IP

```sql
SELECT ip_address, COUNT(*) as fail_count,
       MIN(timestamp) as first_attempt,
       MAX(timestamp) as last_attempt,
       GROUP_CONCAT(DISTINCT wallet_address) as targeted_wallets
FROM audit_log
WHERE event_type = 'auth.siwe.fail'
  AND timestamp > datetime('now', '-1 hour')
GROUP BY ip_address
HAVING fail_count >= 5
ORDER BY fail_count DESC
```

**Interpretation**: An attacker is trying different wallet signatures from the same IP. This could be an attempt to forge SIWE messages or replay old nonces.

---

### 2. TOTP Brute Force

**Severity**: CRITICAL
**Window**: 30 minutes
**Threshold**: 3+ failed TOTP attempts per user

```sql
SELECT user_id, wallet_address, ip_address,
       COUNT(*) as fail_count,
       MIN(timestamp) as first_attempt,
       MAX(timestamp) as last_attempt
FROM audit_log
WHERE event_type = 'auth.totp.fail'
  AND timestamp > datetime('now', '-30 minutes')
GROUP BY user_id
HAVING fail_count >= 3
ORDER BY fail_count DESC
```

**Interpretation**: Someone has valid credentials (SIWE + password) but is brute-forcing the TOTP code. The 6-digit TOTP has 1M combinations but rotates every 30 seconds, so 3+ rapid failures is highly suspicious.

---

### 3. Credential Stuffing

**Severity**: CRITICAL
**Window**: 1 hour
**Threshold**: 3+ unique users AND 10+ total attempts from same IP

```sql
SELECT ip_address,
       COUNT(DISTINCT COALESCE(user_id, wallet_address)) as unique_identities,
       COUNT(*) as total_attempts,
       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as failures,
       GROUP_CONCAT(DISTINCT event_type) as attempt_types
FROM audit_log
WHERE event_type IN ('auth.login.fail', 'auth.siwe.fail', 'auth.siwe.verify')
  AND timestamp > datetime('now', '-1 hour')
GROUP BY ip_address
HAVING unique_identities >= 3 AND total_attempts >= 10
ORDER BY total_attempts DESC
```

**Interpretation**: Automated attack cycling through stolen credential lists. The high volume + multiple user targets from a single IP is the signature.

---

### 4. Expired JWT Reuse

**Severity**: MEDIUM
**Window**: 1 hour
**Threshold**: 3+ attempts per user/IP combination

```sql
SELECT user_id, ip_address, COUNT(*) as reuse_count,
       MIN(timestamp) as first_attempt,
       MAX(timestamp) as last_attempt
FROM audit_log
WHERE event_type = 'auth.token.expired'
  AND timestamp > datetime('now', '-1 hour')
GROUP BY user_id, ip_address
HAVING reuse_count >= 3
ORDER BY reuse_count DESC
```

**Interpretation**: Could be a stolen JWT being replayed, or a misconfigured client not refreshing tokens. Either way, it indicates the token is in unauthorized hands or the refresh flow is broken.

---

### 5. API Key Rate Limit Abuse

**Severity**: HIGH
**Window**: 1 hour
**Threshold**: 10+ rate limit hits for same key

```sql
SELECT json_extract(details, '$.api_key_id') as key_id,
       json_extract(details, '$.tier') as tier,
       COUNT(*) as hit_count,
       COUNT(DISTINCT ip_address) as unique_ips,
       MIN(timestamp) as first_hit,
       MAX(timestamp) as last_hit
FROM audit_log
WHERE event_type = 'rate_limit.hit'
  AND json_extract(details, '$.api_key_id') IS NOT NULL
  AND timestamp > datetime('now', '-1 hour')
GROUP BY key_id
HAVING hit_count >= 10
ORDER BY hit_count DESC
```

**Interpretation**: An API key is being used to hammer the platform beyond its configured limit. Could be a compromised key or a poorly written integration.

---

### 6. Endpoint Sweep (Wallet)

**Severity**: HIGH
**Window**: 24 hours
**Threshold**: 50+ unique endpoints per wallet

```sql
SELECT wallet_address,
       COUNT(DISTINCT endpoint) as unique_endpoints,
       COUNT(*) as total_requests,
       MIN(timestamp) as first_seen,
       MAX(timestamp) as last_seen
FROM audit_log
WHERE wallet_address IS NOT NULL
  AND timestamp > datetime('now', '-24 hours')
GROUP BY wallet_address
HAVING unique_endpoints >= 50
ORDER BY unique_endpoints DESC
```

**Interpretation**: A wallet is systematically probing the API surface — hitting many different endpoints. This is the signature of automated API scraping or vulnerability scanning.

---

### 7. Multi-IP Session (Wallet)

**Severity**: MEDIUM
**Window**: 24 hours
**Threshold**: 5+ unique IPs per wallet

```sql
SELECT wallet_address,
       COUNT(DISTINCT ip_address) as unique_ips,
       COUNT(*) as total_requests,
       GROUP_CONCAT(DISTINCT ip_address) as ips
FROM audit_log
WHERE wallet_address IS NOT NULL
  AND timestamp > datetime('now', '-24 hours')
GROUP BY wallet_address
HAVING unique_ips >= 5
ORDER BY unique_ips DESC
```

**Interpretation**: A single wallet is being used from many different IPs. Could indicate: shared credentials, VPN rotation (evasion), or a compromised wallet being used by multiple attackers.

---

### 8. Anonymous Rate Limit Saturation

**Severity**: MEDIUM
**Window**: 1 hour
**Threshold**: IP hitting anonymous rate limit repeatedly

```sql
SELECT ip_address, COUNT(*) as hit_count,
       MIN(timestamp) as first_hit,
       MAX(timestamp) as last_hit
FROM audit_log
WHERE event_type = 'rate_limit.hit'
  AND json_extract(details, '$.tier') = 'anonymous'
  AND timestamp > datetime('now', '-1 hour')
GROUP BY ip_address
HAVING hit_count >= 5
ORDER BY hit_count DESC
```

**Interpretation**: Unauthenticated user (or bot) repeatedly hitting the 25 req/day anonymous limit. May be scraping public endpoints or testing the API before authenticating.

---

### 9. Admin Access Outside Hours

**Severity**: MEDIUM
**Window**: 24 hours
**Note**: Adjust the hour range to match the admin's normal timezone

```sql
SELECT user_id, ip_address, endpoint, method, timestamp
FROM audit_log
WHERE event_type = 'admin.action'
  AND timestamp > datetime('now', '-24 hours')
  AND CAST(strftime('%H', timestamp) AS INTEGER) NOT BETWEEN 8 AND 22
ORDER BY timestamp DESC
```

**Interpretation**: Admin endpoint access outside typical working hours. Could be legitimate (global team, emergency) or unauthorized access with a compromised admin JWT.

---

### 10. Rapid Key Creation

**Severity**: HIGH
**Window**: 1 hour
**Threshold**: 3+ API keys created by same user

```sql
SELECT user_id, wallet_address, COUNT(*) as keys_created,
       MIN(timestamp) as first_key,
       MAX(timestamp) as last_key
FROM audit_log
WHERE event_type = 'keys.create'
  AND timestamp > datetime('now', '-1 hour')
GROUP BY user_id
HAVING keys_created >= 3
ORDER BY keys_created DESC
```

**Interpretation**: Rapidly creating API keys could indicate an attacker who has compromised all 3 auth layers and is generating keys for persistent access before the compromise is discovered.

---

## Response Playbook

| Detection | Recommended Response |
|---|---|
| SIWE brute force | Monitor IP; if persistent, recommend firewall block |
| TOTP brute force | Recommend temporary account lock + password reset |
| Credential stuffing | Recommend IP block + rate limit decrease for anonymous tier |
| Expired JWT reuse | Recommend token revocation for affected user |
| API key abuse | Recommend key revocation or limit decrease |
| Endpoint sweep | Monitor; if scraping confirmed, recommend key revocation |
| Multi-IP session | Investigate; may be legitimate VPN usage |
| Admin outside hours | Verify with admin; if unrecognized, treat as compromise |
| Rapid key creation | Recommend immediate key revocation + account audit |
