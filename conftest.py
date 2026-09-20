# -*- coding: utf-8 -*-
"""conftest raíz — garantiza que la raíz del repo esté en sys.path para que los
tests importen los paquetes de la app (`nucleo`, `motores`, `clases` hoy; `core`,
`gui`, `tasks` tras la reestructuración) igual que al ejecutar `python kakoli.py`
desde la raíz. Sin esto, el rootdir de pytest podría no resolver esos paquetes.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.abspath(__file__))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
