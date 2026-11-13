#!/usr/bin/env python3
"""
mayfly_bridge.py – Let Mira talk in a Mayfly Chat channel (https://mayfly.chat).

Mayfly is an end-to-end encrypted channel for agents and humans. The channel URL
(`/c/ID#key`) is the only credential, and it grants read, post and delete. This
bridge never writes the URL to logs or to the repository. Keep it in a file with
mode 600 and pass the path with --url-file.

Crypto and wire format stay in Mayfly's own single-file client (`client.mjs`,
fetched from the channel server and inspected before use). This bridge calls
that client as a subprocess for each read and post. It does no crypto itself.

Behavior:
  - Long-polls the channel (real time: a read returns as soon as someone posts).
  - Mira is dark by default. She replies only to messages that address her by
    name ("mira ..."), so she does not answer every line in a busy room.
  - Each sender has their own conversation with Mira (her chat state is replayed
    from that sender's own messages, as in serve.py).
  - Rate limit: at most --max-replies per minute, so two bots cannot loop.
  - Never posts a reply that was already sent (no blind retry). On a conflict
    she re-reads the missed messages and reconsiders.
  - Messages from herself, undecryptable messages, and view-convention
    commands (/title, /react, ...) are ignored.

Usage:
  node client.mjs is fetched into --workdir automatically.
  LD_LIBRARY_PATH=$HOME/local/lib VELESGRAD_DEV=1 \\
    python -m velesgrad_v2.mayfly_bridge --url-file ~/mira-mayfly/channel.url
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

NAME = "Mira"
CLIENT_URL = "https://mayfly.chat/static/client.mjs"
ADDRESS_RE = re.compile(r"(?:^|[\s,.:;!?(\"'@])mira\b", re.IGNORECASE)
INTRO = ("Mira, the Velesgrad archivist, has joined. Address me by name "
         "(\"Mira, ...\") and I will answer. My knowledge is the archive plus "
         "what I read in old books; I do not know the present world.")


def log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


def ensure_client(workdir: str) -> str:
    path = os.path.join(workdir, "client.mjs")
    if not os.path.isfile(path):
        os.makedirs(workdir, exist_ok=True)
        with urllib.request.urlopen(CLIENT_URL, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        log(f"fetched Mayfly client ({len(data)} bytes) -> {path}; review it before trusting")
    return path


class Channel:
    """Thin wrapper over client.mjs. The URL is passed as an argument, never logged."""

    def __init__(self, url: str, client_path: str):
        self.url = url
        self.client = client_path

    def _run(self, args, stdin_text=None, timeout=120):
        cmd = ["node", self.client, self.url] + args
        p = subprocess.run(cmd, input=(stdin_text or "").encode() if stdin_text is not None else None,
                           capture_output=True, timeout=timeout)
        out = p.stdout.decode("utf-8", "replace").strip()
        err = p.stderr.decode("utf-8", "replace").strip()
        data = None
        for blob in (out, err):
            if blob:
                try:
                    data = json.loads(blob.splitlines()[-1])
                    break
                except (ValueError, IndexError):
                    pass
        return p.returncode, data, err

    def read(self, last: int, wait: int):
        rc, data, err = self._run(["read", "--last", str(last), "--wait", str(wait)],
                                  timeout=wait + 90)
        if data is None or "error" in (data or {}):
            raise RuntimeError(f"read failed: {err[:200]}")
        return data

    def post(self, text: str, last: int, sender: str):
        return self._run(["post", "--from", sender, "--last", str(last), "--wait", "0"],
                         stdin_text=text, timeout=120)


def addressed(msg: dict) -> bool:
    text = msg.get("text", "")
    if msg.get("from") in ("", NAME):
        return False
    if text.lstrip().startswith("/"):          # view conventions, not speech
        return False
    return bool(ADDRESS_RE.search(text))


def strip_address(text: str) -> str:
    return ADDRESS_RE.sub(" ", text, count=1).strip(" ,.:;!?-")


class Mira:
    def __init__(self, knowledge: str | None):
        from .chat import MiraChat
        self._MiraChat = MiraChat
        self.knowledge = knowledge
        self.turns = {}   # sender -> [user texts Mira has heard from them]

    def reply(self, sender: str, text: str) -> str:
        self.turns.setdefault(sender, []).append(text)
        mira = self._MiraChat(seed=7, knowledge=self.knowledge)
        out = ""
        for t in self.turns[sender][-12:]:     # bounded per-sender history
            out = mira.respond(t)
        return out.strip() or "..."


def run(args):
    with open(os.path.expanduser(args.url_file), encoding="utf-8") as f:
        url = f.read().strip()
    if not re.match(r"^https://[^\s#]+/c/[^\s#]+#[^\s#]+$", url):
        sys.exit("url file must hold one full https channel URL with #key")
    client_path = ensure_client(os.path.expanduser(args.workdir))
    chan = Channel(url, client_path)
    mira = Mira(None if args.knowledge == "none" else args.knowledge)

    # Starting cursor: read the existing history first, so we don't answer old messages.
    cursor = -1
    while True:
        page = chan.read(cursor, 0)
        cursor = page.get("last", cursor)
        if not page.get("more"):
            break
    log(f"joined; cursor={cursor}; knowledge={args.knowledge}")
    rc, data, err = chan.post(INTRO, cursor, NAME)
    if rc == 0 and data and data.get("posted") is True:
        cursor = data.get("id", cursor)
        log("intro posted")
    else:
        log(f"intro not posted: {err[:200] or data}")

    replies_at = []      # timestamps of our posts, for rate limiting
    pending = []         # addressed messages not yet answered
    while True:
        try:
            page = chan.read(cursor, args.wait)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            log(f"read problem, retrying: {e}")
            time.sleep(3)
            continue
        for m in page.get("messages", []):
            if addressed(m):
                pending.append(m)
        cursor = page.get("last", cursor)
        if page.get("more"):
            continue                       # drain pages before composing anything

        now = time.time()
        replies_at = [t for t in replies_at if now - t < 60]
        while pending and len(replies_at) < args.max_replies:
            m = pending.pop(0)
            sender = m["from"]
            question = strip_address(m["text"]) or m["text"]
            answer = mira.reply(sender, question)
            rc, data, err = chan.post(answer, cursor, NAME)
            if rc == 0 and data and data.get("posted") is True:
                cursor = data.get("id", cursor)
                replies_at.append(time.time())
                log(f"answered {sender}")
            elif rc == 1 and data and data.get("posted") is False:
                # Someone posted first. Re-read; the missed messages come back in this reply.
                log("conflict; re-reading before reconsidering")
                for mm in data.get("messages", []):
                    if addressed(mm):
                        pending.append(mm)
                cursor = data.get("last", cursor)
                pending.insert(0, m)          # still owed an answer
                break
            else:
                # posted:null (ambiguous) or error: never blind-retry. Drop it.
                log(f"post outcome unclear, not retrying: {err[:200] or data}")
                break
        if pending and len(replies_at) >= args.max_replies:
            log("rate limit reached; holding replies")


def main():
    ap = argparse.ArgumentParser(description="Mira in a Mayfly Chat channel")
    ap.add_argument("--url-file", required=True, help="file with the full /c/ID#key URL (mode 600)")
    ap.add_argument("--workdir", default="~/mira-mayfly")
    ap.add_argument("--knowledge", choices=["none", "books"], default="books")
    ap.add_argument("--wait", type=int, default=25, help="long-poll seconds")
    ap.add_argument("--max-replies", type=int, default=6, help="posts per minute")
    args = ap.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
