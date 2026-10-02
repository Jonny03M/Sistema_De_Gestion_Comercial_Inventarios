from datetime import datetime, timedelta
from typing import Callable
import flet as ft


class SelectorRangoFechas(ft.Row):
    """Componente reutilizable de filtrado por fechas con botones rápidos
    (Hoy, Semana, Mes) y selector de rango mediante DatePickers.
    """

    def __init__(self, page: ft.Page, al_cambiar_rango: Callable[[str, str, str], None]):
        super().__init__()
        self.page = page
        self.al_cambiar_rango = al_cambiar_rango
        self.spacing = 6
        self.wrap = True

        hoy_str = datetime.now().strftime("%Y-%m-%d")
        self.fecha_inicio = hoy_str
        self.fecha_fin = hoy_str
        self.descripcion = "Periodo: Hoy"

        self._f_ini_temp = hoy_str
        self._f_fin_temp = hoy_str

        self._crear_pickers_y_dialogos()
        self._construir_ui()

    def _crear_pickers_y_dialogos(self):
        # Picker un solo día
        self.picker_un_dia = ft.DatePicker(
            on_change=self._al_seleccionar_un_dia,
            first_date=datetime(2023, 1, 1),
            last_date=datetime(2035, 12, 31),
        )

        # Pickers para modal de rango
        self.lbl_desde = ft.Text(f"📅 Desde: {self.fecha_inicio}", size=14, weight=ft.FontWeight.BOLD)
        self.lbl_hasta = ft.Text(f"📅 Hasta: {self.fecha_fin}", size=14, weight=ft.FontWeight.BOLD)

        self.picker_inicio = ft.DatePicker(
            on_change=self._al_cambiar_picker_inicio,
            first_date=datetime(2023, 1, 1),
            last_date=datetime(2035, 12, 31),
        )
        self.picker_fin = ft.DatePicker(
            on_change=self._al_cambiar_picker_fin,
            first_date=datetime(2023, 1, 1),
            last_date=datetime(2035, 12, 31),
        )

        # Modal Rango
        self.dialogo_rango = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.DATE_RANGE, color=ft.Colors.BLUE_700),
                ft.Text("Seleccionar Periodo"),
            ]),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Selecciona las fechas de inicio y fin:", size=12, color=ft.Colors.GREY_700),
                        ft.Divider(height=1),
                        ft.Container(
                            content=ft.Row(
                                [
                                    self.lbl_desde,
                                    ft.Button(
                                        "Elegir Inicio",
                                        icon=ft.Icons.CALENDAR_MONTH,
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                                        on_click=lambda e: self._abrir_picker(self.picker_inicio),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            bgcolor=ft.Colors.GREY_100,
                            padding=10,
                            border_radius=8,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    self.lbl_hasta,
                                    ft.Button(
                                        "Elegir Fin",
                                        icon=ft.Icons.CALENDAR_MONTH,
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                                        on_click=lambda e: self._abrir_picker(self.picker_fin),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            bgcolor=ft.Colors.GREY_100,
                            padding=10,
                            border_radius=8,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=450,
            ),
            actions=[
                ft.Button(
                    "Cancelar",
                    style=ft.ButtonStyle(color=ft.Colors.GREY_700),
                    on_click=lambda e: self._cerrar_dialogo_rango(),
                ),
                ft.Button(
                    "Consultar",
                    icon=ft.Icons.CHECK,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                    on_click=self._aplicar_rango_personalizado,
                ),
            ],
        )

        for elemento in [self.picker_un_dia, self.picker_inicio, self.picker_fin, self.dialogo_rango]:
            if elemento not in self.page.overlay:
                self.page.overlay.append(elemento)

    def _abrir_picker(self, picker: ft.DatePicker):
        picker.open = True
        self.page.update()

    def _al_cambiar_picker_inicio(self, e):
        if self.picker_inicio.value:
            self._f_ini_temp = self.picker_inicio.value.strftime("%Y-%m-%d")
            self.lbl_desde.value = f"📅 Desde: {self._f_ini_temp}"
            self.page.update()

    def _al_cambiar_picker_fin(self, e):
        if self.picker_fin.value:
            self._f_fin_temp = self.picker_fin.value.strftime("%Y-%m-%d")
            self.lbl_hasta.value = f"📅 Hasta: {self._f_fin_temp}"
            self.page.update()

    def _cerrar_dialogo_rango(self):
        self.dialogo_rango.open = False
        self.page.update()

    def _al_seleccionar_un_dia(self, e):
        if self.picker_un_dia.value:
            f_str = self.picker_un_dia.value.strftime("%Y-%m-%d")
            self.fecha_inicio = f_str
            self.fecha_fin = f_str
            self.descripcion = f"Fecha: {f_str}"
            self.al_cambiar_rango(self.fecha_inicio, self.fecha_fin, self.descripcion)

    def _aplicar_rango_personalizado(self, e):
        d_ini = datetime.strptime(self._f_ini_temp, "%Y-%m-%d")
        d_fin = datetime.strptime(self._f_fin_temp, "%Y-%m-%d")
        if d_ini > d_fin:
            return  # Validación de rango

        self.fecha_inicio = self._f_ini_temp
        self.fecha_fin = self._f_fin_temp
        self.descripcion = f"Periodo: {self.fecha_inicio} al {self.fecha_fin}"
        self._cerrar_dialogo_rango()
        self.al_cambiar_rango(self.fecha_inicio, self.fecha_fin, self.descripcion)

    def aplicar_filtro_rapido(self, tipo: str):
        hoy = datetime.now()
        if tipo == "hoy":
            f_str = hoy.strftime("%Y-%m-%d")
            self.fecha_inicio = f_str
            self.fecha_fin = f_str
            self.descripcion = f"Periodo: Hoy ({f_str})"
        elif tipo == "semana":
            f_ini = (hoy - timedelta(days=6)).strftime("%Y-%m-%d")
            f_fin = hoy.strftime("%Y-%m-%d")
            self.fecha_inicio = f_ini
            self.fecha_fin = f_fin
            self.descripcion = f"Periodo: Últimos 7 Días ({f_ini} al {f_fin})"
        elif tipo == "mes":
            f_ini = hoy.strftime("%Y-%m-01")
            f_fin = hoy.strftime("%Y-%m-%d")
            self.fecha_inicio = f_ini
            self.fecha_fin = f_fin
            self.descripcion = f"Periodo: Este Mes ({f_ini} al {f_fin})"

        self.al_cambiar_rango(self.fecha_inicio, self.fecha_fin, self.descripcion)

    def _abrir_dialogo_rango(self, e):
        self._f_ini_temp = self.fecha_inicio
        self._f_fin_temp = self.fecha_fin
        self.lbl_desde.value = f"📅 Desde: {self._f_ini_temp}"
        self.lbl_hasta.value = f"📅 Hasta: {self._f_fin_temp}"
        self.dialogo_rango.open = True
        self.page.update()

    def _construir_ui(self):
        self.controls = [
            ft.Button(
                "Hoy",
                style=ft.ButtonStyle(color=ft.Colors.BLUE_900, bgcolor=ft.Colors.BLUE_50),
                on_click=lambda e: self.aplicar_filtro_rapido("hoy"),
            ),
            ft.Button(
                "Un Día",
                icon=ft.Icons.CALENDAR_TODAY,
                style=ft.ButtonStyle(color=ft.Colors.BLUE_900, bgcolor=ft.Colors.BLUE_50),
                on_click=lambda e: self._abrir_picker(self.picker_un_dia),
            ),
            ft.Button(
                "Semana",
                style=ft.ButtonStyle(color=ft.Colors.BLUE_900, bgcolor=ft.Colors.BLUE_50),
                on_click=lambda e: self.aplicar_filtro_rapido("semana"),
            ),
            ft.Button(
                "Mes",
                style=ft.ButtonStyle(color=ft.Colors.BLUE_900, bgcolor=ft.Colors.BLUE_50),
                on_click=lambda e: self.aplicar_filtro_rapido("mes"),
            ),
            ft.Button(
                "Rango Fechas",
                icon=ft.Icons.DATE_RANGE,
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                on_click=self._abrir_dialogo_rango,
            ),
        ]