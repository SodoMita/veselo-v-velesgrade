#!/bin/bash
# Installs Link Grammar + hunspell + English dictionary into ~/local without root,
# from Debian packages (apt-get download + dpkg-deb -x). Idempotent.
set -e
L="$HOME/local/lib"; S="$HOME/local/share"; W="$(mktemp -d)"
mkdir -p "$L" "$S" && cd "$W"
apt-get download liblink-grammar5t64 libhunspell-1.7-0 link-grammar-dictionaries-en >/dev/null 2>&1 || \
  apt-get download liblink-grammar5t64 libhunspell-1.7-0t64 link-grammar-dictionaries-en
for f in *.deb; do dpkg-deb -x "$f" x; done
cp -a x/usr/lib/x86_64-linux-gnu/liblink-grammar.so.5* x/usr/lib/x86_64-linux-gnu/libhunspell-1.7.so* "$L/"
cd "$L"
ln -sf liblink-grammar.so.5.12.5 liblink-grammar.so
ln -sf liblink-grammar.so.5.12.5 liblink-grammar.so.5.13.0
ln -sf libhunspell-1.7.so.0.0.1 libhunspell-1.7.so.0 2>/dev/null || true
cp -a "$W/x/usr/share/link-grammar" "$S/"
rm -rf "$W"
echo "installed to $L and $S"
