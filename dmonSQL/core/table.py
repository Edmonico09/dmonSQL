"""Module de gestion des tables de base de données
"""

import re
from datetime import datetime
from typing import Any, List, Dict, Tuple
from pathlib import Path
from dmonSQL.core.column import Column
from dmonSQL.utils.logger import get_logger
from typing import Any, Dict

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
        
        # Foreign keys
        self.foreign_keys = []
        self.database = None  # Référence à la base de données
        
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
    
    # ==================== FOREIGN KEY METHODS ====================
    
    def add_foreign_key(self, column: str, ref_table: str, ref_column: str,
                        on_delete: str = 'RESTRICT', on_update: str = 'RESTRICT'):
        """Ajoute une contrainte de clé étrangère"""
        if column not in self.columns:
            raise ValueError(f"Column '{column}' does not exist in table '{self.name}'")
        
        fk = {
            'column': column,
            'ref_table': ref_table,
            'ref_column': ref_column,
            'on_delete': on_delete.upper(),
            'on_update': on_update.upper()
        }
        self.foreign_keys.append(fk)
        get_logger().info(f"Foreign key added: {self.name}.{column} -> {ref_table}.{ref_column}")
    
    def validate_foreign_keys(self, row: Dict):
        """Valide les clés étrangères pour une ligne"""
        # ⭐ CORRECTION : Initialiser foreign_keys si manquant
        if not hasattr(self, 'foreign_keys'):
            self.foreign_keys = []
        
        if not self.database or not self.foreign_keys:
            return True
        
        for fk in self.foreign_keys:
            value = row.get(fk['column'])
            
            # NULL est accepté (sauf si NOT NULL)
            if value is None:
                continue
            
            # Vérifier que la valeur existe dans la table référencée
            try:
                ref_table = self.database.get_table(fk['ref_table'])
                exists = any(
                    ref_row.get(fk['ref_column']) == value 
                    for ref_row in ref_table.rows
                )
                
                if not exists:
                    raise ValueError(
                        f"Foreign key constraint failed: {self.name}.{fk['column']}={value} "
                        f"not found in {fk['ref_table']}.{fk['ref_column']}"
                    )
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Foreign key validation error: {e}")
        
        return True
    # def validate_foreign_keys(self, row: Dict):
    #     """Valide les clés étrangères pour une ligne"""
    #     if not self.database or not self.foreign_keys:
    #         return True
        
    #     for fk in self.foreign_keys:
    #         value = row.get(fk['column'])
            
    #         # NULL est accepté (sauf si NOT NULL)
    #         if value is None:
    #             continue
            
    #         # Vérifier que la valeur existe dans la table référencée
    #         try:
    #             ref_table = self.database.get_table(fk['ref_table'])
    #             exists = any(
    #                 ref_row.get(fk['ref_column']) == value 
    #                 for ref_row in ref_table.rows
    #             )
                
    #             if not exists:
    #                 raise ValueError(
    #                     f"Foreign key constraint failed: {self.name}.{fk['column']}={value} "
    #                     f"not found in {fk['ref_table']}.{fk['ref_column']}"
    #                 )
    #         except ValueError:
    #             raise
    #         except Exception as e:
    #             raise ValueError(f"Foreign key validation error: {e}")
        
    #     return True
    
    def _handle_cascade_delete(self, deleted_rows: List[Dict]):
        """Gère CASCADE DELETE pour les tables dépendantes"""
        if not self.database:
            return
        
        # Chercher les tables qui ont une FK vers cette table
        for table_name, table in self.database.tables.items():
            if table_name == self.name:
                continue
            
            # ⭐ CORRECTION : Vérifier que foreign_keys existe
            if not hasattr(table, 'foreign_keys'):
                continue
            
            for fk in table.foreign_keys:
                if fk['ref_table'] == self.name:
                    for deleted_row in deleted_rows:
                        ref_value = deleted_row.get(fk['ref_column'])
                        
                        if fk['on_delete'] == 'CASCADE':
                            # Supprimer les lignes dépendantes
                            before_count = len(table.rows)
                            table.rows = [
                                r for r in table.rows 
                                if r.get(fk['column']) != ref_value
                            ]
                            after_count = len(table.rows)
                            if before_count != after_count:
                                get_logger().info(
                                    f"CASCADE DELETE: {before_count - after_count} row(s) "
                                    f"removed from {table_name}"
                                )
                        
                        elif fk['on_delete'] == 'SET_NULL':
                            # Mettre NULL dans les lignes dépendantes
                            for r in table.rows:
                                if r.get(fk['column']) == ref_value:
                                    r[fk['column']] = None
                        
                        elif fk['on_delete'] in ('RESTRICT', 'NO ACTION'):
                            # Vérifier s'il y a des lignes dépendantes
                            has_dependent = any(
                                r.get(fk['column']) == ref_value 
                                for r in table.rows
                            )
                            if has_dependent:
                                raise ValueError(
                                    f"Cannot delete: foreign key constraint from "
                                    f"{table_name}.{fk['column']} references this row"
                                )
    # def _handle_cascade_delete(self, deleted_rows: List[Dict]):
    #     """Gère CASCADE DELETE pour les tables dépendantes"""
    #     if not self.database:
    #         return
        
    #     # Chercher les tables qui ont une FK vers cette table
    #     for table_name, table in self.database.tables.items():
    #         if table_name == self.name:
    #             continue
            
    #         for fk in getattr(table, 'foreign_keys', []):
    #             if fk['ref_table'] == self.name:
    #                 for deleted_row in deleted_rows:
    #                     ref_value = deleted_row.get(fk['ref_column'])
                        
    #                     if fk['on_delete'] == 'CASCADE':
    #                         # Supprimer les lignes dépendantes
    #                         before_count = len(table.rows)
    #                         table.rows = [
    #                             r for r in table.rows 
    #                             if r.get(fk['column']) != ref_value
    #                         ]
    #                         after_count = len(table.rows)
    #                         if before_count != after_count:
    #                             get_logger().info(
    #                                 f"CASCADE DELETE: {before_count - after_count} row(s) "
    #                                 f"removed from {table_name}"
    #                             )
                        
    #                     elif fk['on_delete'] == 'SET NULL':
    #                         # Mettre NULL dans les lignes dépendantes
    #                         for r in table.rows:
    #                             if r.get(fk['column']) == ref_value:
    #                                 r[fk['column']] = None
                        
    #                     elif fk['on_delete'] in ('RESTRICT', 'NO ACTION'):
    #                         # Vérifier s'il y a des lignes dépendantes
    #                         has_dependent = any(
    #                             r.get(fk['column']) == ref_value 
    #                             for r in table.rows
    #                         )
    #                         if has_dependent:
    #                             raise ValueError(
    #                                 f"Cannot delete: foreign key constraint from "
    #                                 f"{table_name}.{fk['column']} references this row"
    #                             )
    
    # ==================== END FOREIGN KEY METHODS ====================
    
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
        
        # Valider les clés étrangères
        self.validate_foreign_keys(row)
        
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
           order_by: List[Tuple[str, str]] = None, 
           limit: int = None, offset: int = None,
           distinct: bool = False) -> List[Dict]:
        """Sélectionne des lignes avec support DISTINCT, LIMIT, OFFSET"""
        
        if columns is None:
            columns = list(self.columns.keys())
        
        # Filtrage
        result = self.rows if where is None else [row for row in self.rows if where(row)]
        
        # Tri
        if order_by:
            for col, direction in reversed(order_by):
                reverse = direction.upper() == "DESC"
                result = sorted(result, key=lambda x: (x.get(col) is None, x.get(col)), reverse=reverse)
        
        # DISTINCT
        if distinct:
            from dmonSQL.query.advanced_features import execute_distinct
            result = execute_distinct(result, columns)
        
        # OFFSET puis LIMIT
        if offset and offset > 0:
            result = result[offset:]
        
        if limit and limit > 0:
            result = result[:limit]
        
        # Projection
        return [{col: row[col] for col in columns if col in row} for row in result]
    # def select(self, columns: List[str] = None, where: callable = None, 
    #            order_by: List[Tuple[str, str]] = None, limit: int = None) -> List[Dict]:
    #     """Sélectionne des lignes"""
    #     if columns is None:
    #         columns = list(self.columns.keys())
        
    #     # Filtrage
    #     result = self.rows if where is None else [row for row in self.rows if where(row)]
        
    #     # Tri
    #     if order_by:
    #         for col, direction in reversed(order_by):
    #             reverse = direction.upper() == "DESC"
    #             result = sorted(result, key=lambda x: x.get(col), reverse=reverse)
        
    #     # Limite
    #     if limit:
    #         result = result[:limit]
        
    #     # Projection
    #     return [{col: row[col] for col in columns if col in row} for row in result]
    
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
        """Supprime des lignes avec gestion CASCADE"""
        # Identifier les lignes à supprimer
        if where is None:
            deleted_rows = list(self.rows)
        else:
            deleted_rows = [row for row in self.rows if where(row)]
        
        # Gérer ON DELETE CASCADE/RESTRICT avant suppression
        if deleted_rows:
            self._handle_cascade_delete(deleted_rows)
        
        # Supprimer les lignes
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
            'foreign_keys': len(getattr(self, 'foreign_keys', [])),
            'created_at': self.created_at.isoformat(),
            'size_estimate': len(self.rows) * len(self.columns) * 50  # Estimation
        }


