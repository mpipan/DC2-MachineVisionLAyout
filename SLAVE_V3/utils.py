import json
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle NumPy data types, which are not
    natively serializable by the standard json library. This is needed
    when preparing the final payload for MQTT.
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        # Let the base class default method raise the TypeError
        return super(NumpyEncoder, self).default(obj)
