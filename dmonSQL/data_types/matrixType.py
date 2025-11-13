import numpy as np

class MatrixType:
    """Gestion des matrices numpy"""
    def __init__(self, data):
        if isinstance(data, np.ndarray):
            self.matrix = data
        elif isinstance(data, (list, tuple)):
            self.matrix = np.array(data)
        else:
            raise ValueError("Matrix doit être un numpy array ou une liste")
    
    def __repr__(self):
        return f"Matrix{self.matrix.shape}:\n{self.matrix}"
    
    def __eq__(self, other):
        if isinstance(other, MatrixType):
            return np.array_equal(self.matrix, other.matrix)
        return False
    