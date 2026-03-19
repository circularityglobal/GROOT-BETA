"""
Tests for the Agent Engine: SOUL parsing, 4-tier memory, cognitive loop, delegation.
"""

import json
import pytest

from api.services.agent_soul import parse_soul_md


# ── SOUL Parser Tests ────────────────────────────────────────────

class TestSoulParser:
    def test_parse_complete_soul(self):
        """Parse a complete SOUL.md with all sections."""
        soul_md = """# Identity
You are a helpful contract analyst.

# Goals
- Analyze smart contracts
- Find security issues
- Report findings clearly

# Constraints
- Never execute transactions
- Always flag delegatecall

# Tools
- search_registry
- get_contract_sdk
- search_documents

# Delegation
auto
"""
        result = parse_soul_md(soul_md)
        assert result["persona"] == "You are a helpful contract analyst."
        assert len(result["goals"]) == 3
        assert "Analyze smart contracts" in result["goals"]
        assert len(result["constraints"]) == 2
        assert "Never execute transactions" in result["constraints"]
        assert len(result["tools_allowed"]) == 3
        assert "search_registry" in result["tools_allowed"]
        assert result["delegation_policy"] == "auto"

    def test_parse_minimal_soul(self):
        """Parse a SOUL.md with only identity."""
        soul_md = """# Identity
A simple agent.
"""
        result = parse_soul_md(soul_md)
        assert result["persona"] == "A simple agent."
        assert result["goals"] == []
        assert result["constraints"] == []
        assert result["tools_allowed"] == []
        assert result["delegation_policy"] == "none"

    def test_parse_empty_soul(self):
        """Empty SOUL.md should return defaults."""
        result = parse_soul_md("")
        assert result["persona"] is None
        assert result["goals"] == []
        assert result["delegation_policy"] == "none"

    def test_parse_alternative_headings(self):
        """Parser should accept alternative heading names."""
        soul_md = """# Persona
A creative writer.

# Objectives
- Write stories
- Be creative

# Rules
- Keep it family-friendly

# Capabilities
- search_documents

# Delegation
approve
"""
        result = parse_soul_md(soul_md)
        assert result["persona"] == "A creative writer."
        assert len(result["goals"]) == 2
        assert len(result["constraints"]) == 1
        assert len(result["tools_allowed"]) == 1
        assert result["delegation_policy"] == "approve"

    def test_parse_numbered_lists(self):
        """Parser should handle numbered lists."""
        soul_md = """# Goals
1. First goal
2. Second goal
3. Third goal
"""
        result = parse_soul_md(soul_md)
        assert len(result["goals"]) == 3
        assert "First goal" in result["goals"]

    def test_parse_invalid_delegation(self):
        """Invalid delegation policy should default to none."""
        soul_md = """# Delegation
invalid_value
"""
        result = parse_soul_md(soul_md)
        assert result["delegation_policy"] == "none"

    def test_parse_multiline_persona(self):
        """Persona can span multiple lines."""
        soul_md = """# Identity
You are a multi-line
persona with several
lines of description.
"""
        result = parse_soul_md(soul_md)
        assert "multi-line" in result["persona"]
        assert "several" in result["persona"]


# ── Agent Engine Model Tests ─────────────────────────────────────

class TestAgentEngineModels:
    def test_models_importable(self):
        """All agent engine models should import cleanly."""
        from api.models.agent_engine import (
            AgentSoul,
            AgentMemoryWorking,
            AgentMemoryEpisodic,
            AgentMemorySemantic,
            AgentMemoryProcedural,
            AgentTask,
            AgentDelegation,
        )
        # Verify table names
        assert AgentSoul.__tablename__ == "agent_souls"
        assert AgentMemoryWorking.__tablename__ == "agent_memory_working"
        assert AgentMemoryEpisodic.__tablename__ == "agent_memory_episodic"
        assert AgentMemorySemantic.__tablename__ == "agent_memory_semantic"
        assert AgentMemoryProcedural.__tablename__ == "agent_memory_procedural"
        assert AgentTask.__tablename__ == "agent_tasks"
        assert AgentDelegation.__tablename__ == "agent_delegations"


