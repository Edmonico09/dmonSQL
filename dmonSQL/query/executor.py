"""
dmonSQL/query/executor.py
Gestionnaire principal d'exécution des requêtes SQL
Orchestre les exécuteurs spécialisés (SELECT, DML, DDL)
"""

import re
from typing import Any
from datetime import datetime

from dmonSQL.core.database import Database
from dmonSQL.query.select_executor import SelectExecutor
from dmonSQL.query.dml_executor import DMLExecutor
from dmonSQL.query.ddl_executor import DDLExecutor
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_duration


class SQLExecutor:
    """Gestionnaire principal d'exécution des requêtes SQL"""
    
    def __init__(self, dmonsql_instance):
        """
        Args:
            dmonsql_instance: Instance de DmonSQL (pour accès aux bases, transaction_manager, etc.)
        """
        self.dmonsql = dmonsql_instance
        self.logger = get_logger("SQLExecutor")
        
        # Sous-exécuteurs spécialisés
        self.select_executor = SelectExecutor(dmonsql_instance)
        self.dml_executor = DMLExecutor(dmonsql_instance)
        self.ddl_executor = DDLExecutor(dmonsql_instance)
    
    def execute(self, sql: str) -> Any:
        """
        Exécute une requête SQL
        
        Args:
            sql: Requête SQL à exécuter
            
        Returns:
            Résultat de la requête
        """
        sql = sql.strip()
        sql_upper = sql.upper()
        
        start_time = datetime.now()
        
        try:
            result = self._route_query(sql, sql_upper)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Query executed in {format_duration(duration)}: {sql[:50]}...")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query failed: {sql[:50]}... - Error: {e}")
            raise
    
    def _route_query(self, sql: str, sql_upper: str) -> Any:
        """Route la requête vers le bon exécuteur"""
        
        # ==================== GESTION DES BASES ====================
        
        if sql_upper.startswith('CREATE DATABASE'):
            return self._execute_create_database(sql)
        
        if sql_upper.startswith('DROP DATABASE'):
            return self._execute_drop_database(sql)
        
        if sql_upper.startswith('USE'):
            return self._execute_use_database(sql)
        
        if sql_upper == 'SHOW DATABASES':
            self.dmonsql.show_databases()
            return
        
        if sql_upper == 'SHOW TABLES':
            self.dmonsql.show_tables()
            return
        
        # ==================== TRANSACTIONS ====================
        
        if hasattr(self.dmonsql, 'transaction_manager') and self.dmonsql.transaction_manager:
            if sql_upper in ('BEGIN TRANSACTION', 'BEGIN', 'START TRANSACTION'):
                return self._execute_begin_transaction()
            
            if sql_upper == 'COMMIT':
                return self._execute_commit()
            
            if sql_upper == 'ROLLBACK':
                return self._execute_rollback()
        
        # ==================== VÉRIFIER BASE SÉLECTIONNÉE ====================
        
        if not self.dmonsql.current_db:
            raise ValueError("No database selected. Use 'USE database_name'")
        
        db = self.dmonsql.databases[self.dmonsql.current_db]
        
        # ==================== VUES ====================
        
        if sql_upper.startswith('CREATE VIEW'):
            return self.dmonsql._execute_create_view(sql)
        
        if sql_upper.startswith('DROP VIEW'):
            return self.dmonsql._execute_drop_view(sql)
        
        if sql_upper == 'SHOW VIEWS':
            return self.dmonsql._execute_show_views()
        
        # ==================== EXPLAIN ====================
        
        if sql_upper.startswith('EXPLAIN'):
            return self.dmonsql._execute_explain(sql)
        
        # ==================== SELECT ====================
        
        if sql_upper.startswith('SELECT'):
            return self.select_executor.execute(sql, db)
        
        # ==================== DDL (CREATE, DROP, ALTER) ====================
        
        if sql_upper.startswith('CREATE TABLE'):
            return self.ddl_executor.execute_create_table(sql, db)
        
        if sql_upper.startswith('DROP TABLE'):
            return self.ddl_executor.execute_drop_table(sql, db)
        
        if sql_upper.startswith('ALTER TABLE'):
            return self.ddl_executor.execute_alter_table(sql, db)
        
        if sql_upper.startswith('CREATE INDEX'):
            return self.ddl_executor.execute_create_index(sql, db)
        
        # ==================== DML (INSERT, UPDATE, DELETE) ====================
        
        if sql_upper.startswith('INSERT'):
            return self.dml_executor.execute_insert(sql, db)
        
        if sql_upper.startswith('UPDATE'):
            return self.dml_executor.execute_update(sql, db)
        
        if sql_upper.startswith('DELETE'):
            return self.dml_executor.execute_delete(sql, db)
        
        # ==================== UTILITAIRES ====================
        
        if sql_upper == 'SHOW STATS':
            self.dmonsql._show_statistics(db)
            return
        
        raise ValueError(f"Unsupported SQL statement: {sql}")
    
    # ==================== GESTION DES BASES ====================
    
    def _execute_create_database(self, sql: str):
        """CREATE DATABASE"""
        match = re.match(r'CREATE\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
        if match:
            self.dmonsql.create_database(match.group(1))
            return
        raise ValueError("Invalid CREATE DATABASE syntax")
    
    def _execute_drop_database(self, sql: str):
        """DROP DATABASE"""
        match = re.match(r'DROP\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
        if match:
            self.dmonsql.drop_database(match.group(1))
            return
        raise ValueError("Invalid DROP DATABASE syntax")
    
    def _execute_use_database(self, sql: str):
        """USE DATABASE"""
        match = re.match(r'USE\s+(\w+)', sql, re.IGNORECASE)
        if match:
            self.dmonsql.use_database(match.group(1))
            return
        raise ValueError("Invalid USE syntax")
    
    # ==================== TRANSACTIONS ====================
    
    def _execute_begin_transaction(self):
        """BEGIN TRANSACTION"""
        if not self.dmonsql.current_db:
            raise ValueError("No database selected")
        
        db = self.dmonsql.databases[self.dmonsql.current_db]
        self.dmonsql.transaction_manager.begin_transaction(db)
        print("✓ Transaction started")
    
    def _execute_commit(self):
        """COMMIT"""
        if not self.dmonsql.transaction_manager.is_in_transaction():
            raise ValueError("No active transaction")
        
        db = self.dmonsql.databases[self.dmonsql.current_db]
        self.dmonsql.transaction_manager.commit_transaction(db)
        self.dmonsql.save_database(self.dmonsql.current_db)
        print("✓ Transaction committed")
    
    def _execute_rollback(self):
        """ROLLBACK"""
        if not self.dmonsql.transaction_manager.is_in_transaction():
            raise ValueError("No active transaction")
        
        db = self.dmonsql.databases[self.dmonsql.current_db]
        self.dmonsql.transaction_manager.rollback_transaction(db)
        print("✓ Transaction rolled back")