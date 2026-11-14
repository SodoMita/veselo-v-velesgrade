# Source this before running Link-Grammar-backed code (chat, serve, tests).
# Points at the Debian-extracted liblink-grammar + libhunspell and dictionary
# built into ~/local (see README: "Real Link Grammar").
export LD_LIBRARY_PATH="$HOME/local/lib:${LD_LIBRARY_PATH:-}"
# Sandbox restores drop the soname symlinks; recreate them so ctypes finds the real library.
if [ -f "$HOME/local/lib/liblink-grammar.so.5.12.5" ]; then
  ( cd "$HOME/local/lib" && ln -sf liblink-grammar.so.5.12.5 liblink-grammar.so \
    && ln -sf liblink-grammar.so.5.12.5 liblink-grammar.so.5.13.0 \
    && ln -sf libhunspell-1.7.so.0.0.1 libhunspell-1.7.so.0 ) 2>/dev/null
fi
