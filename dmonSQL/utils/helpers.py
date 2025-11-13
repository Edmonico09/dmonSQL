
# ============================================================================
# dmonSQL/utils/helpers.py
# ============================================================================
"""Fonctions utilitaires pour dmonSQL"""

import hashlib
import uuid
from datetime import datetime
from typing import Any, List, Dict


def generate_id() -> str:
    """Génère un ID unique"""
    return str(uuid.uuid4())


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash un mot de passe avec salt"""
    if salt is None:
        salt = generate_id()
    
    hash_obj = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    
    return hash_obj.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Vérifie un mot de passe hashé"""
    new_hash, _ = hash_password(password, salt)
    return new_hash == hashed


def format_size(bytes_size: int) -> str:
    """Formate une taille en bytes en format lisible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def format_duration(seconds: float) -> str:
    """Formate une durée en secondes"""
    if seconds < 0.001:
        return f"{seconds*1000000:.2f} µs"
    elif seconds < 1:
        return f"{seconds*1000:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def deep_merge(dict1: dict, dict2: dict) -> dict:
    """Fusionne récursivement deux dictionnaires"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """Aplatit un dictionnaire imbriqué"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Divise une liste en chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier"""
    import re
    # Remplacer les caractères invalides
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limiter la longueur
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized


def get_timestamp() -> str:
    """Retourne un timestamp formaté"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def measure_time(func):
    """Décorateur pour mesurer le temps d'exécution"""
    import time
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"{func.__name__} took {format_duration(duration)}")
        return result
    
    return wrapper