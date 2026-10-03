from typing import Callable
import flet as ft
from database.configuracion_db import (
    obtener_configuraciones,
    guardar_configuracion,
)


class ConfiguracionView(ft.Container):
    """Vista modular para encender o apagar módulos y personalizar datos del negocio."""

    def __init__(
        self, page: ft.Page, mostrar_mensaje: Callable[[str, str], None]
    ):
        super().__init__(expand=True, padding=20)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje

        self._crear_controles()
        self._construir_ui()
        self._cargar_valores()

    def _crear_controles(self):
        # 1. Identidad de negocio para tickets
        self.txt_nombre = ft.TextField(
            label="Nombre del Negocio (Aparece en Ticket)", expand=True
        )
        self.txt_direccion = ft.TextField(
            label="Dirección / Localidad", expand=True
        )
        self.txt_telefono = ft.TextField(
            label="Teléfono de Contacto", width=250
        )

        # 2. Switches de módulos opcionales
        self.sw_puntos = ft.Switch(
            label="Módulo de Monedero / Puntos de Lealtad", value=True
        )
        self.sw_envases = ft.Switch(
            label="Módulo de Envases Retornables y Cascos", value=True
        )
        self.sw_tickets_auto = ft.Switch(
            label="Mostrar Ticket Automáticamente al Cobrar", value=False
        )

        self.dd_ancho_ticket = ft.Dropdown(
            label="Ancho de Papel Térmico",
            width=260,
            options=[
                ft.dropdown.Option("32", "58 mm (32 columnas)"),
                ft.dropdown.Option("42", "80 mm Estándar (42 columnas)"),
                ft.dropdown.Option("48", "80 mm Amplio (48 columnas)"),
            ],
            value="32",
        )

    def _construir_ui(self):
        btn_guardar = ft.Button(
            "Guardar Configuración",
            icon=ft.Icons.SAVE,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE
            ),
            height=48,
            on_click=lambda e: self._guardar_ajustes(),
        )

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.SETTINGS_OUTLINED,
                            size=28,
                            color=ft.Colors.BLUE_800,
                        ),
                        ft.Text(
                            "Configuración del Sistema",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Text(
                    "Personaliza los datos impresos en comprobantes y activa o desactiva módulos según las necesidades del negocio.",
                    color=ft.Colors.GREY_600,
                ),
                ft.Divider(),
                ft.Text(
                    "1. Datos del Establecimiento",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Row([self.txt_nombre]),
                ft.Row([self.txt_direccion, self.txt_telefono]),
                ft.Divider(),
                ft.Text(
                    "2. Módulos y Comprobantes",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Row([self.sw_puntos]),
                ft.Row([self.sw_envases]),
                ft.Row([self.sw_tickets_auto]),
                ft.Row([self.dd_ancho_ticket]),
                ft.Divider(height=20),
                btn_guardar,
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        )

    def _cargar_valores(self):
        c = obtener_configuraciones()
        self.txt_nombre.value = c.get("nombre_tienda", "")
        self.txt_direccion.value = c.get("direccion_tienda", "")
        self.txt_telefono.value = c.get("telefono_tienda", "")

        self.sw_puntos.value = c.get("modulo_puntos", "true") == "true"
        self.sw_envases.value = c.get("modulo_envases", "true") == "true"
        self.sw_tickets_auto.value = (
            c.get("imprimir_tickets_auto", "false") == "true"
        )
        self.dd_ancho_ticket.value = c.get("ancho_ticket", "32")
        self.pagina.update()

    def _guardar_ajustes(self):
        guardar_configuracion("nombre_tienda", self.txt_nombre.value.strip())
        guardar_configuracion(
            "direccion_tienda", self.txt_direccion.value.strip()
        )
        guardar_configuracion(
            "telefono_tienda", self.txt_telefono.value.strip()
        )

        guardar_configuracion(
            "modulo_puntos", "true" if self.sw_puntos.value else "false"
        )
        guardar_configuracion(
            "modulo_envases", "true" if self.sw_envases.value else "false"
        )
        guardar_configuracion(
            "imprimir_tickets_auto",
            "true" if self.sw_tickets_auto.value else "false",
        )
        guardar_configuracion("ancho_ticket", self.dd_ancho_ticket.value)

        self.mostrar_mensaje(
            "✅ Ajustes actualizados con éxito", ft.Colors.GREEN_700
        )