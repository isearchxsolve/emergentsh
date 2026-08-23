"""
AuthManager — secure authentication and credential management.

Features:
- Windows Credential Manager integration for secure API key storage
- OAuth 2.0 flow support (GitHub, Google, etc.)
- JWT token management for session persistence
- API key encryption at rest
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..workspace import WorkspaceManager, get_workspace


# ════════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Credential:
    """A stored credential (API key, token, etc.)."""
    name: str
    value: str
    type: str  # "api_key", "oauth_token", "jwt", "password"
    provider: str  # "nvidia", "openrouter", "anthropic", "openai", "github", etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type,
            "provider": self.provider,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Credential":
        return cls(
            name=data["name"],
            value=data["value"],
            type=data["type"],
            provider=data["provider"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )


@dataclass
class UserSession:
    """User session with JWT token."""
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        if self.expires_at is None:
            return True
        return datetime.now() < self.expires_at


# ════════════════════════════════════════════════════════════════════════════
# Windows Credential Manager Integration
# ════════════════════════════════════════════════════════════════════════════

class WindowsCredentialManager:
    """
    Windows Credential Manager integration using cmdkey / PowerShell.
    
    Provides secure, OS-level credential storage using Windows Credential Manager.
    """
    
    PREFIX = "EmergentSH_"
    
    @staticmethod
    def is_available() -> bool:
        """Check if Windows Credential Manager is available."""
        return sys.platform == "win32"
    
    @classmethod
    def store(cls, name: str, value: str, comment: str = "") -> bool:
        """Store a credential in Windows Credential Manager."""
        if not cls.is_available():
            return False
        
        full_name = f"{cls.PREFIX}{name}"
        try:
            # Use cmdkey to store credential
            cmd = [
                "cmdkey", "/add", full_name,
                "/user", "EmergentSH",
                "/pass", value,
            ]
            if comment:
                cmd.extend(["/comment", comment])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False
    
    @classmethod
    def retrieve(cls, name: str) -> Optional[str]:
        """Retrieve a credential from Windows Credential Manager."""
        if not cls.is_available():
            return None
        
        full_name = f"{cls.PREFIX}{name}"
        try:
            # Use PowerShell to retrieve credential
            ps_script = f"""
            $cred = Get-StoredCredential -Target '{full_name}'
            if ($cred) {{
                $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($cred.Password)
                $password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
                Write-Output $password
            }}
            """
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    @classmethod
    def delete(cls, name: str) -> bool:
        """Delete a credential from Windows Credential Manager."""
        if not cls.is_available():
            return False
        
        full_name = f"{cls.PREFIX}{name}"
        try:
            result = subprocess.run(
                ["cmdkey", "/delete", full_name],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all EmergentSH credentials."""
        if not cls.is_available():
            return []
        
        try:
            result = subprocess.run(
                ["cmdkey", "/list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return []
            
            names = []
            for line in result.stdout.splitlines():
                if cls.PREFIX in line:
                    # Parse target name from output
                    parts = line.split()
                    for part in parts:
                        if part.startswith(cls.PREFIX):
                            names.append(part[len(cls.PREFIX):])
            return names
        except Exception:
            return []


# ════════════════════════════════════════════════════════════════════════════
# Credential Encryption (Cross-platform fallback)
# ════════════════════════════════════════════════════════════════════════════

class CredentialEncryption:
    """
    AES-256-GCM encryption for credential storage.
    
    Uses a master key derived from user's system entropy + optional password.
    """
    
    def __init__(self, master_key: Optional[bytes] = None):
        if master_key:
            self._master_key = master_key
        else:
            # Derive key from machine-specific entropy
            machine_id = self._get_machine_id()
            self._master_key = hashlib.pbkdf2_hmac(
                'sha256',
                machine_id.encode(),
                b'emergentsh_salt_v1',
                100000,
                dklen=32
            )
    
    def _get_machine_id(self) -> str:
        """Get a stable machine identifier."""
        # Combine multiple sources for stability
        parts = [
            os.environ.get("COMPUTERNAME", ""),
            os.environ.get("USERNAME", ""),
            str(os.getuid()) if hasattr(os, "getuid") else "",
        ]
        return "|".join(parts)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string using AES-256-GCM."""
        import secrets
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        aesgcm = AESGCM(self._master_key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()
    
    def decrypt(self, ciphertext_b64: str) -> Optional[str]:
        """Decrypt a string using AES-256-GCM."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            
            data = base64.b64decode(ciphertext_b64)
            nonce = data[:12]
            ciphertext = data[12:]
            
            aesgcm = AESGCM(self._master_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode()
        except Exception:
            return None


# ════════════════════════════════════════════════════════════════════════════
# AuthManager
# ════════════════════════════════════════════════════════════════════════════

class AuthManager:
    """
    High-level authentication and credential manager.
    
    Features:
    - Secure credential storage (Windows Credential Manager + encrypted fallback)
    - OAuth 2.0 flows (GitHub, Google, etc.)
    - JWT session management
    - API key management per provider
    """
    
    def __init__(self, workspace: Optional[WorkspaceManager] = None):
        self._workspace = workspace or get_workspace()
        self._use_windows_cred = WindowsCredentialManager.is_available()
        self._encryption = CredentialEncryption()
        self._credentials: Dict[str, Credential] = {}
        self._sessions: Dict[str, UserSession] = {}
        self._load_credentials()
    
    # ----------------------------------------------------------------------
    # Credential Management
    # ----------------------------------------------------------------------
    
    def _load_credentials(self) -> None:
        """Load credentials from storage."""
        # Try Windows Credential Manager first
        if self._use_windows_cred:
            for name in WindowsCredentialManager.list_all():
                value = WindowsCredentialManager.retrieve(name)
                if value:
                    self._credentials[name] = Credential(
                        name=name,
                        value=value,
                        type="api_key",
                        provider=name.split("_")[0] if "_" in name else "unknown",
                    )
        
        # Fallback to encrypted file storage
        creds_file = Path.home() / ".emergentsh_credentials.enc"
        if creds_file.exists():
            try:
                data = json.loads(creds_file.read_text())
                for name, enc_value in data.items():
                    if name not in self._credentials:
                        decrypted = self._encryption.decrypt(enc_value)
                        if decrypted:
                            self._credentials[name] = Credential(
                                name=name,
                                value=decrypted,
                                type="api_key",
                                provider=name.split("_")[0] if "_" in name else "unknown",
                            )
            except Exception:
                pass
    
    def _save_credentials(self) -> None:
        """Save credentials to encrypted file (fallback)."""
        creds_file = Path.home() / ".emergentsh_credentials.enc"
        data = {}
        for name, cred in self._credentials.items():
            data[name] = self._encryption.encrypt(cred.value)
        creds_file.parent.mkdir(parents=True, exist_ok=True)
        creds_file.write_text(json.dumps(data))
    
    def store_credential(
        self,
        name: str,
        value: str,
        provider: str,
        cred_type: str = "api_key",
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Store a credential securely."""
        credential = Credential(
            name=name,
            value=value,
            type=cred_type,
            provider=provider,
            metadata=metadata or {},
            expires_at=expires_at,
        )
        
        self._credentials[name] = credential
        
        # Try Windows Credential Manager first
        if self._use_windows_cred:
            comment = f"EmergentSH {provider} {cred_type} - {metadata.get('description', '')}"
            if WindowsCredentialManager.store(name, value, comment):
                return True
        
        # Fallback to encrypted file
        self._save_credentials()
        return True
    
    def get_credential(self, name: str) -> Optional[str]:
        """Retrieve a credential value by name."""
        # Check in-memory cache first
        if name in self._credentials:
            cred = self._credentials[name]
            if not cred.is_expired():
                return cred.value
            else:
                del self._credentials[name]
        
        # Try Windows Credential Manager
        if self._use_windows_cred:
            value = WindowsCredentialManager.retrieve(name)
            if value:
                self._credentials[name] = Credential(
                    name=name,
                    value=value,
                    type="api_key",
                    provider=name.split("_")[0] if "_" in name else "unknown",
                )
                return value
        
        return None
    
    def get_credential_obj(self, name: str) -> Optional[Credential]:
        """Get the full Credential object."""
        if name in self._credentials:
            cred = self._credentials[name]
            if not cred.is_expired():
                return cred
            else:
                del self._credentials[name]
        return None
    
    def list_credentials(self) -> List[Credential]:
        """List all stored credentials (without values)."""
        creds = []
        for name, cred in self._credentials.items():
            if not cred.is_expired():
                cred_copy = Credential(
                    name=cred.name,
                    value="***REDACTED***",
                    type=cred.type,
                    provider=cred.provider,
                    metadata=cred.metadata,
                    created_at=cred.created_at,
                    updated_at=cred.updated_at,
                    expires_at=cred.expires_at,
                )
                creds.append(cred_copy)
        return creds
    
    def delete_credential(self, name: str) -> bool:
        """Delete a credential."""
        if name in self._credentials:
            del self._credentials[name]
        
        if self._use_windows_cred:
            WindowsCredentialManager.delete(name)
        
        self._save_credentials()
        return True
    
    # ----------------------------------------------------------------------
    # OAuth 2.0 Flows
    # ----------------------------------------------------------------------
    
    def get_github_auth_url(
        self,
        client_id: str,
        redirect_uri: str,
        scopes: List[str] = None,
        state: Optional[str] = None,
    ) -> str:
        """Generate GitHub OAuth authorization URL."""
        if scopes is None:
            scopes = ["repo", "user:email", "read:org"]
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "response_type": "code",
        }
        if state:
            params["state"] = state
        else:
            state = secrets.token_urlsafe(32)
            params["state"] = state
        
        return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    
    def exchange_github_code(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """Exchange GitHub OAuth code for access token."""
        import requests
        
        response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def get_google_auth_url(
        self,
        client_id: str,
        redirect_uri: str,
        scopes: List[str] = None,
        state: Optional[str] = None,
    ) -> str:
        """Generate Google OAuth authorization URL."""
        if scopes is None:
            scopes = ["openid", "email", "profile"]
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        else:
            state = secrets.token_urlsafe(32)
            params["state"] = state
        
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    
    def exchange_google_code(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """Exchange Google OAuth code for access token."""
        import requests
        
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    # ----------------------------------------------------------------------
    # Session Management
    # ----------------------------------------------------------------------
    
    def create_session(
        self,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        scopes: List[str] = None,
    ) -> UserSession:
        """Create a new user session."""
        expires_at = None
        if expires_in:
            expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        session = UserSession(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=scopes or [],
        )
        
        session_id = f"session_{user_id}_{int(time.time())}"
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_valid():
            return session
        elif session:
            del self._sessions[session_id]
        return None
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    # ----------------------------------------------------------------------
    # JWT Token Management
    # ----------------------------------------------------------------------
    
    def create_jwt_token(
        self,
        payload: Dict[str, Any],
        expires_in: int = 3600,
    ) -> str:
        """Create a JWT token."""
        import jwt
        
        secret = self._get_jwt_secret()
        payload = {
            **payload,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in,
        }
        return jwt.encode(payload, secret, algorithm="HS256")
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token."""
        import jwt
        
        secret = self._get_jwt_secret()
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def _get_jwt_secret(self) -> str:
        """Get or create JWT secret."""
        secret = self.get_credential("jwt_secret")
        if not secret:
            secret = secrets.token_urlsafe(64)
            self.store_credential("jwt_secret", secret, "internal", "jwt_secret")
        return secret
    
    # ----------------------------------------------------------------------
    # Provider-Specific API Key Management
    # ----------------------------------------------------------------------
    
    def set_provider_key(self, provider: str, key: str) -> None:
        """Set API key for a provider."""
        self.store_credential(
            name=f"{provider}_api_key",
            value=key,
            provider=provider,
            cred_type="api_key",
        )
    
    def get_provider_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        return self.get_credential(f"{provider}_api_key")
    
    def get_all_provider_keys(self) -> Dict[str, Optional[str]]:
        """Get all provider API keys."""
        providers = [
            "nvidia", "openrouter", "anthropic", "openai",
            "github", "google", "fly", "railway", "render",
            "netlify", "vercel", "aws", "azure", "gcp",
        ]
        return {p: self.get_provider_key(p) for p in providers}


# ════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════

def create_auth_manager(workspace: Optional[WorkspaceManager] = None) -> AuthManager:
    return AuthManager(workspace)


def get_auth_manager() -> AuthManager:
    return create_auth_manager()


# Import urllib at module level
import urllib.parse