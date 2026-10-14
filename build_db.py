# -*- coding: utf-8 -*-
"""把 JMdict_e.xml 转成 SQLite 词库 jmdict.db。

表结构：
  entries(seq, kanji, kana)    词条：seq=词条ID, kanji=全部词形('|'分隔), kana=全部假名
  senses(seq, pos, gloss)      义项：pos=词性, gloss=英文释义
  word_forms(word_form, seq)   词形→词条映射（每个 kanji/假名 值一行），用于精确查词

精确查词示例：
  SELECT seq FROM word_forms WHERE word_form = '食べる'
"""
import xml.etree.ElementTree as ET
import sqlite3
import os

XML = os.path.join(os.path.dirname(__file__), "JMdict_e.xml")
DB = os.path.join(os.path.dirname(__file__), "jmdict.db")

if os.path.exists(DB):
    os.remove(DB)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=OFF")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("CREATE TABLE entries (seq INTEGER PRIMARY KEY, kanji TEXT, kana TEXT)")
conn.execute("CREATE TABLE senses (seq INTEGER, pos TEXT, gloss TEXT)")
conn.execute("CREATE TABLE word_forms (word_form TEXT, seq INTEGER)")
conn.execute("CREATE INDEX idx_entries_kanji ON entries(kanji)")
conn.execute("CREATE INDEX idx_entries_kana ON entries(kana)")
conn.execute("CREATE INDEX idx_senses_seq ON senses(seq)")
conn.execute("CREATE INDEX idx_word_forms ON word_forms(word_form)")

count = 0
e_buf, s_buf, w_buf = [], [], []


def flush():
    conn.executemany("INSERT INTO entries VALUES (?,?,?)", e_buf)
    conn.executemany("INSERT INTO senses VALUES (?,?,?)", s_buf)
    conn.executemany("INSERT INTO word_forms VALUES (?,?)", w_buf)
    e_buf.clear()
    s_buf.clear()
    w_buf.clear()


for event, elem in ET.iterparse(XML, events=("end",)):
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

n_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
n_senses = conn.execute("SELECT COUNT(*) FROM senses").fetchone()[0]
n_forms = conn.execute("SELECT COUNT(*) FROM word_forms").fetchone()[0]
print(f"done: {n_entries} entries, {n_senses} senses, {n_forms} word_forms -> {DB}")
conn.close()
