"""
Seed PostgreSQL with Faker-generated test data for migration testing.

Creates N tables (default 100) with M rows each (default 1,000,000).
Uses PostgreSQL COPY for fast bulk loading.

Usage:
    python scripts/seed_postgres.py
    python scripts/seed_postgres.py --tables 100 --rows-per-table 1000000
    python scripts/seed_postgres.py --tables 5 --rows-per-table 10000   # quick test
    python scripts/seed_postgres.py --start-table 1 --end-table 10       # partial run
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import uuid

# Ensure progress prints immediately when piped to a log file.
def _log(msg: str) -> None:
    print(msg, flush=True)
from pathlib import Path

import psycopg2
from faker import Faker
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import POSTGRES_CONFIG

TABLE_PREFIX = "seed_table_"
COLUMNS = (
    "id",
    "record_uuid",
    "full_name",
    "email",
    "phone",
    "address",
    "amount",
    "quantity",
    "is_active",
    "created_at",
    "birth_date",
    "metadata",
    "notes",
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    id BIGINT PRIMARY KEY,
    record_uuid UUID NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(30),
    address TEXT,
    amount NUMERIC(12, 2),
    quantity INTEGER,
    is_active BOOLEAN,
    created_at TIMESTAMP,
    birth_date DATE,
    metadata JSONB,
    notes TEXT
);
"""


def table_name(index: int) -> str:
    return f"{TABLE_PREFIX}{index:03d}"


def connect():
    return psycopg2.connect(
        host=POSTGRES_CONFIG["host"],
        port=POSTGRES_CONFIG["port"],
        dbname=POSTGRES_CONFIG["database"],
        user=POSTGRES_CONFIG["username"],
        password=POSTGRES_CONFIG["password"],
    )


def create_table(cur, name: str) -> None:
    cur.execute(CREATE_TABLE_SQL.format(table=name))


def get_row_count(cur, name: str) -> int:
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(name)))
    return cur.fetchone()[0]


class FakerPool:
    """Pre-generates Faker values once, then reuses them for high throughput."""

    def __init__(self, fake: Faker, pool_size: int = 10_000) -> None:
        _log(f"  Building Faker pool ({pool_size:,} samples)...")
        t0 = time.time()
        self.names = [fake.name()[:100] for _ in range(pool_size)]
        self.emails = [fake.email() for _ in range(pool_size)]
        self.phones = [fake.msisdn()[:30] for _ in range(pool_size)]
        self.addresses = [
            f"{fake.building_number()} {fake.street_name()}, {fake.city()}"[:500]
            for _ in range(pool_size)
        ]
        self.amounts = [round(fake.random.uniform(0, 99999.99), 2) for _ in range(pool_size)]
        self.quantities = [fake.random_int(min=0, max=10000) for _ in range(pool_size)]
        self.flags = [fake.random_int(0, 1) == 1 for _ in range(pool_size)]
        self.timestamps = [
            fake.date_time_between(start_date="-5y", end_date="now") for _ in range(pool_size)
        ]
        self.dates = [
            fake.date_of_birth(minimum_age=18, maximum_age=80) for _ in range(pool_size)
        ]
        self.metadata = [
            json.dumps({"city": fake.city(), "country_code": fake.country_code(), "score": fake.random_int(1, 100)})
            for _ in range(pool_size)
        ]
        self.notes = [fake.sentence(nb_words=6)[:200] for _ in range(pool_size)]
        self.pool_size = pool_size
        _log(f"  Pool ready in {time.time() - t0:.1f}s")

    def row(self, row_id: int) -> tuple:
        i = row_id % self.pool_size
        return (
            row_id,
            str(uuid.uuid4()),
            self.names[i],
            self.emails[i],
            self.phones[i],
            self.addresses[i],
            self.amounts[i],
            self.quantities[i],
            self.flags[i],
            self.timestamps[i],
            self.dates[i],
            self.metadata[i],
            self.notes[i],
        )

    def batch(self, start_id: int, count: int) -> list[tuple]:
        return [self.row(start_id + i) for i in range(count)]


def copy_batch(cur, name: str, rows: list[tuple]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in COLUMNS)
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV)").format(
        sql.Identifier(name), col_list
    )
    cur.copy_expert(copy_sql.as_string(cur.connection), buffer)


