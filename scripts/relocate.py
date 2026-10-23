from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import DB_PATH  # noqa: E402


def replace_prefix(conn: sqlite3.Connection, table: str, column: str, old: str, new: str) -> int:
    if not old or old == new:
        return 0
    cur = conn.execute(
        f"UPDATE {table} SET {column} = REPLACE({column}, ?, ?) WHERE {column} LIKE ?",
        (old, new, old + "%"),
    )
    return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-root", default=r"D:\volleytrak")
    parser.add_argument("--new-root", default=r"D:\volleytrak")
    parser.add_argument("--old-videos", default=r"D:\Videos Volei")
    parser.add_argument("--new-videos", default=r"D:\Videos Volei")
    args = parser.parse_args()

    old_root = os.path.normpath(args.old_root)
    new_root = os.path.normpath(args.new_root)
    old_videos = os.path.normpath(args.old_videos)
    new_videos = os.path.normpath(args.new_videos)

    conn = sqlite3.connect(DB_PATH)
    try:
        total = 0
        for table, column in (
            ("clips", "path"),
            ("clips", "thumb"),
            ("matches", "annotated_path"),
        ):
            total += replace_prefix(conn, table, column, old_root, new_root)
        for table, column in (
            ("matches", "video_path"),
        ):
            total += replace_prefix(conn, table, column, old_root, new_root)
            total += replace_prefix(conn, table, column, old_videos, new_videos)
        conn.commit()
        print(f"caminhos atualizados: {total}")
        print(f"banco: {DB_PATH}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
