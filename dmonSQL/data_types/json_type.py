import json
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict
import re


# ============================================================================
# JSON TYPE
# ============================================================================

class JSONType:
    """Type de données JSON natif"""
    
    def __init__(self, data):
        if isinstance(data, str):
            self.data = json.loads(data)
        elif isinstance(data, (dict, list)):
            self.data = data
        elif isinstance(data, JSONType):
            self.data = data.data
        else:
            raise ValueError(f"Invalid JSON data: {type(data)}")
    
    def __repr__(self):
        return f"JSON({json.dumps(self.data, indent=2)})"
    
    def __str__(self):
        return json.dumps(self.data)
    
    def __eq__(self, other):
        if isinstance(other, JSONType):
            return self.data == other.data
        return False
    
    def get(self, path: str, default=None):
        """Récupère une valeur par chemin JSON (ex: 'user.address.city')"""
        keys = path.split('.')
        current = self.data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
            
            if current is None:
                return default
        
        return current
    
    def set(self, path: str, value):
        """Définit une valeur par chemin JSON"""
        keys = path.split('.')
        current = self.data
        
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def contains(self, key: str) -> bool:
        """Vérifie si une clé existe"""
        return self.get(key) is not None
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire Python"""
        return self.data
    
    def to_json(self) -> str:
        """Convertit en chaîne JSON"""
        return json.dumps(self.data)
    
    @staticmethod
    def from_json(json_str: str):
        """Crée un JSONType depuis une chaîne JSON"""
        return JSONType(json_str)
    
    @staticmethod
    def validate(data) -> bool:
        """Valide si les données sont JSON-sérialisables"""
        try:
            json.dumps(data)
            return True
        except:
            return False


class JSONQuery:
    """Requêtes sur des champs JSON"""
    
    @staticmethod
    def extract(json_obj: JSONType, path: str):
        """Extrait une valeur (équivalent JSON_EXTRACT)"""
        return json_obj.get(path)
    
    @staticmethod
    def contains_key(json_obj: JSONType, key: str) -> bool:
        """Vérifie si une clé existe"""
        return json_obj.contains(key)
    
    @staticmethod
    def array_length(json_obj: JSONType) -> int:
        """Retourne la longueur d'un tableau JSON"""
        if isinstance(json_obj.data, list):
            return len(json_obj.data)
        return 0
    
    @staticmethod
    def keys(json_obj: JSONType) -> List[str]:
        """Retourne les clés d'un objet JSON"""
        if isinstance(json_obj.data, dict):
            return list(json_obj.data.keys())
        return []
    
    @staticmethod
    def merge(json1: JSONType, json2: JSONType) -> JSONType:
        """Fusionne deux objets JSON"""
        if isinstance(json1.data, dict) and isinstance(json2.data, dict):
            merged = {**json1.data, **json2.data}
            return JSONType(merged)
        return json1