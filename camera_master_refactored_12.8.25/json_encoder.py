import json
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that handles NumPy data types.
    
    This is necessary for serializing data like arrays, integers, and floats
    that come from NumPy into standard Python types for JSON.
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # Convert ndarray to lists
        if isinstance(obj, np.integer):
            return int(obj)  # Convert numpy integers to Python integers
        if isinstance(obj, np.floating):
            return float(obj)  # Convert numpy floats to Python floats
        if isinstance(obj, np.bool_):
            return bool(obj)  # Convert numpy booleans to Python booleans
        return super().default(obj)  # Let the base class handle anything else
