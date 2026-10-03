from datetime import datetime
from typing import Dict, List, Optional
from database.conexion import obtener_conexion


def obtener_turno_activo(id_empleado: int) -> Optional[Dict]:
    """Retorna el turno actualmente abierto para el empleado, si existe."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM turnos_caja
            WHERE id_empleado = ? AND estado = 'Abierto'
            ORDER BY id_turno DESC LIMIT 1;
        """,
            (id_empleado,),
        )
        fila = cursor.fetchone()
        return dict(fila) if fila else None


def abrir_nuevo_turno(id_empleado: int, monto_inicial: float) -> int:
    """Registra la apertura de un turno con fondo inicial."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO turnos_caja (id_empleado, monto_inicial, estado)
            VALUES (?, ?, 'Abierto');
        """,
            (id_empleado, monto_inicial),
        )
        conn.commit()
        return cursor.lastrowid


def calcular_totales_turno(id_turno: int, id_empleado: int, fecha_apertura: str) -> Dict[str, float]:
    """Calcula las ventas en efectivo y salidas registradas desde la apertura del turno."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()

        # Ventas en efectivo durante el turno
        cursor.execute(
            """
            SELECT COALESCE(SUM(total), 0.0) AS total_ventas_efectivo
            FROM ventas
            WHERE id_empleado = ?
              AND metodo_pago = 'Efectivo'
              AND fecha_hora >= ?;
        """,
            (id_empleado, fecha_apertura),
        )
        ventas_efectivo = float(cursor.fetchone()["total_ventas_efectivo"])

        # Salidas de efectivo (gastos / pagos autorizados)
        cursor.execute(
            """
            SELECT COALESCE(SUM(monto), 0.0) AS total_salidas
            FROM movimientos_caja
            WHERE id_empleado = ?
              AND tipo = 'Salida'
              AND fecha_hora >= ?;
        """,
            (id_empleado, fecha_apertura),
        )
        salidas_efectivo = float(cursor.fetchone()["total_salidas"])

        return {
            "ventas_efectivo": ventas_efectivo,
            "salidas_efectivo": salidas_efectivo,
        }


def cerrar_turno_ciego(
    id_turno: int,
    monto_declarado: float,
    observaciones: str = "",
) -> Dict:
    """Cierra el turno registrando el conteo a ciegas y calculando internamente la diferencia."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()

        # Obtener datos del turno
        cursor.execute(
            "SELECT * FROM turnos_caja WHERE id_turno = ?;", (id_turno,)
        )
        turno = cursor.fetchone()
        if not turno:
            raise ValueError("Turno no encontrado")

        totales = calcular_totales_turno(
            id_turno=id_turno,
            id_empleado=turno["id_empleado"],
            fecha_apertura=turno["fecha_apertura"],
        )

        monto_inicial = float(turno["monto_inicial"])
        ventas = totales["ventas_efectivo"]
        salidas = totales["salidas_efectivo"]

        # Fondo inicial + cobros en efectivo - dinero que salió
        monto_esperado = monto_inicial + ventas - salidas
        diferencia = round(monto_declarado - monto_esperado, 2)

        cursor.execute(
            """
            UPDATE turnos_caja
            SET fecha_cierre = datetime('now', 'localtime'),
                ventas_efectivo = ?,
                salidas_efectivo = ?,
                monto_esperado = ?,
                monto_declarado = ?,
                diferencia = ?,
                estado = 'Cerrado',
                observaciones = ?
            WHERE id_turno = ?;
        """,
            (
                ventas,
                salidas,
                monto_esperado,
                monto_declarado,
                diferencia,
                observaciones,
                id_turno,
            ),
        )
        conn.commit()

        return {
            "id_turno": id_turno,
            "monto_declarado": monto_declarado,
            "monto_esperado": monto_esperado,
            "diferencia": diferencia,
        }


def obtener_historial_cortes(limite: int = 50) -> List[Dict]:
    """Obtiene los últimos cortes para auditoría del Administrador."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                t.id_turno,
                t.fecha_apertura,
                t.fecha_cierre,
                e.nombre || ' ' || e.apellido AS cajero,
                t.monto_inicial,
                t.ventas_efectivo,
                t.salidas_efectivo,
                t.monto_esperado,
                t.monto_declarado,
                t.diferencia,
                t.estado,
                t.observaciones
            FROM turnos_caja t
            INNER JOIN empleados e ON t.id_empleado = e.id_empleado
            ORDER BY t.id_turno DESC
            LIMIT ?;
        """,
            (limite,),
        )
        filas = cursor.fetchall()
        return [dict(f) for f in filas]

