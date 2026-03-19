# Configuration — YAML Hierarchy

GROOT uses a layered YAML configuration system alongside environment variables.

## Merge Order (lowest → highest precedence)

```
configs/default.yaml          ← Base settings for all environments
  ↓ merged with
configs/production.yaml       ← Overrides when REFINET_ENV=production
  ↓ overridden by
Environment variables (.env)  ← Highest precedence (secrets, host-specific)
```

## Files

### `default.yaml`

Base configuration with all tunable parameters:

| Section | Keys | Description |
|---|---|---|
| `groot` | model, context_window, default_max_tokens, temperature | Inference defaults |
| `heartbeat` | interval_seconds, max_consecutive_failures | System health pulse |
| `memory` | episodic_ttl_days, working_clear_on_new_task, procedural_update_threshold | Memory tier policies |
| `orchestration` | max_iterations, timeout_seconds, max_delegation_depth | Agent execution limits |
| `trigger_router` | enabled, min_trigger_interval_seconds, event_map | Event → agent routing |
| `tools` | enabled (list), sandbox settings | Tool access control |
| `safety` | inject_constraints, max_tokens_per_request, require_siwe_for_writes | Safety enforcement |
| `logging` | jsonl_enabled, jsonl_path, level | Audit trail settings |

### `production.yaml`

Production overrides — tighter limits, lower temperature, warning-level logging.

## Usage in Code

```python
from api.config import get_yaml_value

# Get a value with dot-notation path
model = get_yaml_value("groot.model", "bitnet-b1.58-2b")
max_iter = get_yaml_value("orchestration.max_iterations", 5)
ttl = get_yaml_value("memory.episodic_ttl_days", 90)

# Load full config dict
from api.config import load_yaml_config
config = load_yaml_config()
```

## Adding a New Config Key

1. Add the key with a sensible default to `configs/default.yaml`
2. Add production override to `configs/production.yaml` if needed
3. Access in code via `get_yaml_value("section.key", default_value)`
