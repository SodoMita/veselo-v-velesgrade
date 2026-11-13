# Source this before running Link-Grammar-backed code (chat, serve, tests).
# Points at the Debian-extracted liblink-grammar + libhunspell and dictionary
# built into ~/local (see README: "Real Link Grammar").
export LD_LIBRARY_PATH="$HOME/local/lib:${LD_LIBRARY_PATH:-}"
