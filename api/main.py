"""
REFINET Cloud — Main Application
FastAPI app factory with router registration, middleware, and database init.
Multi-protocol MCP gateway: REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.database import init_databases
from api.middleware.rate_limit import limiter
from api.middleware.request_size import RequestSizeMiddleware
from api.middleware.cors import add_cors
from api.middleware.logging import LoggingMiddleware

# Import all models to register with SQLAlchemy metadata
import api.models  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

_grpc_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, start gRPC, register event bus. Shutdown: cleanup."""
    global _grpc_task

    init_databases()
    logging.getLogger("refinet").info("Databases initialized")

    # Seed platform config defaults (only inserts if key doesn't exist)
    try:
        from api.database import get_internal_db
        from api.services.config_defaults import seed_config_defaults
        with get_internal_db() as int_db:
            seed_config_defaults(int_db)
    except Exception as e:
        logging.getLogger("refinet").warning(f"Config seed failed: {e}")

    # Seed default EVM chains into supported_chains table
    try:
        from api.database import get_public_db
        from api.models.chain import SupportedChain
        with get_public_db() as pub_db:
            existing = pub_db.query(SupportedChain).count()
            if existing == 0:
                defaults = [
                    SupportedChain(chain_id=1, name="Ethereum Mainnet", short_name="ethereum", currency="ETH", rpc_url="https://eth.llamarpc.com", explorer_url="https://etherscan.io", explorer_api_url="https://api.etherscan.io/api", added_by="system"),
                    SupportedChain(chain_id=137, name="Polygon", short_name="polygon", currency="MATIC", rpc_url="https://polygon-rpc.com", explorer_url="https://polygonscan.com", explorer_api_url="https://api.polygonscan.com/api", added_by="system"),
                    SupportedChain(chain_id=42161, name="Arbitrum One", short_name="arbitrum", currency="ETH", rpc_url="https://arb1.arbitrum.io/rpc", explorer_url="https://arbiscan.io", explorer_api_url="https://api.arbiscan.io/api", added_by="system"),
                    SupportedChain(chain_id=10, name="Optimism", short_name="optimism", currency="ETH", rpc_url="https://mainnet.optimism.io", explorer_url="https://optimistic.etherscan.io", explorer_api_url="https://api-optimistic.etherscan.io/api", added_by="system"),
                    SupportedChain(chain_id=8453, name="Base", short_name="base", currency="ETH", rpc_url="https://mainnet.base.org", explorer_url="https://basescan.org", explorer_api_url="https://api.basescan.org/api", added_by="system"),
                    SupportedChain(chain_id=11155111, name="Sepolia", short_name="sepolia", currency="ETH", rpc_url="https://rpc.sepolia.org", explorer_url="https://sepolia.etherscan.io", explorer_api_url="https://api-sepolia.etherscan.io/api", is_testnet=True, added_by="system"),
                ]
                for c in defaults:
                    pub_db.add(c)
                logging.getLogger("refinet").info("Seeded 6 default EVM chains")
    except Exception as e:
        logging.getLogger("refinet").warning(f"Chain seed skipped: {e}")

    # ── Ensure FTS5 index exists for knowledge search ───────────
    try:
        from api.database import get_public_db
        from api.services.fts import ensure_fts5
        with get_public_db() as pub_db:
            ensure_fts5(pub_db)
    except Exception as e:
        logging.getLogger("refinet").warning(f"FTS5 init skipped: {e}")

    # ── Ensure sqlite-vec vector index exists ───────────────────
    try:
        from api.database import get_public_db
        from api.services.vector_memory import ensure_vec_index
        with get_public_db() as pub_db:
            ensure_vec_index(pub_db)
    except Exception as e:
        logging.getLogger("refinet").warning(f"Vector memory init skipped: {e}")

    # ── Initialize model gateway (multi-provider inference) ─────
    try:
        from api.services.gateway import ModelGateway
        await ModelGateway.get().initialize()
    except Exception as e:
        logging.getLogger("refinet").warning(f"Model gateway init: {e}")

    # ── Register event bus handlers ──────────────────────────────
    from api.services.event_bus import EventBus
    from api.routes.mcp_websocket import ws_manager
    from api.services.webhook_delivery import deliver_bus_event

    bus = EventBus.get()
    # WebSocket broadcast for real-time UI updates
    bus.subscribe("registry.*", ws_manager.broadcast_event)
    bus.subscribe("messaging.*", ws_manager.broadcast_event)
    bus.subscribe("system.*", ws_manager.broadcast_event)
    # Webhook delivery for all event types
    bus.subscribe("registry.*", deliver_bus_event)
    bus.subscribe("messaging.*", deliver_bus_event)
    bus.subscribe("system.*", deliver_bus_event)
    # Knowledge base events — reactive system for GROOT awareness
    bus.subscribe("knowledge.*", ws_manager.broadcast_event)
    bus.subscribe("knowledge.*", deliver_bus_event)
    from api.services.knowledge_refresh import on_knowledge_change
    bus.subscribe("knowledge.*", on_knowledge_change)
    # SDK→Knowledge bridge: auto-ingest SDK definitions into RAG when published
    async def _on_sdk_publish(event: str, data: dict):
        """Bridge SDK definitions into knowledge chunks for RAG search."""
        try:
            from api.database import get_public_db
            from api.services.contract_brain import ingest_sdk_to_knowledge
            from api.models.brain import ContractRepo, SDKDefinition
            contract_id = data.get("contract_id")
            if not contract_id:
                return
            with get_public_db() as pub_db:
                contract = pub_db.query(ContractRepo).filter(
                    ContractRepo.id == contract_id,
                ).first()
                sdk = pub_db.query(SDKDefinition).filter(
                    SDKDefinition.contract_id == contract_id,
                    SDKDefinition.is_public == True,  # noqa: E712
                ).first()
                if contract and sdk:
                    ingest_sdk_to_knowledge(pub_db, contract, sdk)
        except Exception as e:
            logging.getLogger("refinet").warning(f"SDK→Knowledge bridge error: {e}")

    bus.subscribe("registry.sdk.*", _on_sdk_publish)
    bus.subscribe("registry.visibility.*", _on_sdk_publish)
    # Chain events — on-chain events detected by watchers → WS broadcast + webhook delivery
    bus.subscribe("chain.*", ws_manager.broadcast_event)
    bus.subscribe("chain.*", deliver_bus_event)
    # Agent events — task completion, delegation → WS broadcast + webhook delivery
    bus.subscribe("agent.*", ws_manager.broadcast_event)
    bus.subscribe("agent.*", deliver_bus_event)
    # Pipeline events — step completion, approval needed, run complete → WS + webhooks
    bus.subscribe("pipeline.*", ws_manager.broadcast_event)
    bus.subscribe("pipeline.*", deliver_bus_event)
    # Broker events — session lifecycle → WS + webhooks
    bus.subscribe("broker.*", ws_manager.broadcast_event)
    bus.subscribe("broker.*", deliver_bus_event)
    # Trigger router — maps events to agent tasks automatically
    from api.services.trigger_router import register_all_triggers
    register_all_triggers(bus)
    logging.getLogger("refinet").info(
        "Event bus handlers registered (registry + messaging + system + knowledge + chain + agent + trigger router → WS + webhooks)"
    )

    # ── Start SMTP bridge (if enabled) ───────────────────────────
    try:
        from api.config import get_settings as _get_settings
        settings = _get_settings()
        if settings.smtp_enabled:
            from api.services.smtp_bridge import start_smtp_server
            await start_smtp_server(host=settings.smtp_host, port=settings.smtp_port)
    except Exception as e:
        logging.getLogger("refinet").warning(f"SMTP bridge not started: {e}")

    # ── Start gRPC server (if available) ─────────────────────────
    try:
        from api.grpc.grpc_server import start_grpc_server
        _grpc_task = asyncio.create_task(start_grpc_server(port=50051))
        logging.getLogger("refinet").info("gRPC server task created (port 50051)")
    except Exception as e:
        logging.getLogger("refinet").warning(f"gRPC server not started: {e}")

    # ── Start configurable task scheduler ──────────────────────────
    # The scheduler handles all periodic tasks (p2p_cleanup, health_monitor,
    # auth_cleanup, agent_memory_cleanup) via seeded ScheduledTask entries.
    # No duplicate hardcoded loops needed.
    try:
        from api.services.scheduler import TaskScheduler, seed_default_tasks
        from api.database import get_internal_db as _get_int_db
        # Seed default scheduled tasks (6 platform + 5 brain workers)
        with _get_int_db() as sched_db:
            seed_default_tasks(sched_db)
        # Start the scheduler master loop (10s tick, checks due tasks)
        _scheduler_task = asyncio.create_task(TaskScheduler.get().start())
        logging.getLogger("refinet").info("Task scheduler started (10s tick)")
    except Exception as e:
        _scheduler_task = None
        logging.getLogger("refinet").warning(f"Scheduler not started: {e}")

    # ── Start webhook delivery worker ─────────────────────────────
    from api.services.webhook_delivery import webhook_worker
    _webhook_task = asyncio.create_task(webhook_worker())
    logging.getLogger("refinet").info("Webhook delivery worker started")

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    _webhook_task.cancel()
    if _scheduler_task:
        try:
            from api.services.scheduler import TaskScheduler
            await TaskScheduler.get().stop()
        except Exception:
            pass
        _scheduler_task.cancel()
    if _grpc_task:
        _grpc_task.cancel()
        try:
            from api.grpc.grpc_server import stop_grpc_server
            await stop_grpc_server()
        except Exception:
            pass
    try:
        from api.services.smtp_bridge import stop_smtp_server
        await stop_smtp_server()
    except Exception:
        pass
    logging.getLogger("refinet").info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="REFINET Cloud",
        description="Grass Root Project Intelligence — Sovereign AI Infrastructure",
        version="3.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middleware (order matters — last added = first executed) ────
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestSizeMiddleware)
    from api.middleware.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
    add_cors(app)

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Core Routers ─────────────────────────────────────────────
    from api.routes.health import router as health_router
    from api.routes.auth import router as auth_router
    from api.routes.inference import router as inference_router
    from api.routes.devices import router as devices_router
    from api.routes.agents import router as agents_router
    from api.routes.webhooks import router as webhooks_router
    from api.routes.mcp import router as mcp_router
    from api.routes.keys import router as keys_router
    from api.routes.admin import router as admin_router
    from api.routes.knowledge import router as knowledge_router
    from api.routes.identity import router as identity_router
    from api.routes.messaging import router as messaging_router
    from api.routes.p2p import router as p2p_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(identity_router)
    app.include_router(messaging_router)
    app.include_router(p2p_router)
    app.include_router(inference_router)
    app.include_router(devices_router)
    app.include_router(agents_router)
    app.include_router(webhooks_router)
    app.include_router(mcp_router)
    app.include_router(keys_router)
    from api.routes.provider_keys import router as provider_keys_router
    app.include_router(provider_keys_router)
    app.include_router(admin_router)
    app.include_router(knowledge_router)

    # ── Registry Routes (REST API) ───────────────────────────────
    from api.routes.registry import router as registry_router
    app.include_router(registry_router)

    # ── GROOT Brain Routes (Contract Repository + Explore) ────────
    from api.routes.repo import router as repo_router
    from api.routes.explore import router as explore_router
    app.include_router(repo_router)
    app.include_router(explore_router)

    # ── Chain Event Routes ─────────────────────────────────────────
    from api.routes.chain import router as chain_router
    app.include_router(chain_router)

    # ── Pipeline Routes (Wizard Workers) ───────────────────────────
    from api.routes.pipeline import router as pipeline_router
    app.include_router(pipeline_router)

    # ── Individual Worker Endpoints ──────────────────────────────
    from api.routes.workers import router as workers_router
    app.include_router(workers_router)

    # ── Deployment Tracking Routes ─────────────────────────────────
    from api.routes.deployments import router as deployments_router
    app.include_router(deployments_router)

    # ── Payment & Subscription Routes ──────────────────────────────
    from api.routes.payments import router as payments_router
    app.include_router(payments_router)

    # ── Broker Routes ──────────────────────────────────────────────
    from api.routes.broker import router as broker_router
    app.include_router(broker_router)

    # ── Vector Memory Routes ─────────────────────────────────────
    from api.routes.vector_memory import router as vector_memory_router
    app.include_router(vector_memory_router)

    # ── DApp Factory Routes ───────────────────────────────────────
    from api.routes.dapp import router as dapp_router
    app.include_router(dapp_router)

    # ── Submission Review Pipeline (must be before app_store — has /apps prefix too) ──
    from api.routes.submissions import router as submissions_router
    app.include_router(submissions_router)

    # ── App Store Routes (has {slug:path} catch-all — must be LAST /apps router) ──
    from api.routes.app_store import router as app_store_router
    app.include_router(app_store_router)

    # ── WebSocket Routes ─────────────────────────────────────────
    from api.routes.mcp_websocket import router as ws_router
    app.include_router(ws_router)

    # ── GraphQL (Strawberry) ─────────────────────────────────────
    try:
        from api.routes.mcp_graphql import graphql_app
        app.include_router(graphql_app, prefix="/graphql")
        logging.getLogger("refinet").info("GraphQL endpoint mounted at /graphql")
    except ImportError as e:
        logging.getLogger("refinet").warning(f"GraphQL not available: {e}")

    # ── SOAP (spyne via WSGIMiddleware) ──────────────────────────
    try:
        from api.routes.mcp_soap import get_soap_wsgi_app
        soap_wsgi = get_soap_wsgi_app()
        if soap_wsgi:
            from starlette.middleware.wsgi import WSGIMiddleware
            app.mount("/soap", WSGIMiddleware(soap_wsgi))
            logging.getLogger("refinet").info("SOAP endpoint mounted at /soap")
    except ImportError as e:
        logging.getLogger("refinet").warning(f"SOAP not available: {e}")

    return app


app = create_app()
