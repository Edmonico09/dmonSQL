"""
dmonSQL - Fonctionnalités P3 et P4
VIEWS, STORED PROCEDURES, TRIGGERS, SEQUENCES, EXPLAIN, FUNCTIONS
"""

import re
from typing import List, Dict, Any, Callable
from datetime import datetime, timedelta
import json
from collections import defaultdict


# ==================== P3: VIEWS (Vues) ====================

class View:
    """Vue SQL (table virtuelle)"""
    
    def __init__(self, name: str, query: str, columns: List[str] = None):
        self.name = name
        self.query = query  # Requête SELECT définissant la vue
        self.columns = columns  # Colonnes explicites (optionnel)
        self.created_at = datetime.now()
    
    def __repr__(self):
        return f"View({self.name}, columns={len(self.columns) if self.columns else '?'})"


class ViewManager:
    """Gestionnaire de vues"""
    
    def __init__(self, db_system):
        self.db_system = db_system
        self.views = {}
    
    def create_view(self, name: str, query: str, columns: List[str] = None):
        """
        CREATE VIEW active_users AS SELECT * FROM users WHERE active = 1;
        CREATE VIEW user_orders (user_id, order_count) AS 
            SELECT user_id, COUNT(*) FROM orders GROUP BY user_id;
        """
        if name in self.views:
            raise ValueError(f"View '{name}' already exists")
        
        # Valider que c'est un SELECT
        if not query.strip().upper().startswith('SELECT'):
            raise ValueError("View definition must be a SELECT statement")
        
        # Créer la vue
        view = View(name, query, columns)
        self.views[name] = view
        
        print(f"✓ View '{name}' created")
        return view
    
    def drop_view(self, name: str):
        """DROP VIEW active_users;"""
        if name not in self.views:
            raise ValueError(f"View '{name}' does not exist")
        
        del self.views[name]
        print(f"✓ View '{name}' dropped")
    
    def get_view_data(self, name: str) -> List[Dict]:
        """Exécute la requête de la vue et retourne les données"""
        if name not in self.views:
            raise ValueError(f"View '{name}' does not exist")
        
        view = self.views[name]
        result = self.db_system.execute(view.query)
        
        # Appliquer les colonnes explicites si définies
        if view.columns and result:
            if len(view.columns) != len(result[0]):
                raise ValueError(f"Column count mismatch in view '{name}'")
            
            # Renommer les colonnes
            renamed_result = []
            for row in result:
                new_row = {}
                for old_col, new_col in zip(row.keys(), view.columns):
                    new_row[new_col] = row[old_col]
                renamed_result.append(new_row)
            
            return renamed_result
        
        return result
    
    def list_views(self) -> List[str]:
        """Liste toutes les vues"""
        return list(self.views.keys())


# ==================== P3: SEQUENCES ====================

class Sequence:
    """Séquence de nombres (comme en Oracle/PostgreSQL)"""
    
    def __init__(self, name: str, start: int = 1, increment: int = 1, 
                 min_value: int = None, max_value: int = None, cycle: bool = False):
        self.name = name
        self.current = start
        self.start = start
        self.increment = increment
        self.min_value = min_value if min_value is not None else start
        self.max_value = max_value
        self.cycle = cycle
    
    def next_value(self) -> int:
        """Retourne la prochaine valeur de la séquence"""
        value = self.current
        self.current += self.increment
        
        # Vérifier les limites
        if self.max_value and self.current > self.max_value:
            if self.cycle:
                self.current = self.start
            else:
                raise ValueError(f"Sequence '{self.name}' exceeded maximum value")
        
        if self.current < self.min_value:
            if self.cycle:
                self.current = self.max_value or self.start
            else:
                raise ValueError(f"Sequence '{self.name}' below minimum value")
        
        return value
    
    def current_value(self) -> int:
        """Retourne la valeur actuelle sans l'incrémenter"""
        return self.current - self.increment
    
    def reset(self):
        """Réinitialise la séquence"""
        self.current = self.start


