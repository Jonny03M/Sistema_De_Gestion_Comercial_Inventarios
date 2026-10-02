import sqlite3
from typing import List, Optional
from database.conexion import obtener_conexion


def obtener_todos_los_productos() -> List[sqlite3.Row]:
    """Obtiene la lista completa de productos ordenados por estado activo e identificador."""
    query = """
        SELECT 
            p.id_producto,
            p.codigo_barras,
            p.nombre,
            p.tipo_unidad,
            p.precio_venta,
            p.precio_costo,
            p.stock_actual,
            p.stock_minimo,
            p.es_retornable,
            p.precio_envase,
            p.id_categoria,
            p.id_producto_padre,
            p.factor_conversion,
            p.activo,
            c.nombre AS categoria
        FROM productos p
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        ORDER BY p.activo DESC, p.id_producto DESC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def buscar_producto_por_codigo_o_nombre(termino: str) -> List[sqlite3.Row]:
    """Busca productos activos por coincidencia parcial en nombre o código de barras,

    resolviendo herencia de envases si tiene producto padre.
    """
    query = """
        SELECT 
            p.id_producto,
            p.codigo_barras,
            p.nombre,
            p.tipo_unidad,
            p.precio_venta,
            p.precio_costo,
            p.stock_actual,
            p.stock_minimo,
            CASE 
                WHEN p.id_producto_padre IS NOT NULL AND padre.id_producto IS NOT NULL 
                THEN padre.es_retornable 
                ELSE p.es_retornable 
            END AS es_retornable,
            CASE 
                WHEN p.id_producto_padre IS NOT NULL AND padre.id_producto IS NOT NULL 
                THEN padre.precio_envase 
                ELSE p.precio_envase 
            END AS precio_envase,
            p.id_producto_padre,
            p.factor_conversion,
            c.nombre AS categoria
        FROM productos p
        LEFT JOIN productos padre ON p.id_producto_padre = padre.id_producto
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        WHERE p.activo = 1 AND (
            p.codigo_barras LIKE ? OR 
            p.nombre LIKE ?
        )
        ORDER BY p.nombre ASC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        param = f"%{termino}%"
        cursor.execute(query, (param, param))
        return cursor.fetchall()


def agregar_producto(
    nombre: str,
    precio_venta: float,
    codigo_barras: Optional[str] = None,
    tipo_unidad: str = "pieza",
    precio_costo: float = 0.0,
    stock_actual: float = 0.0,
    stock_minimo: float = 1.0,
    id_categoria: Optional[int] = None,
    id_producto_padre: Optional[int] = None,
    factor_conversion: Optional[int] = None,
    es_retornable: int = 0,
    precio_envase: float = 0.0,
) -> int:
    """Inserta un nuevo producto en el catálogo y retorna su identificador."""
    query = """
        INSERT INTO productos (
            nombre, precio_venta, codigo_barras, tipo_unidad,
            precio_costo, stock_actual, stock_minimo, id_categoria,
            id_producto_padre, factor_conversion, es_retornable, precio_envase, activo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            (
                nombre,
                precio_venta,
                codigo_barras,
                tipo_unidad,
                precio_costo,
                stock_actual,
                stock_minimo,
                id_categoria,
                id_producto_padre,
                factor_conversion,
                es_retornable,
                precio_envase,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def actualizar_producto(
    id_producto: int,
    nombre: str,
    precio_venta: float,
    codigo_barras: Optional[str] = None,
    tipo_unidad: str = "pieza",
    precio_costo: float = 0.0,
    stock_actual: float = 0.0,
    stock_minimo: float = 1.0,
    id_categoria: Optional[int] = None,
    id_producto_padre: Optional[int] = None,
    factor_conversion: Optional[int] = None,
    es_retornable: int = 0,
    precio_envase: float = 0.0,
):
    """Actualiza la información técnica y comercial de un producto existente."""
    query = """
        UPDATE productos
        SET nombre = ?, 
            precio_venta = ?, 
            codigo_barras = ?, 
            tipo_unidad = ?,
            precio_costo = ?, 
            stock_actual = ?, 
            stock_minimo = ?, 
            id_categoria = ?,
            id_producto_padre = ?, 
            factor_conversion = ?, 
            es_retornable = ?, 
            precio_envase = ?
        WHERE id_producto = ?;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            (
                nombre,
                precio_venta,
                codigo_barras,
                tipo_unidad,
                precio_costo,
                stock_actual,
                stock_minimo,
                id_categoria,
                id_producto_padre,
                factor_conversion,
                es_retornable,
                precio_envase,
                id_producto,
            ),
        )
        conn.commit()


def cambiar_estado_producto(id_producto: int, nuevo_estado: int):
    """Habilita (1) o deshabilita (0) un producto de forma lógica."""
    query = "UPDATE productos SET activo = ? WHERE id_producto = ?;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nuevo_estado, id_producto))
        conn.commit()


def obtener_productos_stock_critico() -> List[sqlite3.Row]:
    """Obtiene los productos activos cuyo stock actual es menor o igual al mínimo."""
    query = """
        SELECT 
            p.id_producto,
            p.codigo_barras,
            p.nombre,
            p.tipo_unidad,
            p.stock_actual,
            p.stock_minimo,
            p.precio_venta,
            c.nombre AS categoria
        FROM productos p
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        WHERE p.activo = 1 
          AND p.id_producto_padre IS NULL
          AND p.stock_actual <= p.stock_minimo
        ORDER BY p.stock_actual ASC;
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def obtener_categorias() -> List[sqlite3.Row]:
    """Retorna todas las categorías disponibles ordenadas alfabéticamente."""
    query = "SELECT id_categoria, nombre FROM categorias ORDER BY nombre ASC;"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def agregar_categoria(nombre: str, descripcion: str = "") -> int:
    """Registra una nueva categoría y retorna su identificador."""
    query = "INSERT INTO categorias (nombre, descripcion) VALUES (?, ?);"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (nombre, descripcion))
        conn.commit()
        return cursor.lastrowid