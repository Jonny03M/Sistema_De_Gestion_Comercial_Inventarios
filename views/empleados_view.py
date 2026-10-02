from typing import Callable, Optional
import flet as ft

from components.dialogo_base import DialogoModalBase
from database.usuarios_db import (
    actualizar_empleado,
    cambiar_estado_empleado,
    crear_empleado,
    obtener_todos_los_empleados,
)


class EmpleadosView(ft.Container):
    """Vista modular para la administración de empleados y permisos de acceso."""

    def __init__(self, page: ft.Page, mostrar_mensaje: Callable[[str, str], None]):
        super().__init__(expand=True, padding=10)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje
        self.id_empleado_editar: Optional[int] = None

        self._crear_tabla()
        self._crear_modal()
        self._construir_ui()
        self.cargar_empleados()

    def _crear_tabla(self):
        self.tabla_empleados = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nombre Completo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Usuario", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Puesto / Rol", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Teléfono", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True,
            horizontal_margin=15,
        )

    def _crear_modal(self):
        self.txt_nombre = ft.TextField(label="Nombre(s) *", expand=True)
        self.txt_apellido = ft.TextField(label="Apellidos *", expand=True)
        self.txt_usuario = ft.TextField(label="Nombre de Usuario *", expand=True)
        self.txt_password = ft.TextField(
            label="Contraseña *",
            password=True,
            can_reveal_password=True,
            expand=True,
        )
        self.txt_telefono = ft.TextField(label="Teléfono (Opcional)", expand=True)
        self.dd_puesto = ft.Dropdown(
            label="Rol / Puesto",
            expand=True,
            options=[
                ft.dropdown.Option("Cajero", "Cajero"),
                ft.dropdown.Option("Administrador", "Administrador"),
            ],
            value="Cajero",
        )

        self.modal_empleado = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Empleado",
            icono=ft.Icons.PERSON,
            ancho=500,
            texto_confirmar="Guardar",
            color_confirmar=ft.Colors.BLUE_700,
            al_confirmar=self._guardar_empleado,
        )
        self.modal_empleado.set_contenido([
            ft.Row([self.txt_nombre, self.txt_apellido]),
            ft.Row([self.txt_usuario, self.txt_password]),
            ft.Row([self.dd_puesto, self.txt_telefono]),
        ])

    def _construir_ui(self):
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Gestión de Empleados y Accesos",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Button(
                            "Nuevo Empleado",
                            icon=ft.Icons.PERSON_ADD,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREEN_700,
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda e: self.abrir_modal_nuevo(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [self.tabla_empleados],
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
            expand=True,
            spacing=10,
        )

    def cargar_empleados(self):
        self.tabla_empleados.rows.clear()
        empleados = obtener_todos_los_empleados()

        for emp in empleados:
            es_activo = int(emp["activo"]) == 1
            es_admin_principal = emp["id_empleado"] == 1

            btn_editar = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_600,
                tooltip="Editar empleado",
                data=emp,
                on_click=lambda e: self.abrir_modal_editar(e.control.data),
            )

            btn_estado = ft.IconButton(
                icon=(
                    ft.Icons.PERSON_OFF_OUTLINED
                    if es_activo
                    else ft.Icons.CHECK_CIRCLE_OUTLINE
                ),
                icon_color=(
                    ft.Colors.RED_500 if es_activo else ft.Colors.GREEN_600
                ),
                tooltip="Desactivar acceso" if es_activo else "Reactivar acceso",
                data=emp,
                disabled=es_admin_principal,
                on_click=lambda e: self._alternar_estado_empleado(e.control.data),
            )

            badge_puesto = ft.Container(
                content=ft.Text(
                    emp["puesto"],
                    size=12,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_500,
                ),
                bgcolor=(
                    ft.Colors.INDIGO_700
                    if emp["puesto"] == "Administrador"
                    else ft.Colors.BLUE_GREY_700
                ),
                padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                border_radius=6,
            )

            badge_estado = ft.Container(
                content=ft.Text(
                    "Activo" if es_activo else "Inactivo",
                    size=12,
                    color=ft.Colors.WHITE,
                ),
                bgcolor=(
                    ft.Colors.GREEN_700 if es_activo else ft.Colors.GREY_600
                ),
                padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                border_radius=10,
            )

            self.tabla_empleados.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{emp['id_empleado']}")),
                        ft.DataCell(
                            ft.Text(
                                f"{emp['nombre']} {emp['apellido']}",
                                weight=ft.FontWeight.BOLD,
                                color=(
                                    ft.Colors.BLACK
                                    if es_activo
                                    else ft.Colors.GREY_500
                                ),
                            )
                        ),
                        ft.DataCell(ft.Text(emp["usuario"])),
                        ft.DataCell(badge_puesto),
                        ft.DataCell(ft.Text(emp["telefono"] or "—")),
                        ft.DataCell(badge_estado),
                        ft.DataCell(ft.Row([btn_editar, btn_estado], spacing=0)),
                    ]
                )
            )
        self.pagina.update()

    def _alternar_estado_empleado(self, emp_data):
        if emp_data["id_empleado"] == 1:
            self.mostrar_mensaje(
                "⚠️ No se puede desactivar al Administrador Principal",
                ft.Colors.ORANGE_800,
            )
            return

        st_actual = int(emp_data["activo"])
        nuevo_st = 0 if st_actual == 1 else 1
        cambiar_estado_empleado(emp_data["id_empleado"], nuevo_st)
        self.mostrar_mensaje(
            "🚫 Empleado desactivado" if nuevo_st == 0 else "✅ Empleado reactivado",
            ft.Colors.ORANGE_800 if nuevo_st == 0 else ft.Colors.GREEN_700,
        )
        self.cargar_empleados()

    def abrir_modal_nuevo(self):
        self.id_empleado_editar = None
        self.modal_empleado.lbl_titulo.value = "Nuevo Empleado"
        self.txt_nombre.value = ""
        self.txt_apellido.value = ""
        self.txt_usuario.value = ""
        self.txt_password.value = ""
        self.txt_password.hint_text = ""
        self.txt_telefono.value = ""
        self.dd_puesto.value = "Cajero"
        self.dd_puesto.disabled = False
        self.modal_empleado.abrir()

    def abrir_modal_editar(self, emp):
        self.id_empleado_editar = emp["id_empleado"]
        self.modal_empleado.lbl_titulo.value = f"Editar: {emp['usuario']}"
        self.txt_nombre.value = emp["nombre"]
        self.txt_apellido.value = emp["apellido"]
        self.txt_usuario.value = emp["usuario"]
        self.txt_password.value = ""
        self.txt_password.hint_text = "Dejar en blanco para conservar actual"
        self.txt_telefono.value = emp["telefono"] or ""
        self.dd_puesto.value = emp["puesto"]
        self.dd_puesto.disabled = emp["id_empleado"] == 1

        self.modal_empleado.abrir()

    def _guardar_empleado(self, e):
        nom = self.txt_nombre.value.strip() if self.txt_nombre.value else ""
        ape = self.txt_apellido.value.strip() if self.txt_apellido.value else ""
        usu = self.txt_usuario.value.strip() if self.txt_usuario.value else ""
        pwd = self.txt_password.value.strip() if self.txt_password.value else ""
        tel = self.txt_telefono.value.strip() if self.txt_telefono.value else ""
        rol = self.dd_puesto.value or "Cajero"

        if not nom or not ape or not usu:
            self.mostrar_mensaje(
                "Nombre, apellido y usuario son obligatorios", ft.Colors.RED_600
            )
            return

        if self.id_empleado_editar is None and not pwd:
            self.mostrar_mensaje(
                "Debes asignar una contraseña al nuevo empleado",
                ft.Colors.RED_600,
            )
            return

        try:
            if self.id_empleado_editar is None:
                crear_empleado(
                    nombre=nom,
                    apellido=ape,
                    usuario=usu,
                    password_texto=pwd,
                    puesto=rol,
                    telefono=tel,
                )
                self.mostrar_mensaje(
                    f"✅ Empleado '{usu}' registrado", ft.Colors.GREEN_700
                )
            else:
                actualizar_empleado(
                    id_empleado=self.id_empleado_editar,
                    nombre=nom,
                    apellido=ape,
                    usuario=usu,
                    password_texto=pwd if pwd else None,
                    puesto=rol,
                    telefono=tel,
                )
                self.mostrar_mensaje(
                    "Datos del empleado actualizados", ft.Colors.GREEN_700
                )

            self.modal_empleado.cerrar()
            self.cargar_empleados()
        except Exception as err:
            self.mostrar_mensaje(f" Error: {err}", ft.Colors.RED_600)