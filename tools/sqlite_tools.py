"""
Module:  sqlite_tools.py
Agent:   Shared (all agents)
Purpose: DatabaseManager singleton — the single gateway to SQLite via SQLAlchemy Core.
         Enforces 'all SQL through DatabaseManager, all queries parameterized'.
Inputs:  db_path (pathlib.Path) from config/paths.py
Outputs: SQLAlchemy Engine and Connection objects for agent use.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import Connection, Engine, MetaData, Table, create_engine, text


class DatabaseManager:
    """Singleton managing all SQLAlchemy Core connections to the run-scoped SQLite DB.

    Usage:
        db = DatabaseManager(paths["SQLITE_DB_PATH"])
        with db.get_connection() as conn:
            conn.execute(text("SELECT ..."), {"param": value})

    Each agent defines its own Table objects and passes them to create_tables().
    The DatabaseManager itself has zero knowledge of any table schema.
    """

    _instances: dict[Path, "DatabaseManager"] = {}

    def __new__(cls, db_path: Path) -> "DatabaseManager":
        """Ensure only one DatabaseManager exists per db_path (singleton)."""
        resolved = db_path.resolve()
        if resolved not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[resolved] = instance
        return cls._instances[resolved]

    def __init__(self, db_path: Path) -> None:
        """Initialize the DatabaseManager with a path to the SQLite database.

        Args:
            db_path: Path to the SQLite database file (from config/paths.py).
        """
        if self._initialized:
            return

        self._db_path: Path = db_path.resolve()
        self._engine: Engine | None = None
        self._metadata: MetaData = MetaData()
        self._initialized: bool = True

    @property
    def metadata(self) -> MetaData:
        """Return the shared MetaData instance for table definitions."""
        return self._metadata

    def get_engine(self) -> Engine:
        """Return the SQLAlchemy Engine, creating it lazily on first call."""
        if self._engine is None:
            # Ensure parent directory exists so SQLite can create the file
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(
                f"sqlite:///{self._db_path}",
                echo=False,
            )
        return self._engine

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Yield a SQLAlchemy Connection as a context manager.

        Commits on clean exit, rolls back on exception.

        Usage:
            with db.get_connection() as conn:
                conn.execute(stmt)
        """
        engine = self.get_engine()
        with engine.connect() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def create_tables(self, tables: list[Table]) -> None:
        """Create the given tables in the database if they don't already exist.

        Args:
            tables: List of SQLAlchemy Table objects to create.
        """
        engine = self.get_engine()
        self._metadata.create_all(engine, tables=tables)

    def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> Any:
        """Execute a parameterized SQL statement and return the result.

        This is a convenience wrapper for simple one-shot queries.
        For multi-statement transactions, use get_connection() instead.

        Args:
            stmt: A SQLAlchemy text() or compiled statement.
            params: Optional dict of bind parameters.

        Returns:
            The CursorResult from SQLAlchemy.
        """
        with self.get_connection() as conn:
            if params is not None:
                return conn.execute(stmt, params)
            return conn.execute(stmt)

    def dispose(self) -> None:
        """Dispose of the engine and remove this instance from the singleton cache.

        Call this at end-of-run or in test teardown to cleanly release resources.
        """
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

        resolved = self._db_path
        if resolved in self._instances:
            del self._instances[resolved]
        self._initialized = False
