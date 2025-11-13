"""
dmonSQL - Système de Gestion de Base de Données Relationnelle
Version Améliorée - Compatible tous OS
Inspiré de MySQL avec extensions (Matrix, Email, JSON, Division)
"""

import numpy as np
import pickle
import os
import re
import json
import csv
import shutil
from datetime import datetime
from typing import Any, List, Dict, Tuple, Optional, Union
from pathlib import Path
import hashlib
import logging


# ==================== LOGGING ====================

def get_logger(name: str = "dmonSQL") -> logging.Logger:
    """Retourne un logger configuré"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


# ==================== HELPERS ====================

def format_size(size_bytes: int) -> str:
    """Formate une taille en bytes en format lisible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """Formate une durée en secondes"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f} µs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.2f} s"


# ==================== DATA TYPES ====================

class DataType:
    """Types de données supportés"""
    INT = "INT"
    FLOAT = "FLOAT"
    VARCHAR = "VARCHAR"
    TEXT = "TEXT"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    MATRIX = "MATRIX"
    EMAIL = "EMAIL"
    JSON = "JSON"


class EmailValidator:
    """Validateur d'emails"""
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    @staticmethod
    def is_valid(email: str) -> bool:
        if not isinstance(email, str):
            return False
        return EmailValidator.EMAIL_REGEX.match(email) is not None


class EmailType:
    """Type EMAIL avec validation"""
    def __init__(self, email: str):
        if not EmailValidator.is_valid(email):
            raise ValueError(f"Invalid email: {email}")
        self.email = email
    
    def __str__(self):
        return self.email
    
    def __repr__(self):
        return f"Email('{self.email}')"
    
    def __eq__(self, other):
        if isinstance(other, EmailType):
            return self.email == other.email
        return False


class MatrixType:
    """Gestion des matrices numpy"""
    def __init__(self, data):
        if isinstance(data, np.ndarray):
            self.matrix = data
        elif isinstance(data, (list, tuple)):
            self.matrix = np.array(data)
        else:
            raise ValueError("Matrix doit être un numpy array ou une liste")
    
    @property
    def shape(self):
        return self.matrix.shape
    
    def __repr__(self):
        return f"Matrix{self.matrix.shape}:\n{self.matrix}"
    
    def __str__(self):
        return f"Matrix{self.shape}"
    
    def __eq__(self, other):
        if isinstance(other, MatrixType):
            return np.array_equal(self.matrix, other.matrix)
        return False


class JSONType:
    """Type JSON natif"""
    def __init__(self, data):
        if isinstance(data, str):
            self.data = json.loads(data)
        elif isinstance(data, (dict, list)):
            self.data = data
        elif isinstance(data, JSONType):
            self.data = data.data
        else:
            raise ValueError(f"Invalid JSON data: {type(data)}")
    
    def __repr__(self):
        return f"JSON({json.dumps(self.data, indent=2)})"
    
    def __str__(self):
        return json.dumps(self.data)
    
    def __eq__(self, other):
        if isinstance(other, JSONType):
            return self.data == other.data
        return False
    
    def get(self, path: str, default=None):
        """Récupère une valeur par chemin JSON (ex: 'user.address.city')"""
        keys = path.split('.')
        current = self.data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
            
            if current is None:
                return default
        
        return current


# ==================== CONSTRAINTS ====================

class Constraint:
    """Classe de base pour les contraintes"""
    def __init__(self, name: str):
        self.name = name
    
    def validate(self, row: Dict, table=None, db=None) -> bool:
        raise NotImplementedError


class NotNullConstraint(Constraint):
    """Contrainte NOT NULL"""
    def __init__(self, name: str, column: str):
        super().__init__(name)
        self.column = column
    
    def validate(self, row: Dict, table=None, db=None) -> bool:
        if row.get(self.column) is None:
            raise ValueError(f"Column {self.column} cannot be NULL")
        return True


class ForeignKeyConstraint(Constraint):
    """Contrainte FOREIGN KEY"""
    def __init__(self, name: str, column: str, ref_table: str, ref_column: str):
        super().__init__(name)
        self.column = column
        self.ref_table = ref_table
        self.ref_column = ref_column
    
    def validate(self, row: Dict, table=None, db=None) -> bool:
        value = row.get(self.column)
        
        # NULL est accepté pour les foreign keys (sauf si NOT NULL)
        if value is None:
            return True
        
        # Vérifier que la table référencée existe
        if db is None:
            raise ValueError(f"Database context required for foreign key validation")
        
        try:
            ref_table = db.get_table(self.ref_table)
        except ValueError:
            raise ValueError(f"Referenced table '{self.ref_table}' does not exist")
        
        # Vérifier que la valeur existe dans la table référencée
        exists = any(
            ref_row.get(self.ref_column) == value 
            for ref_row in ref_table.rows
        )
        
        if not exists:
            raise ValueError(
                f"Foreign key constraint failed: value {value} not found in "
                f"{self.ref_table}({self.ref_column})"
            )
        
        return True


class ConstraintManager:
    """Gestionnaire de contraintes"""
    def __init__(self):
        self.constraints = []
        self.foreign_keys = []
    
    def add_constraint(self, constraint: Constraint):
        self.constraints.append(constraint)
        if isinstance(constraint, ForeignKeyConstraint):
            self.foreign_keys.append(constraint)
    
    def validate_row(self, row: Dict, table=None, db=None):
        for constraint in self.constraints:
            constraint.validate(row, table, db)


# ==================== COLUMN ====================

