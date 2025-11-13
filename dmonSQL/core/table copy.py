"""Module de gestion des tables de base de données
"""

import re
from datetime import datetime
from typing import Any, List, Dict, Tuple
from pathlib import Path

# Imports des modules dmonSQL
from dmonSQL.data_types.matrixType import MatrixType
from dmonSQL.data_types.email_type import EmailType
from dmonSQL.data_types.json_type import JSONType
from dmonSQL.core.column import Column
from dmonSQL.core.index import Index
from dmonSQL.core.constraint import ConstraintManager, NotNullConstraint
from dmonSQL.storage.file_manager import FileManager
from dmonSQL.storage.serializer import DatabaseSerializer
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_size, format_duration
from dmonSQL.query.parser import QueryParser

class Table:
    """Table de base de données améliorée"""
    
    def __init__(self, name: str, columns: List[Column]):
        self.name = name
        self.columns = {col.name: col for col in columns}
        self.rows = []
        self.indexes = {}
        self.auto_increment_counters = {}
        self.constraint_manager = ConstraintManager()
        self.created_at = datetime.now()
        self.row_count_history = []
        
        # Initialiser les compteurs auto-increment
        for col_name, col in self.columns.items():
            if col.auto_increment:
                self.auto_increment_counters[col_name] = 0
            
            # Ajouter contrainte NOT NULL si nécessaire
            if not col.nullable and not col.primary_key:
                constraint = NotNullConstraint(f"nn_{col_name}", col_name)
                self.constraint_manager.add_constraint(constraint)
    
    def get_primary_key_columns(self) -> List[str]:
        """Retourne les colonnes de clé primaire"""
        return [name for name, col in self.columns.items() if col.primary_key]
    
    def create_index(self, name: str, columns: List[str], unique: bool = False):
        """Crée un index"""
        for col in columns:
            if col not in self.columns:
                raise ValueError(f"Column {col} does not exist")
        
        index = Index(name, columns, unique)
        index.build(self.rows)
        self.indexes[name] = index
        
        get_logger().info(f"Index '{name}' created on table '{self.name}'")
    
    def insert(self, values: Dict[str, Any]) -> int:
        """Insère une ligne avec validation des contraintes"""
        row = {}
        
        
        for val in values:
            get_logger().info(f'Value to insert {val}')
        
        # Construire la ligne
        for col_name, col in self.columns.items():
            if col.auto_increment:
                self.auto_increment_counters[col_name] += 1
                row[col_name] = self.auto_increment_counters[col_name]
            elif col_name in values:
                row[col_name] = col.validate(values[col_name])
            elif col.default is not None:
                row[col_name] = col.default
            elif col.nullable:
                row[col_name] = None
            else:
                raise ValueError(f"Missing required column: {col_name}")
        
        # Valider les contraintes
        self.constraint_manager.validate_row(row)
        
        # Vérifier les contraintes unique
        for col_name, col in self.columns.items():
            if col.unique or col.primary_key:
                for existing_row in self.rows:
                    if existing_row[col_name] == row[col_name] and row[col_name] is not None:
                        raise ValueError(f"Duplicate value for unique column {col_name}: {row[col_name]}")
        
        # Ajouter la ligne
        self.rows.append(row)
        
        # Reconstruire les index
        for index in self.indexes.values():
            index.build(self.rows)
        
        # Historique
        self.row_count_history.append((datetime.now(), len(self.rows)))
        
        get_logger().debug(f"Row inserted into table '{self.name}'")
        return len(self.rows) - 1
    
    def select(self, columns: List[str] = None, where: callable = None, 
               order_by: List[Tuple[str, str]] = None, limit: int = None) -> List[Dict]:
        """Sélectionne des lignes"""
        if columns is None:
            columns = list(self.columns.keys())
        
        # Filtrage
        result = self.rows if where is None else [row for row in self.rows if where(row)]
        
        # Tri
        if order_by:
            for col, direction in reversed(order_by):
                reverse = direction.upper() == "DESC"
                result = sorted(result, key=lambda x: x.get(col), reverse=reverse)
        
        # Limite
        if limit:
            result = result[:limit]
        
        # Projection
        return [{col: row[col] for col in columns if col in row} for row in result]
    
    def update(self, values: Dict[str, Any], where: callable = None) -> int:
        """Met à jour des lignes"""
        count = 0
        for row in self.rows:
            if where is None or where(row):
                # Appliquer les modifications
                for col_name, value in values.items():
                    if col_name in self.columns:
                        row[col_name] = self.columns[col_name].validate(value)
                
                # Valider les contraintes
                self.constraint_manager.validate_row(row)
                count += 1
        
        # Reconstruire les index
        for index in self.indexes.values():
            index.build(self.rows)
        
        get_logger().debug(f"{count} row(s) updated in table '{self.name}'")
        return count
    
    def delete(self, where: callable = None) -> int:
        """Supprime des lignes"""
        if where is None:
            count = len(self.rows)
            self.rows.clear()
        else:
            initial_count = len(self.rows)
            self.rows = [row for row in self.rows if not where(row)]
            count = initial_count - len(self.rows)
        
        # Reconstruire les index
        for index in self.indexes.values():
            index.build(self.rows)
        
        get_logger().debug(f"{count} row(s) deleted from table '{self.name}'")
        return count
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques de la table"""
        return {
            'name': self.name,
            'columns': len(self.columns),
            'rows': len(self.rows),
            'indexes': len(self.indexes),
            'created_at': self.created_at.isoformat(),
            'size_estimate': len(self.rows) * len(self.columns) * 50  # Estimation
        }
