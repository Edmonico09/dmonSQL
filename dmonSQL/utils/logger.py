# ============================================================================
# dmonSQL/utils/logger.py
# ============================================================================
"""Système de logging pour dmonSQL"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class DmonSQLLogger:
    """Logger personnalisé pour dmonSQL"""
    
    def __init__(self, name: str = "dmonSQL", log_file: str = None, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (optionnel)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        """Log niveau DEBUG"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log niveau INFO"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log niveau WARNING"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log niveau ERROR"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Log niveau CRITICAL"""
        self.logger.critical(message)


# Logger global par défaut
_default_logger = None

def get_logger(name: str = "dmonSQL") -> DmonSQLLogger:
    """Récupère le logger global"""
    global _default_logger
    if _default_logger is None:
        _default_logger = DmonSQLLogger(name)
    return _default_logger