"""
REFINET Cloud — Agent Cognitive Loop Engine
PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE

The brain of the agent system. Takes a task, runs it through a structured
cognitive loop using BitNet inference and MCP tools, and stores the results.
"""

import asyncio
import json
import logging
import time
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.models.agent_engine import AgentTask, AgentDelegation
from api.models.public import AgentRegistration
from api.services.agent_soul import build_agent_system_prompt, get_allowed_tools
from api.services.agent_memory import (
    store_working, recall_working, clear_working,
    store_episode, recall_relevant_episodes,
    learn_fact, recall_facts,
    store_procedure, match_procedure,
    build_memory_context,
)
from api.services.event_bus import EventBus

logger = logging.getLogger("refinet.agent.engine")


@dataclass
class StepResult:
    """Result of a single cognitive loop step."""
    action: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    tokens_used: int = 0


@dataclass
class TaskResult:
    """Final result of a completed agent task."""
    success: bool
    output: str
    steps: list[dict] = field(default_factory=list)
    memories_created: int = 0
    tokens_used: int = 0
    inference_calls: int = 0
    tool_calls: int = 0


# ── Task Management ──────────────────────────────────────────────

def create_task(
    db: Session,
    agent_id: str,
    user_id: str,
    description: str,
) -> AgentTask:
    """Create a new task for an agent."""
    task = AgentTask(
        id=f"task_{uuid.uuid4().hex[:16]}",
        agent_id=agent_id,
        user_id=user_id,
        description=description,
        status="pending",
    )
    db.add(task)
    db.flush()
    return task


def get_task(db: Session, task_id: str, agent_id: str) -> Optional[AgentTask]:
    """Get a task by ID, scoped to an agent."""
    return db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.agent_id == agent_id,
    ).first()


