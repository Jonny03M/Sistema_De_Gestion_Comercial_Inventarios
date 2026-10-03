from typing import Callable, Optional
import flet as ft

from components.dialogo_base import DialogoModalBase
from components.selector_fechas import SelectorRangoFechas
from database.ventas_db import (
    obtener_detalle_venta_por_id,
    obtener_resumen_corte_por_rango,
    obtener_ventas_por_rango,
)
from database.turnos_db import obtener_historial_cortes
from services.ticket_service import TicketService

class ReportesView(ft.Container):
    """Vista modular para cortes de caja, resumen financiero e historial de tickets."""

    def __init__(self, page: ft.Page, mostrar_mensaje: Callable[[str, str], None]):
        super().__init__(expand=True, padding=10)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje

        self._crear_kpis()
        self._crear_tablas()
        self._crear_modal_ticket()
        self._construir_ui()
        self.cargar_datos_corte()
        self._construir_seccion_cortes()
        self.ticket_service = TicketService()
        

    def _crear_kpis(self):
        self.lbl_total_dia = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lbl_ganancia = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lbl_efectivo = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lbl_fiado = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lbl_salidas = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lbl_digital = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

        self.fila_kpis = ft.ResponsiveRow(
            controls=[
                self._crear_tarjeta_kpi("Ventas Totales", self.lbl_total_dia, ft.Icons.ATTACH_MONEY, ft.Colors.BLUE_800),
                self._crear_tarjeta_kpi("Ganancia Est.", self.lbl_ganancia, ft.Icons.TRENDING_UP, ft.Colors.GREEN_800),
                self._crear_tarjeta_kpi("Efectivo en Cajón", self.lbl_efectivo, ft.Icons.PAYMENTS, ft.Colors.TEAL_800),
                self._crear_tarjeta_kpi("Ventas Fiadas", self.lbl_fiado, ft.Icons.ASSIGNMENT_LATE, ft.Colors.ORANGE_900),
                self._crear_tarjeta_kpi("Gastos / Salidas", self.lbl_salidas, ft.Icons.MONEY_OFF, ft.Colors.RED_800),
                self._crear_tarjeta_kpi("Tarjetas / SPEI", self.lbl_digital, ft.Icons.QR_CODE, ft.Colors.INDIGO_800),
            ],
            spacing=8,
        )

    def _crear_tarjeta_kpi(self, titulo: str, control_valor: ft.Control, icono: str, color_fondo: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono, size=24, color=ft.Colors.WHITE),
                    ft.Column(
                        [
                            ft.Text(titulo, color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.W_500),
                            control_valor,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=1,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
            ),
            bgcolor=color_fondo,
            border_radius=8,
            padding=8,
            col={"xs": 12, "sm": 6, "md": 4, "lg": 2},
        )

    def _crear_tablas(self):
        # 1. Tabla Ventas
        self.tabla_ventas = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("# Ticket", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Fecha / Hora", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cajero", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Método", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True,
            column_spacing=14,
            horizontal_margin=8,
        )

        # 2. Tabla Detalle Ticket Modal
        self.tabla_articulos_ticket = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Precio U.", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD), numeric=True),
            ],
            rows=[],
            column_spacing=16,
            horizontal_margin=10,
        )

    def _crear_modal_ticket(self):
        self.lbl_ticket_id = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
        self.lbl_ticket_fecha = ft.Text("", size=12, color=ft.Colors.GREY_700)
        self.lbl_ticket_cliente = ft.Text("", size=13)
        self.lbl_ticket_cajero = ft.Text("", size=13)
        self.lbl_ticket_metodo = ft.Text("", size=13)

        self.lbl_ticket_subtotal_art = ft.Text("", size=13, weight=ft.FontWeight.W_500)
        self.lbl_ticket_envases = ft.Text("", size=13, color=ft.Colors.ORANGE_900, weight=ft.FontWeight.BOLD)
        self.lbl_ticket_descuento = ft.Text("", size=13, color=ft.Colors.GREEN_800)
        self.lbl_ticket_total = ft.Text("", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)

        self.modal_ticket = DialogoModalBase(
            page=self.pagina,
            titulo="Detalle del Ticket",
            icono=ft.Icons.RECEIPT_LONG,
            ancho=540,
            mostrar_boton_confirmar=False,
        )
        self.modal_ticket.set_contenido([
            self.lbl_ticket_fecha,
            ft.Divider(height=1),
            ft.Row([self.lbl_ticket_cliente, self.lbl_ticket_cajero], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.lbl_ticket_metodo,
            ft.Divider(height=1),
            ft.Text("Artículos Comprados:", size=13, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column(
                    [ft.Row([self.tabla_articulos_ticket], scroll=ft.ScrollMode.AUTO, expand=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                height=180,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=8,
                padding=4,
            ),
            ft.Divider(height=1),
            ft.Row([ft.Text("Subtotal Productos:"), self.lbl_ticket_subtotal_art], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Garantía Envases (Sin Casco):"), self.lbl_ticket_envases], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Descuento Monedero:"), self.lbl_ticket_descuento], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1),
            ft.Row([ft.Text("Total Pagado:", size=16, weight=ft.FontWeight.BOLD), self.lbl_ticket_total], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ])

    def _construir_ui(self):
        self.lbl_fecha_mostrada = ft.Text(
            "Periodo: Hoy",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE_900,
        )
        self.selector_fechas = SelectorRangoFechas(
            page=self.pagina, al_cambiar_rango=self._al_cambiar_periodo
        )

        # 1. Contenedor original de Ventas y Métricas
        self.vista_ventas = ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    "Corte de Caja y Reportes de Venta",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                self.lbl_fecha_mostrada,
                            ],
                            spacing=2,
                        ),
                        self.selector_fechas,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
                ft.Divider(),
                self.fila_kpis,
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "Historial de Ventas Registradas:",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [self.tabla_ventas],
                                            scroll=ft.ScrollMode.AUTO,
                                            expand=True,
                                        )
                                    ],
                                    scroll=ft.ScrollMode.AUTO,
                                    expand=True,
                                ),
                                expand=True,
                            ),
                        ],
                        expand=True,
                        spacing=8,
                    ),
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    padding=10,
                    expand=True,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=8,
        )

        # 2. Contenedor dinámico que alternará entre Ventas y Turnos
        self.area_reporte = ft.Container(
            content=self.vista_ventas,
            expand=True,
        )

        # 3. Botones tipo pestaña
        btn_ventas = ft.Button(
            "Ventas y Finanzas",
            icon=ft.Icons.ANALYTICS_OUTLINED,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800, color=ft.Colors.WHITE),
        )

        btn_turnos = ft.Button(
            "Auditoría de Turnos",
            icon=ft.Icons.BADGE_OUTLINED,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREY_200, color=ft.Colors.BLACK87),
        )

        def mostrar_ventas(e):
            btn_ventas.style.bgcolor = ft.Colors.BLUE_800
            btn_ventas.style.color = ft.Colors.WHITE
            btn_turnos.style.bgcolor = ft.Colors.GREY_200
            btn_turnos.style.color = ft.Colors.BLACK87
            self.area_reporte.content = self.vista_ventas
            self.pagina.update()

        def mostrar_turnos(e):
            btn_turnos.style.bgcolor = ft.Colors.BLUE_800
            btn_turnos.style.color = ft.Colors.WHITE
            btn_ventas.style.bgcolor = ft.Colors.GREY_200
            btn_ventas.style.color = ft.Colors.BLACK87
            self.area_reporte.content = self._construir_seccion_turnos()
            self.pagina.update()

        btn_ventas.on_click = mostrar_ventas
        btn_turnos.on_click = mostrar_turnos

        # Estructura principal
        self.content = ft.Column(
            [
                ft.Row([btn_ventas, btn_turnos], spacing=10),
                self.area_reporte,
            ],
            expand=True,
            spacing=14,
        )

    def _al_cambiar_periodo(self, f_ini: str, f_fin: str, descripcion: str):
        self.lbl_fecha_mostrada.value = descripcion
        self.cargar_datos_corte(f_ini, f_fin)

    def cargar_datos_corte(self, f_ini: Optional[str] = None, f_fin: Optional[str] = None):
        if not f_ini:
            f_ini = self.selector_fechas.fecha_inicio
            f_fin = self.selector_fechas.fecha_fin

        resumen = obtener_resumen_corte_por_rango(f_ini, f_fin)

        self.lbl_total_dia.value = f"${resumen['total_general']:.2f}"
        self.lbl_ganancia.value = f"${resumen['ganancia_estimada']:.2f}"
        self.lbl_efectivo.value = f"${resumen['efectivo_real_en_caja']:.2f}"
        self.lbl_fiado.value = f"${resumen.get('total_fiado', 0.0):.2f}"
        self.lbl_salidas.value = f"-${resumen['total_salidas']:.2f}"
        self.lbl_digital.value = f"${resumen['total_digital']:.2f}"

        # Cargar Ventas
        self.tabla_ventas.rows.clear()
        ventas = obtener_ventas_por_rango(f_ini, f_fin)

        for v in ventas:
            id_venta = v["id_venta"]

            btn_ver = ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                icon_color=ft.Colors.BLUE_700,
                tooltip="Ver desglose del ticket",
                on_click=lambda e, id_v=v["id_venta"]: self.abrir_detalle_ticket(id_v),
            )

            btn_imprimir = ft.IconButton(
                icon = ft.Icons.PRINT,
                icon_color = ft.Colors.TEAL_700,
                tooltip="Reimprimir ticket", 
                on_click= lambda e, id_v = id_venta: self._reimprimir_ticket(id_v),
            )

            color_metodo = ft.Colors.BLUE_700
            if v["metodo_pago"] == "Efectivo":
                color_metodo = ft.Colors.GREEN_700
            elif v["metodo_pago"] == "Crédito / Fiado":
                color_metodo = ft.Colors.ORANGE_900

            self.tabla_ventas.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{v['id_venta']}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(v["fecha_hora"] or "—")),
                        ft.DataCell(ft.Text(v["cliente"])),
                        ft.DataCell(ft.Text(v["cajero"])),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(v["metodo_pago"], size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                bgcolor=color_metodo,
                                padding=4,
                                border_radius=4,
                            )
                        ),
                        ft.DataCell(ft.Text(f"${v['total']:.2f}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(
                            ft.Row(
                                [btn_ver, btn_imprimir],
                                spacing=0,
                                alignment=ft.MainAxisAlignment.START,
                            )
                        ),
                    ]
                )
            )

        self.pagina.update()

    def abrir_detalle_ticket(self, id_venta: int):
        data = obtener_detalle_venta_por_id(id_venta)
        venta = data.get("venta")
        detalles = data.get("detalles", [])
        monto_env = data.get("monto_envases", 0.0)
        subt_art = data.get("subtotal_articulos", 0.0)

        if not venta:
            self.mostrar_mensaje("No se pudo cargar la información del ticket", ft.Colors.RED_600)
            return

        self.lbl_ticket_id.value = f"Ticket de Venta #{venta['id_venta']}"
        self.lbl_ticket_fecha.value = f"📅 {venta['fecha_hora']}"
        self.lbl_ticket_cliente.value = f"👤 Cliente: {venta['cliente']}"
        self.lbl_ticket_cajero.value = f"💼 Cajero: {venta['cajero']}"
        self.lbl_ticket_metodo.value = f"💳 Método: {venta['metodo_pago']}"
        self.lbl_ticket_subtotal_art.value = f"${subt_art:.2f}"

        self.lbl_ticket_envases.value = f"+${monto_env:.2f}" if monto_env > 0 else "$0.00"

        puntos_usados = venta.get("puntos_canjeados", 0)
        if puntos_usados > 0:
            ahorro = puntos_usados * 0.10
            self.lbl_ticket_descuento.value = f"-${ahorro:.2f} ({puntos_usados} pts)"
        else:
            self.lbl_ticket_descuento.value = "$0.00"

        self.lbl_ticket_total.value = f"${venta['total']:.2f}"

        self.tabla_articulos_ticket.rows.clear()
        for art in detalles:
            self.tabla_articulos_ticket.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{art['cantidad']}")),
                        ft.DataCell(ft.Text(art["nombre"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"${art['precio_unitario']:.2f}")),
                        ft.DataCell(ft.Text(f"${art['subtotal']:.2f}", weight=ft.FontWeight.BOLD)),
                    ]
                )
            )

        self.modal_ticket.abrir()

    def _construir_seccion_cortes(self) -> ft.Control:
        cortes = obtener_historial_cortes(limite=30)
        filas = []

        for c in cortes:
            dif = float(c["diferencia"] or 0.0)
            if dif < 0:
                color_dif = ft.Colors.RED_700
                texto_dif = f"-${abs(dif):.2f} (Faltante)"
            elif dif > 0:
                color_dif = ft.Colors.BLUE_700
                texto_dif = f"+${dif:.2f} (Sobrante)"
            else:
                color_dif = ft.Colors.GREEN_700
                texto_dif = "Exacto ($0.00)"

            filas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{c['id_turno']}")),
                        ft.DataCell(ft.Text(c["cajero"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(c["fecha_apertura"] or "—")),
                        ft.DataCell(ft.Text(c["fecha_cierre"] or "Abierto")),
                        ft.DataCell(ft.Text(f"${c['monto_inicial']:.2f}")),
                        ft.DataCell(ft.Text(f"${c['ventas_efectivo']:.2f}")),
                        ft.DataCell(ft.Text(f"${c['salidas_efectivo']:.2f}")),
                        ft.DataCell(ft.Text(f"${c['monto_esperado']:.2f}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"${c['monto_declarado']:.2f}")),
                        ft.DataCell(
                            ft.Text(texto_dif, color=color_dif, weight=ft.FontWeight.BOLD)
                        ),
                    ]
                )
            )

        tabla = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#")),
                ft.DataColumn(ft.Text("Cajero")),
                ft.DataColumn(ft.Text("Apertura")),
                ft.DataColumn(ft.Text("Cierre")),
                ft.DataColumn(ft.Text("Fondo Inicial")),
                ft.DataColumn(ft.Text("Ventas Efec.")),
                ft.DataColumn(ft.Text("Salidas")),
                ft.DataColumn(ft.Text("Esperado")),
                ft.DataColumn(ft.Text("Declarado")),
                ft.DataColumn(ft.Text("Diferencia")),
            ],
            rows=filas,
            column_spacing=14,
        )

        return ft.Column(
            [
                ft.Text("Auditoría de Cortes y Entregas de Turno", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
            ],
            spacing=10,
        )

    def _construir_seccion_turnos(self) -> ft.Control:
        """Genera la tabla interactiva de auditoría de turnos de caja."""
        cortes = obtener_historial_cortes(limite=50)

        if not cortes:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.INVENTORY_2_OUTLINED,
                            size=48,
                            color=ft.Colors.GREY_400,
                        ),
                        ft.Text(
                            "Aún no hay registros de aperturas o cierres de turno.",
                            color=ft.Colors.GREY_600,
                            size=14,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=40,
                alignment=ft.alignment.center,
            )

        filas = []
        for c in cortes:
            estado = c.get("estado", "Cerrado")
            dif = float(c.get("diferencia") or 0.0)

            # Formato y semáforo visual de diferencia
            if estado == "Abierto":
                badge_estado = ft.Container(
                    content=ft.Text(
                        "En Curso",
                        color=ft.Colors.WHITE,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=ft.Colors.GREEN_700,
                    padding=ft.Padding(8, 3, 8, 3),  # (left, top, right, bottom)
                    border_radius=12,
                )
                txt_dif = ft.Text("—", color=ft.Colors.GREY_600)
                monto_decl_str = "—"
                monto_esp_str = "—"
                fecha_cierre_str = "—"
            else:
                badge_estado = ft.Container(
                    content=ft.Text(
                        "Cerrado",
                        color=ft.Colors.WHITE,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=ft.Colors.BLUE_GREY_700,
                    padding=ft.Padding(8, 3, 8, 3),  # (left, top, right, bottom)
                    border_radius=12,
                )
                monto_decl_str = f"${float(c.get('monto_declarado') or 0.0):.2f}"
                monto_esp_str = f"${float(c.get('monto_esperado') or 0.0):.2f}"
                fecha_cierre_str = c.get("fecha_cierre") or "—"

                if dif < 0:
                    txt_dif = ft.Text(
                        f"-${abs(dif):.2f} (Faltante)",
                        color=ft.Colors.RED_700,
                        weight=ft.FontWeight.BOLD,
                    )
                elif dif > 0:
                    txt_dif = ft.Text(
                        f"+${dif:.2f} (Sobrante)",
                        color=ft.Colors.BLUE_800,
                        weight=ft.FontWeight.BOLD,
                    )
                else:
                    txt_dif = ft.Text(
                        "Exacto ($0.00)",
                        color=ft.Colors.GREEN_700,
                        weight=ft.FontWeight.BOLD,
                    )

            filas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                f"#{c['id_turno']}", weight=ft.FontWeight.BOLD
                            )
                        ),
                        ft.DataCell(ft.Text(c["cajero"])),
                        ft.DataCell(badge_estado),
                        ft.DataCell(ft.Text(c.get("fecha_apertura") or "—")),
                        ft.DataCell(ft.Text(fecha_cierre_str)),
                        ft.DataCell(
                            ft.Text(
                                f"${float(c.get('monto_inicial') or 0.0):.2f}"
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${float(c.get('ventas_efectivo') or 0.0):.2f}"
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${float(c.get('salidas_efectivo') or 0.0):.2f}"
                            )
                        ),
                        ft.DataCell(
                            ft.Text(monto_esp_str, weight=ft.FontWeight.BOLD)
                        ),
                        ft.DataCell(ft.Text(monto_decl_str)),
                        ft.DataCell(txt_dif),
                        ft.DataCell(
                            ft.Text(
                                c.get("observaciones") or "—",
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            )
                        ),
                    ]
                )
            )

        tabla = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#")),
                ft.DataColumn(ft.Text("Cajero")),
                ft.DataColumn(ft.Text("Estado")),
                ft.DataColumn(ft.Text("Apertura")),
                ft.DataColumn(ft.Text("Cierre")),
                ft.DataColumn(ft.Text("Fondo Inicial")),
                ft.DataColumn(ft.Text("Ventas Efectivo")),
                ft.DataColumn(ft.Text("Salidas")),
                ft.DataColumn(ft.Text("Esperado en Caja")),
                ft.DataColumn(ft.Text("Declarado")),
                ft.DataColumn(ft.Text("Auditoría / Dif.")),
                ft.DataColumn(ft.Text("Notas")),
            ],
            rows=filas,
            column_spacing=18,
            horizontal_margin=12,
            border=ft.Border.all(1, ft.Colors.GREY_300),  # <-- 'Border' con B mayúscula
            border_radius=8,
            heading_row_color=ft.Colors.GREY_100,
        )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.POINT_OF_SALE,
                            size=24,
                            color=ft.Colors.BLUE_800,
                        ),
                        ft.Text(
                            "Historial de Arqueos y Cortes Ciegos",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Resultados de las entregas de dinero físico contrastados contra las ventas del sistema.",
                    color=ft.Colors.GREY_600,
                    size=13,
                ),
                ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _reimprimir_ticket(self, id_venta: int):
        """Genera el ticket de la venta seleccionada y abre el modal de vista previa/impresión."""
        try:
            self.ticket_service.recargar_configuracion()
            texto_ticket = self.ticket_service.generar_ticket_desde_id(id_venta)
            if not texto_ticket:
                self.mostrar_mensaje(f"⚠ No se pudo generar el ticket para la venta #{id_venta}", ft.Colors.ORANGE_800)
                return

            def cerrar_dialogo(e=None):
                try:
                    self.pagina.close(dlg)
                except Exception:
                    dlg.open = False
                    self.pagina.update()

            borde_box = None
            if hasattr(ft, "Border") and hasattr(ft.Border, "all"):
                borde_box = ft.Border.all(1, ft.Colors.GREY_300)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [
                        ft.Icon(ft.Icons.PRINT, color=ft.Colors.BLUE_700),
                        ft.Text(f"Reimpresión - Ticket #{id_venta}", size=18, weight=ft.FontWeight.BOLD),
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
                        "Imprimir Copia",
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

        except Exception as err:
            print(f"[Error Reimprimiendo Ticket] {err}")
            self.mostrar_mensaje(f"Error al reimprimir ticket: {err}", ft.Colors.RED_600)