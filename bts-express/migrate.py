#!/usr/bin/env python3
"""JSON fayldagi ma'lumotlarni PostgreSQL'ga (RDS) ko'chirish.

  BTS_STORAGE=postgres DB_HOST=... DB_USER=... DB_PASSWORD=... (yoki DB_SECRET_ID=...) python3 migrate.py data/db.json

Maqsad baza bo'sh bo'lishi kerak; to'la bo'lsa --force kerak (mavjud yozuvlar ustiga yoziladi).
"""
import json
import sys

import cloud
import storage

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    raise SystemExit(__doc__)
cfg = cloud.Config()
if cfg.storage == "json":
    raise SystemExit("BTS_STORAGE=postgres (yoki sqlite) qilib qo'ying")
store = storage.make_store(cfg)
if store.load() is not None and "--force" not in sys.argv:
    raise SystemExit("Maqsad baza bo'sh emas. Ustiga yozish uchun --force bering")
with open(args[0], encoding="utf-8") as f:
    db = json.load(f)
store.save(db)
print("Ko'chirildi: %s" % json.dumps(store.info(), ensure_ascii=False))
