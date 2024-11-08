import sqlite3
from datetime import datetime
import time
import traceback
from typing import List, Optional, Tuple
from contextlib import contextmanager


class Database:
    def __init__(self, db_path="simplechat.db", *, migrate=True):
        if db_path.startswith("sqlite:///"):
            db_path = db_path[10:]
        self.db_path = db_path
        if migrate:
            self.migrate()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, **params) -> List[sqlite3.Row]:
        """Execute a query and return all results"""
        with self.get_connection() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, **params) -> None:
        """Execute a query with no return value"""
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def migrate(self):
        """Creates the tables."""
        schemes = [
            """
            CREATE TABLE IF NOT EXISTS memory (
                entity TEXT,
                source TEXT,
                last_mentioned TIMESTAMP,
                mention_count INTEGER DEFAULT 1,
                PRIMARY KEY (entity, source)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS essence_markers (
                marker_type TEXT,
                marker_text TEXT,
                timestamp TIMESTAMP,
                PRIMARY KEY (marker_type, marker_text)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS identity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP,
                last_seen TIMESTAMP
            )
            """,
        ]

        with self.get_connection() as conn:
            for scheme in schemes:
                conn.execute(scheme)
            conn.commit()

    def store_entity(self, entity: str, source: str = "user") -> None:
        """Store or update an entity in the memory table"""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO memory (entity, source, last_mentioned, mention_count)
                    VALUES (:entity, :source, :timestamp, 1)
                    ON CONFLICT(entity, source) DO UPDATE SET
                        last_mentioned = :timestamp,
                        mention_count = mention_count + 1
                """,
                    {"entity": entity, "source": source, "timestamp": now},
                )
                conn.commit()
        except Exception as e:
            print(f"ERROR storing entity: {e}")
            traceback.print_exc()

    def retrieve_recent_entities(self, days: int = 7) -> List[Tuple]:
        """Retrieve entities with improved error handling"""
        try:
            with self.get_connection() as conn:
                result = conn.execute(
                    """
                    SELECT
                        entity,
                        COUNT(*) as total_mentions,
                        SUM(CASE WHEN source = 'user' THEN 1 ELSE 0 END) as user_mentions,
                        SUM(CASE WHEN source = 'llm' THEN 1 ELSE 0 END) as llm_mentions
                    FROM memory
                    WHERE last_mentioned >= datetime('now', ?)
                    GROUP BY entity
                    ORDER BY total_mentions DESC
                """,
                    (f"-{days} days",),
                )

                return [
                    (
                        row["entity"],
                        row["total_mentions"],
                        row["user_mentions"],
                        row["llm_mentions"],
                    )
                    for row in result.fetchall()
                ]
        except Exception as e:
            print(f"Database error in retrieve_recent_entities: {e}")
            traceback.print_exc()
            return []

    def store_essence_marker(self, marker_type: str, marker_text: str) -> None:
        """Store essence marker in database"""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO essence_markers
                    (marker_type, marker_text, timestamp)
                    VALUES (?, ?, ?)
                """,
                    (marker_type, marker_text, now),
                )
                conn.commit()
        except Exception as e:
            print(f"ERROR storing essence marker: {e}")
            traceback.print_exc()

    def retrieve_essence_markers(self, days: int = 30) -> List[Tuple[str, str]]:
        """Retrieve essence markers"""
        try:
            with self.get_connection() as conn:
                result = conn.execute(
                    """
                    SELECT marker_type, marker_text
                    FROM essence_markers
                    WHERE timestamp >= datetime('now', ?)
                    ORDER BY timestamp DESC
                """,
                    (f"-{days} days",),
                )

                return [
                    (row["marker_type"], row["marker_text"])
                    for row in result.fetchall()
                ]
        except Exception as e:
            print(f"Database error in retrieve_essence_markers: {e}")
            traceback.print_exc()
            return []

    def store_identity(self, identity: str) -> None:
        """Store or update user identity"""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO identity (identity, created_at, last_seen)
                    VALUES (?, ?, ?)
                    ON CONFLICT(identity) DO UPDATE SET
                        last_seen = ?
                """,
                    (identity, now, now, now),
                )
                conn.commit()
        except Exception as e:
            print(f"ERROR storing identity: {e}")
            traceback.print_exc()

    def get_identity(self) -> Optional[str]:
        """Retrieve most recently seen identity"""
        try:
            with self.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT identity
                    FROM identity
                    ORDER BY last_seen DESC
                    LIMIT 1
                """
                ).fetchone()
                return row["identity"] if row else None
        except Exception as e:
            print(f"ERROR getting identity: {e}")
            traceback.print_exc()
            return None

    def update_last_seen(self, identity: str) -> None:
        """Update last_seen timestamp for an identity with retry logic"""
        max_retries = 3
        retry_delay = 0.1  # seconds

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE identity
                        SET last_seen = datetime('now')
                        WHERE identity = ?
                    """,
                        (identity,),
                    )
                    conn.commit()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    print(
                        f"Warning: Failed to update last_seen for {identity}: {str(e)}"
                    )
