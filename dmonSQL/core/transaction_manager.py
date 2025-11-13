#--------------------------------------#
# /dmonSQL/core/transaction_manager.py #
#--------------------------------------#

"""
Système de transactions ACID pour dmonSQL
Permet BEGIN, COMMIT, ROLLBACK
"""

import copy
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional
from dmonSQL.utils.logger import get_logger


class TransactionState(Enum):
    """États d'une transaction"""
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class Transaction:
    """Représente une transaction"""
    
    def __init__(self, transaction_id: int):
        self.id = transaction_id
        self.state = TransactionState.ACTIVE
        self.started_at = datetime.now()
        self.committed_at = None
        
        # Sauvegarde de l'état de la database AVANT la transaction
        self.savepoint: Optional[Dict] = None
        
        # Log des opérations pour UNDO
        self.operations_log: List[Dict] = []
    
    def log_operation(self, operation_type: str, table_name: str, data: Any):
        """Enregistre une opération dans le log"""
        self.operations_log.append({
            'type': operation_type,
            'table': table_name,
            'data': data,
            'timestamp': datetime.now()
        })
    
    def __repr__(self):
        duration = (datetime.now() - self.started_at).total_seconds()
        return f"Transaction(id={self.id}, state={self.state.value}, duration={duration:.2f}s)"


class TransactionManager:
    """Gestionnaire de transactions ACID"""
    
    def __init__(self):
        self.current_transaction: Optional[Transaction] = None
        self.transaction_counter = 0
        self.transaction_history: List[Transaction] = []
        self.logger = get_logger("TransactionManager")
    
    def begin_transaction(self, database) -> Transaction:
        """
        Démarre une nouvelle transaction
        
        Usage SQL:
            BEGIN TRANSACTION;
            BEGIN;
        """
        if self.current_transaction is not None:
            raise ValueError(
                f"Transaction {self.current_transaction.id} already active. "
                "Commit or rollback before starting a new transaction."
            )
        
        self.transaction_counter += 1
        transaction = Transaction(self.transaction_counter)
        
        # Créer un savepoint (copie profonde de toute la database)
        transaction.savepoint = self._create_savepoint(database)
        
        self.current_transaction = transaction
        self.logger.info(f"Transaction {transaction.id} started")
        
        return transaction
    
    def commit_transaction(self, database) -> None:
        """
        Valide la transaction en cours
        
        Usage SQL:
            COMMIT;
        """
        if self.current_transaction is None:
            raise ValueError("No active transaction to commit")
        
        transaction = self.current_transaction
        transaction.state = TransactionState.COMMITTED
        transaction.committed_at = datetime.now()
        
        # Libérer le savepoint (pas besoin de le garder)
        transaction.savepoint = None
        
        self.transaction_history.append(transaction)
        self.current_transaction = None
        
        duration = (transaction.committed_at - transaction.started_at).total_seconds()
        self.logger.info(
            f"Transaction {transaction.id} committed successfully "
            f"({len(transaction.operations_log)} operations, {duration:.2f}s)"
        )
    
    def rollback_transaction(self, database) -> None:
        """
        Annule la transaction en cours
        
        Usage SQL:
            ROLLBACK;
        """
        if self.current_transaction is None:
            raise ValueError("No active transaction to rollback")
        
        transaction = self.current_transaction
        
        # Restaurer l'état depuis le savepoint
        if transaction.savepoint:
            self._restore_savepoint(database, transaction.savepoint)
        
        transaction.state = TransactionState.ABORTED
        
        self.transaction_history.append(transaction)
        self.current_transaction = None
        
        self.logger.info(
            f"Transaction {transaction.id} rolled back "
            f"({len(transaction.operations_log)} operations undone)"
        )
    
    def _create_savepoint(self, database) -> Dict:
        """
        Crée un savepoint (snapshot) de la database
        
        Sauvegarde:
        - Toutes les tables
        - Toutes les lignes
        - Tous les compteurs auto_increment
        """
        savepoint = {
            'tables': {}
        }
        
        for table_name, table in database.tables.items():
            savepoint['tables'][table_name] = {
                'rows': copy.deepcopy(table.rows),
                'auto_increment_counters': copy.deepcopy(table.auto_increment_counters)
            }
        
        self.logger.debug(f"Savepoint created with {len(database.tables)} tables")
        return savepoint
    
    def _restore_savepoint(self, database, savepoint: Dict) -> None:
        """Restaure la database depuis un savepoint"""
        for table_name, table_data in savepoint['tables'].items():
            if table_name in database.tables:
                table = database.tables[table_name]
                table.rows = copy.deepcopy(table_data['rows'])
                table.auto_increment_counters = copy.deepcopy(table_data['auto_increment_counters'])
                
                # Reconstruire les index
                for index in table.indexes.values():
                    index.build(table.rows)
        
        self.logger.debug(f"Database restored from savepoint")
    
    def is_in_transaction(self) -> bool:
        """Vérifie si une transaction est active"""
        return self.current_transaction is not None
    
    def get_current_transaction(self) -> Optional[Transaction]:
        """Retourne la transaction active"""
        return self.current_transaction
    
    def log_operation(self, operation_type: str, table_name: str, data: Any):
        """Enregistre une opération dans la transaction active"""
        if self.current_transaction:
            self.current_transaction.log_operation(operation_type, table_name, data)
    
    def get_statistics(self) -> Dict:
        """Retourne des statistiques sur les transactions"""
        committed = sum(1 for t in self.transaction_history if t.state == TransactionState.COMMITTED)
        aborted = sum(1 for t in self.transaction_history if t.state == TransactionState.ABORTED)
        
        return {
            'total_transactions': len(self.transaction_history),
            'committed': committed,
            'aborted': aborted,
            'active': 1 if self.current_transaction else 0,
            'current_id': self.transaction_counter
        }


