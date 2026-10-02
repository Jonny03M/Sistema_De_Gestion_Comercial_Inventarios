from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
import sqlite3

from database.ventas_db import registrar_venta_con_lealtad

CENTAVOS = Decimal("0.01")


def a_decimal(valor) -> Decimal:
    """Convierte de forma segura cualquier número o cadena a Decimal con 2 decimales."""
    if valor is None or valor == "":
        return Decimal("0.00")
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


@dataclass
class ItemCarrito:
    id_producto: int
    nombre: str
    precio_unitario: Decimal
    cantidad: Decimal = Decimal("1.0")
    es_retornable: bool = False
    envases_por_unidad: int = 1
    precio_envase_unitario: Decimal = Decimal("0.00")
    envases_a_cobrar: int = 0

    @property
    def subtotal_articulos(self) -> Decimal:
        return a_decimal(self.cantidad * self.precio_unitario)

    @property
    def max_envases_posibles(self) -> int:
        return int(self.cantidad * self.envases_por_unidad)

    @property
    def costo_total_envases(self) -> Decimal:
        return a_decimal(Decimal(self.envases_a_cobrar) * self.precio_envase_unitario)

    @property
    def subtotal_con_envases(self) -> Decimal:
        return self.subtotal_articulos + self.costo_total_envases


