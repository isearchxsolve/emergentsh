"""
Migration script to move from JSON-based ConfigManager to SQLite WorkspaceManager.

Run this once after upgrading to the new schema:
    python -m src.core.migrate_config
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import ConfigManager
from src.core.workspace import WorkspaceManager, get_workspace


def main():
    print("=" * 60)
    print("EmergentSH Configuration Migration")
    print("=" * 60)

    # Paths to old JSON files
    config_path = Path.home() / ".emergentsh_config.json"
    sessions_path = Path.home() / ".emergentsh_sessions.json"

    print(f"Config file: {config_path}")
    print(f"Sessions file: {sessions_path}")
    print()

    # Check if files exist
    if not config_path.exists():
        print("No config file found. Nothing to migrate.")
        return 0

    if not sessions_path.exists():
        print("No sessions file found. Will only migrate profiles.")
    else:
        print("Both files found. Will migrate profiles and sessions.")

    print()

    # Initialize workspace manager
    workspace = get_workspace()

    # Run migration
    stats = workspace.migrate_from_json(str(config_path), str(sessions_path))

    print()
    print("Migration Results:")
    print(f"  Profiles migrated: {stats.get('profiles', 0)}")
    print(f"  Sessions migrated: {stats.get('sessions', 0)}")
    print(f"  Projects created: {stats.get('projects', 0)}")
    print()

    if stats.get('profiles', 0) > 0 or stats.get('sessions', 0) > 0:
        print("Migration completed successfully!")
        print()
        print("You can now delete the old JSON files if desired:")
        print(f"  {config_path}")
        print(f"  {sessions_path}")
        print()
        print("The new SQLite database is at:")
        print(f"  {Path.home() / '.emergentsh_workspace.db'}")
        return 0
    else:
        print("No data was migrated.")
        return 1


if __name__ == "__main__":
    sys.exit(main())