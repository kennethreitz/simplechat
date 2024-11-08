from records import Database as RecordsDatabase


class Database:
    def __init__(self, db_path="sqlite:///simplechat.db", *, migrate=True):
        # Initialize the database.
        self.db = RecordsDatabase(db_path)

        if migrate:
            # Perform migration.
            self.migrate()

    def migrate(self):
        """Creates the tables."""
        scheme_1 = """
            CREATE TABLE IF NOT EXISTS memory (
                    entity TEXT,
                    source TEXT,
                    last_mentioned TIMESTAMP,
                    mention_count INTEGER DEFAULT 1,
                    PRIMARY KEY (entity, source)
                )
        """

        scheme_2 = """
            CREATE TABLE IF NOT EXISTS essence_markers (
                marker_type TEXT,
                marker_text TEXT,
                timestamp TIMESTAMP,
                PRIMARY KEY (marker_type, marker_text)
            )
        """

        schemes = [scheme_1, scheme_2]

        for scheme in schemes:
            self.query(scheme)

    @property
    def query(self):
        return self.db.query