class Column:
    """Définition d'une colonne"""
    def __init__(self, name: str, dtype: str, length: int = None, 
                 nullable: bool = True, primary_key: bool = False,
                 auto_increment: bool = False, unique: bool = False,
                 default=None):
        self.name = name
        self.dtype = dtype
        self.length = length
        self.nullable = nullable
        self.primary_key = primary_key
        self.auto_increment = auto_increment
        self.unique = unique
        self.default = default
        
    def validate(self, value):
        """Valide une valeur selon le type de colonne"""
        if value is None:
            if not self.nullable and not self.auto_increment:
                raise ValueError(f"Column {self.name} cannot be NULL")
            return None
        
        if self.dtype == DataType.INT:
            return int(value)
        elif self.dtype == DataType.FLOAT:
            return float(value)
        elif self.dtype == DataType.VARCHAR:
            s = str(value)
            if self.length and len(s) > self.length:
                raise ValueError(f"VARCHAR exceeds length {self.length}")
            return s
        elif self.dtype == DataType.TEXT:
            return str(value)
        elif self.dtype == DataType.DATE:
            if isinstance(value, str):
                return datetime.strptime(value, "%Y-%m-%d").date()
            return value
        elif self.dtype == DataType.DATETIME:
            if isinstance(value, str):
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return value
        elif self.dtype == DataType.BOOLEAN:
            return bool(value)
        elif self.dtype == DataType.EMAIL:
            if isinstance(value, EmailType):
                return value
            return EmailType(value)
        elif self.dtype == DataType.MATRIX:
            if isinstance(value, MatrixType):
                return value
            return MatrixType(value)
        elif self.dtype == DataType.JSON:
            if isinstance(value, JSONType):
                return value
            return JSONType(value)
        
        return value


# ==================== INDEX ====================

class Index:
    """Index pour accélérer les recherches"""
    def __init__(self, name: str, columns: List[str], unique: bool = False):
        self.name = name
        self.columns = columns
        self.unique = unique
        self.index_data = {}
    
    def build(self, rows: List[Dict]):
        """Construit l'index"""
        self.index_data.clear()
        for idx, row in enumerate(rows):
            key = tuple(row.get(col) for col in self.columns)
            if self.unique and key in self.index_data:
                raise ValueError(f"Duplicate key in unique index: {key}")
            if key not in self.index_data:
                self.index_data[key] = []
            self.index_data[key].append(idx)
    
    def search(self, key_values: Tuple) -> List[int]:
        """Recherche dans l'index"""
        return self.index_data.get(key_values, [])


# ==================== TABLE ====================

class Table:
    """Table de base de données"""
    def __init__(self, name: str, columns: List[Column], database=None):
        self.name = name
        self.columns = {col.name: col for col in columns}
        self.rows = []
        self.indexes = {}
        self.auto_increment_counters = {}
        self.constraint_manager = ConstraintManager()
        self.created_at = datetime.now()
        self.row_count_history = []
        self.database = database  # Référence à la base de données
        
        # Initialiser les compteurs auto-increment
        for col_name, col in self.columns.items():
            if col.auto_increment:
                self.auto_increment_counters[col_name] = 0
            
            # Ajouter contrainte NOT NULL si nécessaire
            if not col.nullable and not col.primary_key and not col.auto_increment:
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
        
        # Valider les contraintes (inclut les foreign keys)
        self.constraint_manager.validate_row(row, self, self.database)
        
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
                for col_name, value in values.items():
                    if col_name in self.columns:
                        row[col_name] = self.columns[col_name].validate(value)
                
                # Valider les contraintes (inclut les foreign keys)
                self.constraint_manager.validate_row(row, self, self.database)
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
            'foreign_keys': len(self.constraint_manager.foreign_keys),
            'created_at': self.created_at.isoformat(),
            'size_estimate': len(self.rows) * len(self.columns) * 50
        }


# ==================== DATABASE ====================

