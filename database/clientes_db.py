import sqlite3
from typing import List, Optional
from database.conexion import obtener_conexion


def buscar_cliente_por_telefono(telefono: str) -> Optional[sqlite3.Row]:
    """Busca un cliente por su número telefónico exacto."""
    query = "SELECT * FROM clientes WHERE telefono = ?;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (telefono.strip(),))
        return cursor.fetchone()


def registrar_cliente_rapido(nombre: str, telefono: str) -> int:
    """Registra rápidamente a un cliente con valores de crédito predeterminados."""
    query = """
        INSERT INTO clientes (
            nombre, telefono, puntos_acumulados, limite_credito, saldo_pendiente
        ) VALUES (?, ?, 0, 1000.0, 0.0);
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nombre.strip(), telefono.strip()))
        conn.commit()
        return cursor.lastrowid


def actualizar_limite_credito_cliente(id_cliente: int, nuevo_limite: float):
    """Actualiza el tope máximo de crédito otorgado a un cliente."""
    query = "UPDATE clientes SET limite_credito = ? WHERE id_cliente = ?;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nuevo_limite, id_cliente))
        conn.commit()


def obtener_clientes_con_deuda_y_envases() -> List[sqlite3.Row]:
    """Obtiene el listado de clientes calculando saldo pendiente, envases y garantías retenidas."""
    query = """
        SELECT 
            c.id_cliente,
            c.nombre,
            c.telefono,
            c.puntos_acumulados,
            COALESCE(c.limite_credito, 0.0) AS limite_credito,
            COALESCE(c.saldo_pendiente, 0.0) AS saldo_pendiente,
            COALESCE(SUM(CASE WHEN re.estado = 'Pendiente' THEN (re.cantidad_prestada - re.cantidad_devuelta) ELSE 0 END), 0) AS envases_pendientes,
            COALESCE(SUM(CASE WHEN re.estado = 'Pendiente' THEN (re.cantidad_prestada - re.cantidad_devuelta) * re.deposito_unitario ELSE 0 END), 0.0) AS importe_envases_retenido
        FROM clientes c
        LEFT JOIN registro_envases re ON c.id_cliente = re.id_cliente
        GROUP BY c.id_cliente
        ORDER BY c.saldo_pendiente DESC, c.nombre ASC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def registrar_abono_credito(
    id_cliente: int, id_empleado: int, monto_abono: float
) -> float:
    """Registra un abono a cuenta de deuda, actualiza saldo y genera entrada de caja."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO abonos_credito (id_cliente, id_empleado, monto) VALUES (?, ?, ?);",
            (id_cliente, id_empleado, monto_abono),
        )
        cursor.execute(
            "UPDATE clientes SET saldo_pendiente = MAX(0.0, saldo_pendiente - ?) WHERE id_cliente = ?;",
            (monto_abono, id_cliente),
        )
        cursor.execute(
            """
            INSERT INTO movimientos_caja (tipo, monto, motivo, id_empleado, fecha_hora) 
            VALUES ('Entrada', ?, 'Abono a Cuenta Fiada (Cliente #' || ? || ')', ?, datetime('now', 'localtime'));
            """,
            (monto_abono, id_cliente, id_empleado),
        )
        cursor.execute(
            "SELECT saldo_pendiente FROM clientes WHERE id_cliente = ?;",
            (id_cliente,),
        )
        saldo_nuevo = cursor.fetchone()["saldo_pendiente"]
        conn.commit()
        return saldo_nuevo


def obtener_envases_pendientes_por_cliente(id_cliente: int) -> List[sqlite3.Row]:
    """Obtiene los registros de envases prestados que aún no se han devuelto."""
    query = """
        SELECT 
            re.id_registro,
            re.id_producto,
            p.nombre AS producto,
            (re.cantidad_prestada - re.cantidad_devuelta) AS cantidad_pendiente,
            re.deposito_unitario,
            strftime('%Y-%m-%d %I:%M %p', re.fecha_prestamo) AS fecha
        FROM registro_envases re
        INNER JOIN productos p ON re.id_producto = p.id_producto
        WHERE re.id_cliente = ? AND re.estado = 'Pendiente' AND (re.cantidad_prestada - re.cantidad_devuelta) > 0
        ORDER BY re.id_registro ASC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (id_cliente,))
        return cursor.fetchall()


def procesar_devolucion_envases_cliente(
    id_cliente: int,
    id_empleado: int,
    cant_a_devolver: int,
    metodo_devolucion: str = "Efectivo",
) -> float:
    """Registra la devolución de envases bajo criterio FIFO y aplica reembolso o saldo a favor."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id_registro, (cantidad_prestada - cantidad_devuelta) AS faltante, deposito_unitario
            FROM registro_envases
            WHERE id_cliente = ? AND estado = 'Pendiente' AND (cantidad_prestada - cantidad_devuelta) > 0
            ORDER BY id_registro ASC;
            """,
            (id_cliente,),
        )
        pendientes = cursor.fetchall()

        restante_por_devolver = cant_a_devolver
        total_dinero_reembolso = 0.0

        for reg in pendientes:
            if restante_por_devolver <= 0:
                break

            disponible_en_reg = reg["faltante"]
            deposito_u = reg["deposito_unitario"]

            a_devolver_en_este = min(disponible_en_reg, restante_por_devolver)
            total_dinero_reembolso += a_devolver_en_este * deposito_u
            restante_por_devolver -= a_devolver_en_este

            cursor.execute(
                """
                UPDATE registro_envases 
                SET cantidad_devuelta = cantidad_devuelta + ?,
                    estado = CASE WHEN (cantidad_prestada <= cantidad_devuelta + ?) THEN 'Devuelto' ELSE 'Pendiente' END,
                    fecha_devolucion = datetime('now', 'localtime')
                WHERE id_registro = ?;
                """,
                (a_devolver_en_este, a_devolver_en_este, reg["id_registro"]),
            )

        if metodo_devolucion == "Abonar a Deuda":
            cursor.execute(
                """
                UPDATE clientes 
                SET saldo_pendiente = MAX(0.0, saldo_pendiente - ?)
                WHERE id_cliente = ?;
                """,
                (total_dinero_reembolso, id_cliente),
            )
            cursor.execute(
                """
                INSERT INTO abonos_credito (id_cliente, id_empleado, monto)
                VALUES (?, ?, ?);
                """,
                (id_cliente, id_empleado, total_dinero_reembolso),
            )
        else:
            cursor.execute(
                """
                INSERT INTO movimientos_caja (tipo, monto, motivo, id_empleado, fecha_hora)
                VALUES ('Salida', ?, 'Reembolso por devolución de ' || ? || ' envase(s) (Cliente #' || ? || ')', ?, datetime('now', 'localtime'));
                """,
                (total_dinero_reembolso, cant_a_devolver, id_cliente, id_empleado),
            )

        conn.commit()
        return total_dinero_reembolso