# ============================================================================
# INTÉGRATION DANS DMONSQL_MAIN.PY
# ============================================================================

def integrate_transactions_in_dmonsql():
    """
    Guide d'intégration dans dmonsql_main.py
    """
    
    code_example = '''
# Dans dmonsql_main.py, méthode __init__
class DmonSQL:
    def __init__(self, data_dir: str = "./dmonsql_data"):
        # ... code existant ...
        
        # ⭐ Ajouter le gestionnaire de transactions
        self.transaction_manager = TransactionManager()
        self.logger.info("Transaction manager initialized")

# Dans dmonsql_main.py, méthode _execute_internal
def _execute_internal(self, sql: str) -> Any:
    sql_upper = sql.upper()
    
    # ⭐ BEGIN TRANSACTION
    if sql_upper in ('BEGIN TRANSACTION', 'BEGIN', 'START TRANSACTION'):
        if not self.current_db:
            raise ValueError("No database selected")
        db = self.databases[self.current_db]
        self.transaction_manager.begin_transaction(db)
        print("✓ Transaction started")
        return
    
    # ⭐ COMMIT
    if sql_upper == 'COMMIT':
        if not self.transaction_manager.is_in_transaction():
            raise ValueError("No active transaction")
        db = self.databases[self.current_db]
        self.transaction_manager.commit_transaction(db)
        # Sauvegarder après COMMIT
        self.save_database(self.current_db)
        print("✓ Transaction committed")
        return
    
    # ⭐ ROLLBACK
    if sql_upper == 'ROLLBACK':
        if not self.transaction_manager.is_in_transaction():
            raise ValueError("No active transaction")
        db = self.databases[self.current_db]
        self.transaction_manager.rollback_transaction(db)
        print("✓ Transaction rolled back")
        return
    
    # ... reste du code ...
    
    # ⭐ Logger les opérations si en transaction
    if sql_upper.startswith('INSERT'):
        # ... code INSERT existant ...
        
        # Logger dans la transaction si active
        if self.transaction_manager.is_in_transaction():
            self.transaction_manager.log_operation('INSERT', table_name, values_dict)
    
    elif sql_upper.startswith('UPDATE'):
        # ... code UPDATE existant ...
        
        # Logger dans la transaction si active
        if self.transaction_manager.is_in_transaction():
            self.transaction_manager.log_operation('UPDATE', table_name, values)
    
    elif sql_upper.startswith('DELETE'):
        # ... code DELETE existant ...
        
        # Logger dans la transaction si active
        if self.transaction_manager.is_in_transaction():
            self.transaction_manager.log_operation('DELETE', table_name, where_clause)
    
    # ⭐ NE PAS sauvegarder automatiquement si en transaction
    # Remplacer tous les self.save_database() par:
    if not self.transaction_manager.is_in_transaction():
        self.save_database(self.current_db)
    '''
    
    return code_example


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EXEMPLE : Système de Transactions ACID")
    print("=" * 80)
    
    # Simuler une database
    class FakeDatabase:
        def __init__(self):
            self.tables = {
                'users': FakeTable('users', [
                    {'id': 1, 'name': 'Alice'},
                    {'id': 2, 'name': 'Bob'}
                ])
            }
    
    class FakeTable:
        def __init__(self, name, rows):
            self.name = name
            self.rows = rows
            self.auto_increment_counters = {'id': len(rows)}
            self.indexes = {}
    
    db = FakeDatabase()
    tm = TransactionManager()
    
    print("\n1️⃣  État initial:")
    print(f"   Users: {db.tables['users'].rows}")
    
    print("\n2️⃣  Démarrer une transaction:")
    tm.begin_transaction(db)
    print(f"   {tm.get_current_transaction()}")
    
    print("\n3️⃣  Modifier des données:")
    db.tables['users'].rows.append({'id': 3, 'name': 'Charlie'})
    db.tables['users'].rows[0]['name'] = 'Alice_Modified'
    tm.log_operation('INSERT', 'users', {'id': 3, 'name': 'Charlie'})
    tm.log_operation('UPDATE', 'users', {'id': 1, 'name': 'Alice_Modified'})
    print(f"   Users après modifications: {db.tables['users'].rows}")
    
    print("\n4️⃣  ROLLBACK (annuler les modifications):")
    tm.rollback_transaction(db)
    print(f"   Users après ROLLBACK: {db.tables['users'].rows}")
    print("   ✓ Données restaurées à l'état initial!")
    
    print("\n5️⃣  Nouvelle transaction avec COMMIT:")
    tm.begin_transaction(db)
    db.tables['users'].rows.append({'id': 3, 'name': 'Dave'})
    tm.log_operation('INSERT', 'users', {'id': 3, 'name': 'Dave'})
    print(f"   Users après INSERT: {db.tables['users'].rows}")
    tm.commit_transaction(db)
    print(f"   Users après COMMIT: {db.tables['users'].rows}")
    print("   ✓ Modifications validées définitivement!")
    
    print("\n6️⃣  Statistiques:")
    stats = tm.get_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("USAGE SQL:")
    print("=" * 80)
    print("""
BEGIN TRANSACTION;
INSERT INTO users (name) VALUES ('Charlie');
UPDATE users SET name = 'Alice_Modified' WHERE id = 1;
-- Si tout va bien:
COMMIT;
-- Sinon:
ROLLBACK;
    """)