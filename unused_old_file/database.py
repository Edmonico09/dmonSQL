
from unused_old_file.table import Table
class Database:
    """Base de données"""
    def __init__(self, name: str):
        self.name = name
        self.tables = {}
    
    def create_table(self, table: Table):
        """Crée une table"""
        if table.name in self.tables:
            raise ValueError(f"Table {table.name} already exists")
        self.tables[table.name] = table
    
    def drop_table(self, table_name: str):
        """Supprime une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        del self.tables[table_name]
    
    def get_table(self, table_name: str) -> Table:
        """Récupère une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        return self.tables[table_name]
