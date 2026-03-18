"""
REFINET Cloud — GraphQL API (Strawberry)
Schema for the smart contract registry accessible via /graphql.
"""

import json
import logging
from typing import Optional, List, AsyncGenerator

import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from api.database import get_public_session
from api.services import registry_service
from api.services.mcp_gateway import dispatch_tool
from api.middleware.protocol_auth import authenticate_token, AuthError

logger = logging.getLogger(__name__)


# ── Helper to get DB session and auth from context ───────────────────

def get_db_from_info(info: Info):
    """Get database session from GraphQL context."""
    return info.context.get("db")


def get_user_id_from_info(info: Info) -> Optional[str]:
    """Get user ID from GraphQL context (set during auth)."""
    return info.context.get("user_id")


# ── GraphQL Types ────────────────────────────────────────────────────

@strawberry.type
class Project:
    id: str
    slug: str
    name: str
    description: Optional[str]
    owner_id: str
    owner_username: Optional[str]
    visibility: str
    category: str
    chain: str
    tags: Optional[List[str]]
    stars_count: int
    forks_count: int
    watchers_count: int
    is_starred: bool
    abi_count: int
    sdk_count: int
    logic_count: int
    readme: Optional[str]
    license: Optional[str]
    website_url: Optional[str]
    repo_url: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@strawberry.type
class ABI:
    id: str
    project_id: str
    contract_name: str
    contract_address: Optional[str]
    chain: str
    abi_json: Optional[str]
    compiler_version: Optional[str]
    is_verified: bool
    created_at: Optional[str]


@strawberry.type
class SDK:
    id: str
    project_id: str
    name: str
    language: str
    version: str
    package_name: Optional[str]
    install_command: Optional[str]
    documentation: Optional[str]
    readme_content: Optional[str]
    created_at: Optional[str]


@strawberry.type
class ExecLogic:
    id: str
    project_id: str
    name: str
    logic_type: str
    description: Optional[str]
    function_signature: Optional[str]
    chain: Optional[str]
    gas_estimate: Optional[int]
    is_read_only: bool
    is_verified: bool
    execution_count: int
    created_at: Optional[str]


@strawberry.type
class PaginatedProjects:
    items: List[Project]
    total: int
    page: int
    page_size: int
    has_next: bool


@strawberry.type
class ContractFn:
    name: str
    type: str
    state_mutability: Optional[str]
    inputs: Optional[str]  # JSON
    outputs: Optional[str]  # JSON


@strawberry.type
class ContractInterface:
    functions: List[ContractFn]
    events: List[ContractFn]
    total_functions: int
    total_events: int


@strawberry.type
class UserProfile:
    username: str
    eth_address: Optional[str]
    tier: str
    project_count: int
    stars_given: int
    total_stars_received: int
    joined_at: Optional[str]


@strawberry.type
class ToolResult:
    result: Optional[str]  # JSON string
    error: Optional[str]


# ── Converters ───────────────────────────────────────────────────────

def _dict_to_project(d: dict) -> Project:
    return Project(
        id=d.get("id", ""),
        slug=d.get("slug", ""),
        name=d.get("name", ""),
        description=d.get("description"),
        owner_id=d.get("owner_id", ""),
        owner_username=d.get("owner_username"),
        visibility=d.get("visibility", "public"),
        category=d.get("category", "utility"),
        chain=d.get("chain", "ethereum"),
        tags=d.get("tags"),
        stars_count=d.get("stars_count", 0),
        forks_count=d.get("forks_count", 0),
        watchers_count=d.get("watchers_count", 0),
        is_starred=d.get("is_starred", False),
        abi_count=d.get("abi_count", 0),
        sdk_count=d.get("sdk_count", 0),
        logic_count=d.get("logic_count", 0),
        readme=d.get("readme"),
        license=d.get("license"),
        website_url=d.get("website_url"),
        repo_url=d.get("repo_url"),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
    )


# ── Query ────────────────────────────────────────────────────────────

