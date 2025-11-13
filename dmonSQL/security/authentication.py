# ============================================================================
# dmonSQL/security/authentication.py
# ============================================================================
"""Module d'authentification"""

from typing import Dict, Optional
from dmonSQL.utils.helpers import hash_password, verify_password, generate_id
from datetime import datetime, timedelta


class User:
    """Représente un utilisateur"""
    
    def __init__(self, username: str, password_hash: str, salt: str, role: str = "user"):
        self.username = username
        self.password_hash = password_hash
        self.salt = salt
        self.role = role
        self.created_at = datetime.now()
        self.last_login = None


class AuthenticationManager:
    """Gère l'authentification des utilisateurs"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, tuple] = {}  # {session_id: (username, expiry)}
    
    def create_user(self, username: str, password: str, role: str = "user"):
        """Crée un nouvel utilisateur"""
        if username in self.users:
            raise ValueError(f"User {username} already exists")
        
        password_hash, salt = hash_password(password)
        user = User(username, password_hash, salt, role)
        self.users[username] = user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authentifie un utilisateur et retourne un session ID"""
        if username not in self.users:
            return None
        
        user = self.users[username]
        if not verify_password(password, user.password_hash, user.salt):
            return None
        
        # Créer une session
        session_id = generate_id()
        expiry = datetime.now() + timedelta(hours=24)
        self.sessions[session_id] = (username, expiry)
        
        user.last_login = datetime.now()
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """Valide une session et retourne le username"""
        if session_id not in self.sessions:
            return None
        
        username, expiry = self.sessions[session_id]
        if datetime.now() > expiry:
            del self.sessions[session_id]
            return None
        
        return username

