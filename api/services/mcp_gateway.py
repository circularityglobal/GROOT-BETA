"""
REFINET Cloud — MCP Gateway Service
Unified tool dispatcher for all protocol adapters.
Maps MCP tool names to registry service methods.
"""

import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.services import registry_service


from api.services.crypto_utils import keccak256 as _keccak256_impl


def _keccak256(data: bytes) -> bytes:
    """Keccak-256 hash — delegates to shared crypto_utils."""
    return _keccak256_impl(data)

logger = logging.getLogger(__name__)


# ── MCP Tool Definitions ─────────────────────────────────────────────

MCP_TOOLS = {
    "search_registry": {
        "description": "Search the REFINET registry for smart contract projects by keyword, category, or chain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
                "chain": {"type": "string", "description": "Blockchain filter (ethereum, base, arbitrum, polygon, solana, multi-chain)"},
                "category": {"type": "string", "description": "Category filter (defi, token, governance, bridge, utility, oracle, nft, dao, sdk, library)"},
                "page": {"type": "integer", "description": "Page number (default 1)"},
                "page_size": {"type": "integer", "description": "Results per page (default 20)"},
            },
        },
    },
    "get_project": {
        "description": "Get full details of a registry project by its slug (owner/project-name).",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Project slug (e.g. 'alice/staking-pool')"},
            },
            "required": ["slug"],
        },
    },
    "get_abi": {
        "description": "Get the full ABI JSON for a specific contract ABI entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "abi_id": {"type": "string", "description": "ABI entry ID"},
            },
            "required": ["abi_id"],
        },
    },
    "get_sdk": {
        "description": "Get SDK definition and documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sdk_id": {"type": "string", "description": "SDK entry ID"},
            },
            "required": ["sdk_id"],
        },
    },
    "get_execution_logic": {
        "description": "Get execution logic entry with function signature, input/output schemas, and preconditions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "logic_id": {"type": "string", "description": "Execution logic entry ID"},
            },
            "required": ["logic_id"],
        },
    },
    "list_projects": {
        "description": "List registry projects with optional filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "category": {"type": "string"},
                "sort_by": {"type": "string", "enum": ["stars", "recent", "name"]},
                "page": {"type": "integer"},
                "page_size": {"type": "integer"},
            },
        },
    },
    "get_contract_interface": {
        "description": "Parse an ABI JSON and return a human-readable contract interface (functions, events).",
        "input_schema": {
            "type": "object",
            "properties": {
                "abi_json": {"type": "string", "description": "Full ABI JSON string"},
            },
            "required": ["abi_json"],
        },
    },
    "decode_function": {
        "description": "Decode a contract function call from hex calldata using the ABI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "abi_json": {"type": "string", "description": "Full ABI JSON string"},
                "calldata": {"type": "string", "description": "Hex-encoded calldata (0x...)"},
            },
            "required": ["abi_json", "calldata"],
        },
    },
    "encode_function": {
        "description": "Encode a contract function call with arguments into hex calldata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "abi_json": {"type": "string", "description": "Full ABI JSON string"},
                "function_name": {"type": "string", "description": "Function name"},
                "args": {"type": "array", "description": "Function arguments"},
            },
            "required": ["abi_json", "function_name", "args"],
        },
    },
    # ── GROOT Brain: Contract SDK Tools ──────────────────────────────
    "list_contract_sdks": {
        "description": "List public smart contract SDK definitions available on REFINET. These are user-uploaded contracts with parsed ABIs and access control classification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (contract name, function name, or description)"},
                "chain": {"type": "string", "description": "Blockchain filter (ethereum, base, arbitrum, polygon, solana)"},
                "max_results": {"type": "integer", "description": "Maximum results (default 5)"},
            },
        },
    },
    "get_contract_sdk": {
        "description": "Get the full SDK definition for a specific public contract by chain and address. Returns function signatures, access levels, and security summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "Blockchain (ethereum, base, arbitrum, polygon, solana)"},
                "address": {"type": "string", "description": "Contract address (0x...)"},
            },
            "required": ["chain", "address"],
        },
    },
    "call_contract_function": {
        "description": "Get encoding info for calling a specific function on a public contract. Returns function signature, inputs, and access level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "Blockchain"},
                "address": {"type": "string", "description": "Contract address"},
                "function_name": {"type": "string", "description": "Function name to call"},
                "args": {"type": "array", "description": "Function arguments"},
            },
            "required": ["chain", "address", "function_name"],
        },
    },
    # ── SDK Gateway Tools (deterministic, no LLM) ─────────────────────
    "resolve_contract": {
        "description": "Resolve a smart contract by name, slug, or address. Returns all deployment addresses across all chains. No LLM — instant DB lookup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Contract name, slug (user/contract), or address (0x...)"},
                "chain": {"type": "string", "description": "Optional chain filter (ethereum, base, polygon, arbitrum, etc.)"},
            },
            "required": ["query"],
        },
    },
    "fetch_sdk": {
        "description": "Fetch the full public SDK for a smart contract. Supports lookup by chain+address or by slug. Returns functions, events, security summary, and deployments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "Blockchain name (if using address lookup)"},
                "address": {"type": "string", "description": "Contract address (0x...)"},
                "slug": {"type": "string", "description": "Contract slug (alternative to chain+address)"},
                "include_abi": {"type": "boolean", "description": "Include raw ABI JSON in response (default false)"},
            },
        },
    },
    "list_chains_for_contract": {
        "description": "List all blockchain networks where a contract is deployed. Quick deployment lookup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string", "description": "Contract UUID"},
                "slug": {"type": "string", "description": "Contract slug (alternative to ID)"},
            },
        },
    },
    "bulk_sdk_export": {
        "description": "Export a paginated catalog of all public SDKs for agent discovery and bootstrapping. Compact mode returns names+addresses+chains only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "Optional chain filter"},
                "category": {"type": "string", "description": "Optional tag/category filter"},
                "compact": {"type": "boolean", "description": "If true, return only names+addresses+chains (default true)"},
                "page": {"type": "integer", "description": "Page number (default 1)"},
                "page_size": {"type": "integer", "description": "Results per page (default 50, max 200)"},
            },
        },
    },
    # ── Script Execution Tool ──────────────────────────────────────────
    "execute_script": {
        "description": "Execute a registered platform script. Returns the script output. Use 'list_scripts' action with no script_name to discover available scripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "script_name": {"type": "string", "description": "Name of the script to execute (e.g. 'db_stats', 'health_report')"},
                "args": {"type": "object", "description": "Optional arguments to pass to the script"},
            },
            "required": ["script_name"],
        },
    },
    "list_scripts": {
        "description": "List all available platform scripts with their descriptions and categories.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    # ── Agent Delegation Tool ─────────────────────────────────────────
    "delegate_to_agent": {
        "description": "Delegate a subtask to another agent. The target agent must have delegation_policy set to 'auto' or 'approve' in its SOUL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_agent_id": {"type": "string", "description": "ID of the agent to delegate to"},
                "subtask_description": {"type": "string", "description": "Description of what the target agent should do"},
            },
            "required": ["target_agent_id", "subtask_description"],
        },
    },
    # ── Document Ingestion & Tagging Tools ────────────────────────────
    "search_documents": {
        "description": "Search REFINET knowledge base documents by natural language query. Supports filtering by category and semantic tags. Returns relevant document chunks with relevance scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "category": {"type": "string", "description": "Filter by category (about|product|docs|blockchain|contract|faq)"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by semantic tags (e.g. ['defi', 'staking'])"},
                "max_results": {"type": "integer", "description": "Maximum results (default 5)"},
            },
            "required": ["query"],
        },
    },
    "compare_documents": {
        "description": "Compare two knowledge base documents by semantic similarity, keyword overlap, structural differences, and tag overlap.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id_a": {"type": "string", "description": "First document ID"},
                "doc_id_b": {"type": "string", "description": "Second document ID"},
            },
            "required": ["doc_id_a", "doc_id_b"],
        },
    },
    "get_document_tags": {
        "description": "Get auto-generated semantic tags for a knowledge base document. Tags describe what the document is about in natural language, optimized for LLM search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID"},
            },
            "required": ["doc_id"],
        },
    },
}