# ── Cognitive Loop Helper Tests ──────────────────────────────────

class TestCognitiveLoopHelpers:
    def test_json_extraction_direct(self):
        """Should extract JSON from plain JSON text."""
        from api.services.agent_engine import AgentCognitiveLoop
        # Create a loop with mock params (no DB needed for helper tests)
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)

        result = loop._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_extraction_from_markdown(self):
        """Should extract JSON from markdown code blocks."""
        from api.services.agent_engine import AgentCognitiveLoop
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)

        text = 'Here is my plan:\n```json\n{"steps": [{"action": "reason"}]}\n```\nDone.'
        result = loop._extract_json(text)
        assert result is not None
        assert "steps" in result

    def test_json_extraction_from_prose(self):
        """Should extract JSON embedded in prose."""
        from api.services.agent_engine import AgentCognitiveLoop
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)

        text = 'I think the answer is {"success": true, "summary": "done"} and that is it.'
        result = loop._extract_json(text)
        assert result is not None
        assert result.get("success") is True

    def test_json_extraction_returns_none_for_no_json(self):
        """Should return None when no JSON is found."""
        from api.services.agent_engine import AgentCognitiveLoop
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)

        result = loop._extract_json("Just some plain text with no JSON.")
        assert result is None

    def test_tool_permission_check(self):
        """Should correctly check tool permissions with wildcards."""
        from api.services.agent_engine import AgentCognitiveLoop
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)
        loop.allowed_tools = ["search_*", "get_project", "execute_script:maintenance.*"]

        assert loop._is_tool_allowed("search_registry") is True
        assert loop._is_tool_allowed("search_documents") is True
        assert loop._is_tool_allowed("get_project") is True
        assert loop._is_tool_allowed("delete_everything") is False

    def test_tool_permission_empty(self):
        """Agent with no tools should reject all."""
        from api.services.agent_engine import AgentCognitiveLoop
        loop = AgentCognitiveLoop.__new__(AgentCognitiveLoop)
        loop.allowed_tools = []

        assert loop._is_tool_allowed("anything") is False


# ── Schema Tests ─────────────────────────────────────────────────

class TestAgentSchemas:
    def test_soul_create_request(self):
        """SoulCreateRequest should validate correctly."""
        from api.schemas.agent_engine import SoulCreateRequest
        req = SoulCreateRequest(soul_md="# Identity\nTest agent")
        assert req.soul_md == "# Identity\nTest agent"

    def test_task_submit_request(self):
        """TaskSubmitRequest should validate correctly."""
        from api.schemas.agent_engine import TaskSubmitRequest
        req = TaskSubmitRequest(description="Analyze the staking contract")
        assert req.description == "Analyze the staking contract"

    def test_delegation_request(self):
        """DelegationRequest should validate correctly."""
        from api.schemas.agent_engine import DelegationRequest
        req = DelegationRequest(
            target_agent_id="ag_123",
            subtask_description="Search for related contracts",
        )
        assert req.target_agent_id == "ag_123"


# ── Memory Service Tests ─────────────────────────────────────────

class TestMemoryHelpers:
    def test_memory_module_imports(self):
        """Memory service should import cleanly."""
        from api.services.agent_memory import (
            store_working, recall_working, clear_working,
            cleanup_expired_working,
            store_episode, recall_episodes, recall_relevant_episodes,
            learn_fact, recall_facts,
            store_procedure, match_procedure,
            build_memory_context,
        )
        assert callable(store_working)
        assert callable(recall_working)
        assert callable(store_episode)
        assert callable(learn_fact)
        assert callable(store_procedure)
        assert callable(build_memory_context)
