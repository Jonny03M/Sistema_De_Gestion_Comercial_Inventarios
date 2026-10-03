import sqlite3
from typing import List, Optional
from database.conexion import obtener_conexion


def registrar_venta_con_lealtad(
    id_empleado: int,
    total: float,
    metodo_pago: str,
    carrito: list,
    id_cliente: Optional[int] = None,
    puntos_canjeados: int = 0,
    importes_envases: Optional[list] = None,
) -> int:
    """Registra una venta completa en una sola transacción: valida crédito,

    descuenta stock (simple o padre/hijo), registra garantías y actualiza puntos.
    """
    if importes_envases is None:
        importes_envases = []

    with obtener_conexion() as conn:
        cursor = conn.cursor()

        if metodo_pago == "Crédito / Fiado":
            if not id_cliente:
                raise ValueError("Debes seleccionar un cliente registrado para fiar.")

            cursor.execute(
                "SELECT saldo_pendiente, limite_credito FROM clientes WHERE id_cliente = ?;",
                (id_cliente,),
            )
            cl = cursor.fetchone()
            if cl:
                saldo_actual = cl["saldo_pendiente"] or 0.0
                limite = cl["limite_credito"] or 0.0
                if (saldo_actual + total) > limite:
                    raise ValueError(
                        f"El cliente supera su límite de crédito de ${limite:.2f} (Deuda actual: ${saldo_actual:.2f})"
                    )

                cursor.execute(
                    "UPDATE clientes SET saldo_pendiente = saldo_pendiente + ? WHERE id_cliente = ?;",
                    (total, id_cliente),
                )

        cursor.execute(
            """
            INSERT INTO ventas (total, metodo_pago, id_empleado, id_cliente, puntos_canjeados)
            VALUES (?, ?, ?, ?, ?);
            """,
            (total, metodo_pago, id_empleado, id_cliente, puntos_canjeados),
        )
        id_venta = cursor.lastrowid

        for item in carrito:
            id_prod = item.get("id_producto")
            cant = float(item.get("cantidad", 1))
            precio_u = float(item.get("precio_unitario", 0.0))
            subt = float(item.get("subtotal", cant * precio_u))

            cursor.execute(
                """
                INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?);
                """,
                (id_venta, id_prod, cant, precio_u, subt),
            )

            cursor.execute(
                "SELECT id_producto_padre, factor_conversion FROM productos WHERE id_producto = ?;",
                (id_prod,),
            )
            prod_info = cursor.fetchone()
            if prod_info and prod_info["id_producto_padre"] and prod_info["factor_conversion"]:
                piezas = cant * prod_info["factor_conversion"]
                cursor.execute(
                    "UPDATE productos SET stock_actual = stock_actual - ? WHERE id_producto = ?;",
                    (piezas, prod_info["id_producto_padre"]),
                )
            else:
                cursor.execute(
                    "UPDATE productos SET stock_actual = stock_actual - ? WHERE id_producto = ?;",
                    (cant, id_prod),
                )

        for env in importes_envases:
            cursor.execute(
                """
                INSERT INTO registro_envases (id_cliente, id_producto, cantidad_prestada, deposito_unitario, estado)
                VALUES (?, ?, ?, ?, 'Pendiente');
                """,
                (
                    id_cliente,
                    env["id_producto"],
                    env["cantidad"],
                    env["precio_envase"],
                ),
            )

        if id_cliente:
            if puntos_canjeados > 0:
                cursor.execute(
                    "UPDATE clientes SET puntos_acumulados = MAX(0, puntos_acumulados - ?) WHERE id_cliente = ?;",
                    (puntos_canjeados, id_cliente),
                )

            if metodo_pago != "Crédito / Fiado":
                tot_garantias = sum(e["cantidad"] * e["precio_envase"] for e in importes_envases)
                monto_base = max(0.0, total - tot_garantias)
                pts_ganados = int(monto_base // 10.0)
                if pts_ganados > 0:
                    cursor.execute(
                        "UPDATE clientes SET puntos_acumulados = puntos_acumulados + ? WHERE id_cliente = ?;",
                        (pts_ganados, id_cliente),
                    )

        conn.commit()
        return id_venta


def registrar_movimiento_caja(
    tipo: str, monto: float, motivo: str, id_empleado: int
) -> int:
    """Registra entradas o salidas manuales de efectivo en caja."""
    query = """
        INSERT INTO movimientos_caja (fecha_hora, tipo, monto, motivo, id_empleado) 
        VALUES (datetime('now', 'localtime'), ?, ?, ?, ?);
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (tipo, monto, motivo.strip(), id_empleado))
        conn.commit()
        return cursor.lastrowid


def obtener_todos_los_proveedores() -> List[sqlite3.Row]:
    """Retorna la lista de proveedores registrados."""
    query = "SELECT id_proveedor, nombre_empresa, contacto_nombre, telefono FROM proveedores ORDER BY nombre_empresa ASC;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def agregar_proveedor(
    nombre_empresa: str, contacto_nombre: str = "", telefono: str = ""
) -> int:
    """Registra un nuevo proveedor."""
    query = "INSERT INTO proveedores (nombre_empresa, contacto_nombre, telefono) VALUES (?, ?, ?);"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nombre_empresa, contacto_nombre, telefono))
        conn.commit()
        return cursor.lastrowid


def registrar_compra_mercancia(id_proveedor: int, items_compra: list[dict]) -> int:
    """Registra la compra de mercancía, sumando stock y actualizando costo."""
    total_compra = sum(float(it["subtotal"]) for it in items_compra)
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO compras (total, id_proveedor, fecha_hora) VALUES (?, ?, datetime('now', 'localtime'));",
            (total_compra, id_proveedor),
        )
        id_compra = cursor.lastrowid

        for item in items_compra:
            id_prod = item["id_producto"]
            cant = float(item["cantidad"])
            costo_u = float(item["precio_costo_unitario"])
            subt = float(item["subtotal"])

            cursor.execute(
                "INSERT INTO detalle_compra (id_compra, id_producto, cantidad, precio_costo_unitario, subtotal) VALUES (?, ?, ?, ?, ?);",
                (id_compra, id_prod, cant, costo_u, subt),
            )
            cursor.execute(
                "UPDATE productos SET stock_actual = stock_actual + ?, precio_costo = ? WHERE id_producto = ?;",
                (cant, costo_u, id_prod),
            )
        conn.commit()
        return id_compra


def obtener_detalle_venta_por_id(id_venta: int) -> dict:
    """Obtiene los datos de cabecera, artículos y cobros de una venta para el ticket."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                v.id_venta,
                strftime('%Y-%m-%d %I:%M %p', v.fecha_hora) AS fecha_hora,
                v.total,
                v.metodo_pago,
                COALESCE(v.puntos_canjeados, 0) AS puntos_canjeados,
                COALESCE(c.nombre, 'Venta Mostrador') AS cliente,
                COALESCE(c.telefono, '') AS telefono_cliente,
                e.nombre || ' ' || e.apellido AS cajero
            FROM ventas v
            LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
            INNER JOIN empleados e ON v.id_empleado = e.id_empleado
            WHERE v.id_venta = ?;
            """,
            (id_venta,),
        )
        venta = cursor.fetchone()

        cursor.execute(
            """
            SELECT 
                p.nombre,
                dv.cantidad,
                dv.precio_unitario,
                dv.subtotal
            FROM detalle_venta dv
            INNER JOIN productos p ON dv.id_producto = p.id_producto
            WHERE dv.id_venta = ?;
            """,
            (id_venta,),
        )
        detalles = cursor.fetchall()

        subtotal_articulos = sum(d["subtotal"] for d in detalles)
        total_venta = venta["total"] if venta else 0.0
        puntos = venta["puntos_canjeados"] if venta else 0
        ahorro_puntos = puntos * 0.10
        monto_envases = max(0.0, total_venta + ahorro_puntos - subtotal_articulos)

        return {
            "venta": dict(venta) if venta else None,
            "detalles": [dict(d) for d in detalles],
            "monto_envases": monto_envases,
            "subtotal_articulos": subtotal_articulos,
        }


def obtener_resumen_corte_por_rango(
    fecha_inicio: str, fecha_fin: Optional[str] = None
) -> dict:
    """Calcula totales desglosados, flujo de caja y balance del turno o fecha."""
    if not fecha_fin:
        fecha_fin = fecha_inicio

    with obtener_conexion() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(total), 0.0) AS total_general,
                COALESCE(SUM(CASE WHEN metodo_pago = 'Efectivo' THEN total ELSE 0.0 END), 0.0) AS total_efectivo,
                COALESCE(SUM(CASE WHEN metodo_pago IN ('Transferencia', 'Tarjeta') THEN total ELSE 0.0 END), 0.0) AS total_digital,
                COALESCE(SUM(CASE WHEN metodo_pago = 'Crédito / Fiado' THEN total ELSE 0.0 END), 0.0) AS total_fiado
            FROM ventas
            WHERE date(fecha_hora) BETWEEN date(?) AND date(?);
            """,
            (fecha_inicio, fecha_fin),
        )
        res_ventas = cursor.fetchone()

        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN tipo = 'Entrada' THEN monto ELSE 0.0 END), 0.0) AS total_entradas,
                COALESCE(SUM(CASE WHEN tipo = 'Salida' THEN monto ELSE 0.0 END), 0.0) AS total_salidas
            FROM movimientos_caja
            WHERE date(fecha_hora) BETWEEN date(?) AND date(?);
            """,
            (fecha_inicio, fecha_fin),
        )
        res_movs = cursor.fetchone()

        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(dv.subtotal - (dv.cantidad * p.precio_costo)), 0.0) AS ganancia_estimada
            FROM detalle_venta dv
            INNER JOIN ventas v ON dv.id_venta = v.id_venta
            INNER JOIN productos p ON dv.id_producto = p.id_producto
            WHERE date(v.fecha_hora) BETWEEN date(?) AND date(?);
            """,
            (fecha_inicio, fecha_fin),
        )
        res_ganancia = cursor.fetchone()

        total_efectivo_ventas = res_ventas["total_efectivo"]
        total_entradas_caja = res_movs["total_entradas"]
        total_salidas_caja = res_movs["total_salidas"]

        efectivo_en_caja = max(
            0.0, total_efectivo_ventas + total_entradas_caja - total_salidas_caja
        )

        return {
            "total_general": res_ventas["total_general"],
            "total_efectivo": total_efectivo_ventas,
            "total_digital": res_ventas["total_digital"],
            "total_fiado": res_ventas["total_fiado"],
            "total_entradas": total_entradas_caja,
            "total_salidas": total_salidas_caja,
            "ganancia_estimada": res_ganancia["ganancia_estimada"],
            "efectivo_real_en_caja": efectivo_en_caja,
        }


