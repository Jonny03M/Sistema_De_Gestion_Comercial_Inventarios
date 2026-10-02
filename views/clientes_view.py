from decimal import Decimal
from typing import Callable, Optional
import flet as ft

from components.dialogo_base import DialogoModalBase
from database.clientes_db import (
    actualizar_limite_credito_cliente,
    obtener_clientes_con_deuda_y_envases,
    procesar_devolucion_envases_cliente,
    registrar_abono_credito,
)


class ClientesView(ft.Container):
    """Vista modular para la administración de clientes, cuentas por cobrar,

    abonos y control de envases retornables en garantía.
    """

    def __init__(
        self,
        page: ft.Page,
        mostrar_mensaje: Callable[[str, str], None],
        id_empleado_activo: int = 1,
    ):
        super().__init__(expand=True, padding=10)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje
        self.id_empleado_activo = id_empleado_activo

        # Estado transaccional para modales
        self.id_cliente_activo: Optional[int] = None
        self.deuda_actual: float = 0.0
        self.total_envases_pendientes: int = 0

        self._crear_controles_resumen()
        self._crear_tabla()
        self._crear_modales()
        self._construir_ui()
        self.cargar_clientes()

    def _crear_controles_resumen(self):
        self.lbl_total_por_cobrar = ft.Text(
            "Total Fiado: $0.00",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.RED_800,
        )
        self.lbl_total_envases_calle = ft.Text(
            "Envases Fuera: 0 pzas",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.ORANGE_900,
        )
        self.txt_filtro = ft.TextField(
            hint_text="Buscar cliente por nombre o teléfono...",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            on_change=lambda e: self.cargar_clientes(),
        )

    def _crear_tabla(self):
        self.tabla_clientes = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Teléfono", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Saldo Fiado", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Límite Crédito", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Envases Pend.", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Garantía Retenida", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True,
            column_spacing=16,
            horizontal_margin=8,
        )

    def _crear_modales(self):
        # 1. MODAL DE ABONO
        self.lbl_abono_cliente = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.lbl_abono_deuda = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_800)
        self.txt_monto_abono = ft.TextField(
            label="Monto del Abono ($) *",
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )

        self.modal_abono = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Abono a Cuenta",
            icono=ft.Icons.POINT_OF_SALE,
            color_icono=ft.Colors.GREEN_700,
            ancho=380,
            texto_confirmar="Cobrar Abono",
            icono_confirmar=ft.Icons.CHECK,
            color_confirmar=ft.Colors.GREEN_700,
            al_confirmar=self._guardar_abono,
        )
        self.modal_abono.set_contenido([
            self.lbl_abono_cliente,
            self.lbl_abono_deuda,
            ft.Divider(height=1),
            self.txt_monto_abono,
        ])

        # 2. MODAL DE DEVOLUCIÓN DE ENVASES
        self.lbl_dev_cliente = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.lbl_dev_resumen = ft.Text("", size=13, color=ft.Colors.ORANGE_900, weight=ft.FontWeight.BOLD)
        self.txt_cant_envases = ft.TextField(
            label="Cantidad de envases que devuelve *",
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
        )
        self.rg_destino_reembolso = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="Efectivo", label="Reembolsar efectivo (Salida de Caja)"),
                ft.Radio(value="Abonar a Deuda", label="Abonar garantía a saldo fiado (Descontar Deuda)"),
            ]),
            value="Efectivo",
        )

        self.modal_devolucion = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Devolución de Envases",
            icono=ft.Icons.WINE_BAR,
            color_icono=ft.Colors.ORANGE_800,
            ancho=450,
            texto_confirmar="Confirmar Devolución",
            icono_confirmar=ft.Icons.CHECK_CIRCLE,
            color_confirmar=ft.Colors.GREEN_700,
            al_confirmar=self._guardar_devolucion_envases,
        )
        self.modal_devolucion.set_contenido([
            self.lbl_dev_cliente,
            self.lbl_dev_resumen,
            ft.Divider(height=1),
            self.txt_cant_envases,
            ft.Text("¿Cómo devolver la garantía retenida?", size=12, weight=ft.FontWeight.W_500),
            self.rg_destino_reembolso,
        ])

        # 3. MODAL DE EDICIÓN DE LÍMITE DE CRÉDITO
        self.lbl_limite_cliente = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.txt_nuevo_limite = ft.TextField(
            label="Nuevo Límite de Crédito ($) *",
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.modal_limite = DialogoModalBase(
            page=self.pagina,
            titulo="Editar Límite de Crédito",
            icono=ft.Icons.CREDIT_CARD,
            color_icono=ft.Colors.BLUE_700,
            ancho=360,
            texto_confirmar="Guardar Límite",
            icono_confirmar=ft.Icons.SAVE,
            color_confirmar=ft.Colors.BLUE_700,
            al_confirmar=self._guardar_nuevo_limite,
        )
        self.modal_limite.set_contenido([
            self.lbl_limite_cliente,
            self.txt_nuevo_limite,
        ])

    def _construir_ui(self):
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Cuentas por Cobrar y Control de Envases",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Row([self.lbl_total_por_cobrar, self.lbl_total_envases_calle], spacing=12),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
                ft.Divider(),
                ft.Row([self.txt_filtro]),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [self.tabla_clientes],
                                scroll=ft.ScrollMode.AUTO,
                                expand=True,
                            )
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    padding=10,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

    def cargar_clientes(self):
        self.tabla_clientes.rows.clear()
        termino = self.txt_filtro.value.strip().lower() if self.txt_filtro.value else ""

        clientes = obtener_clientes_con_deuda_y_envases()
        total_deuda = sum(c["saldo_pendiente"] for c in clientes)
        total_envases = sum(c["envases_pendientes"] for c in clientes)

        self.lbl_total_por_cobrar.value = f"Total Fiado: ${total_deuda:.2f}"
        self.lbl_total_envases_calle.value = f"Envases Fuera: {total_envases} pzas"

        for cl in clientes:
            nom = cl["nombre"] or ""
            tel = cl["telefono"] or "—"

            if termino and (termino not in nom.lower() and termino not in tel.lower()):
                continue

            deuda = float(cl["saldo_pendiente"] or 0.0)
            tiene_deuda = deuda > 0
            env_pend = int(cl["envases_pendientes"] or 0)
            tiene_env = env_pend > 0
            limite = float(cl["limite_credito"] or 0.0)
            garantia_ret = float(cl["importe_envases_retenido"] or 0.0)

            btn_abonar = ft.Button(
                "Abonar",
                icon=ft.Icons.PAYMENTS_OUTLINED,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                disabled=not tiene_deuda,
                on_click=lambda e, c=cl, d=deuda: self.abrir_modal_abono(c["id_cliente"], c["nombre"], d),
            )

            btn_dev_envases = ft.Button(
                "Devolver Envase",
                icon=ft.Icons.WINE_BAR,
                style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_800, color=ft.Colors.WHITE),
                disabled=not tiene_env,
                on_click=lambda e, c=cl, ep=env_pend, g=garantia_ret: self.abrir_modal_devolucion(
                    c["id_cliente"], c["nombre"], ep, g
                ),
            )

            btn_edit_lim = ft.IconButton(
                icon=ft.Icons.EDIT_NOTE,
                icon_color=ft.Colors.BLUE_700,
                tooltip="Ajustar Límite de Crédito",
                on_click=lambda e, c=cl, l=limite: self.abrir_modal_limite(c["id_cliente"], c["nombre"], l),
            )

            self.tabla_clientes.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{cl['id_cliente']}")),
                        ft.DataCell(ft.Text(nom, weight=ft.FontWeight.BOLD, size=13)),
                        ft.DataCell(ft.Text(tel)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(
                                    f"${deuda:.2f}",
                                    weight=ft.FontWeight.BOLD if tiene_deuda else ft.FontWeight.NORMAL,
                                    color=ft.Colors.RED_800 if tiene_deuda else ft.Colors.BLACK,
                                ),
                                bgcolor=ft.Colors.RED_50 if tiene_deuda else None,
                                padding=4,
                                border_radius=4,
                            )
                        ),
                        ft.DataCell(ft.Text(f"${limite:.2f}")),
                        ft.DataCell(
                            ft.Text(
                                f"{env_pend} pzas",
                                weight=ft.FontWeight.BOLD if tiene_env else ft.FontWeight.NORMAL,
                                color=ft.Colors.ORANGE_900 if tiene_env else ft.Colors.BLACK,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${garantia_ret:.2f}",
                                weight=ft.FontWeight.BOLD if tiene_env else ft.FontWeight.NORMAL,
                            )
                        ),
                        ft.DataCell(ft.Row([btn_abonar, btn_dev_envases, btn_edit_lim], spacing=4)),
                    ]
                )
            )
        self.pagina.update()

    def abrir_modal_abono(self, id_cliente: int, nombre: str, deuda: float):
        self.id_cliente_activo = id_cliente
        self.deuda_actual = deuda
        self.lbl_abono_cliente.value = f"👤 Cliente: {nombre} (#{id_cliente})"
        self.lbl_abono_deuda.value = f"Deuda Pendiente: ${deuda:.2f}"
        self.txt_monto_abono.value = str(deuda)
        self.modal_abono.abrir()

    def _guardar_abono(self, e):
        try:
            monto = float(self.txt_monto_abono.value or "0")
            if monto <= 0:
                self.mostrar_mensaje("El monto debe ser mayor a 0", ft.Colors.RED_600)
                return
            if monto > self.deuda_actual:
                self.mostrar_mensaje("El abono no puede superar la deuda actual", ft.Colors.ORANGE_800)
                return
        except ValueError:
            self.mostrar_mensaje("Ingresa un monto numérico válido", ft.Colors.RED_600)
            return

        nuevo_saldo = registrar_abono_credito(self.id_cliente_activo, self.id_empleado_activo, monto)
        self.modal_abono.cerrar()
        self.cargar_clientes()
        self.mostrar_mensaje(
            f" Abono de ${monto:.2f} registrado. Saldo restante: ${nuevo_saldo:.2f}",
            ft.Colors.GREEN_700,
        )

    def abrir_modal_devolucion(self, id_cliente: int, nombre: str, cant_envases: int, garantia: float):
        self.id_cliente_activo = id_cliente
        self.total_envases_pendientes = cant_envases
        self.lbl_dev_cliente.value = f"👤 {nombre} (#{id_cliente})"
        self.lbl_dev_resumen.value = f"Envases por entregar: {cant_envases} pzas (Garantía: ${garantia:.2f})"
        self.txt_cant_envases.value = str(cant_envases)
        self.modal_devolucion.abrir()

    def _guardar_devolucion_envases(self, e):
        try:
            cant = int(self.txt_cant_envases.value or "0")
            if cant <= 0:
                self.mostrar_mensaje("La cantidad debe ser mayor a 0", ft.Colors.RED_600)
                return
            if cant > self.total_envases_pendientes:
                self.mostrar_mensaje(
                    f"No puedes devolver más de los {self.total_envases_pendientes} envases pendientes",
                    ft.Colors.RED_600,
                )
                return
        except ValueError:
            self.mostrar_mensaje("Ingresa un número entero válido", ft.Colors.RED_600)
            return

        metodo = self.rg_destino_reembolso.value
        monto_reembolsado = procesar_devolucion_envases_cliente(
            id_cliente=self.id_cliente_activo,
            id_empleado=self.id_empleado_activo,
            cant_a_devolver=cant,
            metodo_devolucion=metodo,
        )

        self.modal_devolucion.cerrar()
        self.cargar_clientes()

        if metodo == "Abonar a Deuda":
            self.mostrar_mensaje(
                f" {cant} envase(s) devueltos. Se abonaron ${monto_reembolsado:.2f} a su deuda fiada.",
                ft.Colors.GREEN_700,
            )
        else:
            self.mostrar_mensaje(
                f" {cant} envase(s) devueltos. Entrega ${monto_reembolsado:.2f} en efectivo de caja.",
                ft.Colors.GREEN_700,
            )

    def abrir_modal_limite(self, id_cliente: int, nombre: str, limite_actual: float):
        self.id_cliente_activo = id_cliente
        self.lbl_limite_cliente.value = f"👤 {nombre} (#{id_cliente})"
        self.txt_nuevo_limite.value = str(limite_actual)
        self.modal_limite.abrir()

    def _guardar_nuevo_limite(self, e):
        try:
            lim = float(self.txt_nuevo_limite.value or "0")
            if lim < 0:
                self.mostrar_mensaje("El límite debe ser mayor o igual a 0", ft.Colors.RED_600)
                return
        except ValueError:
            self.mostrar_mensaje("Ingresa un número válido", ft.Colors.RED_600)
            return

        actualizar_limite_credito_cliente(self.id_cliente_activo, lim)
        self.modal_limite.cerrar()
        self.cargar_clientes()
        self.mostrar_mensaje(f"Límite de crédito actualizado a ${lim:.2f}", ft.Colors.GREEN_700)