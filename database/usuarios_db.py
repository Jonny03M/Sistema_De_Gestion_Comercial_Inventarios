import hashlib
import sqlite3
from typing import List, Optional
from database.conexion import obtener_conexion


def hash_password(password: str) -> str:
    """Retorna el hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def validar_login(usuario: str, password_texto: str) -> Optional[sqlite3.Row]:
    """Valida las credenciales activas comparando el hash de la contraseña."""
    password_hash = hash_password(password_texto)
    query = """
        SELECT id_empleado, nombre, apellido, puesto 
        FROM empleados 
        WHERE usuario = ? AND password = ? AND activo = 1;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (usuario, password_hash))
        return cursor.fetchone()


def obtener_todos_los_empleados() -> List[sqlite3.Row]:
    """Retorna la lista de empleados registrados ordenados por identificador."""
    query = """
        SELECT id_empleado, nombre, apellido, usuario, puesto, telefono, activo 
        FROM empleados 
        ORDER BY id_empleado ASC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def crear_empleado(
    nombre: str,
    apellido: str,
    usuario: str,
    password_texto: str,
    puesto: str = "Cajero",
    telefono: str = "",
) -> int:
    """Inserta un nuevo empleado almacenando su contraseña de forma segura."""
    password_hash = hash_password(password_texto)
    query = """
        INSERT INTO empleados (nombre, apellido, usuario, password, puesto, telefono, activo) 
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nombre, apellido, usuario, password_hash, puesto, telefono))
        conn.commit()
        return cursor.lastrowid


def actualizar_empleado(
    id_empleado: int,
    nombre: str,
    apellido: str,
    usuario: str,
    password_texto: Optional[str] = None,
    puesto: str = "Cajero",
    telefono: str = "",
):
    """Actualiza los datos del empleado, aplicando hash a la nueva clave si se especifica."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        if password_texto:
            password_hash = hash_password(password_texto)
            query = """
                UPDATE empleados 
                SET nombre = ?, apellido = ?, usuario = ?, password = ?, puesto = ?, telefono = ? 
                WHERE id_empleado = ?;
            """
            cursor.execute(
                query, (nombre, apellido, usuario, password_hash, puesto, telefono, id_empleado)
            )
        else:
            query = """
                UPDATE empleados 
                SET nombre = ?, apellido = ?, usuario = ?, puesto = ?, telefono = ? 
                WHERE id_empleado = ?;
            """
            cursor.execute(query, (nombre, apellido, usuario, puesto, telefono, id_empleado))
        conn.commit()


def cambiar_estado_empleado(id_empleado: int, nuevo_estado: int):
    """Activa (1) o desactiva (0) a un empleado en el sistema."""
    query = "UPDATE empleados SET activo = ? WHERE id_empleado = ?;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nuevo_estado, id_empleado))
        conn.commit()