def obtener_ventas_por_rango(
    fecha_inicio: str, fecha_fin: Optional[str] = None
) -> List[sqlite3.Row]:
    """Obtiene el historial de ventas registradas en un periodo."""
    if not fecha_fin:
        fecha_fin = fecha_inicio

    query = """
        SELECT 
            v.id_venta,
            strftime('%Y-%m-%d %I:%M %p', v.fecha_hora) AS fecha_hora,
            v.total,
            v.metodo_pago,
            COALESCE(c.nombre, 'Venta Mostrador') AS cliente,
            e.nombre || ' ' || e.apellido AS cajero
        FROM ventas v
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        INNER JOIN empleados e ON v.id_empleado = e.id_empleado
        WHERE date(v.fecha_hora) BETWEEN date(?) AND date(?)
        ORDER BY v.id_venta DESC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (fecha_inicio, fecha_fin))
        return cursor.fetchall()

def actualizar_proveedor(
    id_proveedor: int,
    nombre_empresa: str,
    contacto_nombre: str = "",
    telefono: str = "",
):
    """Actualiza la información de un proveedor existente."""
    query = """
        UPDATE proveedores 
        SET nombre_empresa = ?, contacto_nombre = ?, telefono = ?
        WHERE id_proveedor = ?;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nombre_empresa, contacto_nombre, telefono, id_proveedor))
        conn.commit()


