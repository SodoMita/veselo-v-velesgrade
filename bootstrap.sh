#!/bin/bash
# bootstrap.sh – Restore the compiled OpenCog stack after a fresh sandbox.
# Build directories are excluded from workspace snapshots, so this script
# rebuilds them. Takes ~5 minutes total.
set -e
export PATH=/usr/local/lib/python3.13/site-packages/cmake/data/bin:/home/user/local/bin:/usr/local/bin:$PATH
export LD_LIBRARY_PATH=/home/user/local/lib:/home/user/local/lib/opencog:$LD_LIBRARY_PATH

echo "== 1. Python deps =="
pip install -q cmake Cython==3.2.8 2>/dev/null || true
chmod +x /home/user/atomspace/cmake/*.sh 2>/dev/null || true

echo "== 2. cogutil lib check =="
mkdir -p /home/user/local/lib/opencog
[ -f /home/user/local/lib/opencog/libcogutil.so ] || \
  cp /home/user/local/lib/libcogutil.so /home/user/local/lib/opencog/

echo "== 3. Link-grammar dictionary check =="
if [ ! -f /home/user/local/share/link-grammar/en/4.0.dict ]; then
  mkdir -p /home/user/local/share/link-grammar/en/words
  cd /home/user/local/share/link-grammar/en
  for f in 4.0.dict 4.0.affix 4.0.knowledge 4.0.constant-knowledge 4.0.constituent-knowledge 4.0.regex 4.0.dialect; do
    curl -sL "https://raw.githubusercontent.com/opencog/link-grammar/master/data/en/$f" -o "$f" 2>/dev/null || true
  done
  for f in $(curl -sL "https://api.github.com/repos/opencog/link-grammar/contents/data/en/words" 2>/dev/null | python3 -c "import json,sys; [print(x['name']) for x in json.load(sys.stdin) if not x['name'].startswith('Makefile')]" 2>/dev/null); do
    curl -sL "https://raw.githubusercontent.com/opencog/link-grammar/master/data/en/words/$f" -o "words/$f" 2>/dev/null || true
  done
fi

echo "== 4. AtomSpace build (if bindings missing) =="
if ! python3 -c "import opencog.atomspace" 2>/dev/null; then
  cd /home/user/atomspace
  mkdir -p build && cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=/home/user/local -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_PREFIX_PATH=/home/user/local -DCYTHON_EXECUTABLE=/usr/local/bin/cython > /tmp/as_cfg.log 2>&1
  make -j2 > /tmp/as_build.log 2>&1
  make install/fast > /tmp/as_install.log 2>&1
fi

echo "== 5. Verify =="
python3 -c "import warnings; warnings.filterwarnings('ignore'); import opencog.atomspace; print('OpenCog Python bindings: OK')"
python3 -c "
import sys; sys.path.insert(0, '/home/user')
from velesgrad_v2.dialogue.lg_ctypes import is_available
print('Link Grammar ctypes:', 'OK' if is_available() else 'MISSING')" 2>/dev/null

echo "== Done. Run: =="
echo "  export LD_LIBRARY_PATH=/home/user/local/lib:/home/user/local/lib/opencog:\$LD_LIBRARY_PATH"
echo "  python3 -m velesgrad_v2.engine --simulate 100"
