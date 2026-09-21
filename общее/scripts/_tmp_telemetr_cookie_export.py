# -*- coding: utf-8 -*-
"""Decrypt cursor-browser cookies for telemetr.me."""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from Cryptodome.Cipher import AES  # type: ignore
import win32crypt  # type: ignore

SNAP = Path(__file__).resolve().parents[1] / "tgads-snapshots"
SNAP.mkdir(exist_ok=True)

SRC = Path(os.environ["APPDATA"]) / "Cursor/Partitions/cursor-browser/Network/Cookies"
DST = SNAP / "_cursor_telemetr_cookies.db"
OUT = SNAP / "_telemetr_cookies.json"

if DST.exists():
    DST.unlink()
try:
    shutil.copy2(SRC, DST)
except Exception as exc:
    print("copy2 failed", exc)
    uri = SRC.resolve().as_uri() + "?mode=ro"
    src_conn = sqlite3.connect(uri, uri=True, timeout=30)
    dst_conn = sqlite3.connect(DST)
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
print("copied cookies db", DST.stat().st_size)

local_state = json.loads(
    (Path(os.environ["APPDATA"]) / "Cursor/Local State").read_text(encoding="utf-8")
)
enc_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
assert enc_key.startswith(b"DPAPI")
key = win32crypt.CryptUnprotectData(enc_key[5:], None, None, None, 0)[1]


def decrypt(blob: bytes) -> str:
    if not blob:
        return ""
    if blob.startswith(b"v10") or blob.startswith(b"v20"):
        iv = blob[3:15]
        payload = blob[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        return cipher.decrypt_and_verify(payload[:-16], payload[-16:]).decode(
            "utf-8", errors="replace"
        )
    try:
        return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1].decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


conn = sqlite3.connect(DST)
rows = conn.execute(
    "SELECT host_key, name, value, encrypted_value, path, is_secure, is_httponly "
    "FROM cookies WHERE host_key LIKE '%telemetr%' ORDER BY host_key, name"
).fetchall()
print("telemetr cookie rows", len(rows))

cookies: dict[str, str] = {}
cookie_list: list[dict] = []
for host, name, value, enc, path, secure, httponly in rows:
    plain = value or decrypt(enc or b"")
    cookies[name] = plain
    cookie_list.append(
        {
            "host": host,
            "name": name,
            "value": plain,
            "path": path,
            "secure": bool(secure),
            "httponly": bool(httponly),
        }
    )
    shown = plain if len(plain) <= 48 else plain[:48] + "..."
    print(f"{host} {name} httponly={httponly} {shown}")

OUT.write_text(
    json.dumps({"map": cookies, "list": cookie_list}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("wrote", OUT, "keys", list(cookies))
