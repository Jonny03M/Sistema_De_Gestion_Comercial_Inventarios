import hashlib
from database.conexion import obtener_conexion


def hash_password(password: str) -> str:
    """Genera un hash SHA-256 para almacenamiento seguro de credenciales."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def inicializar_base_datos():
    """Crea todas las tablas, índices y registros semilla si no existen."""
    script_sql = """
        -- 1. EMPLEADOS
        CREATE TABLE IF NOT EXISTS empleados (
            id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            puesto TEXT NOT NULL DEFAULT 'Cajero',
            telefono TEXT DEFAULT '',
            activo INTEGER NOT NULL DEFAULT 1
        );

        -- 2. CATEGORIAS
        CREATE TABLE IF NOT EXISTS categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );

        -- 3. PROMOCIONES
        CREATE TABLE IF NOT EXISTS promociones (
            id_promocion INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cantidad_minima INTEGER NOT NULL,
            precio_paquete REAL NOT NULL,
            activa INTEGER NOT NULL DEFAULT 1
        );

        -- 4. PRODUCTOS (Con soporte de retornables e importes de envase)
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            tipo_unidad TEXT NOT NULL DEFAULT 'pieza',
            precio_venta REAL NOT NULL,
            precio_costo REAL NOT NULL DEFAULT 0.0,
            stock_actual REAL NOT NULL DEFAULT 0.0,
            stock_minimo REAL NOT NULL DEFAULT 1.0,
            es_retornable INTEGER NOT NULL DEFAULT 0,
            precio_envase REAL NOT NULL DEFAULT 0.0,
            id_categoria INTEGER,
            id_promocion INTEGER,
            id_producto_padre INTEGER,
            factor_conversion INTEGER,
            activo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria) ON DELETE SET NULL,
            FOREIGN KEY (id_promocion) REFERENCES promociones(id_promocion) ON DELETE SET NULL,
            FOREIGN KEY (id_producto_padre) REFERENCES productos(id_producto) ON DELETE SET NULL
        );

        -- 5. CLIENTES (Con límite de crédito y saldo fiado)
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT UNIQUE,
            puntos_acumulados INTEGER DEFAULT 0,
            limite_credito REAL DEFAULT 0.0,
            saldo_pendiente REAL DEFAULT 0.0
        );

        -- 6. CONFIGURACION GLOBAL DEL SISTEMA
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );

        -- 7. PROVEEDORES
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_empresa TEXT NOT NULL,
            contacto_nombre TEXT,
            telefono TEXT
        );

        -- 8. VENTAS
        CREATE TABLE IF NOT EXISTS ventas (
            id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT (datetime('now', 'localtime')),
            total REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            puntos_canjeados INTEGER DEFAULT 0,
            efectivo_recibido REAL DEFAULT 0.0,
            cambio REAL DEFAULT 0.0,
            estado TEXT NOT NULL DEFAULT 'Completada',
            id_empleado INTEGER NOT NULL,
            id_cliente INTEGER,
            FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado),
            FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)
        );

        -- 9. DETALLE_VENTA
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id_detalle_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            envases_cobrados INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );

        -- 10. COMPRAS / ENTRADAS DE MERCANCÍA
        CREATE TABLE IF NOT EXISTS compras (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT (datetime('now', 'localtime')),
            total REAL NOT NULL,
            id_proveedor INTEGER NOT NULL,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        );

        -- 11. DETALLE_COMPRA
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id_detalle_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_compra INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_costo_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (id_compra) REFERENCES compras(id_compra) ON DELETE CASCADE,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );

        -- 12. MOVIMIENTOS_CAJA (Entradas / Salidas)
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT (datetime('now', 'localtime')),
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT NOT NULL,
            id_empleado INTEGER NOT NULL,
            FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
        );

        -- 13. REGISTRO DE ENVASES RETORNABLES (Préstamos / Garantías)
        CREATE TABLE IF NOT EXISTS registro_envases (
            id_registro INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            id_producto INTEGER NOT NULL,
            cantidad_prestada INTEGER NOT NULL,
            cantidad_devuelta INTEGER NOT NULL DEFAULT 0,
            deposito_unitario REAL NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Pendiente',
            fecha_prestamo DATETIME DEFAULT (datetime('now', 'localtime')),
            fecha_devolucion DATETIME,
            FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );

        -- 14. ABONOS A CUENTAS FIADAS
        CREATE TABLE IF NOT EXISTS abonos_credito (
            id_abono INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            id_empleado INTEGER NOT NULL,
            monto REAL NOT NULL,
            fecha_hora DATETIME DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
            FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
        );

        -- ÍNDICES DE RENDIMIENTO
        CREATE INDEX IF NOT EXISTS idx_productos_codigo ON productos(codigo_barras);
        CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);
        CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha_hora);
        CREATE INDEX IF NOT EXISTS idx_compras_fecha ON compras(fecha_hora);
        CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos_caja(fecha_hora);
    """
    with obtener_conexion() as conexion:
        conexion.executescript(script_sql)
        cursor = conexion.cursor()

        # Semilla: Administrador Inicial
        password_admin_hash = hash_password("admin123")
        cursor.execute(
            """
            INSERT OR IGNORE INTO empleados (id_empleado, nombre, apellido, usuario, password, puesto)
            VALUES (1, 'Administrador', 'Principal', 'admin', ?, 'Administrador')
            """,
            (password_admin_hash,),
        )

        # Semilla: Categoría General
        cursor.execute(
            """
            INSERT OR IGNORE INTO categorias (id_categoria, nombre, descripcion)
            VALUES (1, 'General', 'Productos sin categoría específica')
            """
        )

        # Semilla: Configuraciones iniciales por defecto
        configs_default = [
            ("nombre_tienda", "MI TIENDA DE ABARROTES"),
            ("direccion_tienda", "Puebla, México"),
            ("telefono_tienda", "Tel: 222-000-0000"),
            ("monto_por_punto", "10.0"),
            ("valor_peso_por_punto", "0.10"),
            ("modulo_puntos", "true"),
            ("modulo_envases", "true"),
            ("imprimir_tickets_auto", "false"),
            ("ancho_ticket", "32"),
        ]

        cursor.executemany(
            """
            INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?);
            """,
            configs_default,
        )

        conexion.commit()
    print("Base de datos inicializada y verificada con éxito.")


if __name__ == "__main__":
    inicializar_base_datos()