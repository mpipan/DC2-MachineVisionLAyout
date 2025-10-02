import json
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle NumPy data types, which are not
    natively serializable by the standard json library.
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)
