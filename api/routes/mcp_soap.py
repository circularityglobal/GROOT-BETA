"""
REFINET Cloud — SOAP Endpoint for Registry
Enterprise/legacy integration via SOAP/XML.
Uses spyne library mounted via WSGIMiddleware.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports — spyne may not be installed in all environments
_soap_app = None


def get_soap_wsgi_app():
    """
    Create and return the SOAP WSGI application.
    Returns None if spyne is not installed.
    """
    global _soap_app
    if _soap_app is not None:
        return _soap_app

    try:
        from spyne import (
            Application, Service, rpc,
            Unicode, Integer, Boolean, Array, ComplexModel,
        )
        from spyne.protocol.soap import Soap11
        from spyne.server.wsgi import WsgiApplication
    except ImportError:
        logger.warning("spyne not installed — SOAP endpoint disabled")
        return None

    from api.database import get_public_session
    from api.services import registry_service

    # ── SOAP Complex Types ───────────────────────────────────────

    class ProjectResult(ComplexModel):
        id = Unicode
        slug = Unicode
        name = Unicode
        description = Unicode
        chain = Unicode
        category = Unicode
        stars_count = Unicode
        forks_count = Unicode
        owner_username = Unicode

    class ABIResult(ComplexModel):
        id = Unicode
        contract_name = Unicode
        contract_address = Unicode
        chain = Unicode
        abi_json = Unicode
        is_verified = Unicode

    class SDKResult(ComplexModel):
        id = Unicode
        name = Unicode
        language = Unicode
        version = Unicode
        install_command = Unicode
        documentation = Unicode

    class LogicResult(ComplexModel):
        id = Unicode
        name = Unicode
        logic_type = Unicode
        description = Unicode
        function_signature = Unicode
        chain = Unicode
        is_verified = Unicode

    class SearchResponse(ComplexModel):
        projects = Array(ProjectResult)
        total = Unicode
        page = Unicode
        has_next = Unicode

    # ── SOAP Service ─────────────────────────────────────────────

    class RegistrySoapService(Service):

        @rpc(Unicode, Unicode, Unicode, Integer, Integer, _returns=SearchResponse)
        def SearchRegistry(ctx, query, chain, category, page, page_size):
            """Search the REFINET smart contract registry."""
            db = next(get_public_session())
            result = registry_service.search_projects(
                db,
                query=query or None,
                chain=chain or None,
                category=category or None,
                page=page or 1,
                page_size=page_size or 20,
            )

            projects = []
            for item in result.get("items", []):
                projects.append(ProjectResult(
                    id=item.get("id", ""),
                    slug=item.get("slug", ""),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    chain=item.get("chain", ""),
                    category=item.get("category", ""),
                    stars_count=str(item.get("stars_count", 0)),
                    forks_count=str(item.get("forks_count", 0)),
                    owner_username=item.get("owner_username", ""),
                ))

            return SearchResponse(
                projects=projects,
                total=str(result.get("total", 0)),
                page=str(result.get("page", 1)),
                has_next=str(result.get("has_next", False)),
            )

        @rpc(Unicode, _returns=ABIResult)
        def GetABI(ctx, abi_id):
            """Get ABI by ID."""
            db = next(get_public_session())
            abi = registry_service.get_abi(db, abi_id)
            if not abi:
                return ABIResult(id="", contract_name="NOT_FOUND")

            return ABIResult(
                id=abi.id,
                contract_name=abi.contract_name,
                contract_address=abi.contract_address or "",
                chain=abi.chain,
                abi_json=abi.abi_json,
                is_verified=str(abi.is_verified),
            )

        @rpc(Unicode, _returns=SDKResult)
        def GetSDK(ctx, sdk_id):
            """Get SDK by ID."""
            db = next(get_public_session())
            sdk = registry_service.get_sdk(db, sdk_id)
            if not sdk:
                return SDKResult(id="", name="NOT_FOUND")

            return SDKResult(
                id=sdk.id,
                name=sdk.name,
                language=sdk.language,
                version=sdk.version,
                install_command=sdk.install_command or "",
                documentation=sdk.documentation or "",
            )

        @rpc(Unicode, _returns=LogicResult)
        def GetExecutionLogic(ctx, logic_id):
            """Get execution logic by ID."""
            db = next(get_public_session())
            logic = registry_service.get_execution_logic(db, logic_id)
            if not logic:
                return LogicResult(id="", name="NOT_FOUND")

            return LogicResult(
                id=logic.id,
                name=logic.name,
                logic_type=logic.logic_type,
                description=logic.description or "",
                function_signature=logic.function_signature or "",
                chain=logic.chain or "",
                is_verified=str(logic.is_verified),
            )

        @rpc(Unicode, _returns=Unicode)
        def GetProject(ctx, slug):
            """Get project details as JSON string."""
            db = next(get_public_session())
            result = registry_service.get_project_by_slug(db, slug)
            if not result:
                return json.dumps({"error": "Project not found"})
            return json.dumps(result, default=str)

        @rpc(Unicode, Unicode, _returns=Unicode)
        def DecodeFunction(ctx, abi_json, calldata):
            """Decode a function call from ABI and calldata."""
            try:
                abi_data = json.loads(abi_json)
                selector = calldata[:10] if calldata.startswith("0x") else "0x" + calldata[:8]
                for item in abi_data:
                    if item.get("type") != "function":
                        continue
                    name = item.get("name", "")
                    inputs = item.get("inputs", [])
                    sig = f"{name}({','.join(i['type'] for i in inputs)})"
                    return json.dumps({"function": name, "signature": sig})
                return json.dumps({"error": "Function not found"})
            except Exception as e:
                return json.dumps({"error": str(e)})

    # ── Build Application ────────────────────────────────────────

    soap_application = Application(
        [RegistrySoapService],
        tns="http://registry.refinet.io/soap",
        in_protocol=Soap11(validator="lxml"),
        out_protocol=Soap11(),
    )

    _soap_app = WsgiApplication(soap_application)
    return _soap_app
