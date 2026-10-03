import flet as ft
from typing import Callable, Optional, Dict


class ModalVentaGranel:
    """Modal interactivo para calcular productos vendidos por peso (kg) o por importe ($)."""

    def __init__(self, page: ft.Page, al_confirmar: Callable[[Dict, float, float], None]):
        self.page = page
        self.al_confirmar = al_confirmar
        self.producto_actual: Optional[Dict] = None
        self.precio_unitario: float = 0.0

        # TextFields reactivos
        self.txt_peso = ft.TextField(
            label="Peso en Kilogramos (kg)",
            hint_text="Ej. 0.750",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.SCALE,
            autofocus=True,
            width=280,
            on_change=self._al_cambiar_peso,
        )

        self.txt_importe = ft.TextField(
            label="Importe en Dinero ($)",
            hint_text="Ej. 35.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.ATTACH_MONEY,
            width=280,
            on_change=self._al_cambiar_importe,
        )

        self.lbl_info_precio = ft.Text(
            "Precio por kg: $0.00",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLUE_900,
        )

        self.lbl_resumen = ft.Text(
            "Total a cobrar: $0.00 por 0.000 kg",
            size=13,
            color=ft.Colors.GREY_700,
        )

        self.dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.SCALE, color=ft.Colors.BLUE_800),
                    ft.Text("Venta a Granel / Peso", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.lbl_info_precio,
                        ft.Text(
                            "Digita el peso pesado en báscula O el importe solicitado por el cliente:",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                        self.txt_peso,
                        ft.Row(
                            [
                                ft.Divider(expand=True),
                                ft.Text("Ó", size=11, color=ft.Colors.GREY_500),
                                ft.Divider(expand=True),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        self.txt_importe,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.lbl_resumen,
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=340,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.cerrar()),
                ft.Button(
                    "Agregar al Carrito",
                    icon=ft.Icons.ADD_SHOPPING_CART,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                    on_click=self._confirmar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def abrir(self, producto: Dict):
        """Prepara el diálogo con los datos del producto seleccionado."""
        self.producto_actual = producto
        self.precio_unitario = float(producto.get("precio_venta", 0.0))

        self.lbl_info_precio.value = f"Artículo: {producto.get('nombre', '')} (${self.precio_unitario:.2f} / kg)"
        self.txt_peso.value = ""
        self.txt_importe.value = ""
        self.lbl_resumen.value = "Total a cobrar: $0.00 por 0.000 kg"

        # Apertura segura compatible con Flet moderno
        try:
            self.page.open(self.dialogo)
        except Exception:
            if self.dialogo not in self.page.overlay:
                self.page.overlay.append(self.dialogo)
            self.dialogo.open = True
            if self.page:
                self.page.update()

    def cerrar(self):
        try:
            self.page.close(self.dialogo)
        except Exception:
            self.dialogo.open = False
            if self.page:
                self.page.update()
                
    def _al_cambiar_peso(self, e):
        """Calcula el importe automáticamente a partir del peso ingresado."""
        if not self.txt_peso.focus:
            return
        try:
            val = self.txt_peso.value.strip()
            peso = float(val) if val else 0.0
            if peso >= 0:
                importe = round(peso * self.precio_unitario, 2)
                self.txt_importe.value = f"{importe:.2f}"
                self.lbl_resumen.value = f"Total a cobrar: ${importe:.2f} por {peso:.3f} kg"
                self.page.update()
        except ValueError:
            pass

    def _al_cambiar_importe(self, e):
        """Calcula el peso automáticamente a partir del importe ingresado."""
        if not self.txt_importe.focus:
            return
        try:
            val = self.txt_importe.value.strip()
            importe = float(val) if val else 0.0
            if importe >= 0 and self.precio_unitario > 0:
                peso = round(importe / self.precio_unitario, 3)
                self.txt_peso.value = f"{peso:.3f}"
                self.lbl_resumen.value = f"Total a cobrar: ${importe:.2f} por {peso:.3f} kg"
                self.page.update()
        except ValueError:
            pass

    def _confirmar(self, e):
        try:
            peso = float(self.txt_peso.value.strip() or 0.0)
            importe = float(self.txt_importe.value.strip() or 0.0)

            if peso <= 0 or importe <= 0:
                return

            self.cerrar()
            if self.al_confirmar and self.producto_actual:
                self.al_confirmar(self.producto_actual, peso, importe)
        except ValueError:
            pass