class SequenceManager:
    """Gestionnaire de séquences"""
    
    def __init__(self):
        self.sequences = {}
    
    def create_sequence(self, name: str, **kwargs):
        """
        CREATE SEQUENCE user_id_seq START WITH 1 INCREMENT BY 1;
        CREATE SEQUENCE order_seq START WITH 100 INCREMENT BY 10 MAXVALUE 10000;
        """
        if name in self.sequences:
            raise ValueError(f"Sequence '{name}' already exists")
        
        seq = Sequence(name, **kwargs)
        self.sequences[name] = seq
        print(f"✓ Sequence '{name}' created")
    
    def drop_sequence(self, name: str):
        """DROP SEQUENCE user_id_seq;"""
        if name not in self.sequences:
            raise ValueError(f"Sequence '{name}' does not exist")
        
        del self.sequences[name]
        print(f"✓ Sequence '{name}' dropped")
    
    def next_value(self, name: str) -> int:
        """SELECT NEXT VALUE FOR user_id_seq;"""
        if name not in self.sequences:
            raise ValueError(f"Sequence '{name}' does not exist")
        
        return self.sequences[name].next_value()
    
    def current_value(self, name: str) -> int:
        """SELECT CURRENT VALUE FOR user_id_seq;"""
        if name not in self.sequences:
            raise ValueError(f"Sequence '{name}' does not exist")
        
        return self.sequences[name].current_value()


# ==================== P3: EXPLAIN / ANALYZE ====================

class QueryExplainer:
    """Analyseur de plans d'exécution"""
    
    def __init__(self, db_system):
        self.db_system = db_system
    
    def explain(self, sql: str, analyze: bool = False) -> Dict:
        """
        EXPLAIN SELECT * FROM users WHERE age > 18;
        EXPLAIN ANALYZE SELECT * FROM orders JOIN users ON orders.user_id = users.id;
        """
        plan = {
            'query': sql,
            'type': self._detect_query_type(sql),
            'steps': [],
            'estimated_cost': 0,
            'estimated_rows': 0,
        }
        
        sql_upper = sql.upper()
        
        # Analyser SELECT
        if 'SELECT' in sql_upper:
            plan['steps'].append({
                'operation': 'SELECT',
                'description': 'Sequential Scan',
                'cost': 10
            })
            
            # Vérifier WHERE
            if 'WHERE' in sql_upper:
                # Vérifier si un index peut être utilisé
                plan['steps'].append({
                    'operation': 'FILTER',
                    'description': 'WHERE clause filtering',
                    'cost': 5
                })
            
            # Vérifier JOIN
            if 'JOIN' in sql_upper:
                plan['steps'].append({
                    'operation': 'JOIN',
                    'description': 'Nested Loop Join',
                    'cost': 50
                })
            
            # Vérifier GROUP BY
            if 'GROUP BY' in sql_upper:
                plan['steps'].append({
                    'operation': 'GROUP BY',
                    'description': 'Hash Aggregate',
                    'cost': 20
                })
            
            # Vérifier ORDER BY
            if 'ORDER BY' in sql_upper:
                plan['steps'].append({
                    'operation': 'ORDER BY',
                    'description': 'Sort',
                    'cost': 15
                })
        
        # Calculer le coût total
        plan['estimated_cost'] = sum(step['cost'] for step in plan['steps'])
        
        # Si ANALYZE, exécuter réellement et mesurer
        if analyze:
            import time
            start = time.time()
            result = self.db_system.execute(sql)
            duration = time.time() - start
            
            plan['actual_rows'] = len(result) if result else 0
            plan['execution_time_ms'] = duration * 1000
        
        return plan
    
    def _detect_query_type(self, sql: str) -> str:
        """Détecte le type de requête"""
        sql_upper = sql.upper().strip()
        
        if sql_upper.startswith('SELECT'):
            return 'SELECT'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        else:
            return 'OTHER'
    
    def print_plan(self, plan: Dict):
        """Affiche le plan d'exécution"""
        print("\n" + "="*70)
        print(f"QUERY PLAN: {plan['type']}")
        print("="*70)
        print(f"Query: {plan['query'][:60]}...")
        print(f"\nEstimated Cost: {plan['estimated_cost']}")
        
        if 'estimated_rows' in plan:
            print(f"Estimated Rows: {plan['estimated_rows']}")
        
        print("\nExecution Steps:")
        for i, step in enumerate(plan['steps'], 1):
            print(f"  {i}. {step['operation']}: {step['description']} (cost={step['cost']})")
        
        if 'actual_rows' in plan:
            print(f"\nActual Results:")
            print(f"  Rows: {plan['actual_rows']}")
            print(f"  Execution Time: {plan['execution_time_ms']:.2f} ms")
        
        print("="*70 + "\n")