class TableAlterMixin:
    """
    Mixin pour ajouter les fonctionnalités ALTER TABLE à la classe Table
    """
    
    def add_column(self, column: Column, default_value: Any = None):
        """
        Ajoute une nouvelle colonne à la table
        
        ALTER TABLE users ADD COLUMN email VARCHAR(100);
        ALTER TABLE users ADD COLUMN age INT DEFAULT 0;
        ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
        """
        if column.name in self.columns:
            raise ValueError(f"Column '{column.name}' already exists in table '{self.name}'")
        
        # Ajouter la colonne à la structure
        self.columns[column.name] = column
        
        # Mettre à jour toutes les lignes existantes
        for row in self.rows:
            if default_value is not None:
                row[column.name] = column.validate(default_value)
            elif column.default is not None:
                row[column.name] = column.default
            elif column.nullable:
                row[column.name] = None
            else:
                raise ValueError(
                    f"Cannot add NOT NULL column '{column.name}' without DEFAULT value "
                    f"to table with existing data"
                )
        
        # Reconstruire les index si nécessaire
        for index in self.indexes.values():
            index.build(self.rows)
        
        get_logger().info(f"Column '{column.name}' added to table '{self.name}'")
    
    def drop_column(self, column_name: str):
        """
        Supprime une colonne de la table
        
        ALTER TABLE users DROP COLUMN age;
        """
        if column_name not in self.columns:
            raise ValueError(f"Column '{column_name}' does not exist in table '{self.name}'")
        
        # Vérifier que ce n'est pas une clé primaire
        if self.columns[column_name].primary_key:
            raise ValueError(f"Cannot drop primary key column '{column_name}'")
        
        # Vérifier les contraintes de clé étrangère
        if hasattr(self, 'foreign_keys'):
            for fk in self.foreign_keys:
                if fk['column'] == column_name:
                    raise ValueError(
                        f"Cannot drop column '{column_name}': "
                        f"foreign key constraint exists"
                    )
        
        # Vérifier si la colonne est utilisée dans un index
        indexes_to_drop = []
        for idx_name, idx in self.indexes.items():
            if column_name in idx.columns:
                indexes_to_drop.append(idx_name)
        
        # Supprimer les index affectés
        for idx_name in indexes_to_drop:
            del self.indexes[idx_name]
            get_logger().info(f"Index '{idx_name}' dropped (column dependency)")
        
        # Supprimer la colonne de la structure
        del self.columns[column_name]
        
        # Supprimer la colonne de toutes les lignes
        for row in self.rows:
            if column_name in row:
                del row[column_name]
        
        get_logger().info(f"Column '{column_name}' dropped from table '{self.name}'")
    
    def modify_column(self, column_name: str, new_column: Column):
        """
        Modifie le type ou les propriétés d'une colonne
        
        ALTER TABLE users MODIFY COLUMN name VARCHAR(200);
        ALTER TABLE users MODIFY COLUMN age INT NOT NULL;
        """
        if column_name not in self.columns:
            raise ValueError(f"Column '{column_name}' does not exist in table '{self.name}'")
        
        old_column = self.columns[column_name]
        
        # Vérifier que le nom ne change pas (utiliser RENAME pour ça)
        if new_column.name != column_name:
            raise ValueError(
                f"Use RENAME COLUMN to change column name. "
                f"MODIFY COLUMN only changes type and constraints."
            )
        
        # Valider les données existantes avec le nouveau type
        for row in self.rows:
            old_value = row.get(column_name)
            
            # Vérifier la contrainte NOT NULL
            if not new_column.nullable and old_value is None:
                raise ValueError(
                    f"Cannot modify column '{column_name}' to NOT NULL: "
                    f"existing NULL values found"
                )
            
            # Essayer de convertir au nouveau type
            if old_value is not None:
                try:
                    row[column_name] = new_column.validate(old_value)
                except Exception as e:
                    raise ValueError(
                        f"Cannot convert existing value '{old_value}' to new type: {e}"
                    )
        
        # Appliquer la modification
        self.columns[column_name] = new_column
        
        # Reconstruire les index
        for index in self.indexes.values():
            if column_name in index.columns:
                index.build(self.rows)
        
        get_logger().info(
            f"Column '{column_name}' modified in table '{self.name}': "
            f"{old_column.dtype} -> {new_column.dtype}"
        )
    
    def rename_column(self, old_name: str, new_name: str):
        """
        Renomme une colonne
        
        ALTER TABLE users RENAME COLUMN old_name TO new_name;
        """
        if old_name not in self.columns:
            raise ValueError(f"Column '{old_name}' does not exist in table '{self.name}'")
        
        if new_name in self.columns:
            raise ValueError(f"Column '{new_name}' already exists in table '{self.name}'")
        
        # Récupérer la colonne
        column = self.columns[old_name]
        column.name = new_name
        
        # Mettre à jour le dictionnaire des colonnes
        del self.columns[old_name]
        self.columns[new_name] = column
        
        # Mettre à jour toutes les lignes
        for row in self.rows:
            if old_name in row:
                row[new_name] = row.pop(old_name)
        
        # Mettre à jour les index
        for idx in self.indexes.values():
            if old_name in idx.columns:
                idx.columns = [new_name if c == old_name else c for c in idx.columns]
                idx.build(self.rows)
        
        # Mettre à jour les clés étrangères
        if hasattr(self, 'foreign_keys'):
            for fk in self.foreign_keys:
                if fk['column'] == old_name:
                    fk['column'] = new_name
        
        get_logger().info(
            f"Column renamed in table '{self.name}': '{old_name}' -> '{new_name}'"
        )
    
    def add_constraint(self, constraint_type: str, **kwargs):
        """
        Ajoute une contrainte à la table
        
        ALTER TABLE users ADD CONSTRAINT uk_email UNIQUE (email);
        ALTER TABLE orders ADD CONSTRAINT fk_user 
            FOREIGN KEY (user_id) REFERENCES users(id);
        ALTER TABLE products ADD CONSTRAINT chk_price CHECK (price > 0);
        """
        if constraint_type.upper() == 'UNIQUE':
            # Ajouter une contrainte UNIQUE
            columns = kwargs.get('columns', [])
            constraint_name = kwargs.get('name', f'uk_{"_".join(columns)}')
            
            # Vérifier l'unicité des valeurs existantes
            seen_values = set()
            for row in self.rows:
                key = tuple(row.get(col) for col in columns)
                if key in seen_values:
                    raise ValueError(
                        f"Cannot add UNIQUE constraint: duplicate values exist for {columns}"
                    )
                seen_values.add(key)
            
            # Créer un index unique
            from dmonSQL.core.index import Index
            index = Index(constraint_name, columns, unique=True)
            index.build(self.rows)
            self.indexes[constraint_name] = index
            
            get_logger().info(f"UNIQUE constraint '{constraint_name}' added to table '{self.name}'")
        
        elif constraint_type.upper() == 'FOREIGN_KEY':
            # Ajouter une clé étrangère
            column = kwargs.get('column')
            ref_table = kwargs.get('ref_table')
            ref_column = kwargs.get('ref_column')
            on_delete = kwargs.get('on_delete', 'RESTRICT')
            on_update = kwargs.get('on_update', 'RESTRICT')
            
            self.add_foreign_key(column, ref_table, ref_column, on_delete, on_update)
        
        elif constraint_type.upper() == 'CHECK':
            # Ajouter une contrainte CHECK
            from dmonSQL.core.constraint import CheckConstraint
            condition = kwargs.get('condition')
            condition_str = kwargs.get('condition_str', '')
            constraint_name = kwargs.get('name', f'chk_{self.name}')
            
            # Valider les données existantes
            for row in self.rows:
                if not condition(row):
                    raise ValueError(
                        f"Cannot add CHECK constraint: existing data violates condition"
                    )
            
            check_constraint = CheckConstraint(constraint_name, condition, condition_str)
            self.constraint_manager.add_constraint(check_constraint)
            
            get_logger().info(f"CHECK constraint '{constraint_name}' added to table '{self.name}'")
        
        else:
            raise ValueError(f"Unsupported constraint type: {constraint_type}")
    
    def drop_constraint(self, constraint_name: str):
        """
        Supprime une contrainte
        
        ALTER TABLE users DROP CONSTRAINT uk_email;
        """
        # Vérifier si c'est un index (UNIQUE)
        if constraint_name in self.indexes:
            del self.indexes[constraint_name]
            get_logger().info(f"Constraint '{constraint_name}' dropped from table '{self.name}'")
            return
        
        # Vérifier si c'est une contrainte CHECK
        if constraint_name in self.constraint_manager.constraints:
            self.constraint_manager.remove_constraint(constraint_name)
            get_logger().info(f"Constraint '{constraint_name}' dropped from table '{self.name}'")
            return
        
        # Vérifier les clés étrangères
        if hasattr(self, 'foreign_keys'):
            for i, fk in enumerate(self.foreign_keys):
                if fk.get('name') == constraint_name:
                    self.foreign_keys.pop(i)
                    get_logger().info(f"Foreign key '{constraint_name}' dropped from table '{self.name}'")
                    return
        
        raise ValueError(f"Constraint '{constraint_name}' not found in table '{self.name}'")


