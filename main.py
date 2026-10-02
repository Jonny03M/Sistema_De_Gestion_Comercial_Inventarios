import flet as ft

from controllers.auth_controller import AuthController
from database.esquema import inicializar_base_datos
from views.clientes_view import ClientesView
from views.compras_view import ComprasView
from views.empleados_view import EmpleadosView
from views.inventario_view import InventarioView
from views.pos_view import PosView
from views.reportes_view import ReportesView


def main(page: ft.Page):
    page.title = "Sistema de Tienda - Punto de Venta"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.maximized = True

    # Inicialización de esquema e índices
    inicializar_base_datos()

    auth = AuthController()

    def mostrar_mensaje(texto: str, color_fondo: str):
        snack = ft.SnackBar(
            content=ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            bgcolor=color_fondo,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=2500,
            show_close_icon=True,
            close_icon_color=ft.Colors.WHITE,
        )
        try:
            page.open(snack)
        except Exception:
            if snack not in page.overlay:
                page.overlay.append(snack)
            snack.open = True
            page.update()

    # ==========================================
    # PANTALLA: LOGIN
    # ==========================================
    txt_usuario = ft.TextField(
        label="Usuario", icon=ft.Icons.PERSON, autofocus=True, width=320
    )
    txt_password = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        icon=ft.Icons.LOCK,
        width=320,
    )

    def ejecutar_login(e=None):
        if auth.iniciar_sesion(txt_usuario.value or "", txt_password.value or ""):
            txt_usuario.value = ""
            txt_password.value = ""
            cargar_interfaz_principal()
        else:
            mostrar_mensaje("❌ Usuario o contraseña incorrectos", ft.Colors.RED_600)
            txt_password.value = ""
            txt_usuario.autofocus = True
            page.update()

    txt_usuario.on_submit = lambda e: (setattr(txt_password, "autofocus", True), page.update())
    txt_password.on_submit = ejecutar_login

    vista_login = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.STOREFRONT, size=80, color=ft.Colors.BLUE_700),
                ft.Text("Control de Inventario y Ventas", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Ingresa tus credenciales para continuar", color=ft.Colors.GREY_600),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                txt_usuario,
                txt_password,
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Button(
                    "Ingresar al Sistema",
                    icon=ft.Icons.LOGIN,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                    width=320,
                    height=50,
                    on_click=ejecutar_login,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )

    # ==========================================
    # PANTALLA: PANEL PRINCIPAL
    # ==========================================
    def cerrar_sesion(e=None):
        page.on_keyboard_event = None
        auth.cerrar_sesion()
        page.controls.clear()
        page.add(vista_login)
        page.update()

    def cargar_interfaz_principal():
        page.controls.clear()

        vista_pos = PosView(
            page=page,
            mostrar_mensaje=mostrar_mensaje,
            id_empleado_activo=auth.id_empleado,
        )

        contenedor_principal = ft.Container(content=vista_pos, expand=True)

        # Definir vistas permitidas según el rol
        if auth.es_admin:
            destinos = [
                ft.NavigationRailDestination(icon=ft.Icons.POINT_OF_SALE, label="Ventas (POS)"),
                ft.NavigationRailDestination(icon=ft.Icons.INVENTORY, label="Inventario"),
                ft.NavigationRailDestination(icon=ft.Icons.LOCAL_SHIPPING, label="Compras / Prov."),
                ft.NavigationRailDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, label="Créditos / Envases"),
                ft.NavigationRailDestination(icon=ft.Icons.ASSESSMENT, label="Reportes"),
                ft.NavigationRailDestination(icon=ft.Icons.GROUP, label="Usuarios"),
            ]
        else:
            destinos = [
                ft.NavigationRailDestination(icon=ft.Icons.POINT_OF_SALE, label="Ventas (POS)"),
                ft.NavigationRailDestination(icon=ft.Icons.SEARCH, label="Consultar Precios"),
                ft.NavigationRailDestination(icon=ft.Icons.LOCAL_SHIPPING, label="Recepción Compras"),
                ft.NavigationRailDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, label="Créditos / Envases"),
            ]

        def cambiar_pestana(e):
            indice = e.control.selected_index

            if indice == 0:
                contenedor_principal.content = vista_pos
                vista_pos._configurar_atajos_teclado()
            elif indice == 1:
                page.on_keyboard_event = None
                contenedor_principal.content = InventarioView(
                    page, mostrar_mensaje, es_admin=auth.es_admin
                )
            elif indice == 2:
                page.on_keyboard_event = None
                contenedor_principal.content = ComprasView(
                    page, mostrar_mensaje, es_admin=auth.es_admin
                )
            elif indice == 3:
                page.on_keyboard_event = None
                contenedor_principal.content = ClientesView(
                    page, mostrar_mensaje, auth.id_empleado, es_admin=auth.es_admin
                )
            elif indice == 4 and auth.es_admin:
                page.on_keyboard_event = None
                contenedor_principal.content = ReportesView(page, mostrar_mensaje)
            elif indice == 5 and auth.es_admin:
                page.on_keyboard_event = None
                contenedor_principal.content = EmpleadosView(page, mostrar_mensaje)

            page.update()

        rail_navegacion = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            destinations=destinos,
            min_width=105,
            on_change=cambiar_pestana,
        )

        barra_superior = ft.Container(
            content=ft.Row(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.STORE, color=ft.Colors.WHITE),
                        ft.Text(
                            "Abarrotes - Punto de Venta",
                            color=ft.Colors.WHITE,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]),
                    ft.Row([
                        ft.Button(
                            "Salida de Caja",
                            icon=ft.Icons.MONEY_OFF,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                            on_click=lambda e: vista_pos.abrir_modal_salida_caja(),
                        ),
                        ft.Chip(
                            label=ft.Text(f"{auth.nombre_completo} ({auth.puesto})"),
                            leading=ft.Icon(ft.Icons.ACCOUNT_CIRCLE),
                            color=ft.Colors.WHITE,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            icon_color=ft.Colors.WHITE,
                            tooltip="Cerrar Sesión",
                            on_click=cerrar_sesion,
                        ),
                    ]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=ft.Colors.BLUE_800,
            padding=10,
        )

        cuerpo = ft.Row(
            [
                rail_navegacion,
                ft.VerticalDivider(width=1),
                contenedor_principal,
            ],
            expand=True,
        )

        page.add(ft.Column([barra_superior, cuerpo], expand=True))
        page.update()
        
    page.add(vista_login)
    page.update()


if __name__ == "__main__":
    ft.run(main)