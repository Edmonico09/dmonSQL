"""
dmonSQL/security/user_manager.py
Gestion des utilisateurs, authentification et permissions
"""

import hashlib
import secrets
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path


class Permission(Enum):
    """Permissions disponibles dans le système"""
    # Permissions base de données
    CREATE_DATABASE = "CREATE_DATABASE"
    DROP_DATABASE = "DROP_DATABASE"
    
    # Permissions tables
    CREATE_TABLE = "CREATE_TABLE"
    DROP_TABLE = "DROP_TABLE"
    ALTER_TABLE = "ALTER_TABLE"
    
    # Permissions données
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    
    # Permissions avancées
    CREATE_INDEX = "CREATE_INDEX"
    CREATE_PROCEDURE = "CREATE_PROCEDURE"
    CREATE_TRIGGER = "CREATE_TRIGGER"
    
    # Permissions administration
    CREATE_USER = "CREATE_USER"
    DROP_USER = "DROP_USER"
    GRANT_PERMISSION = "GRANT_PERMISSION"
    REVOKE_PERMISSION = "REVOKE_PERMISSION"
    
    # Permission super admin
    SUPERUSER = "SUPERUSER"


class Role:
    """Rôle utilisateur avec ensemble de permissions"""
    
    def __init__(self, name: str, permissions: Set[Permission] = None):
        self.name = name
        self.permissions: Set[Permission] = permissions or set()
        self.created_at = datetime.now()
    
    def add_permission(self, permission: Permission):
        """Ajoute une permission au rôle"""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: Permission):
        """Retire une permission du rôle"""
        self.permissions.discard(permission)
    
    def has_permission(self, permission: Permission) -> bool:
        """Vérifie si le rôle a une permission"""
        return permission in self.permissions or Permission.SUPERUSER in self.permissions
    
    def __repr__(self):
        return f"Role({self.name}, {len(self.permissions)} permissions)"


