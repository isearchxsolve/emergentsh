"""
ConfigManager — persistent JSON configuration and session storage.

Profiles define the model, API key, and RPM limits.  Sessions store the
conversation context per profile+directory pair so the agent can resume.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_FILE = Path.home() / ".emergentsh_config.json"
SESSIONS_FILE = Path.home() / ".emergentsh_sessions.json"

DEFAULT_PROFILE_TEMPLATE = {
    "name": "Default",
    "key": "",
    "default_model": "glm",
    "rpm": 40.0,
    "models": {
        "glm": {"name": "GLM-5.2", "id": "z-ai/glm-5.2"},
        "nemotron": {
            "name": "Nemotron-Ultra",
            "id": "nvidia/nemotron-3-ultra-550b-a55b",
        },
    },
}


class ConfigManager:
    """Load / save application config and sessions."""

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    @staticmethod
    def load_config() -> Dict[str, Any]:
        c: Dict[str, Any] = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    c = json.load(f)
            except Exception:
                pass
        if "profiles" not in c:
            c["profiles"] = {}
        return c

    @staticmethod
    def save_config(c: Dict[str, Any]) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        return ConfigManager.load_config().get("profiles", {})

    @staticmethod
    def get_profile(pid: str) -> Optional[Dict[str, Any]]:
        return ConfigManager.get_profiles().get(pid)

    @staticmethod
    def create_profile(
        name: str,
        key: str,
        model_key: str = "glm",
        rpm: float = 40.0,
        models: Optional[Dict] = None,
    ) -> str:
        c = ConfigManager.load_config()
        new_id = str(
            max([int(k) for k in c["profiles"].keys() if k.isdigit()] + [0]) + 1
        )
        c["profiles"][new_id] = {
            "name": name,
            "key": key,
            "default_model": model_key,
            "rpm": rpm,
            "models": models or DEFAULT_PROFILE_TEMPLATE["models"],
        }
        ConfigManager.save_config(c)
        return new_id

    @staticmethod
    def update_profile(pid: str, updates: Dict[str, Any]) -> None:
        c = ConfigManager.load_config()
        if pid in c["profiles"]:
            c["profiles"][pid].update(updates)
            ConfigManager.save_config(c)

    @staticmethod
    def delete_profile(pid: str) -> None:
        c = ConfigManager.load_config()
        c["profiles"].pop(pid, None)
        ConfigManager.save_config(c)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    @staticmethod
    def load_session(profile_name: str, pdir: str) -> Optional[Dict[str, Any]]:
        k = f"{profile_name}::{pdir}"
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get(k)
            except Exception:
                pass
        return None

    @staticmethod
    def save_session(
        profile_name: str,
        pdir: str,
        messages: List[Dict],
        goal: Optional[str],
        compaction_summary: Optional[str],
    ) -> None:
        k = f"{profile_name}::{pdir}"
        s: Dict[str, Any] = {}
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                    s = json.load(f)
            except Exception:
                pass
        s[k] = {
            "messages": messages,
            "goal": goal,
            "compaction_summary": compaction_summary,
        }
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f)

    @staticmethod
    def list_sessions() -> Dict[str, Any]:
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @staticmethod
    def delete_session(profile_name: str, pdir: str) -> None:
        k = f"{profile_name}::{pdir}"
        s = ConfigManager.list_sessions()
        s.pop(k, None)
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f)
