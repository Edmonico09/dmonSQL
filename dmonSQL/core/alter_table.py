"""
ALTER TABLE - Modification de structure de tables
ADD COLUMN, DROP COLUMN, MODIFY COLUMN, RENAME
"""

from typing import Dict, Any
from dmonSQL.core.column import Column
from dmonSQL.core.table import Table
from dmonSQL.utils.logger import get_logger


class AlterTableEngine:
    """Moteur pour ALTER TABLE"""
    
    @staticmethod
    def add_column(table: Table, column: Column, default_value: Any = None):
        """
        ALTER TABLE table_name ADD COLUMN column_name TYPE
        
        Exemple:
            ALTER TABLE users ADD COLUMN age INT DEFAULT 0
        """
        if column.name in table.columns:
            raise ValueError(f"Column '{column.name}' already exists in table '{table.name}'")
        
        # Ajouter la colonne
        table.columns[column.name] = column
        
        # Ajouter la valeur par défaut à toutes les lignes existantes
        value = default_value if default_value is not None else (column.default if column.default is not None else None)
        
        for row in table.rows:
            row[column.name] = value
        
        get_logger().info(f"Column '{column.name}' added to table '{table.name}'")
    
    @staticmethod
    def drop_column(table: Table, column_name: str):
        """
        ALTER TABLE table_name DROP COLUMN column_name
        
        Exemple:
            ALTER TABLE users DROP COLUMN age
        """
        if column_name not in table.columns:
            raise ValueError(f"Column '{column_name}' does not exist in table '{table.name}'")
        
        # Vérifier que ce n'est pas une clé primaire
        if table.columns[column_name].primary_key:
            raise ValueError(f"Cannot drop primary key column '{column_name}'")
        
        # Vérifier qu'elle n'est pas utilisée dans une FK
        for fk in table.foreign_keys:
            if fk['column'] == column_name:
                raise ValueError(
                    f"Cannot drop column '{column_name}': "
                    f"it's used in foreign key to {fk['ref_table']}.{fk['ref_column']}"
                )
        
        # Supprimer la colonne
        del table.columns[column_name]
        
        # Supprimer la colonne de toutes les lignes
        for row in table.rows:
            if column_name in row:
                del row[column_name]
        
        # Supprimer les index utilisant cette colonne
        indexes_to_remove = []
        for idx_name, idx in table.indexes.items():
            if column_name in idx.columns:
                indexes_to_remove.append(idx_name)
        
        for idx_name in indexes_to_remove:
            del table.indexes[idx_name]
            get_logger().info(f"Index '{idx_name}' dropped (used column '{column_name}')")
        
        get_logger().info(f"Column '{column_name}' dropped from table '{table.name}'")
    
    @staticmethod
    def rename_column(table: Table, old_name: str, new_name: str):
        """
        ALTER TABLE table_name RENAME COLUMN old_name TO new_name
        
        Exemple:
            ALTER TABLE users RENAME COLUMN email TO email_address
        """
        if old_name not in table.columns:
            raise ValueError(f"Column '{old_name}' does not exist in table '{table.name}'")
        
        if new_name in table.columns:
            raise ValueError(f"Column '{new_name}' already exists in table '{table.name}'")
        
        # Renommer dans la définition
        column = table.columns[old_name]
        column.name = new_name
        table.columns[new_name] = column
        del table.columns[old_name]
        
        # Renommer dans toutes les lignes
        for row in table.rows:
            if old_name in row:
                row[new_name] = row[old_name]
                del row[old_name]
        
        # Mettre à jour les FK
        for fk in table.foreign_keys:
            if fk['column'] == old_name:
                fk['column'] = new_name
        
        # Mettre à jour les index
        for idx in table.indexes.values():
            if old_name in idx.columns:
                idx.columns = [new_name if c == old_name else c for c in idx.columns]
        
        get_logger().info(f"Column '{old_name}' renamed to '{new_name}' in table '{table.name}'")
    
    @staticmethod
    def modify_column(table: Table, column_name: str, new_type: str, new_length: int = None):
        """
        ALTER TABLE table_name MODIFY COLUMN column_name NEW_TYPE
        
        Exemple:
            ALTER TABLE users MODIFY COLUMN name VARCHAR(100)
        """
        if column_name not in table.columns:
            raise ValueError(f"Column '{column_name}' does not exist in table '{table.name}'")
        
        column = table.columns[column_name]
        old_type = column.dtype
        
        # Modifier le type
        column.dtype = new_type
        if new_length is not None:
            column.length = new_length
        
        # Convertir les valeurs existantes
        for row in table.rows:
            if column_name in row and row[column_name] is not None:
                try:
                    row[column_name] = column.validate(row[column_name])
                except Exception as e:
                    raise ValueError(
                        f"Cannot convert existing data in column '{column_name}' "
                        f"from {old_type} to {new_type}: {e}"
                    )
        
        get_logger().info(
            f"Column '{column_name}' modified in table '{table.name}': "
            f"{old_type} -> {new_type}"
        )
    
    @staticmethod
    def rename_table(table: Table, new_name: str):
        """
        ALTER TABLE old_name RENAME TO new_name
        
        Exemple:
            ALTER TABLE users RENAME TO customers
        """
        old_name = table.name
        table.name = new_name
        
        get_logger().info(f"Table '{old_name}' renamed to '{new_name}'")
    
    @staticmethod
    def add_constraint(table: Table, constraint):
        """
        ALTER TABLE table_name ADD CONSTRAINT constraint_name ...
        
        Exemple:
            ALTER TABLE users ADD CONSTRAINT check_age CHECK (age >= 18)
        """
        table.constraint_manager.add_constraint(constraint)
        get_logger().info(f"Constraint '{constraint.name}' added to table '{table.name}'")
    
    @staticmethod
    def drop_constraint(table: Table, constraint_name: str):
        """
        ALTER TABLE table_name DROP CONSTRAINT constraint_name
        
        Exemple:
            ALTER TABLE users DROP CONSTRAINT check_age
        """
        table.constraint_manager.remove_constraint(constraint_name)
        get_logger().info(f"Constraint '{constraint_name}' dropped from table '{table.name}'")