class User:
    """Utilisateur du système"""
    
    def __init__(self, username: str, password_hash: str, salt: str):
        self.username = username
        self.password_hash = password_hash
        self.salt = salt
        self.roles: Set[str] = set()
        self.direct_permissions: Set[Permission] = set()
        self.created_at = datetime.now()
        self.last_login: Optional[datetime] = None
        self.active = True
        self.failed_login_attempts = 0
        self.locked_until: Optional[datetime] = None
        
        # Restrictions par database/table
        self.database_access: Dict[str, Set[Permission]] = {}
        self.table_access: Dict[str, Dict[str, Set[Permission]]] = {}
    
    def verify_password(self, password: str) -> bool:
        """Vérifie le mot de passe"""
        return self._hash_password(password, self.salt) == self.password_hash
    
    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Hash un mot de passe avec PBKDF2"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
    
    def add_role(self, role_name: str):
        """Ajoute un rôle à l'utilisateur"""
        self.roles.add(role_name)
    
    def remove_role(self, role_name: str):
        """Retire un rôle de l'utilisateur"""
        self.roles.discard(role_name)
    
    def add_permission(self, permission: Permission):
        """Ajoute une permission directe"""
        self.direct_permissions.add(permission)
    
    def remove_permission(self, permission: Permission):
        """Retire une permission directe"""
        self.direct_permissions.discard(permission)
    
    def grant_database_access(self, database: str, permissions: Set[Permission]):
        """Accorde des permissions sur une base de données"""
        if database not in self.database_access:
            self.database_access[database] = set()
        self.database_access[database].update(permissions)
    
    def grant_table_access(self, database: str, table: str, permissions: Set[Permission]):
        """Accorde des permissions sur une table"""
        if database not in self.table_access:
            self.table_access[database] = {}
        if table not in self.table_access[database]:
            self.table_access[database][table] = set()
        self.table_access[database][table].update(permissions)
    
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if not self.locked_until:
            return False
        if datetime.now() < self.locked_until:
            return True
        # Déverrouiller automatiquement après expiration
        self.locked_until = None
        self.failed_login_attempts = 0
        return False
    
    def lock_account(self, duration_minutes: int = 30):
        """Verrouille le compte"""
        self.locked_until = datetime.now() + timedelta(minutes=duration_minutes)
    
    def record_failed_login(self, max_attempts: int = 3):
        """Enregistre une tentative de connexion échouée"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.lock_account()
    
    def record_successful_login(self):
        """Enregistre une connexion réussie"""
        self.last_login = datetime.now()
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def __repr__(self):
        return f"User({self.username}, roles={self.roles}, active={self.active})"


class Session:
    """Session utilisateur"""
    
    def __init__(self, user: User, token: str):
        self.user = user
        self.token = token
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.expires_at = datetime.now() + timedelta(hours=24)
    
    def is_valid(self) -> bool:
        """Vérifie si la session est valide"""
        return datetime.now() < self.expires_at and self.user.active
    
    def refresh(self):
        """Rafraîchit la session"""
        self.last_activity = datetime.now()
        self.expires_at = datetime.now() + timedelta(hours=24)
    
    def __repr__(self):
        return f"Session({self.user.username}, expires={self.expires_at})"


class UserManager:
    """Gestionnaire des utilisateurs et permissions"""
    
    # Rôles prédéfinis
    PREDEFINED_ROLES = {
        'admin': Role('admin', {
            Permission.SUPERUSER
        }),
        'developer': Role('developer', {
            Permission.CREATE_DATABASE,
            Permission.DROP_DATABASE,
            Permission.CREATE_TABLE,
            Permission.DROP_TABLE,
            Permission.ALTER_TABLE,
            Permission.SELECT,
            Permission.INSERT,
            Permission.UPDATE,
            Permission.DELETE,
            Permission.CREATE_INDEX,
            Permission.CREATE_PROCEDURE,
            Permission.CREATE_TRIGGER
        }),
        'analyst': Role('analyst', {
            Permission.SELECT,
            Permission.CREATE_TABLE
        }),
        'readonly': Role('readonly', {
            Permission.SELECT
        })
    }
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        self.data_dir = Path(data_dir)
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = dict(self.PREDEFINED_ROLES)
        self.sessions: Dict[str, Session] = {}
        self.current_session: Optional[Session] = None
        
        # Fichier de stockage
        self.users_file = self.data_dir / "users.dat"
        self.roles_file = self.data_dir / "roles.dat"
        
        # Charger les données
        self.load()
        
        # Créer l'utilisateur admin par défaut si nécessaire
        if not self.users:
            self._create_default_admin()
    
    def _create_default_admin(self):
        """Crée l'utilisateur admin par défaut"""
        salt = secrets.token_hex(16)
        password_hash = User._hash_password("admin", salt)
        admin = User("admin", password_hash, salt)
        admin.add_role('admin')
        self.users['admin'] = admin
        self.save()
        print("⚠️  Default admin user created (username: admin, password: admin)")
        print("    Please change the password immediately!")
    
    # ==================== GESTION DES UTILISATEURS ====================
    
    def create_user(self, username: str, password: str, roles: List[str] = None) -> User:
        """Crée un nouvel utilisateur"""
        self._check_permission(Permission.CREATE_USER)
        
        if username in self.users:
            raise ValueError(f"User '{username}' already exists")
        
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Créer l'utilisateur
        salt = secrets.token_hex(16)
        password_hash = User._hash_password(password, salt)
        user = User(username, password_hash, salt)
        
        # Ajouter les rôles
        if roles:
            for role in roles:
                if role not in self.roles:
                    raise ValueError(f"Role '{role}' does not exist")
                user.add_role(role)
        
        self.users[username] = user
        self.save()
        
        print(f"✓ User '{username}' created successfully")
        return user
    
    def drop_user(self, username: str):
        """Supprime un utilisateur"""
        self._check_permission(Permission.DROP_USER)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        if username == "admin":
            raise ValueError("Cannot drop admin user")
        
        del self.users[username]
        
        # Révoquer toutes les sessions
        self.sessions = {
            token: session for token, session in self.sessions.items()
            if session.user.username != username
        }
        
        self.save()
        print(f"✓ User '{username}' dropped")
    
    def change_password(self, username: str, old_password: str, new_password: str):
        """Change le mot de passe d'un utilisateur"""
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        
        # Vérifier l'ancien mot de passe
        if not user.verify_password(old_password):
            raise ValueError("Invalid old password")
        
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Changer le mot de passe
        salt = secrets.token_hex(16)
        user.password_hash = User._hash_password(new_password, salt)
        user.salt = salt
        
        self.save()
        print(f"✓ Password changed for user '{username}'")
    
    def reset_password(self, username: str, new_password: str):
        """Réinitialise le mot de passe (admin seulement)"""
        self._check_permission(Permission.SUPERUSER)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        salt = secrets.token_hex(16)
        user.password_hash = User._hash_password(new_password, salt)
        user.salt = salt
        
        self.save()
        print(f"✓ Password reset for user '{username}'")
    
    # ==================== AUTHENTIFICATION ====================
    
    def login(self, username: str, password: str) -> str:
        """Authentifie un utilisateur et retourne un token"""
        if username not in self.users:
            raise ValueError("Invalid username or password")
        
        user = self.users[username]
        
        # Vérifier si le compte est verrouillé
        if user.is_locked():
            raise ValueError(f"Account locked until {user.locked_until}")
        
        # Vérifier si le compte est actif
        if not user.active:
            raise ValueError("Account is disabled")
        
        # Vérifier le mot de passe
        if not user.verify_password(password):
            user.record_failed_login()
            self.save()
            raise ValueError("Invalid username or password")
        
        # Connexion réussie
        user.record_successful_login()
        
        # Créer une session
        token = secrets.token_urlsafe(32)
        session = Session(user, token)
        self.sessions[token] = session
        self.current_session = session
        
        self.save()
        print(f"✓ User '{username}' logged in successfully")
        return token
    
    def logout(self, token: str = None):
        """Déconnecte un utilisateur"""
        if token is None:
            if self.current_session:
                token = self.current_session.token
            else:
                return
        
        if token in self.sessions:
            username = self.sessions[token].user.username
            del self.sessions[token]
            if self.current_session and self.current_session.token == token:
                self.current_session = None
            print(f"✓ User '{username}' logged out")
    
    def verify_session(self, token: str) -> bool:
        """Vérifie si une session est valide"""
        if token not in self.sessions:
            return False
        
        session = self.sessions[token]
        if not session.is_valid():
            del self.sessions[token]
            return False
        
        session.refresh()
        return True
    
    def get_current_user(self) -> Optional[User]:
        """Retourne l'utilisateur actuellement connecté"""
        if not self.current_session:
            return None
        return self.current_session.user
    
    def require_authentication(self):
        """Vérifie qu'un utilisateur est connecté"""
        if not self.current_session:
            raise PermissionError("Authentication required")
        
        if not self.current_session.is_valid():
            self.current_session = None
            raise PermissionError("Session expired")
    
    # ==================== GESTION DES RÔLES ====================
    
    def create_role(self, name: str, permissions: Set[Permission] = None) -> Role:
        """Crée un nouveau rôle"""
        self._check_permission(Permission.SUPERUSER)
        
        if name in self.roles:
            raise ValueError(f"Role '{name}' already exists")
        
        role = Role(name, permissions)
        self.roles[name] = role
        self.save()
        
        print(f"✓ Role '{name}' created")
        return role
    
    def drop_role(self, name: str):
        """Supprime un rôle"""
        self._check_permission(Permission.SUPERUSER)
        
        if name in self.PREDEFINED_ROLES:
            raise ValueError(f"Cannot drop predefined role '{name}'")
        
        if name not in self.roles:
            raise ValueError(f"Role '{name}' does not exist")
        
        # Retirer le rôle de tous les utilisateurs
        for user in self.users.values():
            user.remove_role(name)
        
        del self.roles[name]
        self.save()
        print(f"✓ Role '{name}' dropped")
    
    # ==================== GESTION DES PERMISSIONS ====================
    
    def grant(self, username: str, permission: Permission, 
              database: str = None, table: str = None):
        """Accorde une permission à un utilisateur"""
        self._check_permission(Permission.GRANT_PERMISSION)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        
        if table:
            if not database:
                raise ValueError("Database must be specified for table-level permissions")
            user.grant_table_access(database, table, {permission})
            print(f"✓ Granted {permission.value} on {database}.{table} to '{username}'")
        elif database:
            user.grant_database_access(database, {permission})
            print(f"✓ Granted {permission.value} on database '{database}' to '{username}'")
        else:
            user.add_permission(permission)
            print(f"✓ Granted {permission.value} to '{username}'")
        
        self.save()
    
    def revoke(self, username: str, permission: Permission,
               database: str = None, table: str = None):
        """Révoque une permission d'un utilisateur"""
        self._check_permission(Permission.REVOKE_PERMISSION)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        
        if table and database:
            if database in user.table_access and table in user.table_access[database]:
                user.table_access[database][table].discard(permission)
            print(f"✓ Revoked {permission.value} on {database}.{table} from '{username}'")
        elif database:
            if database in user.database_access:
                user.database_access[database].discard(permission)
            print(f"✓ Revoked {permission.value} on database '{database}' from '{username}'")
        else:
            user.remove_permission(permission)
            print(f"✓ Revoked {permission.value} from '{username}'")
        
        self.save()
    
    def grant_role(self, username: str, role_name: str):
        """Assigne un rôle à un utilisateur"""
        self._check_permission(Permission.GRANT_PERMISSION)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        
        user = self.users[username]
        user.add_role(role_name)
        
        self.save()
        print(f"✓ Role '{role_name}' granted to '{username}'")
    
    def revoke_role(self, username: str, role_name: str):
        """Retire un rôle d'un utilisateur"""
        self._check_permission(Permission.REVOKE_PERMISSION)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        user.remove_role(role_name)
        
        self.save()
        print(f"✓ Role '{role_name}' revoked from '{username}'")
    
    # ==================== VÉRIFICATION DES PERMISSIONS ====================
    
    def has_permission(self, permission: Permission, 
                      database: str = None, table: str = None) -> bool:
        """Vérifie si l'utilisateur actuel a une permission"""
        user = self.get_current_user()
        if not user:
            return False
        
        return self._user_has_permission(user, permission, database, table)
    
    def _user_has_permission(self, user: User, permission: Permission,
                            database: str = None, table: str = None) -> bool:
        """Vérifie si un utilisateur a une permission"""
        # Vérifier les permissions directes
        if permission in user.direct_permissions or Permission.SUPERUSER in user.direct_permissions:
            return True
        
        # Vérifier via les rôles
        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                if role.has_permission(permission):
                    return True
        
        # Vérifier les permissions spécifiques à une table
        if table and database:
            if database in user.table_access and table in user.table_access[database]:
                if permission in user.table_access[database][table]:
                    return True
        
        # Vérifier les permissions spécifiques à une database
        if database:
            if database in user.database_access:
                if permission in user.database_access[database]:
                    return True
        
        return False
    
    def _check_permission(self, permission: Permission, 
                         database: str = None, table: str = None):
        """Vérifie une permission et lève une exception si refusée"""
        self.require_authentication()
        
        if not self.has_permission(permission, database, table):
            raise PermissionError(
                f"Permission denied: {permission.value}" +
                (f" on {database}.{table}" if table else f" on {database}" if database else "")
            )
    
    # ==================== INFORMATION ====================
    
    def list_users(self) -> List[str]:
        """Liste tous les utilisateurs"""
        self._check_permission(Permission.SUPERUSER)
        return list(self.users.keys())
    
    def show_user(self, username: str):
        """Affiche les informations d'un utilisateur"""
        self._check_permission(Permission.SUPERUSER)
        
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")
        
        user = self.users[username]
        
        print(f"\n👤 User: {username}")
        print("=" * 60)
        print(f"Active: {user.active}")
        print(f"Roles: {', '.join(user.roles) if user.roles else 'None'}")
        print(f"Created: {user.created_at}")
        print(f"Last login: {user.last_login or 'Never'}")
        
        if user.direct_permissions:
            print(f"\nDirect Permissions:")
            for perm in user.direct_permissions:
                print(f"  • {perm.value}")
        
        if user.database_access:
            print(f"\nDatabase Permissions:")
            for db, perms in user.database_access.items():
                print(f"  • {db}: {', '.join(p.value for p in perms)}")
        
        if user.table_access:
            print(f"\nTable Permissions:")
            for db, tables in user.table_access.items():
                for table, perms in tables.items():
                    print(f"  • {db}.{table}: {', '.join(p.value for p in perms)}")
        
        print("=" * 60)
    
    def list_roles(self) -> List[str]:
        """Liste tous les rôles"""
        return list(self.roles.keys())
    
    def show_role(self, role_name: str):
        """Affiche les informations d'un rôle"""
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        
        role = self.roles[role_name]
        
        print(f"\n👥 Role: {role_name}")
        print("=" * 60)
        print(f"Created: {role.created_at}")
        print(f"Permissions ({len(role.permissions)}):")
        for perm in sorted(role.permissions, key=lambda p: p.value):
            print(f"  • {perm.value}")
        print("=" * 60)
    
    # ==================== PERSISTENCE ====================
    
    def save(self):
        """Sauvegarde les utilisateurs et rôles"""
        self.data_dir.mkdir(exist_ok=True)
        
        with open(self.users_file, 'wb') as f:
            pickle.dump(self.users, f)
        
        with open(self.roles_file, 'wb') as f:
            pickle.dump(self.roles, f)
    
    def load(self):
        """Charge les utilisateurs et rôles"""
        if self.users_file.exists():
            with open(self.users_file, 'rb') as f:
                self.users = pickle.load(f)
        
        if self.roles_file.exists():
            with open(self.roles_file, 'rb') as f:
                loaded_roles = pickle.load(f)
                # Fusionner avec les rôles prédéfinis
                self.roles.update(loaded_roles)
    
    def __repr__(self):
        return f"UserManager({len(self.users)} users, {len(self.roles)} roles)"