# ── Tool Dispatch ────────────────────────────────────────────────────

async def dispatch_tool(
    tool_name: str,
    arguments: dict,
    db: Session,
    user_id: Optional[str] = None,
) -> dict:
    """
    Single entry point for all MCP tool calls from any protocol.
    Returns a dict with the tool result or error.
    """
    if tool_name not in MCP_TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        if tool_name == "search_registry":
            result = registry_service.search_projects(
                db,
                query=arguments.get("query"),
                chain=arguments.get("chain"),
                category=arguments.get("category"),
                page=arguments.get("page", 1),
                page_size=arguments.get("page_size", 20),
            )
            return {"result": result}

        elif tool_name == "get_project":
            result = registry_service.get_project_by_slug(
                db,
                slug=arguments["slug"],
                requesting_user_id=user_id,
            )
            if not result:
                return {"error": "Project not found"}
            return {"result": result}

        elif tool_name == "get_abi":
            abi = registry_service.get_abi(db, arguments["abi_id"])
            if not abi:
                return {"error": "ABI not found"}
            return {"result": {
                "id": abi.id,
                "project_id": abi.project_id,
                "contract_name": abi.contract_name,
                "contract_address": abi.contract_address,
                "chain": abi.chain,
                "abi_json": abi.abi_json,
                "compiler_version": abi.compiler_version,
                "is_verified": abi.is_verified,
            }}

        elif tool_name == "get_sdk":
            sdk = registry_service.get_sdk(db, arguments["sdk_id"])
            if not sdk:
                return {"error": "SDK not found"}
            return {"result": {
                "id": sdk.id,
                "project_id": sdk.project_id,
                "name": sdk.name,
                "language": sdk.language,
                "version": sdk.version,
                "package_name": sdk.package_name,
                "install_command": sdk.install_command,
                "documentation": sdk.documentation,
                "code_samples": sdk.code_samples,
                "readme_content": sdk.readme_content,
            }}

        elif tool_name == "get_execution_logic":
            logic = registry_service.get_execution_logic(db, arguments["logic_id"])
            if not logic:
                return {"error": "Execution logic not found"}
            return {"result": {
                "id": logic.id,
                "project_id": logic.project_id,
                "name": logic.name,
                "logic_type": logic.logic_type,
                "description": logic.description,
                "function_signature": logic.function_signature,
                "input_schema": logic.input_schema,
                "output_schema": logic.output_schema,
                "chain": logic.chain,
                "gas_estimate": logic.gas_estimate,
                "is_read_only": logic.is_read_only,
                "is_verified": logic.is_verified,
                "execution_count": logic.execution_count,
            }}

        elif tool_name == "list_projects":
            result = registry_service.search_projects(
                db,
                chain=arguments.get("chain"),
                category=arguments.get("category"),
                sort_by=arguments.get("sort_by", "stars"),
                page=arguments.get("page", 1),
                page_size=arguments.get("page_size", 20),
            )
            return {"result": result}

        elif tool_name == "get_contract_interface":
            abi_data = json.loads(arguments["abi_json"])
            functions = []
            events = []
            for item in abi_data:
                entry = {
                    "name": item.get("name", ""),
                    "type": item.get("type", ""),
                    "state_mutability": item.get("stateMutability"),
                    "inputs": [{"name": i.get("name", ""), "type": i.get("type", "")} for i in item.get("inputs", [])],
                    "outputs": [{"name": o.get("name", ""), "type": o.get("type", "")} for o in item.get("outputs", [])],
                }
                if item.get("type") == "event":
                    events.append(entry)
                elif item.get("type") in ("function", "constructor", "fallback", "receive"):
                    functions.append(entry)
            return {"result": {
                "functions": functions,
                "events": events,
                "total_functions": len(functions),
                "total_events": len(events),
            }}

        elif tool_name == "decode_function":
            # Basic ABI decode using the ABI JSON
            abi_data = json.loads(arguments["abi_json"])
            calldata = arguments["calldata"]
            selector = calldata[:10] if calldata.startswith("0x") else "0x" + calldata[:8]

            for item in abi_data:
                if item.get("type") != "function":
                    continue
                # Build function signature
                name = item.get("name", "")
                inputs = item.get("inputs", [])
                sig = f"{name}({','.join(i['type'] for i in inputs)})"

                # Check if selector matches (first 4 bytes of keccak256)
                fn_selector = "0x" + _keccak256(sig.encode()).hex()[:8]

                if fn_selector == selector:
                    return {"result": {
                        "function_name": name,
                        "signature": sig,
                        "inputs": [{"name": i.get("name", ""), "type": i.get("type", "")} for i in inputs],
                    }}

            return {"error": "Function selector not found in ABI"}

        elif tool_name == "encode_function":
            # Return the function signature info for encoding
            abi_data = json.loads(arguments["abi_json"])
            fn_name = arguments["function_name"]
            args = arguments.get("args", [])

            for item in abi_data:
                if item.get("type") == "function" and item.get("name") == fn_name:
                    inputs = item.get("inputs", [])
                    return {"result": {
                        "function_name": fn_name,
                        "signature": f"{fn_name}({','.join(i['type'] for i in inputs)})",
                        "inputs": [{"name": i.get("name", ""), "type": i.get("type", "")} for i in inputs],
                        "provided_args": args,
                        "note": "Use web3 library on client to encode with exact ABI types",
                    }}

            return {"error": f"Function '{fn_name}' not found in ABI"}

        # ── GROOT Brain: Contract SDK Tools ─────────────────────────
        elif tool_name == "list_contract_sdks":
            from api.services.contract_brain import search_public_sdks
            results = search_public_sdks(
                db,
                query=arguments.get("query", ""),
                chain=arguments.get("chain"),
                max_results=arguments.get("max_results", 5),
            )
            # Return summaries (not full SDK JSON) for listing
            summaries = []
            for r in results:
                summaries.append({
                    "contract_name": r["contract_name"],
                    "chain": r["chain"],
                    "address": r.get("address"),
                    "description": r.get("description"),
                    "public_functions": r.get("public_functions", []),
                    "admin_functions": r.get("admin_functions", []),
                    "security_summary": r.get("security_summary", {}),
                })
            return {"result": summaries}

        elif tool_name == "get_contract_sdk":
            from api.models.brain import ContractRepo as BrainContractRepo, SDKDefinition
            contract = db.query(BrainContractRepo).filter(
                BrainContractRepo.chain == arguments["chain"],
                BrainContractRepo.address == arguments["address"],
                BrainContractRepo.is_public == True,  # noqa: E712
                BrainContractRepo.is_active == True,  # noqa: E712
            ).first()
            if not contract:
                return {"error": "Public contract not found for this chain/address"}
            sdk = db.query(SDKDefinition).filter(
                SDKDefinition.contract_id == contract.id,
                SDKDefinition.is_public == True,  # noqa: E712
            ).first()
            if not sdk:
                return {"error": "SDK not available for this contract"}
            return {"result": json.loads(sdk.sdk_json)}

        elif tool_name == "call_contract_function":
            from api.models.brain import ContractRepo as BrainContractRepo, SDKDefinition
            contract = db.query(BrainContractRepo).filter(
                BrainContractRepo.chain == arguments["chain"],
                BrainContractRepo.address == arguments["address"],
                BrainContractRepo.is_public == True,  # noqa: E712
                BrainContractRepo.is_active == True,  # noqa: E712
            ).first()
            if not contract:
                return {"error": "Public contract not found"}
            sdk = db.query(SDKDefinition).filter(
                SDKDefinition.contract_id == contract.id,
                SDKDefinition.is_public == True,  # noqa: E712
            ).first()
            if not sdk:
                return {"error": "SDK not available"}
            sdk_data = json.loads(sdk.sdk_json)
            fn_name = arguments["function_name"]
            # Search in public and admin functions
            all_fns = sdk_data.get("functions", {}).get("public", []) + sdk_data.get("functions", {}).get("owner_admin", [])
            for fn in all_fns:
                if fn["name"] == fn_name:
                    result = {
                        "function_name": fn["name"],
                        "signature": fn.get("signature"),
                        "selector": fn.get("selector"),
                        "mutability": fn.get("mutability"),
                        "inputs": fn.get("inputs", []),
                        "outputs": fn.get("outputs", []),
                        "provided_args": arguments.get("args", []),
                        "chain": arguments["chain"],
                        "contract_address": arguments["address"],
                    }
                    if fn.get("access"):
                        result["access_level"] = fn["access"]
                        result["warning"] = fn.get("warning", "Restricted function")
                    return {"result": result}
            return {"error": f"Function '{fn_name}' not found in contract SDK"}

        # ── SDK Gateway Tools (deterministic, no LLM) ────────────────
        elif tool_name == "resolve_contract":
            from api.services.sdk_gateway import resolve_contract
            result = resolve_contract(
                db,
                query=arguments["query"],
                chain=arguments.get("chain"),
            )
            return {"result": result}

        elif tool_name == "fetch_sdk":
            from api.services.sdk_gateway import fetch_sdk
            result = fetch_sdk(
                db,
                chain=arguments.get("chain"),
                address=arguments.get("address"),
                slug=arguments.get("slug"),
                include_abi=arguments.get("include_abi", False),
            )
            if "error" in result:
                return {"error": result["error"]}
            return {"result": result}

        elif tool_name == "list_chains_for_contract":
            from api.services.sdk_gateway import list_chains_for_contract
            result = list_chains_for_contract(
                db,
                contract_id=arguments.get("contract_id"),
                slug=arguments.get("slug"),
            )
            return {"result": result}

        elif tool_name == "bulk_sdk_export":
            from api.services.sdk_gateway import bulk_sdk_export
            result = bulk_sdk_export(
                db,
                chain=arguments.get("chain"),
                category=arguments.get("category"),
                compact=arguments.get("compact", True),
                page=arguments.get("page", 1),
                page_size=arguments.get("page_size", 50),
            )
            return {"result": result}

        # ── Script Execution Tools ────────────────────────────────────
        elif tool_name == "list_scripts":
            from api.services.script_runner import discover_scripts
            scripts = discover_scripts()
            return {"result": [
                {"name": s["name"], "description": s.get("description", ""), "category": s.get("category", "")}
                for s in scripts
            ]}

        elif tool_name == "execute_script":
            from api.services.script_runner import execute_script
            result = await execute_script(
                db,
                script_name=arguments["script_name"],
                args=arguments.get("args"),
                started_by=user_id,
            )
            return {"result": result}

        # ── Agent Delegation Tool ──────────────────────────────────────
        elif tool_name == "delegate_to_agent":
            if not user_id:
                return {"error": "Authentication required for delegation"}
            from api.services.agent_engine import delegate_task
            from api.models.agent_engine import AgentTask
            # Find a running task for the calling agent (source context)
            # The source_agent_id comes from the execution context
            source_task = db.query(AgentTask).filter(
                AgentTask.user_id == user_id,
                AgentTask.status == "running",
            ).order_by(AgentTask.created_at.desc()).first()
            if not source_task:
                return {"error": "No running task context for delegation"}
            delegation = await delegate_task(
                db,
                source_agent_id=source_task.agent_id,
                target_agent_id=arguments["target_agent_id"],
                source_task_id=source_task.id,
                subtask_description=arguments["subtask_description"],
                user_id=user_id,
            )
            if not delegation:
                return {"error": "Delegation rejected by target agent"}
            return {"result": {
                "delegation_id": delegation.id,
                "status": delegation.status,
                "target_agent_id": arguments["target_agent_id"],
            }}

        # ── Document Ingestion & Tagging Tools ────────────────────────
        elif tool_name == "search_documents":
            from api.services.rag import search_knowledge
            # MCP/agent access: user_id=None enforces public+platform only
            results = search_knowledge(
                db,
                query=arguments["query"],
                max_results=arguments.get("max_results", 5),
                category=arguments.get("category"),
                tags=arguments.get("tags"),
                user_id=user_id,  # None for external agents → public+platform only
            )
            return {"result": results}

        elif tool_name == "compare_documents":
            from api.services.document_compare import compare_documents
            from api.models.knowledge import KnowledgeDocument
            # Enforce visibility: MCP agents can only compare public/platform docs
            for did in [arguments["doc_id_a"], arguments["doc_id_b"]]:
                doc_check = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.id == did,
                    KnowledgeDocument.is_active == True,  # noqa: E712
                ).first()
                if not doc_check:
                    return {"error": f"Document not found: {did}"}
                vis = doc_check.visibility or "platform"
                if vis == "private" and (not user_id or doc_check.user_id != user_id):
                    return {"error": f"Access denied: document {did} is private"}
            result = compare_documents(db, arguments["doc_id_a"], arguments["doc_id_b"])
            if "error" in result:
                return {"error": result["error"]}
            return {"result": result}

        elif tool_name == "get_document_tags":
            from api.models.knowledge import KnowledgeDocument
            doc = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.id == arguments["doc_id"],
                KnowledgeDocument.is_active == True,  # noqa: E712
            ).first()
            if not doc:
                return {"error": "Document not found"}
            tags = []
            if doc.tags:
                try:
                    tags = json.loads(doc.tags)
                except (json.JSONDecodeError, TypeError):
                    pass
            return {"result": {
                "doc_id": doc.id,
                "title": doc.title,
                "tags": tags,
                "category": doc.category,
                "doc_type": doc.doc_type,
            }}

        return {"error": f"Tool '{tool_name}' not implemented"}

    except KeyError as e:
        return {"error": f"Missing required argument: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {str(e)}"}
    except Exception as e:
        logger.error(f"MCP tool error ({tool_name}): {e}")
        return {"error": str(e)}


def list_tools() -> list[dict]:
    """Return all available MCP tool definitions."""
    return [
        {
            "name": name,
            "description": tool["description"],
            "input_schema": tool["input_schema"],
        }
        for name, tool in MCP_TOOLS.items()
    ]