# ============================================================================
# PARSER POUR ALTER TABLE
# ============================================================================

import re

class AlterTableParser:
    """Parse les commandes ALTER TABLE"""
    
    @staticmethod
    def parse_alter_table(sql: str) -> Dict:
        """
        Parse ALTER TABLE
        
        Formats supportés:
        - ALTER TABLE table ADD COLUMN col TYPE
        - ALTER TABLE table DROP COLUMN col
        - ALTER TABLE table RENAME COLUMN old TO new
        - ALTER TABLE table MODIFY COLUMN col TYPE
        - ALTER TABLE table RENAME TO new_name
        """
        result = {
            'table': None,
            'action': None,
            'params': {}
        }
        
        # Extraire le nom de la table
        table_match = re.match(r'ALTER\s+TABLE\s+(\w+)\s+(.*)', sql, re.IGNORECASE)
        if not table_match:
            raise ValueError("Invalid ALTER TABLE syntax")
        
        result['table'] = table_match.group(1)
        rest = table_match.group(2).strip()
        
        # ADD COLUMN
        if rest.upper().startswith('ADD COLUMN') or rest.upper().startswith('ADD'):
            match = re.match(
                r'ADD\s+(?:COLUMN\s+)?(\w+)\s+(\w+)(?:\((\d+)\))?(?:\s+DEFAULT\s+(.+))?',
                rest, re.IGNORECASE
            )
            if match:
                result['action'] = 'ADD_COLUMN'
                result['params'] = {
                    'column_name': match.group(1),
                    'type': match.group(2).upper(),
                    'length': int(match.group(3)) if match.group(3) else None,
                    'default': match.group(4).strip("'\"") if match.group(4) else None
                }
        
        # DROP COLUMN
        elif rest.upper().startswith('DROP COLUMN') or rest.upper().startswith('DROP'):
            match = re.match(r'DROP\s+(?:COLUMN\s+)?(\w+)', rest, re.IGNORECASE)
            if match:
                result['action'] = 'DROP_COLUMN'
                result['params'] = {'column_name': match.group(1)}
        
        # RENAME COLUMN
        elif rest.upper().startswith('RENAME COLUMN'):
            match = re.match(r'RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)', rest, re.IGNORECASE)
            if match:
                result['action'] = 'RENAME_COLUMN'
                result['params'] = {
                    'old_name': match.group(1),
                    'new_name': match.group(2)
                }
        
        # MODIFY COLUMN
        elif rest.upper().startswith('MODIFY COLUMN') or rest.upper().startswith('MODIFY'):
            match = re.match(
                r'MODIFY\s+(?:COLUMN\s+)?(\w+)\s+(\w+)(?:\((\d+)\))?',
                rest, re.IGNORECASE
            )
            if match:
                result['action'] = 'MODIFY_COLUMN'
                result['params'] = {
                    'column_name': match.group(1),
                    'type': match.group(2).upper(),
                    'length': int(match.group(3)) if match.group(3) else None
                }
        
        # RENAME TO
        elif rest.upper().startswith('RENAME TO'):
            match = re.match(r'RENAME\s+TO\s+(\w+)', rest, re.IGNORECASE)
            if match:
                result['action'] = 'RENAME_TABLE'
                result['params'] = {'new_name': match.group(1)}
        
        else:
            raise ValueError(f"Unsupported ALTER TABLE action: {rest}")
        
        return result


