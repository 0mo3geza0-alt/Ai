"""Role-Based Access Control: role -> permission mapping."""

ROLE_PERMISSIONS = {
    "owner": {"*"},
    "admin": {"member:manage", "team:manage", "project:*", "file:*", "apikey:manage"},
    "member": {"project:create", "project:read", "project:update", "file:read", "file:write"},
    "viewer": {"project:read", "file:read"},
}

ROLES = list(ROLE_PERMISSIONS.keys())


def has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    if "*" in perms or permission in perms:
        return True
    # wildcard e.g. "project:*" grants "project:create"
    resource = permission.split(":")[0]
    return f"{resource}:*" in perms
