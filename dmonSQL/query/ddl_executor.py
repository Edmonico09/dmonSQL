"""
dmonSQL/query/ddl_executor.py
Exécuteur spécialisé pour CREATE TABLE, DROP TABLE, ALTER TABLE, CREATE INDEX
Gère : Définition de schéma (DDL - Data Definition Language)
"""

import re
from typing import Any

from dmonSQL.core.database import Database
from dmonSQL.core.table import Table
from dmonSQL.core.column import Column
from dmonSQL.utils.logger import get_logger


class DDLExecutor:
    """Exécuteur spécialisé pour les opérations DDL"""
    
    def __init__(self, dmonsql_instance):
        """
        Args:
            dmonsql_instance: Instance de DmonSQL (pour accès aux attributs)
        """
        self.dmonsql = dmonsql_instance
        self.logger = get_logger("DDLExecutor")
    
    # ==================== CREATE TABLE ====================
    
    def execute_create_table(self, sql: str, db: Database):
        """
        Exécute CREATE TABLE
        
        Syntaxe:
            CREATE TABLE table_name (
                col1 TYPE [constraints],
                col2 TYPE [constraints],
                FOREIGN KEY (col) REFERENCES other_table(col)
            )
        
        Args:
            sql: Requête CREATE TABLE
            db: Base de données
        """
        # Parser via QueryParser existant
        result = self.dmonsql.parser.parse_create_table(sql)
        
        if len(result) == 3:
            table_name, columns, foreign_keys = result
        else:
            table_name, columns = result
            foreign_keys = []
        
        # Créer la table
        table = Table(table_name, columns)
        
        # Ajouter les contraintes de clé étrangère
        for fk in foreign_keys:
            table.add_foreign_key(
                column=fk['column'],
                ref_table=fk['ref_table'],
                ref_column=fk['ref_column'],
                on_delete=fk.get('on_delete', 'RESTRICT'),
                on_update=fk.get('on_update', 'RESTRICT')
            )
        
        # Lier la table à la base de données
        table.database = db
        
        # Ajouter la table à la base
        db.create_table(table)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        if foreign_keys:
            print(f"✓ Table '{table_name}' created with {len(foreign_keys)} foreign key(s)")
        else:
            print(f"✓ Table '{table_name}' created successfully")
    
    # ==================== DROP TABLE ====================
    
    def execute_drop_table(self, sql: str, db: Database):
        """
        Exécute DROP TABLE
        
        Syntaxe:
            DROP TABLE table_name
        
        Args:
            sql: Requête DROP TABLE
            db: Base de données
        """
        match = re.match(r'DROP\s+TABLE\s+(\w+)', sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid DROP TABLE syntax")
        
        table_name = match.group(1)
        db.drop_table(table_name)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Table '{table_name}' dropped successfully")
    
    # ==================== ALTER TABLE ====================
    
    def execute_alter_table(self, sql: str, db: Database):
        """
        Exécute ALTER TABLE
        
        Syntaxes supportées:
        - ALTER TABLE table ADD COLUMN col_name data_type [constraints]
        - ALTER TABLE table DROP COLUMN col_name
        - ALTER TABLE table MODIFY COLUMN col_name new_type [constraints]
        - ALTER TABLE table RENAME COLUMN old_name TO new_name
        
        Args:
            sql: Requête ALTER TABLE
            db: Base de données
        """
        sql_upper = sql.upper()
        
        # ADD COLUMN
        if 'ADD COLUMN' in sql_upper or ('ADD' in sql_upper and 'COLUMN' in sql_upper):
            self._execute_add_column(sql, db)
            return
        
        # DROP COLUMN
        if 'DROP COLUMN' in sql_upper or ('DROP' in sql_upper and 'COLUMN' in sql_upper):
            self._execute_drop_column(sql, db)
            return
        
        # MODIFY COLUMN
        if 'MODIFY COLUMN' in sql_upper or 'MODIFY' in sql_upper:
            self._execute_modify_column(sql, db)
            return
        
        # RENAME COLUMN
        if 'RENAME COLUMN' in sql_upper:
            self._execute_rename_column(sql, db)
            return
        
        raise ValueError(f"Unsupported ALTER TABLE syntax: {sql}")
    
    def _execute_add_column(self, sql: str, db: Database):
        """
        ADD COLUMN
        
        Exemples:
            ALTER TABLE users ADD COLUMN age INT DEFAULT 0
            ALTER TABLE users ADD age INT
        """
        match = re.match(
            r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)\s+(.+)',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid ADD COLUMN syntax")
        
        table_name = match.group(1)
        col_name = match.group(2)
        col_def = match.group(3)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser la définition de colonne
        column = self._parse_column_definition(col_name, col_def)
        
        # Extraire DEFAULT si présent
        default_value = None
        if 'DEFAULT' in col_def.upper():
            default_match = re.search(r'DEFAULT\s+(.+?)(?:\s|$)', col_def, re.IGNORECASE)
            if default_match:
                default_value = self._parse_value(default_match.group(1).strip())
        
        # Ajouter la colonne
        table.add_column(column, default_value)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Column '{col_name}' added to table '{table_name}'")
    
    def _execute_drop_column(self, sql: str, db: Database):
        """
        DROP COLUMN
        
        Exemple:
            ALTER TABLE users DROP COLUMN age
        """
        match = re.match(
            r'ALTER\s+TABLE\s+(\w+)\s+DROP\s+(?:COLUMN\s+)?(\w+)',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid DROP COLUMN syntax")
        
        table_name = match.group(1)
        col_name = match.group(2)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Supprimer la colonne
        table.drop_column(col_name)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Column '{col_name}' dropped from table '{table_name}'")
    
    def _execute_modify_column(self, sql: str, db: Database):
        """
        MODIFY COLUMN
        
        Exemple:
            ALTER TABLE users MODIFY COLUMN name VARCHAR(100)
        """
        match = re.match(
            r'ALTER\s+TABLE\s+(\w+)\s+MODIFY\s+(?:COLUMN\s+)?(\w+)\s+(.+)',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid MODIFY COLUMN syntax")
        
        table_name = match.group(1)
        col_name = match.group(2)
        col_def = match.group(3)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser la nouvelle définition
        new_column = self._parse_column_definition(col_name, col_def)
        
        # Modifier la colonne
        table.modify_column(col_name, new_column)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Column '{col_name}' modified in table '{table_name}'")
    
    def _execute_rename_column(self, sql: str, db: Database):
        """
        RENAME COLUMN
        
        Exemple:
            ALTER TABLE users RENAME COLUMN old_name TO new_name
        """
        match = re.match(
            r'ALTER\s+TABLE\s+(\w+)\s+RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid RENAME COLUMN syntax")
        
        table_name = match.group(1)
        old_name = match.group(2)
        new_name = match.group(3)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Renommer la colonne
        table.rename_column(old_name, new_name)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Column renamed in table '{table_name}': '{old_name}' -> '{new_name}'")
    
    # ==================== CREATE INDEX ====================
    
    def execute_create_index(self, sql: str, db: Database):
        """
        Exécute CREATE INDEX
        
        Syntaxe:
            CREATE [UNIQUE] INDEX index_name ON table_name (col1, col2)
        
        Args:
            sql: Requête CREATE INDEX
            db: Base de données
        """
        match = re.match(
            r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((.*?)\)',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid CREATE INDEX syntax")
        
        index_name = match.group(1)
        table_name = match.group(2)
        columns = [c.strip() for c in match.group(3).split(',')]
        unique = 'UNIQUE' in sql.upper()
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Créer l'index
        table.create_index(index_name, columns, unique)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Index '{index_name}' created successfully")
    
    # ==================== HELPERS ====================
    
    def _parse_column_definition(self, col_name: str, col_def: str) -> Column:
        """
        Parse une définition de colonne
        
        Exemple:
            "VARCHAR(50) NOT NULL" -> Column(name, dtype='VARCHAR', length=50, nullable=False)
        """
        
        parts = col_def.strip().split()
        
        dtype = parts[0].upper()
        length = None
        nullable = True
        primary_key = False
        auto_increment = False
        unique = False
        default = None
        
        # Extraire la longueur si présente (ex: VARCHAR(50))
        if '(' in dtype:
            match = re.match(r'(\w+)\((\d+)\)', dtype)
            if match:
                dtype = match.group(1)
                length = int(match.group(2))
        
        # Parser les contraintes
        col_def_upper = col_def.upper()
        
        if 'NOT NULL' in col_def_upper:
            nullable = False
        
        if 'PRIMARY KEY' in col_def_upper:
            primary_key = True
            nullable = False
        
        if 'AUTO_INCREMENT' in col_def_upper:
            auto_increment = True
        
        if 'UNIQUE' in col_def_upper:
            unique = True
        
        if 'DEFAULT' in col_def_upper:
            default_match = re.search(r'DEFAULT\s+(.+?)(?:\s|$)', col_def, re.IGNORECASE)
            if default_match:
                default = self._parse_value(default_match.group(1).strip())
        
        return Column(
            name=col_name,
            dtype=dtype,
            length=length,
            nullable=nullable,
            primary_key=primary_key,
            auto_increment=auto_increment,
            unique=unique,
            default=default
        )
    
    def _parse_value(self, value_str: str) -> Any:
        """
        Parse une valeur depuis une chaîne
        
        Exemples:
            'Alice' -> 'Alice'
            42 -> 42
            NULL -> None
            TRUE -> True
        """
        value_str = value_str.strip()
        
        if value_str.upper() == 'NULL':
            return None
        
        if value_str.upper() in ('TRUE', 'FALSE'):
            return value_str.upper() == 'TRUE'
        
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]
        
        try:
            return int(value_str)
        except ValueError:
            try:
                return float(value_str)
            except ValueError:
                return value_str
    
    def _is_in_transaction(self) -> bool:
        """Vérifie si une transaction est active"""
        return (
            hasattr(self.dmonsql, 'transaction_manager') and
            self.dmonsql.transaction_manager and
            self.dmonsql.transaction_manager.is_in_transaction()
        )