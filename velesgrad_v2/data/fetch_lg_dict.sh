#!/bin/bash
# Fetch the Link Grammar English dictionary into this data dir.
DEST="$(dirname "$0")/link-grammar/en"
mkdir -p "$DEST/words"
cd "$DEST" || exit 1
for f in 4.0.dict 4.0.affix 4.0.knowledge 4.0.constant-knowledge 4.0.constituent-knowledge 4.0.regex 4.0.dialect; do
  curl -sL "https://raw.githubusercontent.com/opencog/link-grammar/master/data/en/$f" -o "$f"
done
curl -sL "https://api.github.com/repos/opencog/link-grammar/contents/data/en/words" \
 | python3 -c "import json,sys; [print(x['name']) for x in json.load(sys.stdin) if not x['name'].startswith('Makefile')]" \
 | while read -r f; do curl -sL "https://raw.githubusercontent.com/opencog/link-grammar/master/data/en/words/$f" -o "words/$f"; done
echo "dictionary files: $(ls | wc -l), words: $(ls words | wc -l)"
