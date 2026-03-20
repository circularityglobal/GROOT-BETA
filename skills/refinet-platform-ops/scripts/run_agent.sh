#!/bin/bash
# =============================================================================
# REFINET Agent Pipeline Runner
# =============================================================================
# Executes an agent task through the zero-cost LLM fallback chain:
#   1. Claude Code CLI (highest quality, free)
#   2. Ollama (local, free)
#   3. BitNet (always-on, free)
#   4. Gemini Flash (free tier, rate-limited)
#
# Usage:
#   ./run_agent.sh <agent_name> "<task_description>"
#   ./run_agent.sh platform-ops "Run heartbeat check and email admin"
#   ./run_agent.sh maintenance "Prune expired working memory"
#
# Environment:
#   REFINET_ROOT    — Path to GROOT-BETA repo (default: current dir)
#   OLLAMA_HOST     — Ollama API host (default: http://localhost:11434)
#   BITNET_HOST     — BitNet API host (default: http://localhost:8080)
#   GEMINI_API_KEY  — Google AI Studio API key (optional, for fallback)
#   ADMIN_EMAIL     — Admin email for alerts
# =============================================================================

set -euo pipefail

AGENT_NAME="${1:-platform-ops}"
TASK="${2:-Run health check on all subsystems}"
REFINET_ROOT="${REFINET_ROOT:-.}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
BITNET_HOST="${BITNET_HOST:-http://localhost:8080}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MEMORY_DIR="${REFINET_ROOT}/memory"
RESULT=""
PROVIDER=""

mkdir -p "${MEMORY_DIR}/episodic" "${MEMORY_DIR}/working"

# ─────────────────────────────────────────────────────────────────────────────
# Assemble context (7-layer injection stack)
# ─────────────────────────────────────────────────────────────────────────────
build_context() {
    local ctx=""

    # Layer 1: SOUL identity
    if [ -f "${REFINET_ROOT}/SOUL.md" ]; then
        ctx+="[SOUL IDENTITY]
$(head -50 "${REFINET_ROOT}/SOUL.md")

"
    fi

    # Layer 2: Safety constraints (always injected)
    if [ -f "${REFINET_ROOT}/SAFETY.md" ]; then
        ctx+="[SAFETY CONSTRAINTS — IMMUTABLE]
$(cat "${REFINET_ROOT}/SAFETY.md")

"
    fi

    # Layer 3: Agent config
    local agent_config="${REFINET_ROOT}/configs/agents/${AGENT_NAME}.yaml"
    if [ -f "$agent_config" ]; then
        ctx+="[AGENT CONFIG]
$(cat "$agent_config")

"
    fi

    # Layer 4: Working memory (last run state)
    local working="${MEMORY_DIR}/working/${AGENT_NAME}.json"
    if [ -f "$working" ]; then
        ctx+="[WORKING MEMORY — LAST STATE]
$(cat "$working")

"
    fi

    # Layer 5: Recent episodic memory (last 5 entries)
    local episodic="${MEMORY_DIR}/episodic/${AGENT_NAME}.jsonl"
    if [ -f "$episodic" ]; then
        ctx+="[EPISODIC MEMORY — LAST 5 RUNS]
$(tail -5 "$episodic")

"
    fi

    # Layer 6: Task
    ctx+="[TASK]
Agent: ${AGENT_NAME}
Timestamp: ${TIMESTAMP}
Task: ${TASK}

Respond with a structured JSON object containing:
- status: 'ok' | 'warning' | 'error'
- summary: brief description of what was done
- actions_taken: list of actions performed
- alerts: list of any alerts that should be sent to admin
- next_steps: recommended follow-up actions
"

    echo "$ctx"
}

CONTEXT=$(build_context)

# ─────────────────────────────────────────────────────────────────────────────
# Fallback chain: Claude Code → Ollama → BitNet → Gemini
# ─────────────────────────────────────────────────────────────────────────────

# Attempt 1: Claude Code CLI
if command -v claude &> /dev/null; then
    echo "[agent] Trying Claude Code CLI..."
    RESULT=$(claude -p "$CONTEXT" 2>/dev/null || echo "")
    if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
        PROVIDER="claude-code"
        echo "[agent] ✅ Claude Code succeeded"
    fi
fi

# Attempt 2: Ollama
if [ -z "$RESULT" ] || [ "$RESULT" = "null" ]; then
    echo "[agent] Trying Ollama..."
    RESULT=$(curl -sf "${OLLAMA_HOST}/api/generate" \
        -d "{\"model\": \"phi3:mini\", \"prompt\": $(echo "$CONTEXT" | jq -Rs .), \"stream\": false}" \
        2>/dev/null | jq -r '.response // empty' 2>/dev/null || echo "")
    if [ -n "$RESULT" ]; then
        PROVIDER="ollama-phi3"
        echo "[agent] ✅ Ollama succeeded"
    fi
fi

# Attempt 3: BitNet (via REFINET API)
if [ -z "$RESULT" ] || [ "$RESULT" = "null" ]; then
    echo "[agent] Trying BitNet..."
    RESULT=$(curl -sf "${BITNET_HOST}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"bitnet-b1.58-2b\", \"messages\": [{\"role\": \"user\", \"content\": $(echo "$CONTEXT" | jq -Rs .)}]}" \
        2>/dev/null | jq -r '.choices[0].message.content // empty' 2>/dev/null || echo "")
    if [ -n "$RESULT" ]; then
        PROVIDER="bitnet"
        echo "[agent] ✅ BitNet succeeded"
    fi
fi

# Attempt 4: Gemini Flash (free tier)
if [ -z "$RESULT" ] || [ "$RESULT" = "null" ]; then
    if [ -n "${GEMINI_API_KEY:-}" ]; then
        echo "[agent] Trying Gemini Flash..."
        RESULT=$(curl -sf "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_API_KEY}" \
            -H "Content-Type: application/json" \
            -d "{\"contents\": [{\"parts\": [{\"text\": $(echo "$CONTEXT" | jq -Rs .)}]}]}" \
            2>/dev/null | jq -r '.candidates[0].content.parts[0].text // empty' 2>/dev/null || echo "")
        if [ -n "$RESULT" ]; then
            PROVIDER="gemini-flash"
            echo "[agent] ✅ Gemini Flash succeeded"
        fi
    fi
fi

# All providers failed
if [ -z "$RESULT" ] || [ "$RESULT" = "null" ]; then
    RESULT="{\"status\": \"error\", \"summary\": \"All LLM providers unavailable\", \"alerts\": [\"No inference provider responded\"]}"
    PROVIDER="none"
    echo "[agent] ❌ All providers failed"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Store result in episodic memory
# ─────────────────────────────────────────────────────────────────────────────
EPISODIC_ENTRY=$(jq -n \
    --arg ts "$TIMESTAMP" \
    --arg agent "$AGENT_NAME" \
    --arg task "$TASK" \
    --arg provider "$PROVIDER" \
    --arg result "$RESULT" \
    '{timestamp: $ts, agent: $agent, task: $task, provider: $provider, result: $result}')

echo "$EPISODIC_ENTRY" >> "${MEMORY_DIR}/episodic/${AGENT_NAME}.jsonl"

# Update working memory with latest state
echo "$EPISODIC_ENTRY" > "${MEMORY_DIR}/working/${AGENT_NAME}.json"

# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  Agent: ${AGENT_NAME}"
echo "  Provider: ${PROVIDER}"
echo "  Time: ${TIMESTAMP}"
echo "═══════════════════════════════════════════"
echo ""
echo "$RESULT"
