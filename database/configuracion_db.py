import sqlite3
from typing import Dict
from database.conexion import obtener_conexion


def obtener_configuraciones() -> Dict[str, str]:
    """Obtiene todas las configuraciones del sistema como un diccionario clave-valor."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor FROM configuracion;")
        filas = cursor.fetchall()
        return {f["clave"]: f["valor"] for f in filas}


def obtener_configuracion(clave: str, valor_defecto: str = "") -> str:
    """Obtiene el valor de una configuración puntual."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT valor FROM configuracion WHERE clave = ?;", (clave,)
        )
        fila = cursor.fetchone()
        return fila["valor"] if fila else valor_defecto


def guardar_configuracion(clave: str, valor: str):
    """Inserta o actualiza una clave de configuración."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO configuracion (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor;
        """,
            (clave, str(valor)),
        )
        conn.commit()


def es_modulo_activo(clave: str) -> bool:
    """Retorna True si la bandera booleana está en 'true'."""
    return obtener_configuracion(clave, "false").strip().lower() == "true"