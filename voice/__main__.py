"""Entry point do zipapp (`jarvis.pyz`).

Empacotado com os modulos de `voice/` na RAIZ do zip (ver scripts/build-pyz.sh),
entao `import loop` funciona. As dependencias pesadas (faster-whisper) NAO vao no
zip: o zipapp roda com o Python/venv que ja as tem em runtime.
"""

import sys

from loop import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
