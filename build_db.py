# -*- coding: utf-8 -*-
"""把 JMdict_e.xml 转成 SQLite 词库 jmdict.db。

只需要 JMdict_e.xml（`python setup_data.py` 会自动下载）。

建出的表：
  entries(seq, kanji, kana)        词条：seq=词条ID, kanji=全部词形('|'分隔), kana=全部假名
  senses(seq, pos, gloss)          义项：pos=词性, gloss=英文释义
  word_forms(word_form, seq)       词形→词条映射（每个 kanji/假名 值一行），用于精确查词
  grammar(...) / jlpt(...) /       由 setup_data.py 填充；
  gloss_zh(...) / examples(...)    这里先建空表，保证接口不会因为「表不存在」报 503
"""
from __future__ import annotations

import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
XML = ROOT / "JMdict_e.xml"
DB = ROOT / "jmdict.db"

if not XML.is_file():
    print(f"[x] 找不到 {XML.name}")
    print("    先运行  python setup_data.py   让它自动下载，")
    print("    或手动从 https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project")
    print("    下载 JMdict_e.gz 解压后放到本目录。")
    sys.exit(1)

if DB.exists():
    backup = DB.with_suffix(".db.bak")
    DB.replace(backup)
    print(f"[i] 已有词库已备份为 {backup.name}")

conn = sqlite3.connect(str(DB))
conn.execute("PRAGMA journal_mode=OFF")
conn.execute("PRAGMA synchronous=OFF")

# --- 词库表 -------------------------------------------------------------
conn.execute("CREATE TABLE entries (seq INTEGER PRIMARY KEY, kanji TEXT, kana TEXT)")
conn.execute("CREATE TABLE senses (seq INTEGER, pos TEXT, gloss TEXT)")
conn.execute("CREATE TABLE word_forms (word_form TEXT, seq INTEGER)")
conn.execute("CREATE INDEX idx_entries_kanji ON entries(kanji)")
conn.execute("CREATE INDEX idx_entries_kana ON entries(kana)")
conn.execute("CREATE INDEX idx_senses_seq ON senses(seq)")
conn.execute("CREATE INDEX idx_word_forms ON word_forms(word_form)")
# 「按 seq 反查词形」全靠这个索引；缺了它每次全表扫 49 万行（实测慢 300 倍以上）
conn.execute("CREATE INDEX idx_word_forms_seq ON word_forms(seq)")

# --- 增强表（空壳，setup_data.py 会填充）--------------------------------
conn.execute(
    "CREATE TABLE grammar (id INTEGER PRIMARY KEY, pattern TEXT, explain TEXT, "
    "level TEXT, connection TEXT, examples TEXT, explain_zh TEXT)"
)
conn.execute("CREATE INDEX idx_grammar_level ON grammar(level)")
conn.execute("CREATE TABLE jlpt (word_form TEXT PRIMARY KEY, level TEXT)")
conn.execute("CREATE TABLE gloss_zh (word_form TEXT PRIMARY KEY, accent TEXT, gloss TEXT)")
conn.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, jpn TEXT, cmn TEXT)")
conn.execute("CREATE INDEX idx_examples_jpn ON examples(jpn)")

count = 0
e_buf: list[tuple] = []
s_buf: list[tuple] = []
w_buf: list[tuple] = []


def flush() -> None:
    conn.executemany("INSERT INTO entries VALUES (?,?,?)", e_buf)
    conn.executemany("INSERT INTO senses VALUES (?,?,?)", s_buf)
    conn.executemany("INSERT INTO word_forms VALUES (?,?)", w_buf)
    e_buf.clear()
    s_buf.clear()
    w_buf.clear()


print(f"[i] 解析 {XML.name} …")
for _event, elem in ET.iterparse(str(XML), events=("end",)):
    if elem.tag != "entry":
        continue
    seq = int(elem.findtext("ent_seq") or 0)
    kanji_vals = [k.findtext("keb") or "" for k in elem.findall("k_ele")]
    kana_vals = [r.findtext("reb") or "" for r in elem.findall("r_ele")]

    for s in elem.findall("sense"):
        pos = "|".join(p.text or "" for p in s.findall("pos"))
        gloss = "|".join(g.text or "" for g in s.findall("gloss"))
        if gloss:
            s_buf.append((seq, pos, gloss))

    e_buf.append((seq, "|".join(kanji_vals), "|".join(kana_vals)))
    for kb in kanji_vals:
        w_buf.append((kb, seq))
    for rb in kana_vals:
        w_buf.append((rb, seq))

    count += 1
    elem.clear()

    if len(e_buf) >= 5000:
        flush()

flush()
conn.commit()
try:
    conn.execute("ANALYZE")
    conn.commit()
except sqlite3.Error:
    pass

n_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
n_senses = conn.execute("SELECT COUNT(*) FROM senses").fetchone()[0]
n_forms = conn.execute("SELECT COUNT(*) FROM word_forms").fetchone()[0]
conn.close()

print(f"[+] 词库完成：{n_entries} 词条 / {n_senses} 义项 / {n_forms} 词形 -> {DB.name}")
print("    提示：语法、JLPT 分级、中文释义、例句由 setup_data.py 统一补全。")
