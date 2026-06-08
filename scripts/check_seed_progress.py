"""Quick check of seed_table_* progress in PostgreSQL."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from config.settings import POSTGRES_CONFIG

conn = psycopg2.connect(
    host=POSTGRES_CONFIG["host"],
    port=POSTGRES_CONFIG["port"],
    dbname=POSTGRES_CONFIG["database"],
    user=POSTGRES_CONFIG["username"],
    password=POSTGRES_CONFIG["password"],
)
cur = conn.cursor()
cur.execute(
    "SELECT tablename FROM pg_tables "
    "WHERE schemaname='public' AND tablename LIKE 'seed_table_%' "
    "ORDER BY tablename"
)
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {len(tables)}")

complete = 0
partial = 0
total_rows = 0
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    total_rows += count
    if count >= 1_000_000:
        complete += 1
    elif count > 0:
        partial += 1

print(f"Complete (1M rows): {complete}")
print(f"In progress:        {partial}")
print(f"Total rows:         {total_rows:,}")
conn.close()
