"""
Auth Package — authentication, credits, and team collaboration.
"""

from .auth_manager import (
    AuthManager,
    Credential,
    UserSession,
    WindowsCredentialManager,
    CredentialEncryption,
    create_auth_manager,
    get_auth_manager,
)

from .credit_manager import (
    CreditManager,
    TokenUsage,
    Budget,
    UsageSummary,
    create_credit_manager,
    get_credit_manager,
)

__all__ = [
    # Auth Manager
    "AuthManager",
    "Credential",
    "UserSession",
    "WindowsCredentialManager",
    "CredentialEncryption",
    "create_auth_manager",
    "get_auth_manager",
    # Credit Manager
    "CreditManager",
    "TokenUsage",
    "Budget",
    "UsageSummary",
    "create_credit_manager",
    "get_credit_manager",
]