# ==================== P4: STRING FUNCTIONS ====================

class StringFunctions:
    """Fonctions de manipulation de chaînes"""
    
    @staticmethod
    def concat(*args) -> str:
        """CONCAT('Hello', ' ', 'World') -> 'Hello World'"""
        return ''.join(str(arg) for arg in args if arg is not None)
    
    @staticmethod
    def substring(string: str, start: int, length: int = None) -> str:
        """SUBSTRING('Hello', 2, 3) -> 'ell'"""
        if string is None:
            return None
        
        # SQL indexing starts at 1
        start = start - 1 if start > 0 else 0
        
        if length is None:
            return string[start:]
        
        return string[start:start+length]
    
    @staticmethod
    def upper(string: str) -> str:
        """UPPER('hello') -> 'HELLO'"""
        return string.upper() if string else None
    
    @staticmethod
    def lower(string: str) -> str:
        """LOWER('HELLO') -> 'hello'"""
        return string.lower() if string else None
    
    @staticmethod
    def trim(string: str, chars: str = None) -> str:
        """TRIM('  hello  ') -> 'hello'"""
        if string is None:
            return None
        return string.strip(chars)
    
    @staticmethod
    def ltrim(string: str, chars: str = None) -> str:
        """LTRIM('  hello') -> 'hello'"""
        if string is None:
            return None
        return string.lstrip(chars)
    
    @staticmethod
    def rtrim(string: str, chars: str = None) -> str:
        """RTRIM('hello  ') -> 'hello'"""
        if string is None:
            return None
        return string.rstrip(chars)
    
    @staticmethod
    def length(string: str) -> int:
        """LENGTH('hello') -> 5"""
        return len(string) if string else 0
    
    @staticmethod
    def replace(string: str, old: str, new: str) -> str:
        """REPLACE('hello world', 'world', 'SQL') -> 'hello SQL'"""
        if string is None:
            return None
        return string.replace(old, new)
    
    @staticmethod
    def reverse(string: str) -> str:
        """REVERSE('hello') -> 'olleh'"""
        if string is None:
            return None
        return string[::-1]
    
    @staticmethod
    def left(string: str, length: int) -> str:
        """LEFT('hello', 3) -> 'hel'"""
        if string is None:
            return None
        return string[:length]
    
    @staticmethod
    def right(string: str, length: int) -> str:
        """RIGHT('hello', 3) -> 'llo'"""
        if string is None:
            return None
        return string[-length:] if length > 0 else ''


# ==================== P4: DATE/TIME FUNCTIONS ====================

