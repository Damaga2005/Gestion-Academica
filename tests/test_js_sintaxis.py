import glob
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(__file__))


@pytest.mark.skipif(shutil.which("node") is None, reason="node no instalado")
@pytest.mark.parametrize("ruta", sorted(glob.glob(os.path.join(RAIZ, "static", "js", "*.js"))), ids=os.path.basename)
def test_js_sin_errores_de_sintaxis(ruta):
    r = subprocess.run(["node", "--check", ruta], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