# ==================== EXEMPLES D'UTILISATION ====================

if __name__ == "__main__":
    print("=" * 60)
    print("USER MANAGER DEMO")
    print("=" * 60)
    
    # Initialiser le gestionnaire
    manager = UserManager()
    
    # Connexion admin
    print("\n1. Login as admin...")
    token = manager.login("admin", "admin")
    print(f"Token: {token[:20]}...")
    
    # Créer des utilisateurs
    print("\n2. Creating users...")
    manager.create_user("alice", "password123", roles=['developer'])
    manager.create_user("bob", "password456", roles=['analyst'])
    manager.create_user("charlie", "password789", roles=['readonly'])
    
    # Lister les utilisateurs
    print("\n3. Listing users...")
    print(f"Users: {manager.list_users()}")
    
    # Afficher un utilisateur
    print("\n4. Show user details...")
    manager.show_user("alice")
    
    # Accorder des permissions spécifiques
    print("\n5. Granting specific permissions...")
    manager.grant("bob", Permission.INSERT, database="sales")
    manager.grant("charlie", Permission.SELECT, database="sales", table="customers")
    
    # Vérifier les permissions
    print("\n6. Checking permissions...")
    print(f"Bob has INSERT on sales: {manager._user_has_permission(manager.users['bob'], Permission.INSERT, 'sales')}")
    print(f"Charlie has SELECT on sales.customers: {manager._user_has_permission(manager.users['charlie'], Permission.SELECT, 'sales', 'customers')}")
    
    # Créer un rôle personnalisé
    print("\n7. Creating custom role...")
    manager.create_role("data_engineer", {
        Permission.SELECT,
        Permission.INSERT,
        Permission.CREATE_TABLE,
        Permission.CREATE_INDEX
    })
    
    manager.grant_role("bob", "data_engineer")
    
    # Lister les rôles
    print("\n8. Listing roles...")
    print(f"Roles: {manager.list_roles()}")
    
    # Déconnexion
    print("\n9. Logout...")
    manager.logout()
    
    print("\n" + "=" * 60)
    print("✓ All demos completed!")
    print("=" * 60)