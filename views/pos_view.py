from decimal import Decimal
from typing import Callable, Optional
import flet as ft

from components.buscador_autocompletado import BuscadorAutocompletado
from components.dialogo_base import DialogoModalBase
from controllers.pos_controller import PosController, a_decimal
from database.clientes_db import buscar_cliente_por_telefono, registrar_cliente_rapido
from database.productos_db import buscar_producto_por_codigo_o_nombre
from database.ventas_db import registrar_movimiento_caja
from components.modal_granel import ModalVentaGranel
from services.ticket_service import TicketService
from utils.formato import formatear_stock

class PosView(ft.Container):
    """Vista modular del Punto de Venta (POS) con manejo de carrito transaccional,

    precisión decimal, atajos de teclado y modales de cobro/envases.
    """

    def __init__(
        self,
        page: ft.Page,
        mostrar_mensaje: Callable[[str, str], None],
        id_empleado_activo: int,
    ):
        super().__init__(expand=True, padding=15)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje
        self.id_empleado_activo = id_empleado_activo

        self.pos_controller = PosController()
        self.indice_envase_actual: Optional[int] = None
        self.ticket_service = TicketService()

        self._crear_tabla_carrito()
        self._crear_modales()
        self._construir_ui()
        self._configurar_atajos_teclado()
        self.modal_granel = ModalVentaGranel(
            page=self.pagina,
            al_confirmar=self._agregar_producto_granel_al_carrito,
        )

    def _crear_tabla_carrito(self):
        self.tabla_carrito = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Producto")),
                ft.DataColumn(ft.Text("Precio U."), numeric=True),
                ft.DataColumn(ft.Text("Cant."), numeric=True),
                ft.DataColumn(ft.Text("Subtotal"), numeric=True),
                ft.DataColumn(ft.Text("Envase")),
                ft.DataColumn(ft.Text("Acción")),
            ],
            rows=[],
            expand=True,
            horizontal_margin=15,
        )

        self.lbl_total = ft.Text(
            "$0.00",
            size=36,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_700,
        )
        self.lbl_items = ft.Text(
            "0 artículos en carrito", color=ft.Colors.GREY_700, size=16
        )

    def _crear_modales(self):
        # MODAL SALIDA DE CAJA
        self.txt_monto_gasto = ft.TextField(
            label="Monto a Retirar ($) *",
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )
        self.txt_motivo_gasto = ft.TextField(
            label="Motivo del Gasto *",
            hint_text="Ej. Pago a proveedor Bimbo, bolsas, etc.",
            expand=True,
            on_submit=lambda e: self._guardar_salida_caja(),
        )

        self.modal_salida_caja = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Salida de Efectivo",
            icono=ft.Icons.MONEY_OFF,
            color_icono=ft.Colors.RED_600,
            ancho=450,
            texto_confirmar="Registrar Salida",
            color_confirmar=ft.Colors.RED_700,
            al_confirmar=lambda e: self._guardar_salida_caja(),
        )
        self.modal_salida_caja.set_contenido([
            self.txt_monto_gasto,
            self.txt_motivo_gasto,
        ])

        # MODAL ENVASES DE PAQUETE / REJA
        self.lbl_envase_prod = ft.Text("", weight=ft.FontWeight.BOLD, size=15)
        self.lbl_envase_unitario = ft.Text("", size=13, color=ft.Colors.GREY_700)
        self.lbl_envase_max = ft.Text("", size=12, color=ft.Colors.BLUE_900)
        self.txt_cant_envases_cobrar = ft.TextField(
            label="Cantidad de envases a cobrar",
            value="0",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=280,
            autofocus=True,
        )

        self.btn_todos_envases = ft.Button(
            "Cobrar Todos",
            icon=ft.Icons.ATTACH_MONEY,
            style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_800, color=ft.Colors.WHITE),
        )
        self.btn_cero_envases = ft.Button(
            "Trajo Todos ($0)",
            icon=ft.Icons.CHECK,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_600, color=ft.Colors.WHITE),
            on_click=lambda e: self._aplicar_envases_config(0),
        )

        self.modal_envase = DialogoModalBase(
            page=self.pagina,
            titulo="Configurar Envases de la Reja",
            icono=ft.Icons.WINE_BAR,
            color_icono=ft.Colors.ORANGE_800,
            ancho=460,
            texto_confirmar="Aplicar Cantidad",
            color_confirmar=ft.Colors.BLUE_700,
            al_confirmar=lambda e: self._aplicar_envases_config_personalizado(),
        )
        self.modal_envase.set_contenido([
            self.lbl_envase_prod,
            self.lbl_envase_unitario,
            self.lbl_envase_max,
            ft.Divider(height=1),
            ft.Row([self.btn_todos_envases, self.btn_cero_envases], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
            ft.Divider(height=1),
            ft.Text("O indica cuántos envases NO trajo:", size=12, weight=ft.FontWeight.W_500),
            self.txt_cant_envases_cobrar,
        ])

        # MODAL DE COBRO FINAL
        self.rg_metodo_pago = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="Efectivo", label="Efectivo"),
                ft.Radio(value="Transferencia", label="Transferencia"),
                ft.Radio(value="Tarjeta", label="Tarjeta"),
                ft.Radio(value="Crédito / Fiado", label="Crédito / Fiado"),
            ]),
            value="Efectivo",
            on_change=lambda e: self._recalcular_cobro_modal(),
        )

        self.lbl_modal_total = ft.Text("$0.00", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800)
        self.txt_tel_cliente = ft.TextField(
            label="Teléfono Cliente (Enter para buscar)",
            hint_text="10 dígitos...",
            expand=True,
            keyboard_type=ft.KeyboardType.PHONE,
            autofocus=True,
            on_submit=lambda e: self._buscar_cliente_cobro(),
        )
        self.lbl_info_cliente = ft.Text("Cliente no asignado", color=ft.Colors.GREY_600, size=13)

        self.txt_nuevo_cliente_nombre = ft.TextField(label="Nombre del Cliente", expand=True)
        self.row_nuevo_cliente = ft.Row(
            [
                self.txt_nuevo_cliente_nombre,
                ft.Button(
                    "Guardar",
                    icon=ft.Icons.CHECK,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                    on_click=lambda e: self._guardar_cliente_rapido(),
                ),
            ],
            visible=False,
        )

        self.txt_canje_puntos = ft.TextField(
            label="¿Cuánto canjear en pesos? ($)",
            value="0.0",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=230,
            visible=False,
            on_change=lambda e: self._al_cambiar_puntos(),
        )

        self.txt_efectivo_recibido = ft.TextField(
            label="Efectivo Recibido ($)",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=220,
            on_change=lambda e: self._recalcular_cobro_modal(),
            on_submit=lambda e: self._confirmar_venta(),
        )
        self.lbl_cambio = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)

        self.modal_cobro = DialogoModalBase(
            page=self.pagina,
            titulo="Cobro de Venta (Ctrl + Enter)",
            icono=ft.Icons.POINT_OF_SALE,
            color_icono=ft.Colors.GREEN_700,
            ancho=500,
            texto_confirmar="CONFIRMAR VENTA (Enter)",
            icono_confirmar=ft.Icons.CHECK_CIRCLE,
            color_confirmar=ft.Colors.GREEN_700,
            al_confirmar=lambda e: self._confirmar_venta(),
        )
        self.modal_cobro.set_contenido([
            ft.Text("Método de Pago:", weight=ft.FontWeight.W_500),
            self.rg_metodo_pago,
            ft.Divider(),
            ft.Row([ft.Text("Total a Pagar:", size=16, weight=ft.FontWeight.BOLD), self.lbl_modal_total], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            ft.Text("Cliente (Obligatorio para Fiado o Envases):", weight=ft.FontWeight.W_500),
            ft.Row([
                self.txt_tel_cliente,
                ft.IconButton(icon=ft.Icons.SEARCH, tooltip="Buscar", on_click=lambda e: self._buscar_cliente_cobro()),
            ]),
            self.lbl_info_cliente,
            self.row_nuevo_cliente,
            self.txt_canje_puntos,
            ft.Divider(),
            ft.Row(
                [
                    self.txt_efectivo_recibido,
                    ft.Column([ft.Text("Cambio / Estado:", size=12, color=ft.Colors.GREY_700), self.lbl_cambio], alignment=ft.MainAxisAlignment.CENTER),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        ])

    def _construir_ui(self):
        self.buscador_pos = BuscadorAutocompletado(
            hint_text="Escribe nombre, código de barras o escanea...",
            icono_sugerencia=ft.Icons.SHOPPING_BAG_OUTLINED,
            funcion_busqueda=buscar_producto_por_codigo_o_nombre,
            generador_titulo=lambda p: p["nombre"],
            generador_subtitulo=lambda p: f"Stock: {formatear_stock(p['stock_actual'], p['tipo_unidad'] or '')} | Cód: {p['codigo_barras'] or '—'}",
            generador_trailing=lambda p: f"${p['precio_venta']:.2f}",
            al_seleccionar=self._al_seleccionar_producto_buscador,
            permitir_deseleccion=False,
            altura_sugerencias=260,
        )

        col_carrito = ft.Container(
            content=ft.Column(
                [ft.Row([self.tabla_carrito], scroll=ft.ScrollMode.AUTO, expand=True)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=3,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
        )

        col_totales = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Total a Cobrar:", size=18, weight=ft.FontWeight.W_500),
                    self.lbl_total,
                    self.lbl_items,
                    ft.Divider(),
                    ft.Button(
                        "COBRAR (Ctrl+Enter)",
                        icon=ft.Icons.POINT_OF_SALE,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE),
                        height=60,
                        width=260,
                        on_click=lambda e: self.abrir_modal_cobro(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=1,
            bgcolor=ft.Colors.GREY_100,
            border_radius=8,
            padding=20,
        )

        self.content = ft.Column(
            [
                self.buscador_pos,
                ft.Row([col_carrito, col_totales], expand=True),
            ],
            expand=True,
            spacing=10,
        )

    def _al_seleccionar_producto_buscador(self, prod):
        """Maneja la selección desde el buscador o lector de código."""
        if not prod:
            return

        prod_dict = dict(prod) if not isinstance(prod, dict) else prod

        if hasattr(self, "txt_buscador"):
            self.txt_buscador.value = ""
            self.txt_buscador.focus()

        self._procesar_producto_para_carrito(prod_dict)

    
    def actualizar_carrito_ui(self):
        self.tabla_carrito.rows.clear()

        for idx, item in enumerate(self.pos_controller.carrito):
            btn_restar = ft.IconButton(
                icon=ft.Icons.REMOVE_CIRCLE_OUTLINED,
                icon_color=ft.Colors.ORANGE_700,
                on_click=lambda e, i=idx: (self.pos_controller.decrementar_cantidad(i), self.actualizar_carrito_ui()),
            )
            btn_sumar = ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE_OUTLINED,
                icon_color=ft.Colors.GREEN_700,
                on_click=lambda e, i=idx: (self.pos_controller.incrementar_cantidad(i), self.actualizar_carrito_ui()),
            )
            btn_eliminar = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                on_click=lambda e, i=idx: (self.pos_controller.eliminar_item(i), self.actualizar_carrito_ui()),
            )

            if item.es_retornable:
                cant_c = item.envases_a_cobrar
                tot_dep = item.costo_total_envases
                txt_btn = f"+${tot_dep:.2f} ({cant_c} env)" if cant_c > 0 else "Trajo Envase ($0)"
                btn_env = ft.Button(
                    txt_btn,
                    icon=ft.Icons.WINE_BAR,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.ORANGE_800 if cant_c > 0 else ft.Colors.BLUE_GREY_600,
                        color=ft.Colors.WHITE,
                    ),
                    on_click=lambda e, i=idx: self._click_envase(i),
                )
            else:
                btn_env = ft.Text("—", color=ft.Colors.GREY_500)

            self.tabla_carrito.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.nombre)),
                        ft.DataCell(ft.Text(f"${item.precio_unitario:.2f}")),
                        ft.DataCell(ft.Text(str(item.cantidad))),
                        ft.DataCell(ft.Text(f"${item.subtotal_articulos:.2f}")),
                        ft.DataCell(btn_env),
                        ft.DataCell(ft.Row([btn_restar, btn_sumar, btn_eliminar], spacing=0)),
                    ]
                )
            )

        self.lbl_total.value = f"${self.pos_controller.total_bruto:.2f}"
        self.lbl_items.value = f"{self.pos_controller.total_articulos} artículo(s) en carrito"
        self.pagina.update()
    

    def actualizar_carrito_ui(self):
        self.tabla_carrito.rows.clear()

        for idx, item in enumerate(self.pos_controller.carrito):
            # Detectar si el artículo se vende por peso
            unidad = str(getattr(item, "unidad_medida", "")).lower()
            es_granel = any(k in unidad for k in ["kilo", "kg", "gramo", "lt", "litro"])

            # Formato de la cantidad (3 decimales si es granel o float)
            cant_val = float(item.cantidad)
            txt_cant = f"{cant_val:.3f} kg" if es_granel else (f"{int(cant_val)}" if cant_val.is_integer() else f"{cant_val:.2f}")

            # Botones estándar
            btn_restar = ft.IconButton(
                icon=ft.Icons.REMOVE_CIRCLE_OUTLINED,
                icon_color=ft.Colors.ORANGE_700,
                on_click=lambda e, i=idx: (self.pos_controller.decrementar_cantidad(i), self.actualizar_carrito_ui()),
            )
            btn_sumar = ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE_OUTLINED,
                icon_color=ft.Colors.GREEN_700,
                on_click=lambda e, i=idx: (self.pos_controller.incrementar_cantidad(i), self.actualizar_carrito_ui()),
            )
            btn_eliminar = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                on_click=lambda e, i=idx: (self.pos_controller.eliminar_item(i), self.actualizar_carrito_ui()),
            )

            # Botón de báscula si es producto por peso
            btn_pesar = ft.IconButton(
                icon=ft.Icons.SCALE,
                icon_color=ft.Colors.BLUE_700,
                tooltip="Ajustar peso / importe ($)",
                on_click=lambda e, prod=item, i=idx: self._abrir_granel_para_item(prod, i),
            ) if es_granel else None

            # Manejo de retornables
            if item.es_retornable:
                cant_c = item.envases_a_cobrar
                tot_dep = item.costo_total_envases
                txt_btn = f"+${tot_dep:.2f} ({cant_c} env)" if cant_c > 0 else "Trajo Envase ($0)"
                btn_env = ft.Button(
                    txt_btn,
                    icon=ft.Icons.WINE_BAR,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.ORANGE_800 if cant_c > 0 else ft.Colors.BLUE_GREY_600,
                        color=ft.Colors.WHITE,
                    ),
                    on_click=lambda e, i=idx: self._click_envase(i),
                )
            else:
                btn_env = ft.Text("—", color=ft.Colors.GREY_500)

            # Lista de botones de acción
            acciones_fila = [btn_restar, btn_sumar]
            if btn_pesar:
                acciones_fila.insert(0, btn_pesar)
            acciones_fila.append(btn_eliminar)

            self.tabla_carrito.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.nombre)),
                        ft.DataCell(ft.Text(f"${item.precio_unitario:.2f}")),
                        ft.DataCell(ft.Text(txt_cant, weight=ft.FontWeight.BOLD if es_granel else ft.FontWeight.NORMAL)),
                        ft.DataCell(ft.Text(f"${item.subtotal_articulos:.2f}")),
                        ft.DataCell(btn_env),
                        ft.DataCell(ft.Row(acciones_fila, spacing=0)),
                    ]
                )
            )

        self.lbl_total.value = f"${self.pos_controller.total_bruto:.2f}"
        self.lbl_items.value = f"{self.pos_controller.total_articulos} artículo(s) en carrito"
        self.pagina.update()

    
    def _click_envase(self, index: int):
        item = self.pos_controller.carrito[index]
        if item.max_envases_posibles == 1:
            self.pos_controller.alternar_envase_individual(index)
            self.actualizar_carrito_ui()
            return

        self.indice_envase_actual = index
        self.lbl_envase_prod.value = f"Producto: {item.nombre}"
        self.lbl_envase_unitario.value = f"Garantía por envase: ${item.precio_envase_unitario:.2f}"
        self.lbl_envase_max.value = f"Máximo de envases en este paquete: {item.max_envases_posibles} pzas"
        self.txt_cant_envases_cobrar.value = str(item.envases_a_cobrar)

        self.btn_todos_envases.text = f"Cobrar Todos ({item.max_envases_posibles} = ${item.max_envases_posibles * item.precio_envase_unitario:.2f})"
        self.btn_todos_envases.on_click = lambda e: self._aplicar_envases_config(item.max_envases_posibles)
        self.modal_envase.abrir()

    def _aplicar_envases_config(self, cant: int):
        if self.indice_envase_actual is not None:
            self.pos_controller.configurar_envases_item(self.indice_envase_actual, cant)
            self.actualizar_carrito_ui()
        self.modal_envase.cerrar()

    def _aplicar_envases_config_personalizado(self):
        try:
            val = int(self.txt_cant_envases_cobrar.value or "0")
        except ValueError:
            val = 0
        self._aplicar_envases_config(val)

    def abrir_modal_salida_caja(self):
        self.txt_monto_gasto.value = ""
        self.txt_motivo_gasto.value = ""
        self.modal_salida_caja.abrir()

    def _guardar_salida_caja(self):
        try:
            monto = float(self.txt_monto_gasto.value or "0")
        except ValueError:
            monto = 0.0

        motivo = self.txt_motivo_gasto.value.strip()
        if monto <= 0 or not motivo:
            self.mostrar_mensaje("Ingresa un monto válido y el motivo", ft.Colors.RED_600)
            return

        registrar_movimiento_caja("Salida", monto, motivo, self.id_empleado_activo)
        self.modal_salida_caja.cerrar()
        self.mostrar_mensaje(f"💸 Salida de ${monto:.2f} registrada", ft.Colors.ORANGE_800)

    def abrir_modal_cobro(self):
        if not self.pos_controller.carrito:
            self.mostrar_mensaje("⚠️️ El carrito está vacío", ft.Colors.ORANGE_800)
            return

        self.pos_controller.desvincular_cliente()
        self.rg_metodo_pago.value = "Efectivo"
        self.txt_tel_cliente.value = ""
        self.lbl_info_cliente.value = "Cliente no asignado"
        self.lbl_info_cliente.color = ft.Colors.GREY_600
        self.row_nuevo_cliente.visible = False
        self.txt_canje_puntos.visible = False
        self.txt_canje_puntos.value = "0.0"
        self.txt_efectivo_recibido.value = ""
        self.txt_efectivo_recibido.visible = True

        self._recalcular_cobro_modal()
        self.modal_cobro.abrir()

    def _recalcular_cobro_modal(self):
        total_neto = self.pos_controller.total_neto
        self.lbl_modal_total.value = f"${total_neto:.2f}"

        if self.rg_metodo_pago.value in ["Transferencia", "Tarjeta", "Crédito / Fiado"]:
            self.txt_efectivo_recibido.visible = False
            self.lbl_cambio.value = "Cuenta Fiada" if self.rg_metodo_pago.value == "Crédito / Fiado" else "Pago Exacto"
            self.lbl_cambio.color = ft.Colors.BLUE_700
        else:
            self.txt_efectivo_recibido.visible = True
            recibido = a_decimal(self.txt_efectivo_recibido.value)
            cambio = recibido - total_neto
            if cambio >= Decimal("0.00"):
                self.lbl_cambio.value = f"${cambio:.2f}"
                self.lbl_cambio.color = ft.Colors.GREEN_700
            else:
                self.lbl_cambio.value = f"Faltan ${abs(cambio):.2f}"
                self.lbl_cambio.color = ft.Colors.RED_600
        self.pagina.update()

    def _buscar_cliente_cobro(self):
        tel = self.txt_tel_cliente.value.strip()
        if not tel:
            self.txt_efectivo_recibido.autofocus = True
            self.pagina.update()
            return

        c = buscar_cliente_por_telefono(tel)
        if c:
            self.pos_controller.vincular_cliente(c["id_cliente"], c["nombre"], c["puntos_acumulados"])
            pesos = c["puntos_acumulados"] * 0.10
            self.lbl_info_cliente.value = f"👤 {c['nombre']} | Saldo: {c['puntos_acumulados']} pts (${pesos:.2f})"
            self.lbl_info_cliente.color = ft.Colors.BLUE_900
            self.row_nuevo_cliente.visible = False
            self.txt_canje_puntos.visible = c["puntos_acumulados"] > 0
            self.txt_canje_puntos.value = "0.0"
        else:
            self.pos_controller.desvincular_cliente()
            self.lbl_info_cliente.value = "⚠️ Cliente no registrado. ¿Deseas darlo de alta?"
            self.lbl_info_cliente.color = ft.Colors.ORANGE_800
            self.row_nuevo_cliente.visible = True
            self.txt_canje_puntos.visible = False
        self._recalcular_cobro_modal()

    def _guardar_cliente_rapido(self):
        nom = self.txt_nuevo_cliente_nombre.value.strip()
        tel = self.txt_tel_cliente.value.strip()
        if not nom:
            self.mostrar_mensaje("Escribe el nombre del cliente", ft.Colors.RED_600)
            return

        nuevo_id = registrar_cliente_rapido(nom, tel)
        self.pos_controller.vincular_cliente(nuevo_id, nom, 0)
        self.lbl_info_cliente.value = f"👤 {nom} (Nuevo Cliente)"
        self.lbl_info_cliente.color = ft.Colors.GREEN_700
        self.row_nuevo_cliente.visible = False
        self.mostrar_mensaje("✅ Cliente registrado", ft.Colors.GREEN_700)
        self._recalcular_cobro_modal()

    def _al_cambiar_puntos(self):
        self.pos_controller.aplicar_canje_puntos(self.txt_canje_puntos.value)
        self._recalcular_cobro_modal()
    
    def _confirmar_venta(self):
        metodo = self.rg_metodo_pago.value
        recibido = self.txt_efectivo_recibido.value or "0.0"

        if metodo == "Efectivo":
            if a_decimal(recibido) < self.pos_controller.total_neto:
                self.mostrar_mensaje("⚠ El dinero recibido no cubre el total", ft.Colors.RED_600)
                return

        try:
            id_v = self.pos_controller.procesar_venta(
                id_empleado=self.id_empleado_activo,
                metodo_pago=metodo,
                efectivo_recibido=recibido,
            )
            self.modal_cobro.cerrar()
            self.actualizar_carrito_ui()
            self.mostrar_mensaje(f" ¡Venta #{id_v} completada con éxito!", ft.Colors.GREEN_700)

            try:
                self.ticket_service.recargar_configuracion()
                texto_ticket = self.ticket_service.generar_ticket_desde_id(id_v)

                if texto_ticket:
                    if getattr(self.ticket_service, "impresion_auto", False):
                        self.ticket_service.imprimir_ticket(texto_ticket)

                    self._mostrar_modal_vista_previa_ticket(texto_ticket, id_v)
            except Exception as e_ticket:
                print(f"[Error Generando Ticket] {e_ticket}")
                self.mostrar_mensaje(f"⚠ Venta guardada, pero ocurrió un error con el ticket: {e_ticket}", ft.Colors.ORANGE_800)

        except Exception as err:
            self.mostrar_mensaje(f" {err}", ft.Colors.RED_600)
                    
    def _configurar_atajos_teclado(self):
        def on_teclado(e: ft.KeyboardEvent):
            if e.ctrl and e.key in ["Enter", " "]:
                if not self.modal_cobro.open and not self.modal_salida_caja.open and not self.modal_envase.open:
                    self.abrir_modal_cobro()
            elif e.key == "Escape":
                self.modal_cobro.cerrar()
                self.modal_salida_caja.cerrar()
                self.modal_envase.cerrar()
                self.buscador_pos.txt_buscar.autofocus = True
                self.pagina.update()

        self.pagina.on_keyboard_event = on_teclado

    def _agregar_producto_detectado(self, producto: dict):
        """Determina si se agrega por unidad normal o si requiere pesaje."""
        unidad = str(producto.get("unidad_medida", "")).lower()
        es_a_granel = producto.get("a_granel") == 1 or unidad in ["kg", "kilo", "kilogramo", "gramo", "lt", "litro"]

        if es_a_granel:
            self.modal_granel.abrir(producto)
        else:
            self._agregar_al_carrito(producto, cantidad=1.0)

    
    def _procesar_producto_para_carrito(self, producto):
        """Si el producto se vende por peso/granel, abre la báscula; si no, agrega 1 unidad."""
        if not producto:
            return

        prod_dict = dict(producto) if not isinstance(producto, dict) else producto

        # Leemos 'tipo_unidad' que es el campo real de tu base de datos
        unidad = str(prod_dict.get("tipo_unidad") or prod_dict.get("unidad_medida") or "").lower()

        # Detección: si contiene kg, kilo, gramo, lt o litro
        es_granel = any(u in unidad for u in ["kilo", "kg", "gramo", "gr", "lt", "litro"])

        if es_granel:
            self.modal_granel.abrir(prod_dict)
        else:
            self.pos_controller.agregar_producto(prod_dict, cantidad=1.0)
            self.actualizar_carrito_ui()
    
    def _abrir_granel_para_item(self, item, indice_carrito: int):
        """Abre el modal de báscula para modificar un producto que ya está en el carrito."""
        prod_dict = {
            "id_producto": item.id_producto,
            "nombre": item.nombre,
            "precio_venta": item.precio_unitario,
            "unidad_medida": getattr(item, "unidad_medida", "kg"),
            "indice_carrito": indice_carrito,
        }
        self.modal_granel.abrir(prod_dict)

    
    def _agregar_producto_granel_al_carrito(self, producto: dict, peso: float, importe: float):
        """Aplica la cantidad calculada por peso o importe."""
        if "indice_carrito" in producto:
            from decimal import Decimal
            idx = producto["indice_carrito"]
            self.pos_controller.carrito[idx].cantidad = Decimal(str(round(peso, 3)))
            self.pos_controller.recalcular_totales()
        else:
            self.pos_controller.agregar_producto(producto, cantidad=round(peso, 3))

        self.actualizar_carrito_ui()
        self.mostrar_mensaje(f"Agregado: {producto.get('nombre', '')} ({peso:.3f} kg)", "green")

    def _mostrar_modal_vista_previa_ticket(self, texto_ticket: str, id_venta: int):
        """Muestra el diálogo con la vista previa del ticket y opción de imprimir."""
        def cerrar_dialogo(e=None):
            try:
                self.pagina.close(dlg)
            except Exception:
                dlg.open = False
                self.pagina.update()

        # Configurar borde compatible con versiones de Flet
        borde_box = None
        if hasattr(ft, "Border") and hasattr(ft.Border, "all"):
            borde_box = ft.Border.all(1, ft.Colors.GREY_300)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.RECEIPT_LONG, color=ft.Colors.BLUE_700),
                    ft.Text(f"Ticket de Venta #{id_venta}", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            texto_ticket,
                            font_family="Courier New",
                            size=12,
                            selectable=True,
                        )
                    ],
                    scroll=ft.ScrollMode.ADAPTIVE,
                    tight=True,
                ),
                width=340,
                height=380,
                border=borde_box,
                border_radius=8,
                padding=10,
                bgcolor=ft.Colors.GREY_50,
            ),
            actions=[
                ft.TextButton("Cerrar (Esc)", on_click=cerrar_dialogo),
                ft.Button(
                    "Imprimir",
                    icon=ft.Icons.PRINT,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                    on_click=lambda e: (self.ticket_service.imprimir_ticket(texto_ticket), cerrar_dialogo()),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        try:
            self.pagina.open(dlg)
        except Exception:
            if dlg not in self.pagina.overlay:
                self.pagina.overlay.append(dlg)
            dlg.open = True
            self.pagina.update()