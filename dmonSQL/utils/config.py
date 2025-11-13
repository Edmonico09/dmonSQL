
# ============================================================================
# dmonSQL/utils/config.py
# ============================================================================
"""Gestionnaire de configuration pour dmonSQL"""

import configparser
from pathlib import Path
from typing import Any, Optional


class Config:
    """Gestionnaire de configuration"""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        
        if config_file and config_file.exists():
            self.load(config_file)
        else:
            self._set_defaults()
    
    def _set_defaults(self):
        """Définit les valeurs par défaut"""
        self.config['database'] = {
            'data_dir': './dmonsql_data',
            'default_compression': 'ZLIB',
            'enable_encryption': 'false',
        }
        
        self.config['performance'] = {
            'cache_size': '1000',
            'index_cache_size': '500',
            'max_connections': '10',
            'query_timeout': '300',
        }
        
        self.config['logging'] = {
            'level': 'INFO',
            'file': 'dmonsql.log',
            'max_size': '10MB',
            'backup_count': '5',
        }
        
        self.config['security'] = {
            'require_auth': 'false',
            'allow_remote': 'false',
            'max_login_attempts': '3',
        }
    
    def load(self, config_file: Path):
        """Charge la configuration depuis un fichier"""
        self.config.read(config_file, encoding='utf-8')
        self.config_file = config_file
    
    def save(self, config_file: Optional[Path] = None):
        """Sauvegarde la configuration"""
        if config_file is None:
            config_file = self.config_file
        
        if config_file is None:
            raise ValueError("No config file specified")
        
        with open(config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Récupère une valeur de configuration"""
        return self.config.get(section, key, fallback=fallback)
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Récupère une valeur entière"""
        return self.config.getint(section, key, fallback=fallback)
    
    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """Récupère une valeur booléenne"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def set(self, section: str, key: str, value: str):
        """Définit une valeur"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire"""
        return {section: dict(self.config[section]) for section in self.config.sections()}
