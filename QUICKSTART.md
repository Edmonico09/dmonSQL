
# ============================================================================
# QUICKSTART.md
# ============================================================================

QUICKSTART_MD = """
# dmonSQL - Guide de Démarrage Rapide 🚀

## Installation

### Option 1 : Installation depuis PyPI (recommandé)
```bash
pip install dmonsql
```

### Option 2 : Installation depuis les sources
```bash
git clone https://github.com/dmonsql/dmonsql.git
cd dmonsql
pip install -e .
```

### Option 3 : Installation avec toutes les fonctionnalités
```bash
pip install dmonsql[full]
```

## Premiers Pas

### 1. Mode Interactif (CLI)

Lancez le shell interactif :

```bash
dmonsql
```

Ou avec Python :

```bash
python -m dmonsql.cli.shell
```

Exemple de session :

```sql
dmonsql> CREATE DATABASE ma_premiere_db
Database 'ma_premiere_db' created successfully

dmonsql> USE ma_premiere_db
Using database 'ma_premiere_db'

ma_premiere_db> CREATE TABLE utilisateurs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nom VARCHAR(100) NOT NULL,
    email EMAIL UNIQUE,
    age INT
)
Table 'utilisateurs' created successfully

ma_premiere_db> INSERT INTO utilisateurs (nom, email, age) VALUES ('Alice', 'alice@example.com', 25)
1 row inserted

ma_premiere_db> SELECT * FROM utilisateurs
nom             | email                | age            
--------------------------------------------------------
Alice           | alice@example.com    | 25             

1 row(s) in set

ma_premiere_db> EXIT
```

### 2. Mode Python (API)

```python
from dmonsql import dmonSQL

# Créer une instance
db = dmonSQL()

# Créer une base de données
db.execute("CREATE DATABASE shop")
db.execute("USE shop")

# Créer une table
db.execute(\"\"\"
    CREATE TABLE products (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        price FLOAT,
        stock INT DEFAULT 0
    )
\"\"\")

# Insérer des données
db.execute("INSERT INTO products (name, price, stock) VALUES ('Laptop', 999.99, 10)")
db.execute("INSERT INTO products (name, price, stock) VALUES ('Mouse', 29.99, 50)")
db.execute("INSERT INTO products (name, price, stock) VALUES ('Keyboard', 79.99, 30)")

# Interroger
result = db.execute("SELECT * FROM products WHERE price < 100")
print(result)

# Mettre à jour
db.execute("UPDATE products SET stock = stock - 1 WHERE name = 'Laptop'")

# Supprimer
db.execute("DELETE FROM products WHERE stock = 0")
```

## Fonctionnalités Avancées

### 1. Type MATRIX (NumPy)

```python
import numpy as np
from dmonsql import dmonSQL, Table, Column, DataType, MatrixType

db = dmonSQL()
db.execute("CREATE DATABASE ml_data")
db.execute("USE ml_data")

# Créer une table avec des matrices
table = Table('models', [
    Column('model_id', DataType.INT, primary_key=True, auto_increment=True),
    Column('model_name', DataType.VARCHAR, length=50),
    Column('weights', DataType.MATRIX),
    Column('accuracy', DataType.FLOAT)
])

db.databases['ml_data'].create_table(table)

# Insérer une matrice NumPy
weights = MatrixType(np.random.randn(100, 50))
table.insert({
    'model_name': 'neural_net_v1',
    'weights': weights,
    'accuracy': 0.95
})

# Récupérer et utiliser
result = table.select()
saved_weights = result[0]['weights'].matrix  # NumPy array
print(f"Shape: {saved_weights.shape}")
```

### 2. Type JSON

```python
from dmonsql.types.json_type import JSONType

db.execute("CREATE DATABASE config")
db.execute("USE config")

# Créer une table avec JSON
table = Table('settings', [
    Column('key', DataType.VARCHAR, length=50, primary_key=True),
    Column('value', DataType.JSON)
])

db.databases['config'].create_table(table)

# Insérer des données JSON
config = JSONType({
    'theme': 'dark',
    'language': 'fr',
    'notifications': {
        'email': True,
        'push': False
    }
})

table.insert({'key': 'user_preferences', 'value': config})

# Requêter des données JSON
result = table.select()
prefs = result[0]['value']
print(prefs.get('theme'))  # 'dark'
print(prefs.get('notifications.email'))  # True
```

### 3. Transactions

```python
from dmonsql.transaction import TransactionManager, TransactionContext

manager = TransactionManager()

# Avec context manager (recommandé)
try:
    with TransactionContext(manager) as txn:
        db.execute("INSERT INTO products (name, price) VALUES ('Item1', 50)")
        db.execute("INSERT INTO products (name, price) VALUES ('Item2', 60)")
        # Commit automatique si pas d'exception
except Exception as e:
    # Rollback automatique en cas d'erreur
    print(f"Transaction annulée: {e}")

# Avec SAVEPOINT
txn_id = manager.begin_transaction()
db.execute("INSERT INTO products (name, price) VALUES ('Item3', 70)")
manager.savepoint('sp1')
db.execute("INSERT INTO products (name, price) VALUES ('Item4', 80)")
manager.rollback_to_savepoint('sp1')  # Annule Item4
manager.commit(txn_id)
```

### 4. Procédures Stockées

```python
from dmonsql.procedures import ProcedureManager, Parameter

proc_manager = ProcedureManager()

# Créer une procédure
sql = \"\"\"
CREATE PROCEDURE update_stock(product_id INT, quantity INT) BEGIN
    UPDATE products SET stock = stock + :quantity WHERE id = :product_id;
    SELECT * FROM products WHERE id = :product_id;
END
\"\"\"

name, params, body = proc_manager.parse_create_procedure(sql)
proc_manager.create_procedure(name, params, body)

# Appeler la procédure
result = proc_manager.call_procedure(
    'update_stock',
    db,
    {'product_id': 1, 'quantity': 5}
)
```

### 5. Triggers

```python
from dmonsql.procedures.trigger import TriggerManager, TriggerTiming, TriggerEvent

trigger_manager = TriggerManager()

# Créer un trigger d'audit
sql = \"\"\"
CREATE TRIGGER audit_changes AFTER UPDATE ON products FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, old_value, new_value, timestamp)
    VALUES ('products', 'UPDATE', OLD.price, NEW.price, CURRENT_TIMESTAMP);
END
\"\"\"

data = trigger_manager.parse_create_trigger(sql)
trigger_manager.create_trigger(**data)

# Le trigger s'exécutera automatiquement lors des UPDATE
```

### 6. GROUP BY et Agrégations

```python
from dmonsql.algebra.aggregation import Aggregator

# Données
sales = [
    {'region': 'East', 'product': 'A', 'amount': 100},
    {'region': 'East', 'product': 'B', 'amount': 150},
    {'region': 'West', 'product': 'A', 'amount': 200},
]

# GROUP BY avec agrégations
result = Aggregator.execute_group_by(
    sales,
    group_by_columns=['region'],
    select_columns=['region', 'SUM(amount)', 'COUNT(*)']
)

# HAVING
filtered = Aggregator.apply_having(result, 'SUM(amount) > 150')
```

### 7. Division Relationnelle

```python
from dmonsql.algebra import RelationalAlgebra

# Trouver les étudiants inscrits à TOUS les cours requis
result = RelationalAlgebra.division(
    enrollments_table,
    required_courses_table,
    common_attrs=['course'],
    dividend_attrs=['student']
)
```

### 8. Compression et Chiffrement

```python
from dmonsql.storage.encryption import SecureStorage, Encryptor
from dmonsql.storage.compression import CompressionAlgorithm

# Générer une clé
key, salt = Encryptor.derive_key_from_password("mon_mot_de_passe")

# Créer un stockage sécurisé
storage = SecureStorage(
    encryption_key=key,
    compression_algo=CompressionAlgorithm.LZ4
)

# Sauvegarder avec chiffrement et compression
storage.save(database_data, 'secure_backup.db')

# Charger
loaded_data = storage.load('secure_backup.db')
```

## Configuration

### Fichier de configuration (config.ini)

```ini
[database]
data_dir = ./dmonsql_data
default_compression = ZLIB
enable_encryption = false

[performance]
cache_size = 1000
index_cache_size = 500
max_connections = 10

[logging]
level = INFO
file = dmonsql.log
```

Charger la configuration :

```python
from dmonsql.utils.config import Config

config = Config.load('config.ini')
db = dmonSQL(data_dir=config.get('database', 'data_dir'))
```

## Commandes Utiles

### Gestion des bases de données
```sql
SHOW DATABASES;
CREATE DATABASE nom_db;
DROP DATABASE nom_db;
USE nom_db;
```

### Gestion des tables
```sql
SHOW TABLES;
DESCRIBE nom_table;
CREATE INDEX idx_nom ON table(colonne);
DROP INDEX idx_nom;
```

### Transactions
```sql
BEGIN TRANSACTION;
COMMIT;
ROLLBACK;
SAVEPOINT nom_sp;
ROLLBACK TO SAVEPOINT nom_sp;
```

### Procédures et fonctions
```sql
SHOW PROCEDURES;
SHOW FUNCTIONS;
CALL procedure_name(param1, param2);
SELECT function_name(param1);
```

## Performance Tips

1. **Utilisez des index** pour les colonnes fréquemment interrogées
2. **Compression** : LZ4 pour la vitesse, BZ2 pour le ratio
3. **Batch inserts** : Insérez plusieurs lignes en une transaction
4. **GROUP BY** : Utilisez sur des données déjà indexées
5. **EXPLAIN** : Analysez vos plans de requête

```python
from dmonsql.query.optimizer import QueryOptimizer

optimizer = QueryOptimizer()
optimizer.collect_statistics(database)
plan = optimizer.optimize_query(parsed_query)
print(optimizer.explain_query(parsed_query))
```

## Exemples Complets

Consultez le dossier `examples/` pour des exemples complets :

- `basic_crud.py` - Opérations CRUD
- `advanced_types.py` - Types MATRIX, EMAIL, JSON
- `transactions.py` - Gestion des transactions
- `procedures_functions.py` - Procédures et fonctions
- `triggers_demo.py` - Utilisation des triggers
- `performance_benchmark.py` - Tests de performance

## Aide et Support

- Documentation complète : `docs/`
- Issues GitHub : https://github.com/dmonsql/dmonsql/issues
- Discussions : https://github.com/dmonsql/dmonsql/discussions

## License

MIT License - Voir LICENSE pour plus de détails
"""

# Sauvegarder QUICKSTART.md
if __name__ == "__main__":
    with open("QUICKSTART.md", "w", encoding="utf-8") as f:
        f.write(QUICKSTART_MD)
    print("✓ QUICKSTART.md créé")
    print("✓ setup.py prêt pour l'installation")
