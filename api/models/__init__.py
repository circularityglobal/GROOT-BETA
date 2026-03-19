"""Import all models so SQLAlchemy metadata is populated."""
from api.models.public import (  # noqa: F401
    User, ApiKey, DeviceRegistration, AgentRegistration,
    IoTTelemetry, WebhookSubscription, UsageRecord, SIWENonce, RefreshToken,
    ChainWatcher, ChainEvent, MessengerLink, DAppBuild,
    AppListing, AppReview, AppInstall,
)
from api.models.internal import (  # noqa: F401
    ServerSecret, RoleAssignment, AdminAuditLog,
    ProductRegistry, MCPServerRegistry, SystemConfig,
    CustodialWallet, WalletShare,
    ScheduledTask, ScriptExecution,
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
from api.models.agent_engine import (  # noqa: F401
    AgentSoul, AgentMemoryWorking, AgentMemoryEpisodic,
    AgentMemorySemantic, AgentMemoryProcedural,
    AgentTask, AgentDelegation,
)
from api.models.pipeline import (  # noqa: F401
    PipelineRun, PipelineStep, PendingAction, DeploymentRecord,
)
from api.models.payments import (  # noqa: F401
    FeeSchedule, PaymentRecord, Subscription, RevenueSplit,
)
from api.models.broker import (  # noqa: F401
    BrokerSession, BrokerFeeConfig,
)