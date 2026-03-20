"""
Utility to add or update a user in config/users.yaml.

Usage:
    python3 scripts/create_user.py
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

try:
    import bcrypt
    import yaml
except ImportError:
    print("Run: pip install bcrypt pyyaml")
    sys.exit(1)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "users.yaml"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print("=== ATP Log Analyzer — Create / Update User ===\n")
    username = input("Username: ").strip()
    name     = input("Display name: ").strip()
    email    = input("Email: ").strip()
    role     = input("Role [admin/user] (default: user): ").strip() or "user"
    password = getpass.getpass("Password: ")
    confirm  = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    config.setdefault("credentials", {}).setdefault("usernames", {})[username] = {
        "name":     name,
        "email":    email,
        "password": hash_password(password),
        "role":     role,
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"\n✅  User '{username}' saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