@strawberry.type
class Query:
    @strawberry.field
    def search_registry(
        self,
        info: Info,
        query: Optional[str] = None,
        chain: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedProjects:
        db = get_db_from_info(info)
        result = registry_service.search_projects(
            db, query=query, chain=chain, category=category,
            page=page, page_size=page_size,
        )
        return PaginatedProjects(
            items=[_dict_to_project(p) for p in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            has_next=result["has_next"],
        )

    @strawberry.field
    def project(self, info: Info, slug: str) -> Optional[Project]:
        db = get_db_from_info(info)
        user_id = get_user_id_from_info(info)
        result = registry_service.get_project_by_slug(db, slug, user_id)
        if not result:
            return None
        return _dict_to_project(result)

    @strawberry.field
    def trending_projects(self, info: Info, limit: int = 10) -> List[Project]:
        db = get_db_from_info(info)
        results = registry_service.get_trending_projects(db, limit=limit)
        return [_dict_to_project(p) for p in results]

    @strawberry.field
    def user_profile(self, info: Info, username: str) -> Optional[UserProfile]:
        db = get_db_from_info(info)
        result = registry_service.get_user_registry_profile(db, username)
        if not result:
            return None
        return UserProfile(
            username=result["username"],
            eth_address=result.get("eth_address"),
            tier=result.get("tier", "free"),
            project_count=result.get("project_count", 0),
            stars_given=result.get("stars_given", 0),
            total_stars_received=result.get("total_stars_received", 0),
            joined_at=result.get("joined_at"),
        )

    @strawberry.field
    def abi(self, info: Info, abi_id: str) -> Optional[ABI]:
        db = get_db_from_info(info)
        a = registry_service.get_abi(db, abi_id)
        if not a:
            return None
        return ABI(
            id=a.id, project_id=a.project_id,
            contract_name=a.contract_name,
            contract_address=a.contract_address,
            chain=a.chain, abi_json=a.abi_json,
            compiler_version=a.compiler_version,
            is_verified=a.is_verified,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )

    @strawberry.field
    def sdk(self, info: Info, sdk_id: str) -> Optional[SDK]:
        db = get_db_from_info(info)
        s = registry_service.get_sdk(db, sdk_id)
        if not s:
            return None
        return SDK(
            id=s.id, project_id=s.project_id,
            name=s.name, language=s.language,
            version=s.version, package_name=s.package_name,
            install_command=s.install_command,
            documentation=s.documentation,
            readme_content=s.readme_content,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )

    @strawberry.field
    def contract_interface(self, info: Info, abi_json: str) -> Optional[ContractInterface]:
        try:
            abi_data = json.loads(abi_json)
        except json.JSONDecodeError:
            return None

        functions = []
        events = []
        for item in abi_data:
            entry = ContractFn(
                name=item.get("name", ""),
                type=item.get("type", ""),
                state_mutability=item.get("stateMutability"),
                inputs=json.dumps(item.get("inputs", [])),
                outputs=json.dumps(item.get("outputs", [])),
            )
            if item.get("type") == "event":
                events.append(entry)
            elif item.get("type") in ("function", "constructor", "fallback", "receive"):
                functions.append(entry)

        return ContractInterface(
            functions=functions, events=events,
            total_functions=len(functions), total_events=len(events),
        )


# ── Mutation ─────────────────────────────────────────────────────────

@strawberry.input
class ProjectInput:
    name: str
    description: Optional[str] = None
    readme: Optional[str] = None
    visibility: str = "public"
    category: str = "utility"
    chain: str = "ethereum"
    tags: Optional[List[str]] = None
    license: Optional[str] = None


@strawberry.input
class ABIInput:
    contract_name: str
    abi_json: str
    contract_address: Optional[str] = None
    chain: str = "ethereum"
    compiler_version: Optional[str] = None


@strawberry.input
class SDKInput:
    name: str
    language: str
    version: str
    package_name: Optional[str] = None
    install_command: Optional[str] = None
    documentation: Optional[str] = None


@strawberry.input
class LogicInput:
    name: str
    logic_type: str
    description: Optional[str] = None
    function_signature: Optional[str] = None
    chain: Optional[str] = None


@strawberry.type
class MutationResult:
    success: bool
    message: str
    id: Optional[str] = None
    slug: Optional[str] = None


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_project(self, info: Info, input: ProjectInput) -> MutationResult:
        db = get_db_from_info(info)
        user_id = get_user_id_from_info(info)
        if not user_id:
            return MutationResult(success=False, message="Authentication required")

        from api.models.public import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return MutationResult(success=False, message="User not found")

        try:
            project = registry_service.create_project(
                db, owner_id=user_id, owner_username=user.username,
                name=input.name, description=input.description,
                readme=input.readme, visibility=input.visibility,
                category=input.category, chain=input.chain,
                tags=input.tags, license=input.license,
            )
            return MutationResult(success=True, message="Project created", id=project.id, slug=project.slug)
        except ValueError as e:
            return MutationResult(success=False, message=str(e))

    @strawberry.mutation
    def star_project(self, info: Info, slug: str) -> MutationResult:
        db = get_db_from_info(info)
        user_id = get_user_id_from_info(info)
        if not user_id:
            return MutationResult(success=False, message="Authentication required")

        project_data = registry_service.get_project_by_slug(db, slug, user_id)
        if not project_data:
            return MutationResult(success=False, message="Project not found")

        try:
            is_starred = registry_service.toggle_star(db, user_id, project_data["id"])
            return MutationResult(success=True, message="Starred" if is_starred else "Unstarred")
        except ValueError as e:
            return MutationResult(success=False, message=str(e))

    @strawberry.mutation
    def fork_project(self, info: Info, slug: str) -> MutationResult:
        db = get_db_from_info(info)
        user_id = get_user_id_from_info(info)
        if not user_id:
            return MutationResult(success=False, message="Authentication required")

        from api.models.public import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return MutationResult(success=False, message="User not found")

        forked = registry_service.fork_project(db, slug, user_id, user.username)
        if not forked:
            return MutationResult(success=False, message="Source project not found")
        return MutationResult(success=True, message="Forked", id=forked.id, slug=forked.slug)


# ── Schema & Router ──────────────────────────────────────────────────

schema = strawberry.Schema(query=Query, mutation=Mutation)


async def get_context(request=None):
    """Build GraphQL context with DB session and optional auth."""
    db = next(get_public_session())
    context = {"db": db, "user_id": None}

    if request:
        auth_header = None
        if hasattr(request, "headers"):
            auth_header = request.headers.get("Authorization", "")
        elif hasattr(request, "scope"):
            # WebSocket connection params
            headers = dict(request.scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()

        if auth_header:
            try:
                result = authenticate_token(auth_header, db)
                context["user_id"] = result.user_id
            except AuthError:
                pass  # Anonymous access allowed for queries

    return context


graphql_app = GraphQLRouter(schema, context_getter=get_context)
