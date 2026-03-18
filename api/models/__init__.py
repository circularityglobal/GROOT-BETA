"""Import all models so SQLAlchemy metadata is populated."""
from api.models.public import (  # noqa: F401
    User, ApiKey, DeviceRegistration, AgentRegistration,
    IoTTelemetry, WebhookSubscription, UsageRecord, SIWENonce, RefreshToken,
)
from api.models.internal import (  # noqa: F401
    ServerSecret, RoleAssignment, AdminAuditLog,
    ProductRegistry, MCPServerRegistry, SystemConfig,
    CustodialWallet, WalletShare,
)
from api.models.knowledge import (  # noqa: F401
    KnowledgeDocument, KnowledgeChunk, ContractDefinition,
)
from api.models.registry import (  # noqa: F401
    RegistryProject, RegistryABI, RegistrySDK,
    ExecutionLogic, RegistryStar, RegistryFork,
)
from api.models.brain import (  # noqa: F401
    UserRepository, ContractRepo, ContractFunction,
    ContractEvent, SDKDefinition,
)