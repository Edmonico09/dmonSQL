from datetime import datetime
from dmonSQL.utils.logger import get_logger
from dmonSQL.core.table import Table
from typing import Dict
try:
    from dmonSQL.core.transaction_manager import TransactionManager
    TRANSACTIONS_AVAILABLE = True
except ImportError:
    TRANSACTIONS_AVAILABLE = False

# try:
#     from dmonSQL.procedures.procedure import ProcedureManager
#     PROCEDURES_AVAILABLE = True
# except ImportError:
#     PROCEDURES_AVAILABLE = False

# try:
#     from dmonSQL.procedures.trigger import TriggerManager
#     TRIGGERS_AVAILABLE = True
# except ImportError:
#     TRIGGERS_AVAILABLE = False

try:
    from dmonSQL.query.optimizer import QueryOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False
    
class Database:
    """Base de données améliorée"""
    
    def __init__(self, name: str):
        self.name = name
        self.tables = {}
        self.created_at = datetime.now()
        self.last_modified = datetime.now()
        
        # Gestionnaires optionnels
        # if PROCEDURES_AVAILABLE:
        #     self.procedure_manager = ProcedureManager()
        
        # if TRIGGERS_AVAILABLE:
        #     self.trigger_manager = TriggerManager()
    
    def create_table(self, table: Table):
        """Crée une table"""
        if table.name in self.tables:
            raise ValueError(f"Table {table.name} already exists")
        
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
            'name': "univ",
            # 'name': self.name,
            'tables': len(self.tables),
            'total_rows': total_rows,
            'total_indexes': total_indexes,
            'created_at': self.created_at.isoformat(),
            'last_modified': self.last_modified.isoformat()
        }
