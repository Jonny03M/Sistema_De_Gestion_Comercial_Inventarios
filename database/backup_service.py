from datetime import datetime
import os
from pathlib import Path
import sqlite3
from typing import Optional

from database.conexion import DB_PATH, obtener_conexion

CARPETA_RESPALDOS = Path(__file__).resolve().parent.parent / "backups"
MAX_RESPALDOS_CONSERVADOS = 15


def asegurar_directorio_respaldos() -> Path:
    """Crea la carpeta de respaldos si aún no existe."""
    if not CARPETA_RESPALDOS.exists():
        CARPETA_RESPALDOS.mkdir(parents=True, exist_ok=True)
    return CARPETA_RESPALDOS


def generar_respaldo_automatico(sufijo: str = "auto") -> Optional[Path]:
    """Genera una copia en caliente de la base de datos con SQLite Backup API

    y depura copias antiguas según la política de retención.
    """
    if not DB_PATH.exists():
        return None

    directorio = asegurar_directorio_respaldos()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"tienda_backup_{timestamp}_{sufijo}.db"
    ruta_destino = directorio / nombre_archivo

    try:
        # Copia segura (Online Backup API)
        with obtener_conexion() as conn_origen:
            with sqlite3.connect(str(ruta_destino)) as conn_destino:
                conn_origen.backup(conn_destino, pages=20, sleep=0.01)

        rotar_respaldos_antiguos()

        return ruta_destino
    except Exception as err:
        print(f"Error al generar respaldo de base de datos: {err}")
        return None


def rotar_respaldos_antiguos(limite: int = MAX_RESPALDOS_CONSERVADOS):
    """Mantiene únicamente los últimos 'limite' archivos de respaldo."""
    try:
        archivos = [
            f
            for f in CARPETA_RESPALDOS.glob("tienda_backup_*.db")
            if f.is_file()
        ]

        if len(archivos) > limite:
            archivos.sort(key=lambda x: x.stat().st_mtime)
            excedente = len(archivos) - limite
            for i in range(excedente):
                try:
                    archivos[i].unlink()
                except OSError:
                    pass
    except Exception as err:
        print(f"Error durante la rotación de respaldos: {err}")