def seed_table(
    conn,
    pool: FakerPool,
    index: int,
    rows_per_table: int,
    batch_size: int,
    skip_existing: bool,
) -> int:
    name = table_name(index)
    cur = conn.cursor()

    create_table(cur, name)
    conn.commit()

    existing = get_row_count(cur, name)
    if skip_existing and existing >= rows_per_table:
        _log(f"  SKIP {name}: already has {existing:,} rows")
        cur.close()
        return existing

    if existing > 0:
        _log(f"  TRUNCATE {name} (had {existing:,} rows)")
        cur.execute(sql.SQL("TRUNCATE {}").format(sql.Identifier(name)))
        conn.commit()

    inserted = 0
    start = time.time()
    table_start = start

    while inserted < rows_per_table:
        current_batch = min(batch_size, rows_per_table - inserted)
        batch_rows = pool.batch(inserted + 1, current_batch)
        copy_batch(cur, name, batch_rows)
        conn.commit()
        inserted += current_batch

        if inserted % (batch_size * 10) == 0 or inserted == rows_per_table:
            elapsed = time.time() - table_start
            rate = inserted / elapsed if elapsed > 0 else 0
            _log(
                f"    {name}: {inserted:,}/{rows_per_table:,} rows "
                f"({rate:,.0f} rows/s)"
            )

    cur.close()
    total_time = time.time() - start
    _log(
        f"  DONE {name}: {inserted:,} rows in {total_time:.1f}s "
        f"({inserted / total_time:,.0f} rows/s)"
    )
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed PostgreSQL with Faker data for migration testing."
    )
    parser.add_argument("--tables", type=int, default=100, help="Number of tables")
    parser.add_argument(
        "--rows-per-table",
        type=int,
        default=1_000_000,
        help="Rows per table (default: 1,000,000)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50_000, help="COPY batch size"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Parallel table workers (1-4)"
    )
    parser.add_argument(
        "--pool-size", type=int, default=10_000, help="Faker value pool size per table"
    )
    parser.add_argument("--start-table", type=int, default=1, help="First table index")
    parser.add_argument(
        "--end-table", type=int, default=None, help="Last table index (inclusive)"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-seed even if table already has enough rows",
    )
    parser.add_argument("--seed", type=int, default=42, help="Faker random seed")
    return parser.parse_args()


def _worker_seed(args_tuple: tuple) -> tuple[int, int]:
    """Seed one table in a worker process. Returns (table_index, row_count)."""
    index, rows_per_table, batch_size, skip_existing, seed, pool_size = args_tuple
    fake = Faker()
    Faker.seed(seed + index)
    pool = FakerPool(fake, pool_size=pool_size)
    conn = connect()
    try:
        count = seed_table(conn, pool, index, rows_per_table, batch_size, skip_existing)
        return index, count
    finally:
        conn.close()


def main() -> None:
    args = parse_args()
    end_table = args.end_table or args.tables
    skip_existing = not args.no_skip_existing
    workers = max(1, min(args.workers, 8))

    total_rows = (end_table - args.start_table + 1) * args.rows_per_table

    _log("=" * 60)
    _log("PostgreSQL Faker Seed Script")
    _log("=" * 60)
    _log(f"Database:  {POSTGRES_CONFIG['database']} @ {POSTGRES_CONFIG['host']}")
    _log(f"Tables:    {TABLE_PREFIX}{args.start_table:03d} .. {TABLE_PREFIX}{end_table:03d}")
    _log(f"Rows:      {args.rows_per_table:,} per table")
    _log(f"Total:     {total_rows:,} rows")
    _log(f"Batch:     {args.batch_size:,}")
    _log(f"Workers:   {workers}")
    _log("=" * 60)

    overall_start = time.time()
    grand_total = 0
    table_indices = list(range(args.start_table, end_table + 1))

    if workers == 1:
        fake = Faker()
        Faker.seed(args.seed)
        conn = connect()
        try:
            for index in table_indices:
                _log(f"\n[{index}/{end_table}] Seeding {table_name(index)}...")
                pool = FakerPool(fake, pool_size=args.pool_size)
                count = seed_table(
                    conn, pool, index,
                    args.rows_per_table, args.batch_size, skip_existing,
                )
                grand_total += count
        finally:
            conn.close()
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        tasks = [
            (i, args.rows_per_table, args.batch_size, skip_existing, args.seed, args.pool_size)
            for i in table_indices
        ]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker_seed, t): t[0] for t in tasks}
            for future in as_completed(futures):
                index, count = future.result()
                _log(f"\n[{index}/{end_table}] Finished {table_name(index)}: {count:,} rows")
                grand_total += count

    elapsed = time.time() - overall_start
    _log("\n" + "=" * 60)
    _log(f"COMPLETE: {grand_total:,} rows across {len(table_indices)} tables")
    _log(f"Time: {elapsed / 60:.1f} minutes ({grand_total / elapsed:,.0f} rows/s avg)")
    _log("=" * 60)


if __name__ == "__main__":
    main()
