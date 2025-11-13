
# ============================================================================
# dmonSQL/security/authorization.py
# ============================================================================
"""Module d'autorisation"""

from typing import Set, Dict
from enum import Enum


class Permission(Enum):
    """Permissions disponibles"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    ADMIN = "ADMIN"


class Role:
    """Rôle utilisateur avec permissions"""
    
    def __init__(self, name: str, permissions: Set[Permission]):
        self.name = name
        self.permissions = permissions
    
    def has_permission(self, permission: Permission) -> bool:
        """Vérifie si le rôle a une permission"""
        return permission in self.permissions or Permission.ADMIN in self.permissions


class AuthorizationManager:
    """Gère les autorisations"""
    
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.user_roles: Dict[str, str] = {}  # {username: role_name}
        self._create_default_roles()
    
    def _create_default_roles(self):
        """Crée les rôles par défaut"""
        self.roles['admin'] = Role('admin', {Permission.ADMIN})
        self.roles['user'] = Role('user', {Permission.SELECT, Permission.INSERT, 
                                           Permission.UPDATE, Permission.DELETE})
        self.roles['readonly'] = Role('readonly', {Permission.SELECT})
    
    def assign_role(self, username: str, role_name: str):
        """Assigne un rôle à un utilisateur"""
        if role_name not in self.roles:
            raise ValueError(f"Role {role_name} does not exist")
        self.user_roles[username] = role_name
    
    def check_permission(self, username: str, permission: Permission) -> bool:
        """Vérifie si un utilisateur a une permission"""
        if username not in self.user_roles:
            return False
        
        role_name = self.user_roles[username]
        role = self.roles[role_name]
        return role.has_permission(permission)