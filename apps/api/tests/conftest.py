"""Las pruebas cubren también los endpoints de casos de estudio, que en producción están desactivados por defecto."""

import os

os.environ.setdefault("ENABLE_CASE_STUDIES", "true")
