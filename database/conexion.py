import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "tienda_inventario.db"


def obtener_conexion() -> sqlite3.Connection:
    """Retorna una conexión activa a la base de datos SQLite con claves foráneas activadas
    y acceso a columnas por nombre (Row factory).
    """
    conexion = sqlite3.connect(DB_PATH, timeout=10.0)
    conexion.execute("PRAGMA foreign_keys = ON;")
    conexion.row_factory = sqlite3.Row
    return conexion