class PosController:
    """Controlador transaccional del carrito con precisión monetaria exacta en base 10."""

    def __init__(self, valor_peso_por_punto: str = "0.10"):
        self.carrito: List[ItemCarrito] = []
        self.valor_peso_por_punto = Decimal(valor_peso_por_punto)
        self.cliente_id: Optional[int] = None
        self.cliente_nombre: str = ""
        self.cliente_puntos: int = 0
        self.descuento_puntos: Decimal = Decimal("0.00")
        self.puntos_a_canjear: int = 0

    def agregar_producto(self, producto: sqlite3.Row):
        keys = producto.keys() if hasattr(producto, "keys") else producto
        p_id = producto["id_producto"]

        # Si ya existe, se suma 1 unidad
        for item in self.carrito:
            if item.id_producto == p_id:
                item.cantidad += Decimal("1.0")
                return

        es_ret = bool(producto["es_retornable"]) if "es_retornable" in keys and producto["es_retornable"] else False
        p_env = a_decimal(producto["precio_envase"]) if "precio_envase" in keys and producto["precio_envase"] else Decimal("0.00")
        factor = int(producto["factor_conversion"]) if "factor_conversion" in keys and producto["factor_conversion"] else 1

        nuevo_item = ItemCarrito(
            id_producto=p_id,
            nombre=producto["nombre"],
            precio_unitario=a_decimal(producto["precio_venta"]),
            cantidad=Decimal("1.0"),
            es_retornable=es_ret,
            envases_por_unidad=factor,
            precio_envase_unitario=p_env,
            envases_a_cobrar=0,
        )
        self.carrito.append(nuevo_item)

    def incrementar_cantidad(self, index: int):
        if 0 <= index < len(self.carrito):
            self.carrito[index].cantidad += Decimal("1.0")

    def decrementar_cantidad(self, index: int):
        if 0 <= index < len(self.carrito):
            item = self.carrito[index]
            if item.cantidad > Decimal("1.0"):
                item.cantidad -= Decimal("1.0")
                if item.envases_a_cobrar > item.max_envases_posibles:
                    item.envases_a_cobrar = item.max_envases_posibles
            else:
                self.eliminar_item(index)

    def eliminar_item(self, index: int):
        if 0 <= index < len(self.carrito):
            self.carrito.pop(index)

    def configurar_envases_item(self, index: int, cantidad_a_cobrar: int):
        if 0 <= index < len(self.carrito):
            item = self.carrito[index]
            item.envases_a_cobrar = max(0, min(cantidad_a_cobrar, item.max_envases_posibles))

    def alternar_envase_individual(self, index: int):
        if 0 <= index < len(self.carrito):
            item = self.carrito[index]
            if item.max_envases_posibles == 1:
                item.envases_a_cobrar = 0 if item.envases_a_cobrar > 0 else 1

    def vaciar_carrito(self):
        self.carrito.clear()
        self.desvincular_cliente()

    @property
    def total_articulos(self) -> Decimal:
        return sum(item.cantidad for item in self.carrito)

    @property
    def subtotal_general(self) -> Decimal:
        return a_decimal(sum(item.subtotal_articulos for item in self.carrito))

    @property
    def total_garantias_envases(self) -> Decimal:
        return a_decimal(sum(item.costo_total_envases for item in self.carrito))

    @property
    def total_bruto(self) -> Decimal:
        return a_decimal(self.subtotal_general + self.total_garantias_envases)

    @property
    def total_neto(self) -> Decimal:
        total = self.total_bruto - self.descuento_puntos
        return a_decimal(max(Decimal("0.00"), total))

    def vincular_cliente(self, id_cliente: int, nombre: str, puntos: int):
        self.cliente_id = id_cliente
        self.cliente_nombre = nombre
        self.cliente_puntos = puntos
        self.descuento_puntos = Decimal("0.00")
        self.puntos_a_canjear = 0

    def desvincular_cliente(self):
        self.cliente_id = None
        self.cliente_nombre = ""
        self.cliente_puntos = 0
        self.descuento_puntos = Decimal("0.00")
        self.puntos_a_canjear = 0

    def aplicar_canje_puntos(self, monto_pesos: float | str | Decimal):
        if not self.cliente_id:
            self.descuento_puntos = Decimal("0.00")
            self.puntos_a_canjear = 0
            return

        monto_dec = a_decimal(monto_pesos)
        max_pesos = a_decimal(Decimal(self.cliente_puntos) * self.valor_peso_por_punto)
        monto_real = min(monto_dec, max_pesos, self.total_bruto)

        self.descuento_puntos = a_decimal(monto_real)
        self.puntos_a_canjear = int(monto_real / self.valor_peso_por_punto)

    def procesar_venta(self, id_empleado: int, metodo_pago: str, efectivo_recibido: float | str = "0.00") -> int:
        if not self.carrito:
            raise ValueError("El carrito está vacío.")

        importes_envases = [
            {
                "id_producto": it.id_producto,
                "cantidad": it.envases_a_cobrar,
                "precio_envase": float(it.precio_envase_unitario),
            }
            for it in self.carrito
            if it.es_retornable and it.envases_a_cobrar > 0
        ]

        if (metodo_pago == "Crédito / Fiado" or len(importes_envases) > 0) and not self.cliente_id:
            raise ValueError("Debes registrar o buscar un cliente para ventas a crédito o préstamo de envases.")

        total_final = self.total_neto
        recibido_dec = a_decimal(efectivo_recibido)

        if metodo_pago == "Efectivo" and total_final > Decimal("0.00"):
            if recibido_dec < total_final:
                diferencia = total_final - recibido_dec
                raise ValueError(f"Efectivo insuficiente. Faltan ${diferencia:.2f}")

        if total_final == Decimal("0.00") and self.descuento_puntos > Decimal("0.00"):
            metodo_pago = "Puntos"

        payload_carrito = [
            {
                "id_producto": it.id_producto,
                "cantidad": float(it.cantidad),
                "precio_unitario": float(it.precio_unitario),
                "subtotal": float(it.subtotal_articulos),
            }
            for it in self.carrito
        ]

        id_venta = registrar_venta_con_lealtad(
            id_empleado=id_empleado,
            total=float(total_final),
            metodo_pago=metodo_pago,
            carrito=payload_carrito,
            id_cliente=self.cliente_id,
            puntos_canjeados=self.puntos_a_canjear,
            importes_envases=importes_envases,
        )

        self.vaciar_carrito()
        return id_venta