
# # ============================================================================
# # dmonSQL/__init__.py
# # ============================================================================

# """
# DmonSQL - Système de Gestion de Base de Données Relationnelle
# Version 2.0.0

# Un SGBDR complet en Python avec support de :
# - Types avancés (MATRIX, EMAIL, JSON)
# - Transactions ACID (COMMIT, ROLLBACK, SAVEPOINT)
# - Procédures stockées et fonctions
# - Triggers (BEFORE/AFTER INSERT/UPDATE/DELETE)
# - Division relationnelle
# - GROUP BY, HAVING, agrégations
# - Compression et chiffrement
# - Optimiseur de requêtes
# - Compatible tous OS
# """

# __version__ = "2.0.0"
# __author__ = "DmonSQL Team"
# __license__ = "MIT"

# # Imports principaux
# from dmonSQL.core.database import Database
# from dmonSQL.core.table import Table
# from dmonSQL.core.column import Column
# from dmonSQL.core.index import Index

# # Types de données
# from dmonSQL.types.base_types import DataType
# from dmonSQL.types.matrix_type import MatrixType
# from dmonSQL.types.email_type import EmailValidator
# from dmonSQL.types.json_type import JSONType, JSONQuery

# # Transactions
# from dmonSQL.transaction.transaction_manager import (
#     TransactionManager,
#     TransactionContext,
#     IsolationLevel,
#     TransactionState
# )

# # Procédures et fonctions
# from dmonSQL.procedures.procedure import (
#     StoredProcedure,
#     StoredFunction,
#     ProcedureManager,
#     Parameter
# )

# # Triggers
# from dmonSQL.procedures.trigger import (
#     Trigger,
#     TriggerManager,
#     TriggerTiming,
#     TriggerEvent,
#     TriggerLevel
# )

# # Algèbre relationnelle
# from dmonSQL.algebra.operations import RelationalAlgebra
# from dmonSQL.algebra.aggregation import Aggregator

# # Query optimization
# from dmonSQL.query.optimizer import QueryOptimizer, QueryPlan
# from dmonSQL.query.parser import QueryParser

# # Storage
# from dmonSQL.storage.compression import (
#     Compressor,
#     CompressionAlgorithm
# )
# from dmonSQL.storage.encryption import (
#     Encryptor,
#     EncryptionAlgorithm,
#     SecureStorage
# )

# # Système principal
# from dmonSQL.core.dmonsql_main import DmonSQL


# # Imports conditionnels (modules optionnels)
# try:
#     from dmonSQL.transaction.transaction_manager import (
#         TransactionManager,
#         TransactionContext,
#         IsolationLevel
#     )
# except ImportError:
#     TransactionManager = None
#     TransactionContext = None
#     IsolationLevel = None

# try:
#     from dmonSQL.procedures.procedure import (
#         StoredProcedure,
#         StoredFunction,
#         ProcedureManager
#     )
# except ImportError:
#     StoredProcedure = None
#     StoredFunction = None
#     ProcedureManager = None

# try:
#     from dmonSQL.procedures.trigger import (
#         Trigger,
#         TriggerManager
#     )
# except ImportError:
#     Trigger = None
#     TriggerManager = None

# # Exports
# __all__ = [
#     # Core
#     'DmonSQL',
#     'Database',
#     'Table',
#     'Column',
#     'Index',
    
#     # Types
#     'DataType',
#     'MatrixType',
#     'EmailValidator',
#     'JSONType',
#     'JSONQuery',
    
#     # Transactions
#     'TransactionManager',
#     'TransactionContext',
#     'IsolationLevel',
#     'TransactionState',
    
#     # Procedures & Functions
#     'StoredProcedure',
#     'StoredFunction',
#     'ProcedureManager',
#     'Parameter',
    
#     # Triggers
#     'Trigger',
#     'TriggerManager',
#     'TriggerTiming',
#     'TriggerEvent',
#     'TriggerLevel',
    
#     # Algebra
#     'RelationalAlgebra',
#     'Aggregator',
    
#     # Query
#     'QueryOptimizer',
#     'QueryPlan',
#     'QueryParser',
    
#     # Storage
#     'Compressor',
#     'CompressionAlgorithm',
#     'Encryptor',
#     'EncryptionAlgorithm',
#     'SecureStorage',
# ]

# def get_version():
#     """Retourne la version de DmonSQL"""
#     return __version__

# def get_info():
#     """Retourne les informations sur DmonSQL"""
#     return {
#         'version': __version__,
#         'author': __author__,
#         'license': __license__,
#         'features': [
#             'SQL Standard (SELECT, INSERT, UPDATE, DELETE)',
#             'Types avancés (MATRIX, EMAIL, JSON)',
#             'Transactions ACID avec SAVEPOINT',
#             'Procédures stockées et fonctions',
#             'Triggers (BEFORE/AFTER)',
#             'Division relationnelle',
#             'GROUP BY, HAVING',
#             'Agrégations (COUNT, SUM, AVG, MIN, MAX, STDDEV)',
#             'Compression (ZLIB, BZ2, LZ4)',
#             'Chiffrement (AES256, ChaCha20)',
#             'Optimiseur de requêtes',
#             'Index B-tree',
#             'Foreign Keys (en développement)',
#             'Réplication (en développement)',
#         ]
#     }

# def print_banner():
#     banner = f"""
#     ╔═══════════════════════════════════════════════════════════╗
#     ║                                                           ║
#     ║               ██████╗ ███╗   ███╗ ██████╗ ███╗   ██╗     ║
#     ║               ██╔══██╗████╗ ████║██╔═══██╗████╗  ██║     ║
#     ║               ██║  ██║██╔████╔██║██║   ██║██╔██╗ ██║     ║
#     ║               ██║  ██║██║╚██╔╝██║██║   ██║██║╚██╗██║     ║
#     ║               ██████╔╝██║ ╚═╝ ██║╚██████╔╝██║ ╚████║     ║
#     ║               ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝     ║
#     ║                         SQL                               ║
#     ║              Version {__version__}                             ║
#     ║      Système de Gestion de Base de Données Relationnelle ║
#     ║                                                           ║
#     ╚═══════════════════════════════════════════════════════════╝
#     """
#     print(banner)

# # Configuration par défaut
# DEFAULT_CONFIG = {
#     'data_dir': './dmonSQL_data',
#     'compression': 'ZLIB',
#     'encryption': False,
#     'cache_size': 1000,
#     'log_level': 'INFO',
# }

# def create_default_instance(**kwargs):
#     """
#     Crée une instance DmonSQL avec la configuration par défaut
    
#     Args:
#         **kwargs: Arguments à passer à DmonSQL
    
#     Returns:
#         DmonSQL: Instance configurée
#     """
#     config = {**DEFAULT_CONFIG, **kwargs}
#     return DmonSQL(**config)

# # Initialisation
# if __name__ != "__main__":
#     # Import automatique en mode module
#     pass
# else:
#     # Mode script : afficher les informations
#     print_banner()
#     info = get_info()
#     print(f"\\n{info['version']} by {info['author']}")
#     print(f"License: {info['license']}")
#     print(f"\\nFonctionnalités:")
#     for feature in info['features']:
#         print(f"  ✓ {feature}")
