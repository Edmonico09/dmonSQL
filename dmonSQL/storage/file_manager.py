# ============================================================================
# dmonSQL/storage/file_manager.py
# ============================================================================
"""Gestionnaire de fichiers pour dmonSQL"""

import os
from pathlib import Path
from typing import List, Optional
import shutil


class FileManager:
    """Gère les opérations sur les fichiers de la base de données"""
    
    def __init__(self, base_dir: str = "./dmonsql_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Créer les sous-dossiers
        self.db_dir = self.base_dir / "databases"
        self.log_dir = self.base_dir / "logs"
        self.backup_dir = self.base_dir / "backups"
        self.temp_dir = self.base_dir / "temp"
        
        for directory in [self.db_dir, self.log_dir, self.backup_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_database_path(self, db_name: str) -> Path:
        """Retourne le chemin vers un fichier de base de données"""
        return self.db_dir / f"{db_name}.db"
    
    def database_exists(self, db_name: str) -> bool:
        """Vérifie si une base de données existe"""
        return self.get_database_path(db_name).exists()
    
    def list_databases(self) -> List[str]:
        """Liste toutes les bases de données"""
        return [f.stem for f in self.db_dir.glob("*.db")]
    
    def delete_database(self, db_name: str):
        """Supprime une base de données"""
        db_path = self.get_database_path(db_name)
        if db_path.exists():
            db_path.unlink()
    
    def backup_database(self, db_name: str) -> Path:
        """Crée un backup d'une base de données"""
        from datetime import datetime
        
        source = self.get_database_path(db_name)
        if not source.exists():
            raise FileNotFoundError(f"Database {db_name} not found")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{db_name}_{timestamp}.db"
        
        shutil.copy2(source, backup_path)
        return backup_path
    
    def restore_database(self, backup_path: Path, db_name: str):
        """Restaure une base de données depuis un backup"""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        target = self.get_database_path(db_name)
        shutil.copy2(backup_path, target)
    
    def get_database_size(self, db_name: str) -> int:
        """Retourne la taille d'une base de données en bytes"""
        db_path = self.get_database_path(db_name)
        if db_path.exists():
            return db_path.stat().st_size
        return 0
    
    def cleanup_temp(self):
        """Nettoie les fichiers temporaires"""
        for temp_file in self.temp_dir.glob("*"):
            if temp_file.is_file():
                temp_file.unlink()
