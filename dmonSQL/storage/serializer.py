# ============================================================================
# dmonSQL/storage/serializer.py
# ============================================================================
"""Sérialiseur pour dmonSQL"""

import pickle
import json
from typing import Any
from pathlib import Path


class Serializer:
    """Gère la sérialisation/désérialisation des données"""
    
    @staticmethod
    def serialize_pickle(data: Any, filepath: Path):
        """Sérialise avec pickle"""
        with open(filepath, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    @staticmethod
    def deserialize_pickle(filepath: Path) -> Any:
        """Désérialise avec pickle"""
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def serialize_json(data: Any, filepath: Path):
        """Sérialise avec JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def deserialize_json(filepath: Path) -> Any:
        """Désérialise avec JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def serialize_binary(data: bytes, filepath: Path):
        """Sauvegarde des données binaires"""
        with open(filepath, 'wb') as f:
            f.write(data)
    
    @staticmethod
    def deserialize_binary(filepath: Path) -> bytes:
        """Charge des données binaires"""
        with open(filepath, 'rb') as f:
            return f.read()


class DatabaseSerializer:
    """Sérialiseur spécialisé pour les bases de données"""
    
    def __init__(self, file_manager):
        self.file_manager = file_manager
        self.serializer = Serializer()
    
    def save_database(self, db_name: str, database: Any):
        """Sauvegarde une base de données"""
        filepath = self.file_manager.get_database_path(db_name)
        self.serializer.serialize_pickle(database, filepath)
    
    def load_database(self, db_name: str) -> Any:
        """Charge une base de données"""
        filepath = self.file_manager.get_database_path(db_name)
        if not filepath.exists():
            raise FileNotFoundError(f"Database file not found: {filepath}")
        return self.serializer.deserialize_pickle(filepath)
    
    def export_to_json(self, db_name: str, output_path: Path):
        """Exporte une base de données en JSON"""
        database = self.load_database(db_name)
        
        # Convertir en format JSON-compatible
        json_data = self._database_to_dict(database)
        
        self.serializer.serialize_json(json_data, output_path)
    
    def _database_to_dict(self, database) -> dict:
        """Convertit une base de données en dictionnaire"""
        return {
            'name': database.name,
            'tables': {
                table_name: {
                    'columns': [
                        {
                            'name': col.name,
                            'type': col.dtype,
                            'length': col.length,
                            'nullable': col.nullable
                        }
                        for col in table.columns.values()
                    ],
                    'rows': table.rows
                }
                for table_name, table in database.tables.items()
            }
        }
