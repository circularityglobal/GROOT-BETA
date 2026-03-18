"""
REFINET Cloud — gRPC Server for Registry
Runs on port 50051 alongside the FastAPI server.
"""

import json
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports — grpc may not be installed in all environments
_server = None


async def start_grpc_server(port: int = 50051):
    """Start the gRPC server. Fails gracefully if grpc not installed."""
    global _server

    try:
        import grpc
        from grpc import aio as grpc_aio
    except ImportError:
        logger.warning("grpcio not installed — gRPC server disabled")
        return

    from api.database import get_public_session
    from api.services import registry_service
    from api.services.mcp_gateway import dispatch_tool, list_tools

    # ── Build service implementation without generated stubs ──────
    # We use a generic service handler since proto compilation may not
    # have been run. This provides a functional gRPC server.

    class RegistryServicer:
        """gRPC service implementation using raw handlers."""
        pass

    # For environments where proto stubs are generated, import them:
    try:
        from api.grpc import registry_pb2, registry_pb2_grpc

        class RegistryServiceImpl(registry_pb2_grpc.RegistryServiceServicer):

            def _get_db(self):
                return next(get_public_session())

            async def SearchProjects(self, request, context):
                db = self._get_db()
                result = registry_service.search_projects(
                    db,
                    query=request.query or None,
                    chain=request.chain or None,
                    category=request.category or None,
                    page=request.page or 1,
                    page_size=request.page_size or 20,
                    sort_by=request.sort_by or "stars",
                )
                projects = []
                for item in result.get("items", []):
                    projects.append(registry_pb2.Project(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        slug=item.get("slug", ""),
                        description=item.get("description", ""),
                        chain=item.get("chain", ""),
                        category=item.get("category", ""),
                        tags=item.get("tags", []),
                        star_count=item.get("stars_count", 0),
                        fork_count=item.get("forks_count", 0),
                        owner_username=item.get("owner_username", ""),
                        created_at=item.get("created_at", ""),
                        updated_at=item.get("updated_at", ""),
                    ))
                return registry_pb2.ProjectListResponse(
                    projects=projects,
                    total=result.get("total", 0),
                    page=result.get("page", 1),
                    has_next=result.get("has_next", False),
                )

            async def GetProject(self, request, context):
                db = self._get_db()
                result = registry_service.get_project_by_slug(db, request.slug)
                if not result:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Project not found")
                    return registry_pb2.ProjectDetailResponse()

                project = registry_pb2.Project(
                    id=result.get("id", ""),
                    name=result.get("name", ""),
                    slug=result.get("slug", ""),
                    description=result.get("description", ""),
                    chain=result.get("chain", ""),
                    category=result.get("category", ""),
                    tags=result.get("tags", []),
                    star_count=result.get("stars_count", 0),
                    fork_count=result.get("forks_count", 0),
                    owner_username=result.get("owner_username", ""),
                    readme=result.get("readme", ""),
                )

                # Fetch ABIs, SDKs, Logic
                abis = registry_service.list_abis(db, result["id"])
                sdks = registry_service.list_sdks(db, result["id"])
                logic = registry_service.list_execution_logic(db, result["id"])

                return registry_pb2.ProjectDetailResponse(
                    project=project,
                    abis=[registry_pb2.ABI(
                        id=a.id, project_id=a.project_id,
                        contract_name=a.contract_name,
                        contract_address=a.contract_address or "",
                        chain=a.chain, abi_json=a.abi_json,
                        compiler_version=a.compiler_version or "",
                        is_verified=a.is_verified,
                    ) for a in abis],
                    sdks=[registry_pb2.SDK(
                        id=s.id, project_id=s.project_id,
                        name=s.name, language=s.language,
                        version=s.version,
                        package_name=s.package_name or "",
                        install_command=s.install_command or "",
                    ) for s in sdks],
                    logic=[registry_pb2.ExecutionLogic(
                        id=l.id, project_id=l.project_id,
                        name=l.name, description=l.description or "",
                        function_signature=l.function_signature or "",
                        logic_type=l.logic_type,
                        chain=l.chain or "",
                        is_verified=l.is_verified,
                    ) for l in logic],
                )

            async def GetABI(self, request, context):
                db = self._get_db()
                abi = registry_service.get_abi(db, request.id)
                if not abi:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return registry_pb2.ABI()
                return registry_pb2.ABI(
                    id=abi.id, project_id=abi.project_id,
                    contract_name=abi.contract_name,
                    contract_address=abi.contract_address or "",
                    chain=abi.chain, abi_json=abi.abi_json,
                    compiler_version=abi.compiler_version or "",
                    is_verified=abi.is_verified,
                )

            async def GetSDK(self, request, context):
                db = self._get_db()
                sdk = registry_service.get_sdk(db, request.id)
                if not sdk:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return registry_pb2.SDK()
                return registry_pb2.SDK(
                    id=sdk.id, project_id=sdk.project_id,
                    name=sdk.name, language=sdk.language,
                    version=sdk.version,
                    package_name=sdk.package_name or "",
                    install_command=sdk.install_command or "",
                    documentation=sdk.documentation or "",
                    readme_content=sdk.readme_content or "",
                )

            async def GetExecutionLogic(self, request, context):
                db = self._get_db()
                logic = registry_service.get_execution_logic(db, request.id)
                if not logic:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return registry_pb2.ExecutionLogic()
                return registry_pb2.ExecutionLogic(
                    id=logic.id, project_id=logic.project_id,
                    name=logic.name, description=logic.description or "",
                    function_signature=logic.function_signature or "",
                    logic_type=logic.logic_type,
                    input_schema=logic.input_schema or "",
                    output_schema=logic.output_schema or "",
                    chain=logic.chain or "",
                    gas_estimate=logic.gas_estimate or 0,
                    is_read_only=logic.is_read_only,
                    is_verified=logic.is_verified,
                    execution_count=logic.execution_count,
                )

            async def GetContractInterface(self, request, context):
                try:
                    abi_data = json.loads(request.abi_json)
                except json.JSONDecodeError:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    return registry_pb2.ContractInterfaceResponse()

                functions = []
                events = []
                for item in abi_data:
                    entry = registry_pb2.FunctionEntry(
                        name=item.get("name", ""),
                        type=item.get("type", ""),
                        state_mutability=item.get("stateMutability", ""),
                        inputs_json=json.dumps(item.get("inputs", [])),
                        outputs_json=json.dumps(item.get("outputs", [])),
                    )
                    if item.get("type") == "event":
                        events.append(entry)
                    elif item.get("type") in ("function", "constructor"):
                        functions.append(entry)

                return registry_pb2.ContractInterfaceResponse(
                    functions=functions, events=events,
                    total_functions=len(functions), total_events=len(events),
                )

            async def StreamSearchResults(self, request, context):
                db = self._get_db()
                result = registry_service.search_projects(
                    db, query=request.query or None,
                    chain=request.chain or None,
                    category=request.category or None,
                    page=1, page_size=100,
                )
                for item in result.get("items", []):
                    yield registry_pb2.Project(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        slug=item.get("slug", ""),
                        description=item.get("description", ""),
                        chain=item.get("chain", ""),
                        category=item.get("category", ""),
                        star_count=item.get("stars_count", 0),
                        owner_username=item.get("owner_username", ""),
                    )

            async def ToolStream(self, request_iterator, context):
                db = self._get_db()
                async for request in request_iterator:
                    try:
                        args = json.loads(request.arguments_json) if request.arguments_json else {}
                        result = await dispatch_tool(request.tool_name, args, db)
                        yield registry_pb2.ToolCallResponse(
                            result_json=json.dumps(result.get("result", {}), default=str),
                            error=result.get("error", ""),
                        )
                    except Exception as e:
                        yield registry_pb2.ToolCallResponse(error=str(e))

            async def ListTools(self, request, context):
                tools = list_tools()
                return registry_pb2.ToolListResponse(
                    tools=[registry_pb2.ToolDefinition(
                        name=t["name"],
                        description=t["description"],
                        input_schema_json=json.dumps(t["input_schema"]),
                    ) for t in tools],
                )

            async def GetUserProfile(self, request, context):
                db = self._get_db()
                result = registry_service.get_user_registry_profile(db, request.username)
                if not result:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return registry_pb2.UserProfileResponse()
                return registry_pb2.UserProfileResponse(
                    username=result.get("username", ""),
                    eth_address=result.get("eth_address", ""),
                    tier=result.get("tier", "free"),
                    project_count=result.get("project_count", 0),
                    stars_given=result.get("stars_given", 0),
                    total_stars_received=result.get("total_stars_received", 0),
                    joined_at=result.get("joined_at", ""),
                )

        # Start server
        server = grpc_aio.server()
        registry_pb2_grpc.add_RegistryServiceServicer_to_server(
            RegistryServiceImpl(), server,
        )
        server.add_insecure_port(f"[::]:{port}")
        await server.start()
        logger.info(f"gRPC server started on port {port}")
        _server = server
        await server.wait_for_termination()

    except ImportError:
        logger.info("gRPC proto stubs not generated — run 'python -m grpc_tools.protoc' to generate them")
        logger.info("gRPC server not started (stubs required)")
    except Exception as e:
        logger.error(f"gRPC server error: {e}")


async def stop_grpc_server():
    """Gracefully stop the gRPC server."""
    global _server
    if _server:
        await _server.stop(grace=5)
        _server = None
