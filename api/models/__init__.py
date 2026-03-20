"""Import all models so SQLAlchemy metadata is populated."""
from api.models.public import (  # noqa: F401
    User, ApiKey, UserProviderKey, DeviceRegistration, AgentRegistration,
    IoTTelemetry, WebhookSubscription, UsageRecord, SIWENonce, RefreshToken,
    WalletIdentity, WalletSession,
    Conversation, ConversationParticipant, Message, EmailAlias,
    ChainWatcher, ChainEvent, MessengerLink, DAppBuild,
    AppListing, AppReview, AppInstall,
    AppSubmission, SubmissionNote,
)
from api.models.internal import (  # noqa: F401
    ServerSecret, RoleAssignment, AdminAuditLog,
    ProductRegistry, MCPServerRegistry, SystemConfig, HealthCheckLog,
    CustodialWallet, WalletShare,
    ScheduledTask, ScriptExecution, SandboxEnvironment,
)
from api.models.knowledge import (  # noqa: F401
    KnowledgeDocument, KnowledgeChunk, ContractDefinition, DocumentShare,
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
from api.models.vector_memory import (  # noqa: F401
    VectorMemory, VectorInteraction, VectorMemoryLink,
)
from api.models.chain import (  # noqa: F401
    SupportedChain, ContractDeployment,
)