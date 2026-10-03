import flet as ft

from controllers.auth_controller import AuthController
from database.esquema import inicializar_base_datos
from views.clientes_view import ClientesView
from views.compras_view import ComprasView
from views.empleados_view import EmpleadosView
from views.inventario_view import InventarioView
from views.pos_view import PosView
from views.reportes_view import ReportesView
from database.backup_service import generar_respaldo_automatico
from views.configuracion_view import ConfiguracionView
from database.turnos_db import (
    obtener_turno_activo,
    abrir_nuevo_turno,
    cerrar_turno_ciego,
)
from components.dialogo_base import DialogoModalBase
def main(page: ft.Page):
    page.title = "Sistema de Tienda - Punto de Venta"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.maximized = True

    # Inicialización de esquema e índices
    inicializar_base_datos()
    generar_respaldo_automatico(sufijo="inicio")

    auth = AuthController()

    def mostrar_mensaje(texto: str, color_fondo: str = ft.Colors.BLUE_700):
        # Cerrar o remover SnackBar previo que siga activo en el overlay
        for control in list(page.overlay):
            if isinstance(control, ft.SnackBar):
                control.open = False
                page.overlay.remove(control)
        page.update()

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
        generar_respaldo_automatico(sufijo=f"cierre_{auth.usuario or 'usuario'}")
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

        # ---------------------------------------------------------
        # MODALES Y LÓGICA DE CONTROL DE TURNOS (CORTE CIEGO)
        # ---------------------------------------------------------
        
        txt_fondo_inicial = ft.TextField(
            label="Monto de Fondo Inicial ($)",
            hint_text="Ej. 300.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.ATTACH_MONEY,
            autofocus=True,
            width=300,
        )

        def confirmar_apertura_turno():
            try:
                texto_monto = (
                    txt_fondo_inicial.value.strip()
                    if txt_fondo_inicial.value
                    else "0"
                )
                monto = float(texto_monto)
                if monto < 0:
                    mostrar_mensaje(
                        "El fondo no puede ser negativo", ft.Colors.RED_600
                    )
                    return
                abrir_nuevo_turno(auth.id_empleado, monto)
                modal_apertura.cerrar()
                txt_fondo_inicial.value = ""
                actualizar_estado_turno_ui()
                mostrar_mensaje(
                    f"✅ Turno abierto con fondo de ${monto:.2f}",
                    ft.Colors.GREEN_700,
                )
            except ValueError:
                mostrar_mensaje(
                    "Ingresa un monto numérico válido", ft.Colors.RED_600
                )
            except Exception as err:
                mostrar_mensaje(
                    f"Error al abrir turno: {err}", ft.Colors.RED_600
                )

        modal_apertura = DialogoModalBase(
            page=page,
            titulo="Apertura de Turno de Caja",
            icono=ft.Icons.LOCK_OPEN,
            ancho=360,
            texto_confirmar="Iniciar Turno",
            icono_confirmar=ft.Icons.CHECK,
            al_confirmar=lambda e: confirmar_apertura_turno(),
        )
        modal_apertura.set_contenido([
            ft.Text(
                "Indica el efectivo disponible en caja para dar cambio:",
                size=13,
                color=ft.Colors.GREY_700,
            ),
            txt_fondo_inicial,
        ])

        # 2. Modal Corte Ciego (Fin de Turno)
        txt_dinero_contado = ft.TextField(
            label="Efectivo Físico en Cajón ($)",
            hint_text="0.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.ATTACH_MONEY,
            autofocus=True,
            width=300,
        )
        txt_notas_corte = ft.TextField(
            label="Notas / Observaciones (Opcional)",
            multiline=True,
            max_lines=2,
            width=300,
        )

        def confirmar_corte_ciego():
            try:
                texto_monto = (
                    txt_dinero_contado.value.strip()
                    if txt_dinero_contado.value
                    else ""
                )
                if not texto_monto:
                    mostrar_mensaje(
                        "Debes ingresar el total contado en caja",
                        ft.Colors.RED_600,
                    )
                    return

                declarado = float(texto_monto)
                if declarado < 0:
                    mostrar_mensaje(
                        "El monto declarado no puede ser negativo",
                        ft.Colors.RED_600,
                    )
                    return

                turno = obtener_turno_activo(auth.id_empleado)
                if not turno:
                    mostrar_mensaje(
                        "No hay un turno activo para cerrar", ft.Colors.RED_600
                    )
                    modal_corte.cerrar()
                    return

                res = cerrar_turno_ciego(
                    id_turno=turno["id_turno"],
                    monto_declarado=declarado,
                    observaciones=txt_notas_corte.value.strip(),
                )

                modal_corte.cerrar()
                txt_dinero_contado.value = ""
                txt_notas_corte.value = ""
                actualizar_estado_turno_ui()

                if auth.es_admin:
                    # El administrador audita en vivo
                    dif = res["diferencia"]
                    txt_dif = (
                        f"+${dif:.2f} (Sobrante)"
                        if dif > 0
                        else (
                            f"-${abs(dif):.2f} (Faltante)"
                            if dif < 0
                            else "Exacto ($0.00)"
                        )
                    )
                    mostrar_mensaje(
                        f"Turno #{res['id_turno']} cerrado. Diferencia: {txt_dif}",
                        ft.Colors.BLUE_800,
                    )
                else:
                    # Corte ciego estricto: el cajero no ve el sobrante o faltante
                    mostrar_mensaje(
                        f"✅ Turno #{res['id_turno']} entregado y cerrado con éxito",
                        ft.Colors.GREEN_700,
                    )

            except ValueError:
                mostrar_mensaje(
                    "Ingresa un valor numérico válido", ft.Colors.RED_600
                )
            except Exception as err:
                mostrar_mensaje(
                    f"Error al cerrar turno: {err}", ft.Colors.RED_600
                )

        modal_corte = DialogoModalBase(
            page=page,
            titulo="Corte de Turno - Entrega de Caja",
            icono=ft.Icons.POINT_OF_SALE,
            ancho=380,
            texto_confirmar="Finalizar y Entregar",
            icono_confirmar=ft.Icons.LOCK,
            al_confirmar=lambda e: confirmar_corte_ciego(),
        )
        modal_corte.set_contenido([
            ft.Text(
                "Cuenta todo el dinero en efectivo que tienes físicamente en el cajón y digita el total:",
                size=13,
                color=ft.Colors.GREY_700,
            ),
            txt_dinero_contado,
            txt_notas_corte,
        ])

        # 3. Botón dinámico en barra superior
        btn_turno = ft.Button(
            "Turno de Caja",
            icon=ft.Icons.LOCK_OPEN,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE
            ),
        )

        def actualizar_estado_turno_ui():
            turno = obtener_turno_activo(auth.id_empleado)
            if turno:
                btn_turno.text = f"Cerrar Turno (#{turno['id_turno']})"
                btn_turno.icon = ft.Icons.LOCK
                btn_turno.style.bgcolor = ft.Colors.ORANGE_800
                btn_turno.on_click = lambda e: modal_corte.abrir()
            else:
                btn_turno.text = "Abrir Turno"
                btn_turno.icon = ft.Icons.LOCK_OPEN
                btn_turno.style.bgcolor = ft.Colors.GREEN_700
                btn_turno.on_click = lambda e: modal_apertura.abrir()
            page.update()

        # ---------------------------------------------------------
        # DEFINICIÓN DE VISTAS POR ROL
        # ---------------------------------------------------------
        if auth.es_admin:
            destinos = [
                ft.NavigationRailDestination(
                    icon=ft.Icons.POINT_OF_SALE, label="Ventas (POS)"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.INVENTORY, label="Inventario"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LOCAL_SHIPPING, label="Compras / Prov."
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                    label="Créditos / Envases",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ASSESSMENT, label="Reportes"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.GROUP, label="Usuarios"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS, label="Configuración"
                ),
            ]
        else:
            destinos = [
                ft.NavigationRailDestination(
                    icon=ft.Icons.POINT_OF_SALE, label="Ventas (POS)"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SEARCH, label="Consultar Precios"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LOCAL_SHIPPING, label="Recepción Compras"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                    label="Créditos / Envases",
                ),
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
                    page,
                    mostrar_mensaje,
                    auth.id_empleado,
                    es_admin=auth.es_admin,
                )
            elif indice == 4 and auth.es_admin:
                page.on_keyboard_event = None
                contenedor_principal.content = ReportesView(
                    page, mostrar_mensaje
                )
            elif indice == 5 and auth.es_admin:
                page.on_keyboard_event = None
                contenedor_principal.content = EmpleadosView(
                    page, mostrar_mensaje
                )
            elif indice == 6 and auth.es_admin:
                page.on_keyboard_event = None
                contenedor_principal.content = ConfiguracionView(
                    page, mostrar_mensaje
                )

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
                        btn_turno,  # <-- Botón dinámico de Turno / Corte
                        ft.Button(
                            "Salida de Caja",
                            icon=ft.Icons.MONEY_OFF,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE
                            ),
                            on_click=lambda e: vista_pos.abrir_modal_salida_caja(),
                        ),
                        ft.Chip(
                            label=ft.Text(
                                f"{auth.nombre_completo} ({auth.puesto})"
                            ),
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
        actualizar_estado_turno_ui()
    
    
    
    
    page.add(vista_login)
    page.update()


if __name__ == "__main__":
    ft.run(main)