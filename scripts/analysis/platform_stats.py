#!/usr/bin/env python3
"""
Platform statistics — comprehensive counts across all system tables.

Usage:
    python scripts/analysis/platform_stats.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "platform_stats",
    "description": "Show platform-wide statistics: users, documents, agents, contracts, watchers",
    "category": "analysis",
    "requires_admin": False,
}


def main():
    from api.database import init_databases, create_public_session
    from sqlalchemy import func as sqlfunc

    init_databases()
    db = create_public_session()

    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        print(f"=== REFINET Cloud Platform Stats ===")
        print(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print()

        # Users
        from api.models.public import User, ApiKey, AgentRegistration, DeviceRegistration
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()  # noqa
        print(f"--- Users ---")
        print(f"  Total: {total_users}")
        print(f"  Active: {active_users}")
        print(f"  API keys (active): {db.query(ApiKey).filter(ApiKey.is_active == True).count()}")  # noqa

        # Agents
        total_agents = db.query(AgentRegistration).count()
        print(f"\n--- Agents ---")
        print(f"  Registered: {total_agents}")

        try:
            from api.models.agent_engine import AgentSoul, AgentTask
            souls = db.query(AgentSoul).count()
            tasks_total = db.query(AgentTask).count()
            tasks_completed = db.query(AgentTask).filter(AgentTask.status == "completed").count()
            tasks_failed = db.query(AgentTask).filter(AgentTask.status == "failed").count()
            print(f"  With SOUL configured: {souls}")
            print(f"  Tasks (total): {tasks_total}")
            print(f"  Tasks (completed): {tasks_completed}")
            print(f"  Tasks (failed): {tasks_failed}")
        except Exception:
            print(f"  (Agent engine tables not available)")

        # Devices
        total_devices = db.query(DeviceRegistration).filter(DeviceRegistration.status == "active").count()
        print(f"\n--- Devices ---")
        print(f"  Active: {total_devices}")

        # Knowledge Base
        from api.models.knowledge import KnowledgeDocument, KnowledgeChunk
        doc_count = db.query(KnowledgeDocument).count()
        chunk_count = db.query(KnowledgeChunk).count()
        print(f"\n--- Knowledge Base ---")
        print(f"  Documents: {doc_count}")
        print(f"  Chunks: {chunk_count}")

        # Contract Registry
        try:
            from api.models.registry import RegistryProject
            projects = db.query(RegistryProject).count()
            public_projects = db.query(RegistryProject).filter(
                RegistryProject.visibility == "public"
            ).count()
            print(f"\n--- Contract Registry ---")
            print(f"  Projects: {projects}")
            print(f"  Public: {public_projects}")
        except Exception:
            pass

        # GROOT Brain
        try:
            from api.models.brain import ContractRepo, SDKDefinition
            contracts = db.query(ContractRepo).filter(ContractRepo.is_active == True).count()  # noqa
            public_sdks = db.query(SDKDefinition).filter(SDKDefinition.is_public == True).count()  # noqa
            print(f"\n--- GROOT Brain ---")
            print(f"  Contracts: {contracts}")
            print(f"  Public SDKs: {public_sdks}")
        except Exception:
            pass

        # Chain Watchers
        try:
            from api.models.public import ChainWatcher, ChainEvent
            watchers = db.query(ChainWatcher).filter(ChainWatcher.is_active == True).count()  # noqa
            events = db.query(ChainEvent).count()
            print(f"\n--- Chain Watchers ---")
            print(f"  Active watchers: {watchers}")
            print(f"  Events detected: {events}")
        except Exception:
            pass

        # Inference Usage
        from api.models.public import UsageRecord
        total_inferences = db.query(UsageRecord).count()
        today_inferences = db.query(UsageRecord).filter(
            sqlfunc.date(UsageRecord.created_at) == today
        ).count()
        print(f"\n--- Inference ---")
        print(f"  Total calls: {total_inferences}")
        print(f"  Today: {today_inferences}")

        # Webhooks
        from api.models.public import WebhookSubscription
        active_webhooks = db.query(WebhookSubscription).filter(
            WebhookSubscription.is_active == True  # noqa
        ).count()
        print(f"\n--- Webhooks ---")
        print(f"  Active subscriptions: {active_webhooks}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