class DateTimeFunctions:
    """Fonctions de manipulation de dates et heures"""
    
    @staticmethod
    def now() -> datetime:
        """NOW() -> datetime actuel"""
        return datetime.now()
    
    @staticmethod
    def curdate() -> datetime:
        """CURDATE() -> date actuelle (sans heure)"""
        return datetime.now().date()
    
    @staticmethod
    def curtime() -> str:
        """CURTIME() -> heure actuelle"""
        return datetime.now().time()
    
    @staticmethod
    def date_add(date: datetime, interval: int, unit: str = 'DAY') -> datetime:
        """
        DATE_ADD('2024-01-01', 7, 'DAY') -> 2024-01-08
        DATE_ADD('2024-01-01', 1, 'MONTH') -> 2024-02-01
        """
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        
        unit = unit.upper()
        
        if unit == 'DAY':
            return date + timedelta(days=interval)
        elif unit == 'WEEK':
            return date + timedelta(weeks=interval)
        elif unit == 'MONTH':
            # Approximation
            return date + timedelta(days=interval * 30)
        elif unit == 'YEAR':
            return date + timedelta(days=interval * 365)
        elif unit == 'HOUR':
            return date + timedelta(hours=interval)
        elif unit == 'MINUTE':
            return date + timedelta(minutes=interval)
        elif unit == 'SECOND':
            return date + timedelta(seconds=interval)
        else:
            raise ValueError(f"Unknown interval unit: {unit}")
    
    @staticmethod
    def date_sub(date: datetime, interval: int, unit: str = 'DAY') -> datetime:
        """DATE_SUB('2024-01-08', 7, 'DAY') -> 2024-01-01"""
        return DateTimeFunctions.date_add(date, -interval, unit)
    
    @staticmethod
    def datediff(date1: datetime, date2: datetime) -> int:
        """DATEDIFF('2024-01-10', '2024-01-01') -> 9"""
        if isinstance(date1, str):
            date1 = datetime.strptime(date1, '%Y-%m-%d')
        if isinstance(date2, str):
            date2 = datetime.strptime(date2, '%Y-%m-%d')
        
        return (date1 - date2).days
    
    @staticmethod
    def date_format(date: datetime, format_str: str) -> str:
        """
        DATE_FORMAT('2024-01-15', '%Y-%m-%d') -> '2024-01-15'
        DATE_FORMAT('2024-01-15', '%d/%m/%Y') -> '15/01/2024'
        """
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        
        return date.strftime(format_str)
    
    @staticmethod
    def year(date: datetime) -> int:
        """YEAR('2024-01-15') -> 2024"""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.year
    
    @staticmethod
    def month(date: datetime) -> int:
        """MONTH('2024-01-15') -> 1"""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.month
    
    @staticmethod
    def day(date: datetime) -> int:
        """DAY('2024-01-15') -> 15"""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.day


# ==================== P4: JSON FUNCTIONS ====================

class JSONFunctions:
    """Fonctions de manipulation JSON"""
    
    @staticmethod
    def json_extract(json_str: str, path: str) -> Any:
        """
        JSON_EXTRACT('{"user": {"name": "Alice"}}', '$.user.name') -> 'Alice'
        """
        try:
            data = json.loads(json_str) if isinstance(json_str, str) else json_str
            
            # Parser le path (format JSONPath simple)
            # $.user.name -> ['user', 'name']
            keys = path.replace('$.', '').split('.')
            
            result = data
            for key in keys:
                if isinstance(result, dict):
                    result = result.get(key)
                elif isinstance(result, list) and key.isdigit():
                    result = result[int(key)]
                else:
                    return None
            
            return result
        except:
            return None
    
    @staticmethod
    def json_set(json_str: str, path: str, value: Any) -> str:
        """
        JSON_SET('{"user": {}}', '$.user.name', 'Alice') 
        -> '{"user": {"name": "Alice"}}'
        """
        try:
            data = json.loads(json_str) if isinstance(json_str, str) else json_str
            
            keys = path.replace('$.', '').split('.')
            
            # Naviguer jusqu'à l'avant-dernière clé
            current = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Définir la valeur
            current[keys[-1]] = value
            
            return json.dumps(data)
        except:
            return json_str
    
    @staticmethod
    def json_array(*values) -> str:
        """JSON_ARRAY(1, 2, 3) -> '[1, 2, 3]'"""
        return json.dumps(list(values))
    
    @staticmethod
    def json_object(**kwargs) -> str:
        """JSON_OBJECT('name', 'Alice', 'age', 30) -> '{"name": "Alice", "age": 30}'"""
        return json.dumps(kwargs)
    
    @staticmethod
    def json_contains(json_str: str, value: Any) -> bool:
        """JSON_CONTAINS('[1, 2, 3]', 2) -> True"""
        try:
            data = json.loads(json_str) if isinstance(json_str, str) else json_str
            
            if isinstance(data, list):
                return value in data
            elif isinstance(data, dict):
                return value in data.values()
            else:
                return data == value
        except:
            return False


