#!/bin/bash
# Reproduce the Aigents comparison (docs/ORIGINAL_VS_OURS.md, section "Aigents").
# Requires java/javac (11+). Clones, compiles their tokenizer subset, runs it
# on the same sentences our ingest test-suite uses.
set -e
cd "$(dirname "$0")/../.."
[ -d aigents-java ] || git clone --depth 1 https://github.com/aigents/aigents-java.git
CAT=aigents-java/src/main/java/net/webstructor/cat
mkdir -p /tmp/aigcat
javac -encoding UTF-8 -d /tmp/aigcat \
  $CAT/StringUtil.java $CAT/Relation.java $CAT/Types.java $CAT/Item.java \
  $CAT/RelevantItem.java $CAT/StoragerRelation.java $CAT/Storager.java
cat > /tmp/CmpTok.java <<'JAVA'
import net.webstructor.cat.StringUtil;
public class CmpTok {
    public static void main(String[] a) throws Exception {
        String[] sents = {
            "The relic lies in the tunnel.", "Mira guards the archive.",
            "The hounds patrol the streets.", "The bell signals danger.",
            "The Veil-relic was kept in the archive." };
        for (String s : sents) {
            String[] t = StringUtil.toTokens(s, StringUtil.DELIMITERS);
            System.out.println(s + "\n  tokens: " + java.util.Arrays.toString(t));
        }
    }
}
JAVA
javac -encoding UTF-8 -cp /tmp/aigcat -d /tmp /tmp/CmpTok.java
java -cp /tmp/aigcat:/tmp CmpTok
