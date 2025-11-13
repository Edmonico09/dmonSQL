from typing import List, Dict, Any, Tuple
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