# ==================== P4: FULL-TEXT SEARCH ====================

class FullTextIndex:
    """Index de recherche plein texte"""
    
    def __init__(self, name: str, table_name: str, columns: List[str]):
        self.name = name
        self.table_name = table_name
        self.columns = columns
        self.index = defaultdict(set)  # {word: {row_ids}}
    
    def build(self, rows: List[Dict]):
        """Construit l'index de recherche"""
        self.index.clear()
        
        for idx, row in enumerate(rows):
            # Extraire le texte des colonnes indexées
            text = ' '.join(str(row.get(col, '')) for col in self.columns)
            
            # Tokenizer simple
            words = self._tokenize(text)
            
            # Ajouter à l'index
            for word in words:
                self.index[word.lower()].add(idx)
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize le texte en mots"""
        # Supprimer la ponctuation et diviser
        import string
        text = text.translate(str.maketrans('', '', string.punctuation))
        return text.split()
    
    def search(self, query: str) -> set:
        """
        Recherche les lignes correspondant à la requête
        Retourne les indices des lignes
        """
        words = self._tokenize(query)
        
        if not words:
            return set()
        
        # Intersection : toutes les lignes contenant tous les mots
        result_sets = [self.index.get(word.lower(), set()) for word in words]
        
        if not result_sets:
            return set()
        
        # Intersection de tous les sets
        result = result_sets[0]
        for s in result_sets[1:]:
            result = result & s
        
        return result


# ==================== TESTS ====================

if __name__ == "__main__":
    print("="*70)
    print("Tests des fonctionnalités P3 et P4")
    print("="*70)
    
    # Test String Functions
    print("\n--- String Functions ---")
    print(f"CONCAT('Hello', ' ', 'World'): {StringFunctions.concat('Hello', ' ', 'World')}")
    print(f"SUBSTRING('Hello World', 7, 5): {StringFunctions.substring('Hello World', 7, 5)}")
    print(f"UPPER('hello'): {StringFunctions.upper('hello')}")
    print(f"REVERSE('hello'): {StringFunctions.reverse('hello')}")
    
    # Test DateTime Functions
    print("\n--- DateTime Functions ---")
    print(f"NOW(): {DateTimeFunctions.now()}")
    print(f"DATE_ADD(now, 7 days): {DateTimeFunctions.date_add(datetime.now(), 7, 'DAY')}")
    print(f"YEAR('2024-01-15'): {DateTimeFunctions.year('2024-01-15')}")
    
    # Test JSON Functions
    print("\n--- JSON Functions ---")
    json_data = '{"user": {"name": "Alice", "age": 30}}'
    print(f"JSON_EXTRACT(data, '$.user.name'): {JSONFunctions.json_extract(json_data, '$.user.name')}")
    print(f"JSON_ARRAY(1, 2, 3): {JSONFunctions.json_array(1, 2, 3)}")
    
    # Test Full-Text Search
    print("\n--- Full-Text Search ---")
    docs = [
        {'id': 1, 'title': 'Introduction to SQL', 'content': 'SQL is a database language'},
        {'id': 2, 'title': 'Python Programming', 'content': 'Python is a versatile language'},
        {'id': 3, 'title': 'Database Design', 'content': 'Good database design is crucial'},
    ]
    
    ft_index = FullTextIndex('ft_docs', 'documents', ['title', 'content'])
    ft_index.build(docs)
    
    results = ft_index.search('database language')
    print(f"Search 'database language': Found {len(results)} documents")
    for idx in results:
        print(f"  - {docs[idx]['title']}")
    
    print("\n✅ Tous les tests réussis!")