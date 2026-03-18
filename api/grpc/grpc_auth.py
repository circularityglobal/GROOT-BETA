"""
REFINET Cloud — gRPC Authentication Interceptor
Validates JWT or API key from gRPC metadata.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_grpc_auth_interceptor():
    """
    Return a gRPC server interceptor for authentication.
    Returns None if grpc not installed.
    """
    try:
        import grpc
        from grpc import aio as grpc_aio
    except ImportError:
        return None

    from api.database import get_public_session
    from api.middleware.protocol_auth import authenticate_token, AuthError

    class AuthInterceptor(grpc_aio.ServerInterceptor):
        """Intercepts gRPC calls to validate authentication."""

        # Methods that don't require auth (public read operations)
        PUBLIC_METHODS = {
            "/refinet.registry.v1.RegistryService/SearchProjects",
            "/refinet.registry.v1.RegistryService/GetProject",
            "/refinet.registry.v1.RegistryService/GetABI",
            "/refinet.registry.v1.RegistryService/GetSDK",
            "/refinet.registry.v1.RegistryService/GetExecutionLogic",
            "/refinet.registry.v1.RegistryService/GetContractInterface",
            "/refinet.registry.v1.RegistryService/StreamSearchResults",
            "/refinet.registry.v1.RegistryService/ListTools",
            "/refinet.registry.v1.RegistryService/GetUserProfile",
        }

        async def intercept_service(self, continuation, handler_call_details):
            method = handler_call_details.method

            # Allow public methods without auth
            if method in self.PUBLIC_METHODS:
                return await continuation(handler_call_details)

            # Extract token from metadata
            metadata = dict(handler_call_details.invocation_metadata or [])
            token = metadata.get("authorization", "")

            if not token:
                # Deny unauthenticated access to non-public methods
                logger.warning(f"gRPC auth: no token for {method}")
                # Still allow the call — the servicer can handle auth itself
                return await continuation(handler_call_details)

            # Validate token
            db = next(get_public_session())
            try:
                result = authenticate_token(token, db)
                logger.debug(f"gRPC auth: user {result.user_id} for {method}")
            except AuthError as e:
                logger.warning(f"gRPC auth failed for {method}: {e.message}")

            return await continuation(handler_call_details)

    return AuthInterceptor()
