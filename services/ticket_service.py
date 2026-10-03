from datetime import datetime
import sys
import subprocess
from typing import Any, List, Optional
from database.ventas_db import obtener_venta_completa_para_ticket
from database.configuracion_db import obtener_configuraciones

class TicketService:
    """Generador en memoria de tickets de texto bajo demanda para miniprinters (58mm / 80mm)."""
    def __init__(self):
        self.recargar_configuracion()

    def recargar_configuracion(self):
        """Lee los ajustes de la tienda directamente de SQLite."""
        configs = obtener_configuraciones()
        try:
            self.ancho = int(configs.get("ancho_ticket",32))
        except ValueError:
            self.ancho = 32

        self.nombre_tienda = configs.get("nombre_tienda", "MI TIENDA")
        self.direccion = configs.get("direccion_tienda", "")
        self.telefono = configs.get("telefono_tienda", "")
        self.impresion_auto = (
            configs.get("imprimir_tickets_auto", "false").lower() == "true"
        )

    def _centrar(self, texto: str) -> str:
        return texto.center(self.ancho)

    def _linea_separadora(self, char: str = "-") -> str:
        return char * self.ancho

    def _fila_dos_columnas(self, izq: str, der: str) -> str:
        espacio = self.ancho - len(der)
        if len(izq) >= espacio:
            izq = izq[: espacio - 1]
        return f"{izq.ljust(espacio)}{der}"

    def generar_ticket_texto(
        self,
        id_venta: int,
        cajero: str,
        carrito: List[Any],
        total: float,
        metodo_pago: str,
        efectivo_recibido: float = 0.0,
        cambio: float = 0.0,
        cliente_nombre: Optional[str] = None,
        descuento_puntos: float = 0.0,
        fecha_hora_str: Optional[str] = None,
    ) -> str:
        """Formatea el ticket en memoria sin escribir archivos a disco."""
        fecha = fecha_hora_str or datetime.now().strftime("%d/%m/%Y %I:%M %p")
        lineas = []

        # Encabezado
        lineas.append(self._linea_separadora("="))
        lineas.append(self._centrar(self.nombre_tienda))
        if self.direccion:
            lineas.append(self._centrar(self.direccion))
        if self.telefono:
            lineas.append(self._centrar(self.telefono))
        lineas.append(self._linea_separadora("="))

        lineas.append(f"Ticket: #{id_venta}")
        lineas.append(f"Fecha : {fecha}")
        lineas.append(f"Atendio: {cajero}")
        if cliente_nombre:
            lineas.append(f"Cliente: {cliente_nombre}")
        lineas.append(self._linea_separadora("-"))

        # Columnas
        lineas.append(self._fila_dos_columnas("CANT DESCRIPCION", "IMPORTE"))
        lineas.append(self._linea_separadora("-"))

        # Artículos
        for item in carrito:
            nombre = (
                getattr(item, "nombre", item.get("nombre", ""))
                if hasattr(item, "nombre")
                else item["nombre"]
            )
            cant = (
                getattr(item, "cantidad", item.get("cantidad", 1))
                if hasattr(item, "cantidad")
                else item["cantidad"]
            )
            subtot = getattr(item, "subtotal_neto", None)
            if subtot is None:
                subtot = getattr(
                    item,
                    "subtotal_articulos",
                    item.get("subtotal", 0.0)
                    if isinstance(item, dict)
                    else 0.0,
                )

            precio_str = f"${float(subtot):.2f}"
            desc = f"{cant}x {nombre}"

            if len(desc) + len(precio_str) + 1 <= self.ancho:
                lineas.append(self._fila_dos_columnas(desc, precio_str))
            else:
                lineas.append(desc)
                lineas.append(self._fila_dos_columnas("", precio_str))

            # Envases si aplica
            env = (
                getattr(item, "envases_a_cobrar", 0)
                if hasattr(item, "envases_a_cobrar")
                else item.get("envases_a_cobrar", 0)
            )
            costo_env = (
                getattr(item, "costo_total_envases", 0.0)
                if hasattr(item, "costo_total_envases")
                else item.get("costo_total_envases", 0.0)
            )
            if env > 0 and costo_env > 0:
                lineas.append(
                    self._fila_dos_columnas(
                        f" +{env} envase(s)", f"${float(costo_env):.2f}"
                    )
                )

        lineas.append(self._linea_separadora("="))

        if descuento_puntos > 0:
            lineas.append(
                self._fila_dos_columnas(
                    "Puntos Canjeados:", f"-${descuento_puntos:.2f}"
                )
            )

        lineas.append(
            self._fila_dos_columnas("TOTAL A PAGAR:", f"${total:.2f}")
        )
        lineas.append(self._fila_dos_columnas("Metodo de Pago:", metodo_pago))

        if metodo_pago == "Efectivo" and efectivo_recibido > 0:
            lineas.append(
                self._fila_dos_columnas(
                    "Efectivo Recibido:", f"${efectivo_recibido:.2f}"
                )
            )
            lineas.append(
                self._fila_dos_columnas("Cambio:", f"${cambio:.2f}")
            )

        lineas.append(self._linea_separadora("-"))
        lineas.append(self._centrar("¡Gracias por su compra!"))
        lineas.append(self._centrar("Conserve su comprobante"))
        lineas.append(self._linea_separadora("="))
        lineas.append("\n\n")

        return "\n".join(lineas)

    def generar_ticket_desde_id(self, id_venta: int) -> Optional[str]:
        """Reconstruye el ticket de cualquier venta pasada usando los datos de SQLite."""
        datos = obtener_venta_completa_para_ticket(id_venta)
        if not datos:
            return None

        v = datos["venta"]
        return self.generar_ticket_texto(
            id_venta=v["id_venta"],
            cajero=v["cajero"],
            carrito=datos["detalles"],
            total=float(v["total"]),
            metodo_pago=v["metodo_pago"],
            efectivo_recibido=float(v["efectivo_recibido"] or 0.0),
            cambio=float(v["cambio"] or 0.0),
            cliente_nombre=v["cliente"],
            fecha_hora_str=v["fecha_hora"],
        )