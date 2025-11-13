"""
dmonSQL/procedures/procedure.py
Gestionnaire de procédures stockées et fonctions
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import re


class Procedure:
    """Procédure stockée"""
    
    def __init__(self, name: str, parameters: List[Dict], body: str, 
                 language: str = "SQL"):
        """
        Initialise une procédure
        
        Args:
            name: Nom de la procédure
            parameters: Liste des paramètres [{name, type, mode}]
            body: Corps de la procédure
            language: Langage (SQL, PYTHON)
        """
        self.name = name
        self.parameters = parameters
        self.body = body
        self.language = language.upper()
        self.created_at = datetime.now()
        self.last_executed = None
        self.execution_count = 0
        self.last_result = None
    
    def validate_parameters(self, args: Dict[str, Any]) -> bool:
        """Valide les paramètres passés"""
        for param in self.parameters:
            param_name = param['name']
            param_type = param['type']
            
            # Paramètre obligatoire
            if param.get('mode', 'IN') in ['IN', 'INOUT']:
                if param_name not in args:
                    raise ValueError(f"Missing required parameter: {param_name}")
            
            # Validation du type (basique)
            if param_name in args:
                value = args[param_name]
                if not self._validate_type(value, param_type):
                    raise TypeError(
                        f"Parameter {param_name} expected {param_type}, "
                        f"got {type(value).__name__}"
                    )
        
        return True
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Valide le type d'une valeur"""
        type_map = {
            'INT': int,
            'FLOAT': float,
            'VARCHAR': str,
            'TEXT': str,
            'BOOLEAN': bool
        }
        
        expected_python_type = type_map.get(expected_type.upper())
        if expected_python_type is None:
            return True  # Type inconnu, on accepte
        
        return isinstance(value, expected_python_type)
    
    def execute(self, db_system, args: Dict[str, Any]) -> Any:
        """
        Exécute la procédure
        
        Args:
            db_system: Instance de DmonSQL
            args: Arguments de la procédure
        
        Returns:
            Résultat de l'exécution
        """
        self.validate_parameters(args)
        
        self.last_executed = datetime.now()
        self.execution_count += 1
        
        if self.language == "SQL":
            result = self._execute_sql(db_system, args)
        elif self.language == "PYTHON":
            result = self._execute_python(db_system, args)
        else:
            raise ValueError(f"Unsupported language: {self.language}")
        
        self.last_result = result
        return result
    
    def _execute_sql(self, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une procédure SQL"""
        # Remplacer les paramètres dans le corps SQL
        sql_body = self.body
        
        for param_name, value in args.items():
            placeholder = f"${param_name}"
            if isinstance(value, str):
                sql_body = sql_body.replace(placeholder, f"'{value}'")
            else:
                sql_body = sql_body.replace(placeholder, str(value))
        
        # Exécuter chaque statement
        statements = [s.strip() for s in sql_body.split(';') if s.strip()]
        last_result = None
        
        for statement in statements:
            last_result = db_system.execute(statement)
        
        return last_result
    
    def _execute_python(self, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une procédure Python"""
        # Créer un environnement d'exécution sécurisé
        local_vars = {
            'db': db_system,
            'args': args,
            'result': None
        }
        
        try:
            exec(self.body, {}, local_vars)
            return local_vars.get('result')
        except Exception as e:
            raise RuntimeError(f"Python procedure execution failed: {e}")
    
    def get_info(self) -> Dict:
        """Retourne les informations sur la procédure"""
        return {
            'name': self.name,
            'parameters': self.parameters,
            'language': self.language,
            'created_at': self.created_at.isoformat(),
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'execution_count': self.execution_count
        }
    
    def __repr__(self):
        params = ', '.join(f"{p['name']} {p['type']}" for p in self.parameters)
        return f"Procedure({self.name}({params}))"


class Function:
    """Fonction stockée (retourne toujours une valeur)"""
    
    def __init__(self, name: str, parameters: List[Dict], 
                 return_type: str, body: str, language: str = "SQL"):
        """
        Initialise une fonction
        
        Args:
            name: Nom de la fonction
            parameters: Liste des paramètres
            return_type: Type de retour
            body: Corps de la fonction
            language: Langage
        """
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body
        self.language = language.upper()
        self.created_at = datetime.now()
        self.execution_count = 0
    
    def execute(self, db_system, args: Dict[str, Any]) -> Any:
        """Exécute la fonction et retourne le résultat"""
        self.execution_count += 1
        
        if self.language == "PYTHON":
            return self._execute_python(db_system, args)
        elif self.language == "SQL":
            return self._execute_sql(db_system, args)
        else:
            raise ValueError(f"Unsupported language: {self.language}")
    
    def _execute_python(self, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une fonction Python"""
        local_vars = {
            'db': db_system,
            'args': args
        }
        
        try:
            exec(self.body, {}, local_vars)
            result = local_vars.get('result')
            
            if result is None:
                raise ValueError("Function must return a value")
            
            return result
        except Exception as e:
            raise RuntimeError(f"Python function execution failed: {e}")
    
    def _execute_sql(self, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une fonction SQL"""
        sql_body = self.body
        
        for param_name, value in args.items():
            placeholder = f"${param_name}"
            if isinstance(value, str):
                sql_body = sql_body.replace(placeholder, f"'{value}'")
            else:
                sql_body = sql_body.replace(placeholder, str(value))
        
        result = db_system.execute(sql_body)
        return result
    
    def __repr__(self):
        params = ', '.join(f"{p['name']} {p['type']}" for p in self.parameters)
        return f"Function({self.name}({params}) -> {self.return_type})"


class ProcedureManager:
    """Gestionnaire de procédures et fonctions"""
    
    def __init__(self):
        self.procedures: Dict[str, Procedure] = {}
        self.functions: Dict[str, Function] = {}
    
    def create_procedure(self, name: str, parameters: List[Dict], 
                        body: str, language: str = "SQL"):
        """Crée une procédure stockée"""
        if name in self.procedures:
            raise ValueError(f"Procedure {name} already exists")
        
        procedure = Procedure(name, parameters, body, language)
        self.procedures[name] = procedure
        return procedure
    
    def create_function(self, name: str, parameters: List[Dict], 
                       return_type: str, body: str, language: str = "SQL"):
        """Crée une fonction stockée"""
        if name in self.functions:
            raise ValueError(f"Function {name} already exists")
        
        function = Function(name, parameters, return_type, body, language)
        self.functions[name] = function
        return function
    
    def drop_procedure(self, name: str):
        """Supprime une procédure"""
        if name not in self.procedures:
            raise ValueError(f"Procedure {name} does not exist")
        del self.procedures[name]
    
    def drop_function(self, name: str):
        """Supprime une fonction"""
        if name not in self.functions:
            raise ValueError(f"Function {name} does not exist")
        del self.functions[name]
    
    def execute_procedure(self, name: str, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une procédure"""
        if name not in self.procedures:
            raise ValueError(f"Procedure {name} does not exist")
        
        procedure = self.procedures[name]
        return procedure.execute(db_system, args)
    
    def execute_function(self, name: str, db_system, args: Dict[str, Any]) -> Any:
        """Exécute une fonction"""
        if name not in self.functions:
            raise ValueError(f"Function {name} does not exist")
        
        function = self.functions[name]
        return function.execute(db_system, args)
    
    def list_procedures(self) -> List[str]:
        """Liste toutes les procédures"""
        return list(self.procedures.keys())
    
    def list_functions(self) -> List[str]:
        """Liste toutes les fonctions"""
        return list(self.functions.keys())
    
    def get_procedure_info(self, name: str) -> Dict:
        """Retourne les informations sur une procédure"""
        if name not in self.procedures:
            raise ValueError(f"Procedure {name} does not exist")
        return self.procedures[name].get_info()
    
    def __repr__(self):
        return (f"ProcedureManager("
                f"{len(self.procedures)} procedures, "
                f"{len(self.functions)} functions)")


# ============================================================================
# EXEMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PROCEDURE MANAGER DEMO")
    print("=" * 60)
    
    manager = ProcedureManager()
    
    # Créer une procédure SQL simple
    print("\n1. Creating SQL procedure...")
    manager.create_procedure(
        name="add_user",
        parameters=[
            {'name': 'username', 'type': 'VARCHAR', 'mode': 'IN'},
            {'name': 'email', 'type': 'VARCHAR', 'mode': 'IN'}
        ],
        body="""
            INSERT INTO users (name, email) 
            VALUES ($username, $email);
        """,
        language="SQL"
    )
    print("✓ Procedure 'add_user' created")
    
    # Créer une fonction Python
    print("\n2. Creating Python function...")
    manager.create_function(
        name="calculate_discount",
        parameters=[
            {'name': 'price', 'type': 'FLOAT', 'mode': 'IN'},
            {'name': 'discount_pct', 'type': 'FLOAT', 'mode': 'IN'}
        ],
        return_type="FLOAT",
        body="""
price = args['price']
discount_pct = args['discount_pct']
result = price * (1 - discount_pct / 100)
        """,
        language="PYTHON"
    )
    print("✓ Function 'calculate_discount' created")
    
    # Lister les procédures et fonctions
    print("\n3. Listing procedures and functions...")
    print(f"Procedures: {manager.list_procedures()}")
    print(f"Functions: {manager.list_functions()}")
    
    # Tester une fonction Python
    print("\n4. Testing Python function...")
    class MockDB:
        pass
    
    mock_db = MockDB()
    result = manager.execute_function(
        "calculate_discount",
        mock_db,
        {'price': 100.0, 'discount_pct': 20.0}
    )
    print(f"calculate_discount(100, 20) = {result}")
    
    # Afficher les informations sur une procédure
    print("\n5. Procedure information...")
    info = manager.get_procedure_info("add_user")
    print(f"Name: {info['name']}")
    print(f"Parameters: {info['parameters']}")
    print(f"Language: {info['language']}")
    print(f"Execution count: {info['execution_count']}")
    
    print("\n" + "=" * 60)
    print("✓ All demos completed!")
    print("=" * 60)