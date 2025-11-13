
# ============================================================================
# dmonSQL/security/audit.py
# ============================================================================
"""Module d'audit"""

from datetime import datetime
from typing import List, Dict
from dmonSQL.utils.logger import get_logger


class AuditEvent:
    """Événement d'audit"""
    
    def __init__(self, username: str, action: str, target: str, 
                 success: bool, details: str = ""):
        self.timestamp = datetime.now()
        self.username = username
        self.action = action
        self.target = target
        self.success = success
        self.details = details
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'username': self.username,
            'action': self.action,
            'target': self.target,
            'success': self.success,
            'details': self.details
        }


class AuditManager:
    """Gestionnaire d'audit"""
    
    def __init__(self):
        self.events: List[AuditEvent] = []
        self.logger = get_logger("dmonSQL.audit")
    
    def log_event(self, username: str, action: str, target: str, 
                  success: bool, details: str = ""):
        """Enregistre un événement d'audit"""
        event = AuditEvent(username, action, target, success, details)
        self.events.append(event)
        
        # Logger aussi dans les logs
        log_msg = f"[{username}] {action} on {target}: {'SUCCESS' if success else 'FAILED'}"
        if details:
            log_msg += f" - {details}"
        
        if success:
            self.logger.info(log_msg)
        else:
            self.logger.warning(log_msg)
    
    def get_events(self, username: str = None, action: str = None, 
                   limit: int = 100) -> List[Dict]:
        """Récupère les événements d'audit"""
        events = self.events
        
        if username:
            events = [e for e in events if e.username == username]
        
        if action:
            events = [e for e in events if e.action == action]
        
        return [e.to_dict() for e in events[-limit:]]