def obtener_historial_compras_filtrado(
    fecha_inicio: str, fecha_fin: Optional[str] = None
) -> List[sqlite3.Row]:
    """Obtiene el historial de compras realizadas a proveedores en un rango de fechas."""
    if not fecha_fin:
        fecha_fin = fecha_inicio

    query = """
        SELECT 
            c.id_compra,
            strftime('%Y-%m-%d %I:%M %p', c.fecha_hora) AS fecha_hora,
            c.total,
            p.nombre_empresa AS proveedor
        FROM compras c
        INNER JOIN proveedores p ON c.id_proveedor = p.id_proveedor
        WHERE date(c.fecha_hora) BETWEEN date(?) AND date(?)
        ORDER BY c.id_compra DESC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (fecha_inicio, fecha_fin))
        return cursor.fetchall()


def obtener_movimientos_caja_por_rango(
    fecha_inicio: str, fecha_fin: Optional[str] = None
) -> List[sqlite3.Row]:
    """Obtiene las entradas y salidas de efectivo registradas en un periodo."""
    if not fecha_fin:
        fecha_fin = fecha_inicio

    query = """
        SELECT 
            m.id_movimiento,
            strftime('%Y-%m-%d %I:%M %p', m.fecha_hora) AS fecha_hora,
            m.tipo,
            m.monto,
            m.motivo,
            e.nombre || ' ' || e.apellido AS cajero
        FROM movimientos_caja m
        INNER JOIN empleados e ON m.id_empleado = e.id_empleado
        WHERE date(m.fecha_hora) BETWEEN date(?) AND date(?)
        ORDER BY m.id_movimiento DESC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (fecha_inicio, fecha_fin))
        return cursor.fetchall()

