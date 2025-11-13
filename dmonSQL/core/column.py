from datetime import datetime
from dmonSQL.data_types.base_types import DataType
from dmonSQL.data_types.matrixType import MatrixType
from dmonSQL.data_types.validators import EmailValidator

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
            if not EmailValidator.is_valid(value):
                raise ValueError(f"Invalid email: {value}")
            return str(value)
        elif self.dtype == DataType.MATRIX:
            if isinstance(value, MatrixType):
                return value
            return MatrixType(value)
        
        return value