# ============================================================================
# INTÉGRATION DANS DMONSQL
# ============================================================================

def integrate_alter_table_in_dmonsql():
    """Guide d'intégration dans dmonsql_main.py"""
    
    code_example = '''
# Dans dmonsql_main.py, méthode _execute_internal:

def _execute_internal(self, sql: str) -> Any:
    sql_upper = sql.upper()
    
    # ... code existant ...
    
    # ⭐ ALTER TABLE
    if sql_upper.startswith('ALTER TABLE'):
        from dmonSQL.query.alter_table import AlterTableEngine, AlterTableParser
        
        parsed = AlterTableParser.parse_alter_table(sql)
        table = db.get_table(parsed['table'])
        
        if parsed['action'] == 'ADD_COLUMN':
            column = Column(
                name=parsed['params']['column_name'],
                dtype=parsed['params']['type'],
                length=parsed['params']['length'],
                default=parsed['params']['default']
            )
            AlterTableEngine.add_column(table, column, parsed['params']['default'])
            print(f"✓ Column '{column.name}' added")
        
        elif parsed['action'] == 'DROP_COLUMN':
            AlterTableEngine.drop_column(table, parsed['params']['column_name'])
            print(f"✓ Column '{parsed['params']['column_name']}' dropped")
        
        elif parsed['action'] == 'RENAME_COLUMN':
            AlterTableEngine.rename_column(
                table,
                parsed['params']['old_name'],
                parsed['params']['new_name']
            )
            print(f"✓ Column renamed")
        
        elif parsed['action'] == 'MODIFY_COLUMN':
            AlterTableEngine.modify_column(
                table,
                parsed['params']['column_name'],
                parsed['params']['type'],
                parsed['params']['length']
            )
            print(f"✓ Column modified")
        
        elif parsed['action'] == 'RENAME_TABLE':
            old_name = table.name
            AlterTableEngine.rename_table(table, parsed['params']['new_name'])
            # Mettre à jour dans la database
            db.tables[parsed['params']['new_name']] = db.tables.pop(old_name)
            print(f"✓ Table renamed to '{parsed['params']['new_name']}'")
        
        self.save_database(self.current_db)
        return
    '''
    
    return code_example


# ============================================================================
# EXEMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EXEMPLES : ALTER TABLE")
    print("=" * 80)
    
    print("""
-- Ajouter une colonne
ALTER TABLE users ADD COLUMN age INT DEFAULT 0;
ALTER TABLE users ADD phone VARCHAR(20);

-- Supprimer une colonne
ALTER TABLE users DROP COLUMN age;

-- Renommer une colonne
ALTER TABLE users RENAME COLUMN email TO email_address;

-- Modifier le type d'une colonne
ALTER TABLE users MODIFY COLUMN name VARCHAR(100);

-- Renommer la table
ALTER TABLE users RENAME TO customers;

-- Ajouter une contrainte
ALTER TABLE users ADD CONSTRAINT check_age CHECK (age >= 18);
    """)