class Database:
    """Base de données"""
    def __init__(self, name: str):
        self.name = name
        self.tables = {}
        self.created_at = datetime.now()
        self.last_modified = datetime.now()
    
    def create_table(self, table: Table):
        """Crée une table"""
        if table.name in self.tables:
            raise ValueError(f"Table {table.name} already exists")
        
        # Lier la table à la base de données
        table.database = self
        
        self.tables[table.name] = table
        self.last_modified = datetime.now()
        get_logger().info(f"Table '{table.name}' created in database '{self.name}'")
    
    def drop_table(self, table_name: str):
        """Supprime une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        del self.tables[table_name]
        self.last_modified = datetime.now()
        get_logger().info(f"Table '{table_name}' dropped from database '{self.name}'")
    
    def get_table(self, table_name: str) -> Table:
        """Récupère une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        return self.tables[table_name]
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques de la base"""
        total_rows = sum(len(table.rows) for table in self.tables.values())
        total_indexes = sum(len(table.indexes) for table in self.tables.values())
        
        return {
            'name': self.name,
            'tables': len(self.tables),
            'total_rows': total_rows,
            'total_indexes': total_indexes,
            # 'created_at': self.created_at.isoformat(),
            # 'last_modified': self.last_modified.isoformat()
        }


# ==================== RELATIONAL ALGEBRA ====================

class RelationalAlgebra:
    """Opérations d'algèbre relationnelle"""
    
    @staticmethod
    def projection(table: Table, columns: List[str]) -> List[Dict]:
        """Projection (SELECT colonnes)"""
        return table.select(columns=columns)
    
    @staticmethod
    def selection(table: Table, condition: callable) -> List[Dict]:
        """Sélection (WHERE)"""
        return table.select(where=condition)
    
    @staticmethod
    def cross_product(table1: Table, table2: Table) -> List[Dict]:
        """Produit cartésien"""
        result = []
        for row1 in table1.rows:
            for row2 in table2.rows:
                combined = {}
                for k, v in row1.items():
                    combined[f"{table1.name}.{k}"] = v
                for k, v in row2.items():
                    combined[f"{table2.name}.{k}"] = v
                result.append(combined)
        return result
    
    @staticmethod
    def join(table1: Table, table2: Table, on: Tuple[str, str]) -> List[Dict]:
        """Jointure naturelle"""
        col1, col2 = on
        result = []
        
        for row1 in table1.rows:
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    combined = {}
                    for k, v in row1.items():
                        combined[k] = v
                    for k, v in row2.items():
                        if k not in combined:
                            combined[k] = v
                    result.append(combined)
        
        return result
    
    @staticmethod
    def union(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
        """Union"""
        result = list(rows1)
        for row in rows2:
            if row not in result:
                result.append(row)
        return result
    
    @staticmethod
    def difference(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
        """Différence"""
        return [row for row in rows1 if row not in rows2]
    
    @staticmethod
    def division(dividend_table: Table, divisor_table: Table, 
                 common_attrs: List[str], dividend_attrs: List[str]) -> List[Dict]:
        """Division relationnelle"""
        divisor_tuples = []
        for row in divisor_table.rows:
            divisor_tuple = tuple(row[attr] for attr in common_attrs)
            divisor_tuples.append(divisor_tuple)
        
        if not divisor_tuples:
            return []
        
        groups = {}
        for row in dividend_table.rows:
            key = tuple(row[attr] for attr in dividend_attrs)
            if key not in groups:
                groups[key] = []
            value = tuple(row[attr] for attr in common_attrs)
            if value not in groups[key]:
                groups[key].append(value)
        
        result = []
        for key, values in groups.items():
            if all(divisor_tuple in values for divisor_tuple in divisor_tuples):
                result_dict = {dividend_attrs[i]: key[i] for i in range(len(dividend_attrs))}
                result.append(result_dict)
        
        return result


# ==================== QUERY PARSER ====================

class QueryParser:
    """Parseur SQL basique"""
    
    @staticmethod
    def parse_create_table(sql: str) -> Tuple[str, List[Column], List[Tuple]]:
        """Parse CREATE TABLE avec support des FOREIGN KEY"""
        match = re.match(r'CREATE\s+TABLE\s+(\w+)\s*\((.*)\)', sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError("Invalid CREATE TABLE syntax")
        
        table_name = match.group(1)
        table_def = match.group(2)
        
        columns = []
        foreign_keys = []
        
        # Séparer les éléments par virgules (attention aux parenthèses imbriquées)
        elements = []
        current = ""
        paren_depth = 0
        
        for char in table_def:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                elements.append(current.strip())
                current = ""
                continue
            current += char
        
        if current.strip():
            elements.append(current.strip())
        
        # Parser chaque élément
        for element in elements:
            element_upper = element.upper().strip()
            
            # Vérifier si c'est une FOREIGN KEY - IGNORER complètement
            if element_upper.startswith('FOREIGN KEY'):
                # FOREIGN KEY (col) REFERENCES table(ref_col)
                fk_match = re.match(
                    r'FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)',
                    element,
                    re.IGNORECASE
                )
                if fk_match:
                    col = fk_match.group(1)
                    ref_table = fk_match.group(2)
                    ref_col = fk_match.group(3)
                    foreign_keys.append((col, ref_table, ref_col))
                # NE PAS créer de colonne pour FOREIGN KEY
                continue
            
            # Sinon c'est une colonne
            parts = element.split()
            
            if len(parts) < 2:
                continue
            
            col_name = parts[0]
            col_type = parts[1].upper()
            
            length = None
            if '(' in col_type:
                col_type, length_str = col_type.split('(')
                length = int(length_str.rstrip(')'))
            
            nullable = 'NOT NULL' not in element_upper
            primary_key = 'PRIMARY KEY' in element_upper
            auto_increment = 'AUTO_INCREMENT' in element_upper
            unique = 'UNIQUE' in element_upper
            
            columns.append(Column(col_name, col_type, length, nullable, 
                                primary_key, auto_increment, unique))
        
        return table_name, columns, foreign_keys


# ==================== FILE MANAGER ====================

class FileManager:
    """Gestionnaire de fichiers"""
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
    
    def get_database_path(self, db_name: str) -> Path:
        """Retourne le chemin d'une base de données"""
        return self.data_dir / f"{db_name}.db"
    
    def delete_database(self, db_name: str):
        """Supprime le fichier d'une base de données"""
        db_file = self.get_database_path(db_name)
        if db_file.exists():
            db_file.unlink()
    
    def get_database_size(self, db_name: str) -> int:
        """Retourne la taille d'une base de données"""
        db_file = self.get_database_path(db_name)
        if db_file.exists():
            return db_file.stat().st_size
        return 0
    
    def list_databases(self) -> List[str]:
        """Liste toutes les bases de données"""
        return [f.stem for f in self.data_dir.glob("*.db")]


class DatabaseSerializer:
    """Sérialiseur de bases de données"""
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
    
    def save_database(self, db_name: str, database: Database):
        """Sauvegarde une base de données"""
        db_file = self.file_manager.get_database_path(db_name)
        with open(db_file, 'wb') as f:
            pickle.dump(database, f)
    
    def load_database(self, db_name: str) -> Database:
        """Charge une base de données"""
        db_file = self.file_manager.get_database_path(db_name)
        with open(db_file, 'rb') as f:
            return pickle.load(f)


# ==================== DMONSQL SYSTEM ====================

class DmonSQL:
    """Système de gestion de base de données principal"""
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        self.data_dir = Path(data_dir)
        self.databases = {}
        self.current_db = None
        
        # Initialiser les gestionnaires
        self.file_manager = FileManager(str(self.data_dir))
        self.serializer = DatabaseSerializer(self.file_manager)
        self.logger = get_logger("dmonSQL")
        self.parser = QueryParser()
        
        # Charger les bases de données existantes
        self.load_databases()
        
        self.logger.info(f"dmonSQL initialized with data directory: {self.data_dir}")
    
    def create_database(self, name: str):
        """Crée une base de données"""
        if name in self.databases:
            raise ValueError(f"Database {name} already exists")
        
        db = Database(name)
        self.databases[name] = db
        self.save_database(name)
        
        self.logger.info(f"Database '{name}' created")
        print(f"✓ Database '{name}' created successfully")
    
    def drop_database(self, name: str):
        """Supprime une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        del self.databases[name]
        self.file_manager.delete_database(name)
        
        self.logger.info(f"Database '{name}' dropped")
        print(f"✓ Database '{name}' dropped successfully")
    
    def use_database(self, name: str):
        """Sélectionne une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        self.current_db = name
        
        self.logger.info(f"Using database '{name}'")
        print(f"✓ Using database '{name}'")
    
    def execute(self, sql: str) -> Any:
        """Exécute une requête SQL"""
        sql = sql.strip()
        start_time = datetime.now()
        
        try:
            result = self._execute_internal(sql)
            
            # Logger les performances
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Query executed in {format_duration(duration)}: {sql[:50]}...")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query failed: {sql[:50]}... - Error: {e}")
            raise
    
    def _execute_internal(self, sql: str) -> Any:
        """Exécution interne des requêtes"""
        sql_upper = sql.upper()
        
        # CREATE DATABASE
        if sql_upper.startswith('CREATE DATABASE'):
            match = re.match(r'CREATE\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.create_database(match.group(1))
                return
        
        # DROP DATABASE
        if sql_upper.startswith('DROP DATABASE'):
            match = re.match(r'DROP\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.drop_database(match.group(1))
                return
        
        # USE DATABASE
        if sql_upper.startswith('USE'):
            match = re.match(r'USE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.use_database(match.group(1))
                return
        
        # Vérifier qu'une base est sélectionnée
        if not self.current_db:
            raise ValueError("No database selected. Use 'USE database_name'")
        
        db = self.databases[self.current_db]
        
        # CREATE TABLE
        if sql_upper.startswith('CREATE TABLE'):
            table_name, columns, foreign_keys = self.parser.parse_create_table(sql)
            table = Table(table_name, columns)
            
            # Ajouter les contraintes de clé étrangère
            for col, ref_table, ref_col in foreign_keys:
                fk_name = f"fk_{table_name}_{col}_{ref_table}_{ref_col}"
                fk_constraint = ForeignKeyConstraint(fk_name, col, ref_table, ref_col)
                table.constraint_manager.add_constraint(fk_constraint)
            
            db.create_table(table)
            self.save_database(self.current_db)
            
            if foreign_keys:
                print(f"✓ Table '{table_name}' created with {len(foreign_keys)} foreign key(s)")
            else:
                print(f"✓ Table '{table_name}' created successfully")
            return
        
        # DROP TABLE
        if sql_upper.startswith('DROP TABLE'):
            match = re.match(r'DROP\s+TABLE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                db.drop_table(table_name)
                self.save_database(self.current_db)
                print(f"✓ Table '{table_name}' dropped successfully")
                return
        
        # CREATE INDEX
        if sql_upper.startswith('CREATE INDEX'):
            match = re.match(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((.*?)\)', 
                           sql, re.IGNORECASE)
            if match:
                index_name = match.group(1)
                table_name = match.group(2)
                columns = [c.strip() for c in match.group(3).split(',')]
                unique = 'UNIQUE' in sql_upper
                
                table = db.get_table(table_name)
                table.create_index(index_name, columns, unique)
                self.save_database(self.current_db)
                print(f"✓ Index '{index_name}' created successfully")
                return
        
        # INSERT avec support multiple VALUES
        if sql_upper.startswith('INSERT'):
            match = re.match(r'INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*(.*)', 
                           sql, re.IGNORECASE | re.DOTALL)
            if match:
                table_name = match.group(1)
                columns = [c.strip() for c in match.group(2).split(',')]
                values_str = match.group(3)
                
                table = db.get_table(table_name)
                
                # Parser multiple VALUES
                value_tuples = re.findall(r'\(([^)]*)\)', values_str)
                
                inserted_count = 0
                for value_tuple in value_tuples:
                    values = []
                    for val in re.findall(r"'[^']*'|[^,]+", value_tuple):
                        val = val.strip()
                        if val.startswith("'") and val.endswith("'"):
                            values.append(val[1:-1])
                        elif val.upper() == 'NULL':
                            values.append(None)
                        else:
                            try:
                                values.append(int(val))
                            except:
                                try:
                                    values.append(float(val))
                                except:
                                    values.append(val)
                    
                    values_dict = dict(zip(columns, values))
                    table.insert(values_dict)
                    inserted_count += 1
                
                self.save_database(self.current_db)
                print(f"✓ {inserted_count} row(s) inserted")
                return inserted_count
        
        # SELECT
        if sql_upper.startswith('SELECT'):
            return self._execute_select(sql, db)
        
        # UPDATE
        if sql_upper.startswith('UPDATE'):
            return self._execute_update(sql, db)
        
        # DELETE
        if sql_upper.startswith('DELETE'):
            return self._execute_delete(sql, db)
        
        # SHOW STATS
        if sql_upper == 'SHOW STATS':
            self._show_statistics(db)
            return
        
        raise ValueError(f"Unsupported SQL statement: {sql}")
    
    def _execute_select(self, sql: str, db: Database):
        """Exécute un SELECT avec support des JOIN"""
        # Vérifier s'il y a un JOIN
        if 'JOIN' in sql.upper():
            return self._execute_select_with_join(sql, db)
        
        # SELECT simple sans JOIN
        match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        
        columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        result = table.select(columns=columns, where=where_func)
        self._print_result(result)
        return result
    
    def _execute_select_with_join(self, sql: str, db: Database):
        """Exécute un SELECT avec JOIN"""
        # Pattern pour INNER JOIN, LEFT JOIN, RIGHT JOIN
        # SELECT cols FROM table1 [INNER|LEFT|RIGHT] JOIN table2 ON table1.col = table2.col [WHERE ...]
        
        pattern = r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+AS\s+(\w+))?\s+(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|JOIN)\s+(\w+)(?:\s+AS\s+(\w+))?\s+ON\s+([\w.]+)\s*=\s*([\w.]+)(?:\s+WHERE\s+(.*))?'
        
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError(
                "Invalid JOIN syntax. Use: SELECT cols FROM table1 JOIN table2 ON table1.col = table2.col"
            )
        
        columns_str = match.group(1).strip()
        table1_name = match.group(2)
        table1_alias = match.group(3) or table1_name
        join_type = match.group(4).upper()
        table2_name = match.group(5)
        table2_alias = match.group(6) or table2_name
        join_col1 = match.group(7)
        join_col2 = match.group(8)
        where_clause = match.group(9)
        
        # Récupérer les tables
        table1 = db.get_table(table1_name)
        table2 = db.get_table(table2_name)
        
        # Extraire les noms de colonnes pour la jointure
        # Gérer table.col ou juste col
        if '.' in join_col1:
            t1_alias, col1 = join_col1.split('.')
        else:
            col1 = join_col1
        
        if '.' in join_col2:
            t2_alias, col2 = join_col2.split('.')
        else:
            col2 = join_col2
        
        # Effectuer la jointure
        if join_type in ['JOIN', 'INNER JOIN']:
            result = self._inner_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'LEFT JOIN':
            result = self._left_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'RIGHT JOIN':
            result = self._right_join(table1, table2, col1, col2, table1_alias, table2_alias)
        else:
            raise ValueError(f"Unsupported join type: {join_type}")
        
        # Appliquer WHERE si présent
        if where_clause:
            where_func = self._parse_where_join(where_clause)
            result = [row for row in result if where_func(row)]
        
        # Projeter les colonnes demandées
        if columns_str != '*':
            requested_cols = [c.strip() for c in columns_str.split(',')]
            result = self._project_columns(result, requested_cols)
        
        self._print_result(result)
        return result
    
    def _inner_join(self, table1: Table, table2: Table, col1: str, col2: str, 
                    alias1: str, alias2: str) -> List[Dict]:
        """Effectue un INNER JOIN"""
        result = []
        for row1 in table1.rows:
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    combined = {}
                    # Préfixer les colonnes avec les alias
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
        return result
    
    def _left_join(self, table1: Table, table2: Table, col1: str, col2: str,
                   alias1: str, alias2: str) -> List[Dict]:
        """Effectue un LEFT JOIN"""
        result = []
        for row1 in table1.rows:
            matched = False
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    combined = {}
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
                    matched = True
            
            # Si aucune correspondance, ajouter avec NULL pour table2
            if not matched:
                combined = {}
                for k, v in row1.items():
                    combined[f"{alias1}.{k}"] = v
                for k in table2.columns.keys():
                    combined[f"{alias2}.{k}"] = None
                result.append(combined)
        
        return result
    
    def _right_join(self, table1: Table, table2: Table, col1: str, col2: str,
                    alias1: str, alias2: str) -> List[Dict]:
        """Effectue un RIGHT JOIN"""
        # RIGHT JOIN = LEFT JOIN inversé
        return self._left_join(table2, table1, col2, col1, alias2, alias1)
    
    def _parse_where_join(self, where_clause: str) -> callable:
        """Parse WHERE pour les jointures (avec préfixes table.)"""
        match = re.match(r'([\w.]+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause")
        
        col = match.group(1)  # Peut être table.col
        op = match.group(2)
        val = match.group(3).strip().strip("'")
        
        try:
            val = int(val)
        except:
            try:
                val = float(val)
            except:
                pass
        
        if op == '=':
            return lambda row: row.get(col) == val
        elif op == '>':
            return lambda row: row.get(col) > val
        elif op == '<':
            return lambda row: row.get(col) < val
        elif op == '>=':
            return lambda row: row.get(col) >= val
        elif op == '<=':
            return lambda row: row.get(col) <= val
        elif op == '!=':
            return lambda row: row.get(col) != val
    
    def _project_columns(self, rows: List[Dict], columns: List[str]) -> List[Dict]:
        """Projette seulement les colonnes demandées"""
        result = []
        for row in rows:
            projected = {}
            for col in columns:
                # Gérer table.col ou juste col
                if col in row:
                    projected[col] = row[col]
                else:
                    # Chercher avec préfixe
                    for key in row.keys():
                        if key.endswith(f".{col}"):
                            projected[key] = row[key]
                            break
            result.append(projected)
        return result
    
    def _execute_update(self, sql: str, db: Database):
        """Exécute un UPDATE"""
        match = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        
        # Parser SET
        values = {}
        for assignment in set_clause.split(','):
            col, val = assignment.split('=')
            col = col.strip()
            val = val.strip().strip("'")
            values[col] = val
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        count = table.update(values, where=where_func)
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) updated")
        return count
    
    def _execute_delete(self, sql: str, db: Database):
        """Exécute un DELETE"""
        match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid DELETE syntax")
        
        table_name = match.group(1)
        where_clause = match.group(2)
        
        table = db.get_table(table_name)
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        count = table.delete(where=where_func)
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) deleted")
        return count
    
    def _parse_where(self, where_clause: str) -> callable:
        """Parse une clause WHERE simple"""
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause")
        
        col = match.group(1)
        op = match.group(2)
        val = match.group(3).strip().strip("'")
        
        try:
            val = int(val)
        except:
            try:
                val = float(val)
            except:
                pass
        
        if op == '=':
            return lambda row: row.get(col) == val
        elif op == '>':
            return lambda row: row.get(col) > val
        elif op == '<':
            return lambda row: row.get(col) < val
        elif op == '>=':
            return lambda row: row.get(col) >= val
        elif op == '<=':
            return lambda row: row.get(col) <= val
        elif op == '!=':
            return lambda row: row.get(col) != val
    
    def _print_result(self, result: List[Dict]):
        """Affiche un résultat formaté"""
        if not result:
            print("\n🔭 Empty set (0 rows)")
            return
        
        # Afficher les colonnes
        columns = list(result[0].keys())
        col_widths = {col: max(len(col), 15) for col in columns}
        
        # Ajuster les largeurs selon les données
        for row in result[:10]:
            for col in columns:
                val = str(row.get(col, ''))[:50]
                col_widths[col] = max(col_widths[col], len(val))
        
        # Header
        header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
        print(f"\n{header}")
        print("-" * len(header))
        
        # Lignes
        for row in result:
            values = []
            for col in columns:
                val = row.get(col)
                if isinstance(val, MatrixType):
                    val_str = f"Matrix{val.shape}"
                elif isinstance(val, JSONType):
                    val_str = str(val)[:50]
                elif isinstance(val, EmailType):
                    val_str = str(val)
                else:
                    val_str = str(val) if val is not None else "NULL"
                
                values.append(val_str[:col_widths[col]])
            
            print(" | ".join(f"{val:<{col_widths[col]}}" for val in values))
        
        print(f"\n✓ {len(result)} row(s) in set\n")
    
    def _show_statistics(self, db: Database):
        """Affiche les statistiques de la base"""
        stats = db.get_statistics()
        
        print(f"\n📊 Database Statistics: {db.name}")
        print("=" * 60)
        print(f"Tables: {stats['tables']}")
        print(f"Total rows: {stats['total_rows']:,}")
        print(f"Total indexes: {stats['total_indexes']}")
        print(f"Created: {stats['created_at']}")
        print(f"Last modified: {stats['last_modified']}")
        
        # Taille estimée
        db_size = self.file_manager.get_database_size(db.name)
        if db_size > 0:
            print(f"Size on disk: {format_size(db_size)}")
        
        print("\nTables:")
        for table_name, table in db.tables.items():
            table_stats = table.get_statistics()
            print(f"  • {table_name}: {table_stats['rows']} rows, "
                  f"{table_stats['indexes']} indexes")
        
        print("=" * 60 + "\n")
    
    def save_database(self, db_name: str):
        """Sauvegarde une base de données"""
        if db_name not in self.databases:
            return
        
        try:
            self.serializer.save_database(db_name, self.databases[db_name])
            self.logger.debug(f"Database '{db_name}' saved")
        except Exception as e:
            self.logger.error(f"Failed to save database '{db_name}': {e}")
            raise
    
    def load_databases(self):
        """Charge toutes les bases de données"""
        db_names = self.file_manager.list_databases()
        
        for db_name in db_names:
            try:
                self.databases[db_name] = self.serializer.load_database(db_name)
                self.logger.debug(f"Database '{db_name}' loaded")
            except Exception as e:
                self.logger.warning(f"Could not load database '{db_name}': {e}")
    
    def show_databases(self):
        """Affiche les bases de données"""
        if not self.databases:
            print("\n🔭 No databases found")
            return
        
        print(f"\n📚 Databases ({len(self.databases)}):")
        print("-" * 60)
        
        for db_name in sorted(self.databases.keys()):
            current = "◀" if db_name == self.current_db else " "
            db_size = self.file_manager.get_database_size(db_name)
            size_str = format_size(db_size) if db_size > 0 else "N/A"
            
            db = self.databases[db_name]
            table_count = len(db.tables)
            
            print(f"  {current} {db_name:<20} ({table_count} tables, {size_str})")
        
        print("-" * 60 + "\n")
    
    def show_tables(self):
        """Affiche les tables de la base courante"""
        if not self.current_db:
            print("\n⚠️  No database selected")
            return
        
        db = self.databases[self.current_db]
        
        if not db.tables:
            print(f"\n🔭 No tables in database '{self.current_db}'")
            return
        
        print(f"\n📊 Tables in '{self.current_db}' ({len(db.tables)}):")
        print("-" * 80)
        print(f"{'Table':<20} {'Rows':<12} {'Columns':<12} {'Indexes':<12} {'Size (est.)'}")
        print("-" * 80)
        
        for table_name in sorted(db.tables.keys()):
            table = db.tables[table_name]
            stats = table.get_statistics()
            
            size_str = format_size(stats['size_estimate'])
            
            print(f"{table_name:<20} {stats['rows']:<12} {stats['columns']:<12} "
                  f"{stats['indexes']:<12} {size_str}")
        
        print("-" * 80 + "\n")
    
    def export_to_csv(self, table_name: str, output_file: str):
        """Exporte une table vers un fichier CSV"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if not table.rows:
                return
            
            writer = csv.DictWriter(f, fieldnames=list(table.columns.keys()))
            writer.writeheader()
            
            for row in table.rows:
                row_export = {}
                for col, val in row.items():
                    if isinstance(val, (MatrixType, EmailType, JSONType)):
                        row_export[col] = str(val)
                    else:
                        row_export[col] = val
                writer.writerow(row_export)
        
        print(f"✓ Table '{table_name}' exported to '{output_file}'")
        self.logger.info(f"Table '{table_name}' exported to CSV: {output_file}")
    
    def import_from_csv(self, table_name: str, input_file: str):
        """Importe des données depuis un fichier CSV"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        count = 0
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                filtered_row = {k: v for k, v in row.items() if k in table.columns}
                table.insert(filtered_row)
                count += 1
        
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) imported into '{table_name}'")
        self.logger.info(f"{count} rows imported from CSV: {input_file}")
    
    def backup_database(self, db_name: str, backup_path: str = None):
        """Crée une sauvegarde d'une base de données"""
        if db_name not in self.databases:
            raise ValueError(f"Database {db_name} does not exist")
        
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_name}_backup_{timestamp}.dmon"
        
        # Sauvegarder d'abord la base
        self.save_database(db_name)
        
        # Copier le fichier
        source = self.file_manager.get_database_path(db_name)
        shutil.copy2(source, backup_path)
        
        print(f"✓ Database '{db_name}' backed up to '{backup_path}'")
        self.logger.info(f"Database '{db_name}' backed up to: {backup_path}")
    
    def restore_database(self, backup_path: str, db_name: str = None):
        """Restaure une base de données depuis une sauvegarde"""
        if db_name is None:
            db_name = Path(backup_path).stem.split('_backup_')[0]
        
        # Copier le fichier de backup
        dest = self.file_manager.get_database_path(db_name)
        shutil.copy2(backup_path, dest)
        
        # Recharger la base
        try:
            self.databases[db_name] = self.serializer.load_database(db_name)
            print(f"✓ Database '{db_name}' restored from '{backup_path}'")
            self.logger.info(f"Database '{db_name}' restored from: {backup_path}")
        except Exception as e:
            self.logger.error(f"Failed to restore database: {e}")
            raise
    
    def analyze_query(self, sql: str):
        """Analyse une requête SQL et affiche le plan d'exécution"""
        print(f"\n🔍 Query Analysis:")
        print("=" * 60)
        print(f"Query: {sql}")
        print("-" * 60)
        
        sql_upper = sql.upper()
        
        if 'SELECT' in sql_upper:
            print("Query Type: SELECT")
            if 'WHERE' in sql_upper:
                print("Has WHERE clause: Yes")
            if 'ORDER BY' in sql_upper:
                print("Has ORDER BY: Yes")
            if 'LIMIT' in sql_upper:
                print("Has LIMIT: Yes")
        elif 'INSERT' in sql_upper:
            print("Query Type: INSERT")
        elif 'UPDATE' in sql_upper:
            print("Query Type: UPDATE")
        elif 'DELETE' in sql_upper:
            print("Query Type: DELETE")
        
        print("\n💡 Optimization Suggestions:")
        
        if 'SELECT *' in sql_upper:
            print("  • Consider selecting only needed columns instead of SELECT *")
        
        if 'WHERE' in sql_upper and 'INDEX' not in sql_upper:
            print("  • Consider creating an index on WHERE clause columns")
        
        if 'ORDER BY' in sql_upper:
            print("  • Consider creating an index on ORDER BY columns")
        
        print("=" * 60 + "\n")
    
    def get_table_info(self, table_name: str) -> Dict:
        """Retourne les informations détaillées d'une table"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        info = {
            'name': table.name,
            'columns': {},
            'indexes': {},
            'foreign_keys': {},
            'statistics': table.get_statistics(),
            'primary_keys': table.get_primary_key_columns(),
            'constraints': len(table.constraint_manager.constraints)
        }
        
        for col_name, col in table.columns.items():
            info['columns'][col_name] = {
                'type': col.dtype,
                'length': col.length,
                'nullable': col.nullable,
                'primary_key': col.primary_key,
                'unique': col.unique,
                'auto_increment': col.auto_increment,
                'default': col.default
            }
        
        for idx_name, idx in table.indexes.items():
            info['indexes'][idx_name] = {
                'columns': idx.columns,
                'unique': idx.unique
            }
        
        # Ajouter les informations des foreign keys
        for fk in table.constraint_manager.foreign_keys:
            info['foreign_keys'][fk.name] = {
                'column': fk.column,
                'references': f"{fk.ref_table}({fk.ref_column})"
            }
        
        return info
    
    def execute_batch(self, sql_statements: List[str], stop_on_error: bool = False):
        """Exécute plusieurs requêtes SQL en batch"""
        results = []
        errors = []
        
        print(f"\n🔄 Executing batch of {len(sql_statements)} statements...")
        print("-" * 60)
        
        for i, sql in enumerate(sql_statements, 1):
            try:
                result = self.execute(sql)
                results.append((i, sql, result, None))
                print(f"✓ Statement {i}/{len(sql_statements)} completed")
            except Exception as e:
                errors.append((i, sql, str(e)))
                print(f"✗ Statement {i}/{len(sql_statements)} failed: {e}")
                
                if stop_on_error:
                    print("\n❌ Batch execution stopped due to error")
                    break
        
        print("-" * 60)
        print(f"\n📊 Batch Summary:")
        print(f"  Total: {len(sql_statements)}")
        print(f"  Successful: {len(results)}")
        print(f"  Failed: {len(errors)}")
        
        if errors:
            print(f"\n❌ Errors:")
            for i, sql, error in errors:
                print(f"  Statement {i}: {error}")
        
        return results, errors
    
    def vacuum(self):
        """Optimise et compacte la base de données courante"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        print(f"\n🧹 Vacuuming database '{self.current_db}'...")
        
        db = self.databases[self.current_db]
        
        total_indexes = 0
        for table in db.tables.values():
            for index in table.indexes.values():
                index.build(table.rows)
                total_indexes += 1
        
        self.save_database(self.current_db)
        
        print(f"✓ Database vacuumed: {total_indexes} index(es) rebuilt")
        self.logger.info(f"Database '{self.current_db}' vacuumed")
    
    def explain_table(self, table_name: str):
        """Explique la structure d'une table"""
        info = self.get_table_info(table_name)
        
        print(f"\n📊 Table: {info['name']}")
        print("=" * 80)
        
        print(f"\n📝 Columns ({len(info['columns'])}):")
        print("-" * 80)
        print(f"{'Column':<20} {'Type':<15} {'Null':<8} {'Key':<10} {'Extra'}")
        print("-" * 80)
        
        for col_name, col_info in info['columns'].items():
            null_str = "YES" if col_info['nullable'] else "NO"
            key_str = "PRI" if col_info['primary_key'] else ("UNI" if col_info['unique'] else "")
            extra = []
            if col_info['auto_increment']:
                extra.append("auto_increment")
            if col_info['default'] is not None:
                extra.append(f"default={col_info['default']}")
            extra_str = ", ".join(extra)
            
            type_str = col_info['type']
            if col_info['length']:
                type_str += f"({col_info['length']})"
            
            print(f"{col_name:<20} {type_str:<15} {null_str:<8} {key_str:<10} {extra_str}")
        
        if info['indexes']:
            print(f"\n🔍 Indexes ({len(info['indexes'])}):")
            print("-" * 80)
            for idx_name, idx_info in info['indexes'].items():
                idx_type = "UNIQUE" if idx_info['unique'] else "INDEX"
                cols = ", ".join(idx_info['columns'])
                print(f"  {idx_type}: {idx_name} ON ({cols})")
        
        if info['foreign_keys']:
            print(f"\n🔗 Foreign Keys ({len(info['foreign_keys'])}):")
            print("-" * 80)
            for fk_name, fk_info in info['foreign_keys'].items():
                print(f"  {fk_info['column']} → {fk_info['references']}")
        
        stats = info['statistics']
        print(f"\n📈 Statistics:")
        print("-" * 80)
        print(f"  Rows: {stats['rows']}")
        print(f"  Columns: {stats['columns']}")
        print(f"  Indexes: {stats['indexes']}")
        print(f"  Foreign Keys: {stats['foreign_keys']}")
        print(f"  Estimated size: {format_size(stats['size_estimate'])}")
        print(f"  Created: {stats['created_at']}")
        
        print("=" * 80 + "\n")


# ==================== MAIN ====================

def main():
    """Fonction principale - Interface interactive"""
    print("=" * 70)
    print("dmonSQL - Système de Gestion de Base de Données Relationnelle")
    print("Version Améliorée - Compatible tous OS")
    print("=" * 70)
    print("\nFonctionnalités:")
    print("  ✓ Types standard (INT, FLOAT, VARCHAR, TEXT, DATE, DATETIME, BOOLEAN)")
    print("  ✓ Type MATRIX (matrices NumPy)")
    print("  ✓ Type EMAIL (avec validation)")
    print("  ✓ Type JSON (documents JSON)")
    print("  ✓ Foreign Keys et contraintes")
    print("  ✓ Jointures (INNER, LEFT, RIGHT)")
    print("  ✓ Division relationnelle")
    print("  ✓ Index et clés primaires")
    print("  ✓ Persistence des données")
    print("  ✓ Export/Import CSV")
    print("  ✓ Backup/Restore")
    print("  ✓ Statistiques et analyse")
    print("\nCommandes SQL:")
    print("  CREATE TABLE, DROP TABLE, INSERT INTO, SELECT, UPDATE, DELETE")
    print("  CREATE INDEX, FOREIGN KEY")
    print("  SELECT ... FROM t1 JOIN t2 ON t1.col = t2.col")
    print("\nCommandes système:")
    print("  SHOW DATABASES      - Afficher les bases de données")
    print("  SHOW TABLES         - Afficher les tables")
    print("  SHOW STATS          - Afficher les statistiques")
    print("  EXPLAIN <table>     - Décrire une table")
    print("  ANALYZE <query>     - Analyser une requête")
    print("  VACUUM              - Optimiser la base courante")
    print("  EXIT                - Quitter")
    print("\nExemples de jointures:")
    print("  SELECT * FROM student JOIN mention ON student.mid = mention.id")
    print("  SELECT s.name, m.name FROM student s JOIN mention m ON s.mid = m.id")
    print("  SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.fk_id WHERE t1.val > 10")
    print("=" * 70)
    
    db_system = DmonSQL()
    
    while True:
        try:
            query = input(f"\n{db_system.current_db or 'dmonsql'}> ").strip()
            
            if not query:
                continue
            
            if query.upper() == 'EXIT':
                print("👋 Goodbye!")
                break
            
            if query.upper() == 'SHOW DATABASES':
                db_system.show_databases()
                continue
            
            if query.upper() == 'SHOW TABLES':
                db_system.show_tables()
                continue
            
            if query.upper().startswith('EXPLAIN '):
                table_name = query.split()[1]
                db_system.explain_table(table_name)
                continue
            
            if query.upper().startswith('ANALYZE '):
                sql_to_analyze = query[8:]
                db_system.analyze_query(sql_to_analyze)
                continue
            
            if query.upper() == 'VACUUM':
                db_system.vacuum()
                continue
            
            db_system.execute(query)
            
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted. Type EXIT to quit.")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()