def obtener_detalle_compra_por_id(id_compra: int) -> dict:
    """Obtiene la información de cabecera y el listado de productos de una compra."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                c.id_compra,
                strftime('%Y-%m-%d %I:%M %p', c.fecha_hora) AS fecha_hora,
                c.total,
                p.nombre_empresa AS proveedor,
                COALESCE(p.telefono, '') AS telefono
            FROM compras c
            INNER JOIN proveedores p ON c.id_proveedor = p.id_proveedor
            WHERE c.id_compra = ?;
            """,
            (id_compra,),
        )
        compra = cursor.fetchone()

        cursor.execute(
            """
            SELECT 
                dc.cantidad,
                p.nombre,
                p.tipo_unidad,
                dc.precio_costo_unitario,
                dc.subtotal
            FROM detalle_compra dc
            INNER JOIN productos p ON dc.id_producto = p.id_producto
            WHERE dc.id_compra = ?;
            """,
            (id_compra,),
        )
        detalles = cursor.fetchall()

        return {
            "compra": dict(compra) if compra else None,
            "detalles": [dict(d) for d in detalles],
        }

def obtener_venta_completa_para_ticket(id_venta: int) -> Optional[dict]:
    """Recupera la cabecera y los productos de una venta para generar su ticket al vuelo."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                v.id_venta,
                strftime('%d/%m/%Y %I:%M %p', v.fecha_hora) AS fecha_hora,
                v.total,
                v.metodo_pago,
                v.efectivo_recibido,
                v.cambio,
                e.nombre || ' ' || e.apellido AS cajero,
                c.nombre AS cliente
            FROM ventas v
            INNER JOIN empleados e ON v.id_empleado = e.id_empleado
            LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
            WHERE v.id_venta = ?;
        """,
            (id_venta,),
        )
        venta = cursor.fetchone()

        if not venta:
            return None

        cursor.execute(
            """
            SELECT 
                dv.cantidad,
                p.nombre,
                dv.precio_unitario,
                dv.subtotal,
                0 AS envases_a_cobrar,
                0.0 AS costo_total_envases
            FROM detalle_venta dv
            INNER JOIN productos p ON dv.id_producto = p.id_producto
            WHERE dv.id_venta = ?;
        """,
            (id_venta,),
        )
        detalles = cursor.fetchall()

        return {
            "venta": dict(venta),
            "detalles": [dict(d) for d in detalles],
        }