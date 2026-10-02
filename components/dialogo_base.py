from typing import Callable, List, Optional
import flet as ft


class DialogoModalBase(ft.AlertDialog):
    """Componente reutilizable de ventana modal con encabezado estandarizado,
    contenedor con scroll y botones de acción configurables.
    """

    def __init__(
        self,
        page: ft.Page,
        titulo: str,
        icono: Optional[str] = None,
        color_icono: str = ft.Colors.BLUE_700,
        ancho: int = 480,
        texto_confirmar: str = "Guardar",
        icono_confirmar: str = ft.Icons.SAVE,
        color_confirmar: str = ft.Colors.GREEN_700,
        al_confirmar: Optional[Callable[[any], None]] = None,
        al_cancelar: Optional[Callable[[any], None]] = None,
        mostrar_boton_confirmar: bool = True,
    ):
        super().__init__()
        self.page = page
        self.al_confirmar = al_confirmar
        self.al_cancelar = al_cancelar

        # Encabezado
        self.lbl_titulo = ft.Text(titulo, weight=ft.FontWeight.BOLD)
        if icono:
            self.title = ft.Row(
                [ft.Icon(icono, color=color_icono), self.lbl_titulo],
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
            )
        else:
            self.title = self.lbl_titulo

        # Contenedor de contenido interno
        self.col_contenido = ft.Column(tight=True, spacing=10, scroll=ft.ScrollMode.AUTO)
        self.content = ft.Container(
            content=self.col_contenido,
            width=ancho,
        )

        # 3. Acciones estándar
        self.btn_cancelar = ft.Button(
            "Cancelar",
            style=ft.ButtonStyle(color=ft.Colors.GREY_700),
            on_click=self._click_cancelar,
        )

        self.btn_confirmar = ft.Button(
            texto_confirmar,
            icon=icono_confirmar,
            style=ft.ButtonStyle(bgcolor=color_confirmar, color=ft.Colors.WHITE),
            on_click=self._click_confirmar,
            visible=mostrar_boton_confirmar,
        )

        self.actions = [self.btn_cancelar, self.btn_confirmar]

        if self not in self.page.overlay:
            self.page.overlay.append(self)

    def set_contenido(self, controles: List[ft.Control]):
        """Reemplaza los controles internos del formulario modal."""
        self.col_contenido.controls = controles

    def abrir(self):
        self.open = True
        self.page.update()

    def cerrar(self):
        self.open = False
        self.page.update()

    def _click_cancelar(self, e):
        self.cerrar()
        if self.al_cancelar:
            self.al_cancelar(e)

    def _click_confirmar(self, e):
        if self.al_confirmar:
            self.al_confirmar(e)