def list_tasks(
    db: Session,
    agent_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List tasks for an agent."""
    q = db.query(AgentTask).filter(AgentTask.agent_id == agent_id)
    if status:
        q = q.filter(AgentTask.status == status)
    tasks = q.order_by(AgentTask.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "description": t.description,
            "status": t.status,
            "current_phase": t.current_phase,
            "tokens_used": t.tokens_used,
            "inference_calls": t.inference_calls,
            "tool_calls": t.tool_calls,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


def cancel_task(db: Session, task_id: str, agent_id: str) -> bool:
    """Cancel a running task."""
    task = get_task(db, task_id, agent_id)
    if not task or task.status not in ("pending", "running"):
        return False
    task.status = "cancelled"
    task.completed_at = datetime.now(timezone.utc)
    db.flush()
    return True


# ── Cognitive Loop ───────────────────────────────────────────────

class AgentCognitiveLoop:
    """
    Implements the 6-phase cognitive loop for autonomous agent execution.
    Each phase updates the task state and can be observed in real-time.
    """

    def __init__(self, db: Session, agent_id: str, user_id: str):
        self.db = db
        self.agent_id = agent_id
        self.user_id = user_id
        self.allowed_tools = get_allowed_tools(db, agent_id)
        self._cancelled = False

    async def run(self, task: AgentTask) -> TaskResult:
        """Execute a full cognitive loop for a task."""
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        self.db.flush()

        steps = []
        total_tokens = 0
        total_inference = 0
        total_tool_calls = 0

        try:
            # Phase 1: PERCEIVE
            task.current_phase = "perceive"
            self.db.flush()
            perception = await self._perceive(task)
            total_tokens += perception.get("tokens", 0)
            total_inference += 1

            if self._cancelled:
                return self._cancel_result(task, steps)

            # Phase 2: PLAN
            task.current_phase = "plan"
            self.db.flush()
            plan = await self._plan(task, perception)
            total_tokens += plan.get("tokens", 0)
            total_inference += 1
            task.plan_json = json.dumps(plan.get("plan", {}))
            self.db.flush()

            if self._cancelled:
                return self._cancel_result(task, steps)

            # Phase 3: ACT
            task.current_phase = "act"
            self.db.flush()
            act_results = await self._act(task, plan.get("plan", {}))
            for step in act_results:
                steps.append({
                    "action": step.action,
                    "tool_name": step.tool_name,
                    "result": step.result,
                    "error": step.error,
                    "tokens_used": step.tokens_used,
                })
                total_tokens += step.tokens_used
                if step.tool_name:
                    total_tool_calls += 1
                if step.tokens_used > 0:
                    total_inference += 1

            if self._cancelled:
                return self._cancel_result(task, steps)

            # Phase 4: OBSERVE
            task.current_phase = "observe"
            self.db.flush()
            observation = await self._observe(task, steps, plan.get("plan", {}))
            total_tokens += observation.get("tokens", 0)
            total_inference += 1

            # Phase 5: REFLECT
            task.current_phase = "reflect"
            self.db.flush()
            reflection = await self._reflect(task, steps, observation)
            total_tokens += reflection.get("tokens", 0)
            total_inference += 1

            # Phase 6: STORE
            task.current_phase = "store"
            self.db.flush()
            memories_created = await self._store(task, steps, reflection)

            # Mark complete
            output = observation.get("summary", reflection.get("summary", "Task completed"))
            success = observation.get("success", True)

            task.status = "completed" if success else "failed"
            task.completed_at = datetime.now(timezone.utc)
            task.steps_json = json.dumps(steps)
            task.result_json = json.dumps({"output": output, "success": success})
            task.tokens_used = total_tokens
            task.inference_calls = total_inference
            task.tool_calls = total_tool_calls
            task.current_phase = None
            self.db.flush()

            # Emit event
            await EventBus.get().publish("agent.task.completed", {
                "agent_id": self.agent_id,
                "task_id": task.id,
                "success": success,
            })

            # Route output to configured targets (agent chaining, webhooks, etc.)
            try:
                from api.services.output_router import route_output, get_output_targets
                output_targets = get_output_targets(self.db, self.agent_id)
                if output_targets:
                    await route_output(
                        db=self.db,
                        task_id=task.id,
                        agent_id=self.agent_id,
                        user_id=self.user_id,
                        result={"output": output, "success": success},
                        targets=output_targets,
                    )
            except Exception as e:
                logger.warning(f"Output routing error (non-fatal): {e}")

            return TaskResult(
                success=success,
                output=output,
                steps=steps,
                memories_created=memories_created,
                tokens_used=total_tokens,
                inference_calls=total_inference,
                tool_calls=total_tool_calls,
            )

        except Exception as e:
            logger.error(f"Cognitive loop error for task {task.id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            task.steps_json = json.dumps(steps)
            task.tokens_used = total_tokens
            task.inference_calls = total_inference
            task.tool_calls = total_tool_calls
            task.current_phase = None
            self.db.flush()

            return TaskResult(
                success=False,
                output=f"Error: {e}",
                steps=steps,
                tokens_used=total_tokens,
                inference_calls=total_inference,
                tool_calls=total_tool_calls,
            )

    # ── Phase Implementations ────────────────────────────────────

    async def _perceive(self, task: AgentTask) -> dict:
        """Phase 1: Parse task, recall memories, build situation awareness."""
        # Recall relevant memories (passed to context assembly as Layer 2)
        memory_context = build_memory_context(
            self.db, self.agent_id, task.description, task_id=task.id,
        )

        # Build system prompt with full 7-layer context injection stack
        system_prompt, sources, token_report = build_agent_system_prompt(
            self.db, self.agent_id, task.description,
            user_id=self.user_id,
            memory_context=memory_context,
        )

        # Ask BitNet to analyze the situation
        perception_prompt = f"""Analyze this task and provide a situation assessment.

Task: {task.description}

Respond with a JSON object:
{{"understanding": "your interpretation of the task",
  "key_entities": ["list of key entities/concepts"],
  "complexity": "simple|moderate|complex",
  "approach_hints": ["possible approaches"]}}"""

        result = await self._call_inference(system_prompt, perception_prompt)

        # Store perception in working memory
        store_working(self.db, self.agent_id, task.id, "perception", result.get("content", ""))

        return {
            "system_prompt": system_prompt,
            "content": result.get("content", ""),
            "tokens": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
        }

    async def _plan(self, task: AgentTask, perception: dict) -> dict:
        """Phase 2: Create a structured plan."""
        system_prompt = perception.get("system_prompt", "")

        # Check for matching procedures
        procedures = match_procedure(self.db, self.agent_id, task.description, max_results=2)
        proc_context = ""
        if procedures:
            proc_lines = [f"- {p['pattern_name']} (success rate: {p['success_rate']:.0%}): {p['trigger_condition']}"
                          for p in procedures]
            proc_context = f"\n\nYou have used these strategies before:\n" + "\n".join(proc_lines)

        # List available tools
        tool_list = ", ".join(self.allowed_tools) if self.allowed_tools else "No tools available — reasoning only"

        plan_prompt = f"""Based on your analysis, create a step-by-step plan.

Task: {task.description}

Available tools: {tool_list}
{proc_context}

Create a plan as JSON:
{{"steps": [
  {{"step": 1, "action": "tool_name or 'reason'", "args": {{}}, "expected": "what you expect to happen"}}
]}}

Keep the plan concise (1-5 steps). Use available tools when helpful."""

        result = await self._call_inference(system_prompt, plan_prompt)
        content = result.get("content", "")

        # Parse plan JSON from response
        plan = self._extract_json(content)
        if not plan or "steps" not in plan:
            plan = {"steps": [{"step": 1, "action": "reason", "args": {}, "expected": "Direct response"}]}

        store_working(self.db, self.agent_id, task.id, "plan", json.dumps(plan))

        return {
            "plan": plan,
            "content": content,
            "tokens": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
        }

    async def _act(self, task: AgentTask, plan: dict) -> list[StepResult]:
        """Phase 3: Execute each step in the plan."""
        results = []

        for step in plan.get("steps", []):
            if self._cancelled:
                break

            action = step.get("action", "reason")
            args = step.get("args", {})
            step_result = StepResult(action=action)

            if action == "reason":
                # Pure reasoning step — call BitNet
                reasoning_prompt = f"Step: {step.get('expected', 'Think about this')}\nTask: {task.description}"
                result = await self._call_inference("You are a helpful AI assistant.", reasoning_prompt)
                step_result.result = {"content": result.get("content", "")}
                step_result.tokens_used = result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)

            elif action in ("deploy_contract", "compile_contract", "compile_test", "wizard_pipeline"):
                # Pipeline dispatch — GROOT is the sole Wizard
                # All deployments go through GROOT's wallet via the wizard pipeline
                step_result.tool_name = action
                step_result.tool_args = args
                try:
                    from api.services.dag_orchestrator import create_pipeline
                    pipeline_type = {
                        "deploy_contract": "deploy",
                        "compile_contract": "compile_test",
                        "compile_test": "compile_test",
                        "wizard_pipeline": "wizard",
                    }.get(action, "compile_test")
                    pipeline = create_pipeline(
                        self.db, self.user_id, pipeline_type,
                        config=args, agent_task_id=task.id,
                    )
                    self.db.flush()
                    step_result.result = {
                        "pipeline_id": pipeline.id,
                        "pipeline_type": pipeline.pipeline_type,
                        "status": pipeline.status,
                        "message": f"Pipeline '{pipeline_type}' created — GROOT will deploy using its wallet",
                    }
                except Exception as e:
                    step_result.error = str(e)

            # ── CAG Tools: GROOT reads and acts on the contract registry ──
            elif action == "cag_query":
                # Search public SDKs — autonomous, no approval needed
                step_result.tool_name = "cag_query"
                step_result.tool_args = args
                try:
                    from api.services.contract_brain import cag_query
                    results = cag_query(
                        self.db,
                        query=args.get("query", ""),
                        chain=args.get("chain"),
                        max_results=args.get("max_results", 3),
                    )
                    step_result.result = {"contracts": results, "count": len(results)}
                except Exception as e:
                    step_result.error = str(e)

            elif action == "cag_execute":
                # Read on-chain state via view/pure calls — autonomous, no gas
                step_result.tool_name = "cag_execute"
                step_result.tool_args = args
                try:
                    from api.services.contract_brain import cag_execute
                    result = cag_execute(
                        self.db,
                        contract_address=args.get("contract_address", ""),
                        chain=args.get("chain", "base"),
                        function_name=args.get("function_name", ""),
                        args=args.get("args", []),
                    )
                    step_result.result = result
                    if not result.get("success"):
                        step_result.error = result.get("error")
                except Exception as e:
                    step_result.error = str(e)

            elif action == "cag_act":
                # State-changing call — creates PendingAction for master_admin approval
                step_result.tool_name = "cag_act"
                step_result.tool_args = args
                try:
                    from api.services.contract_brain import cag_act
                    result = cag_act(
                        self.db,
                        user_id=self.user_id,
                        contract_address=args.get("contract_address", ""),
                        chain=args.get("chain", "base"),
                        function_name=args.get("function_name", ""),
                        args=args.get("args", []),
                    )
                    step_result.result = result
                    if not result.get("success"):
                        step_result.error = result.get("error")
                except Exception as e:
                    step_result.error = str(e)

            elif self._is_tool_allowed(action):
                # Tool execution via MCP gateway
                step_result.tool_name = action
                step_result.tool_args = args
                try:
                    from api.services.mcp_gateway import dispatch_tool
                    tool_result = await dispatch_tool(action, args, self.db, user_id=self.user_id)
                    step_result.result = tool_result
                    if "error" in tool_result:
                        step_result.error = tool_result["error"]
                except Exception as e:
                    step_result.error = str(e)
            else:
                step_result.error = f"Tool '{action}' not allowed for this agent"

            # Store step result in working memory
            store_working(
                self.db, self.agent_id, task.id,
                f"step_{len(results)}", json.dumps({
                    "action": action,
                    "result": step_result.result,
                    "error": step_result.error,
                }),
            )

            results.append(step_result)

        return results

    async def _observe(self, task: AgentTask, steps: list[dict], plan: dict) -> dict:
        """Phase 4: Evaluate results against expectations."""
        steps_summary = "\n".join(
            f"  Step {i+1}: {s.get('action', '?')} → {'error: ' + s['error'] if s.get('error') else 'ok'}"
            for i, s in enumerate(steps)
        )

        observe_prompt = f"""Evaluate the results of your actions.

Task: {task.description}

Steps taken:
{steps_summary}

Respond with JSON:
{{"success": true/false,
  "summary": "brief summary of what was accomplished",
  "gaps": ["anything that wasn't completed"],
  "quality": "excellent|good|adequate|poor"}}"""

        result = await self._call_inference("You are evaluating task completion.", observe_prompt)
        content = result.get("content", "")
        observation = self._extract_json(content)
        if not observation:
            # Determine success from step errors
            has_errors = any(s.get("error") for s in steps)
            observation = {
                "success": not has_errors,
                "summary": content[:500] if content else "Task processed",
                "gaps": [],
                "quality": "adequate",
            }

        return {
            **observation,
            "tokens": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
        }

    async def _reflect(self, task: AgentTask, steps: list[dict], observation: dict) -> dict:
        """Phase 5: Extract lessons learned."""
        reflect_prompt = f"""Reflect on this task execution and extract lessons.

Task: {task.description}
Outcome: {observation.get('summary', 'Unknown')}
Success: {observation.get('success', False)}
Quality: {observation.get('quality', 'unknown')}

Respond with JSON:
{{"lessons": ["lesson 1", "lesson 2"],
  "facts_learned": ["fact 1"],
  "strategy_update": "how to improve next time",
  "summary": "brief reflection"}}"""

        result = await self._call_inference("You are reflecting on your performance.", reflect_prompt)
        content = result.get("content", "")
        reflection = self._extract_json(content)
        if not reflection:
            reflection = {
                "lessons": [],
                "facts_learned": [],
                "strategy_update": "",
                "summary": content[:500] if content else "Reflection complete",
            }

        return {
            **reflection,
            "tokens": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
        }

    async def _store(self, task: AgentTask, steps: list[dict], reflection: dict) -> int:
        """Phase 6: Persist memories from this task."""
        memories_created = 0

        # Store episode
        store_episode(
            self.db,
            agent_id=self.agent_id,
            event_type="task_completed",
            summary=f"Task: {task.description[:200]} → {reflection.get('summary', 'done')}",
            context={"task_id": task.id, "steps_count": len(steps)},
            outcome="success" if task.status == "completed" else "failure",
            tokens_used=task.tokens_used,
        )
        memories_created += 1

        # Store learned facts
        for fact in reflection.get("facts_learned", []):
            if fact and len(fact) > 5:
                learn_fact(self.db, self.agent_id, fact, source=f"task:{task.id}")
                memories_created += 1

        # Update or create procedure if strategy insight is useful
        strategy = reflection.get("strategy_update", "")
        if strategy and len(strategy) > 10:
            store_procedure(
                self.db,
                agent_id=self.agent_id,
                pattern_name=f"learned_from_{task.id[:8]}",
                trigger_condition=task.description[:200],
                action_sequence=[{"strategy": strategy}],
                success_rate=1.0 if task.status == "completed" else 0.0,
            )
            memories_created += 1

        # Clean working memory for this task
        clear_working(self.db, self.agent_id, task.id)

        self.db.flush()
        return memories_created

    # ── Helpers ───────────────────────────────────────────────────

    async def _call_inference(self, system_prompt: str, user_prompt: str) -> dict:
        """Call BitNet inference via the existing inference service."""
        from api.services.inference import call_bitnet
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await call_bitnet(messages=messages, temperature=0.7, max_tokens=512)

    def _is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed for this agent."""
        if not self.allowed_tools:
            return False

        import fnmatch
        for pattern in self.allowed_tools:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from a response that may contain prose + JSON."""
        import re
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON block in markdown
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _cancel_result(self, task: AgentTask, steps: list[dict]) -> TaskResult:
        """Handle task cancellation."""
        task.status = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        task.steps_json = json.dumps(steps)
        self.db.flush()
        return TaskResult(success=False, output="Task cancelled", steps=steps)

    def cancel(self):
        """Signal the loop to stop at the next phase boundary."""
        self._cancelled = True


# ── Delegation Rate Limiter ──────────────────────────────────────

class _DelegationBucket:
    """Token-bucket rate limiter for agent delegations (10/minute)."""

    def __init__(self, max_tokens: int = 10, refill_rate: float = 10.0 / 60.0):
        self._max_tokens = max_tokens
        self._refill_rate = refill_rate  # tokens per second
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


_delegation_limiter = _DelegationBucket()

# ── Delegation ───────────────────────────────────────────────────

async def delegate_task(
    db: Session,
    source_agent_id: str,
    target_agent_id: str,
    source_task_id: str,
    subtask_description: str,
    user_id: str,
) -> Optional[AgentDelegation]:
    """
    Delegate a subtask from one agent to another.
    Checks delegation policy on the target agent's soul.
    Rate-limited to 10 delegations per minute to prevent cascading bursts.
    """
    # Rate limit check
    if not _delegation_limiter.acquire():
        logger.warning("Delegation rate limit exceeded — rejecting delegation from %s to %s",
                        source_agent_id, target_agent_id)
        return None

    from api.services.agent_soul import get_soul

    # Verify both agents belong to the same user
    source = db.query(AgentRegistration).filter(
        AgentRegistration.id == source_agent_id,
        AgentRegistration.user_id == user_id,
    ).first()
    target = db.query(AgentRegistration).filter(
        AgentRegistration.id == target_agent_id,
        AgentRegistration.user_id == user_id,
    ).first()

    if not source or not target:
        return None

    # Check target's delegation policy
    target_soul = get_soul(db, target_agent_id)
    policy = target_soul.get("delegation_policy", "none") if target_soul else "none"

    if policy == "none":
        logger.info(f"Delegation rejected: {target_agent_id} has delegation_policy=none")
        return None

    # Create delegation record
    delegation = AgentDelegation(
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        source_task_id=source_task_id,
        subtask_description=subtask_description,
        status="requested" if policy == "approve" else "accepted",
    )
    db.add(delegation)
    db.flush()

    # If auto-accept, create and run the delegated task
    if policy == "auto":
        delegated_task = create_task(db, target_agent_id, user_id, subtask_description)
        delegation.delegated_task_id = delegated_task.id
        delegation.status = "accepted"
        db.flush()

        # Run the delegated task
        loop = AgentCognitiveLoop(db, target_agent_id, user_id)
        result = await loop.run(delegated_task)

        delegation.status = "completed" if result.success else "failed"
        delegation.result_json = json.dumps({"output": result.output, "success": result.success})
        delegation.resolved_at = datetime.now(timezone.utc)
        db.flush()

    # Emit event
    await EventBus.get().publish("agent.delegation.requested", {
        "delegation_id": delegation.id,
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "status": delegation.status,
    })

    return delegation
