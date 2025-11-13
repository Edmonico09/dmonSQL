# ============================================================================
# dmonSQL/core/table.py
# ============================================================================
"""Module de gestion des tables de base de données"""

from typing import Any, Dict, List, Tuple
from dmonSQL.core.column import Column
from dmonSQL.core.index import Index

class Table:
    """Table de base de données"""
    def __init__(self, name: str, columns: List[Column]):
        self.name = name
        self.columns = {col.name: col for col in columns}
        self.rows = []
        self.indexes = {}
        self.auto_increment_counters = {}
        
        # Initialiser les compteurs auto-increment
        for col_name, col in self.columns.items():
            if col.auto_increment:
                self.auto_increment_counters[col_name] = 0
    
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
    
    def insert(self, values: Dict[str, Any]) -> int:
        """Insère une ligne"""
        row = {}
        
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
        
        # Vérifier les contraintes unique
        for col_name, col in self.columns.items():
            if col.unique or col.primary_key:
                for existing_row in self.rows:
                    if existing_row[col_name] == row[col_name] and row[col_name] is not None:
                        raise ValueError(f"Duplicate value for unique column {col_name}")
        
        self.rows.append(row)
        
        # Reconstruire les index
        for index in self.indexes.values():
            index.build(self.rows)
        
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
                for col_name, value in values.items():
                    if col_name in self.columns:
                        row[col_name] = self.columns[col_name].validate(value)
                count += 1
        
        # Reconstruire les index
        for index in self.indexes.values():
            index.build(self.rows)
        
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
        
        return count