# ============================================================================
# Exemple d'utilisation complète
# ============================================================================

if __name__ == "__main__":
    from dmonSQL.core.table import Table
    from dmonSQL.core.column import Column
    from dmonSQL.data_types.base_types import DataType
    
    # Appliquer le mixin à la classe Table
    Table.__bases__ = (TableAlterMixin,) + Table.__bases__
    
    # Créer une table
    columns = [
        Column('id', DataType.INT, primary_key=True, auto_increment=True),
        Column('name', DataType.VARCHAR, length=50, nullable=False),
        Column('age', DataType.INT, nullable=True),
    ]
    
    users = Table('users', columns)
    
    # Insérer des données
    users.insert({'name': 'Alice', 'age': 30})
    users.insert({'name': 'Bob', 'age': 25})
    
    print("Table initiale:")
    for row in users.rows:
        print(row)
    
    print("\n" + "="*60 + "\n")
    
    # Test 1: ADD COLUMN
    print("Test 1: ADD COLUMN email VARCHAR(100)")
    email_col = Column('email', DataType.VARCHAR, length=100, nullable=True)
    users.add_column(email_col)
    
    for row in users.rows:
        print(row)
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: MODIFY COLUMN
    print("Test 2: MODIFY COLUMN name VARCHAR(100)")
    new_name_col = Column('name', DataType.VARCHAR, length=100, nullable=False)
    users.modify_column('name', new_name_col)
    print(f"Name column length: {users.columns['name'].length}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 3: RENAME COLUMN
    print("Test 3: RENAME COLUMN age TO years_old")
    users.rename_column('age', 'years_old')
    
    for row in users.rows:
        print(row)
    
    print("\n" + "="*60 + "\n")
    
    # Test 4: DROP COLUMN
    print("Test 4: DROP COLUMN email")
    users.drop_column('email')
    
    for row in users.rows:
        print(row)