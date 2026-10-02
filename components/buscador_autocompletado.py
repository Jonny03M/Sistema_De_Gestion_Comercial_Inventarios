from typing import Any, Callable, List, Optional
import flet as ft


class BuscadorAutocompletado(ft.Column):
    """Componente reutilizable de búsqueda en tiempo real con lista desplegable

    de sugerencias y chip de elemento seleccionado.
    """

    def __init__(
        self,
        hint_text: str,
        icono_sugerencia: str,
        funcion_busqueda: Callable[[str], List[Any]],
        generador_titulo: Callable[[Any], str],
        generador_subtitulo: Optional[Callable[[Any], str]] = None,
        generador_trailing: Optional[Callable[[Any], str]] = None,
        al_seleccionar: Optional[Callable[[Any], None]] = None,
        al_limpiar: Optional[Callable[[], None]] = None,
        permitir_deseleccion: bool = True,
        altura_sugerencias: int = 150,
        limite_resultados: int = 8,
    ):
        super().__init__()
        self.spacing = 4

        self.funcion_busqueda = funcion_busqueda
        self.generador_titulo = generador_titulo
        self.generador_subtitulo = generador_subtitulo
        self.generador_trailing = generador_trailing
        self.al_seleccionar = al_seleccionar
        self.al_limpiar = al_limpiar
        self.permitir_deseleccion = permitir_deseleccion
        self.limite_resultados = limite_resultados

        self.item_seleccionado: Optional[Any] = None

        # 1. Campo de texto de búsqueda
        self.txt_buscar = ft.TextField(
            hint_text=hint_text,
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            on_change=self._al_escribir_texto,
            on_submit=self._al_presionar_enter,
        )

        # 2. Contenedor de sugerencias flotantes
        self.col_sugerencias = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)
        self.cont_sugerencias = ft.Container(
            content=self.col_sugerencias,
            visible=False,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.BLUE_300),
            border_radius=8,
            padding=4,
            height=altura_sugerencias,
        )

        # 3. Chip de elemento seleccionado
        self.lbl_seleccionado = ft.Text(
            "Ninguna selección",
            size=13,
            color=ft.Colors.GREEN_800,
            weight=ft.FontWeight.BOLD,
        )
        self.btn_quitar = ft.IconButton(
            icon=ft.Icons.CANCEL,
            icon_color=ft.Colors.RED_600,
            tooltip="Quitar selección",
            visible=False,
            on_click=lambda e: self.limpiar_seleccion(),
        )

        self.chip_seleccion = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono_sugerencia, color=ft.Colors.BLUE_700, size=18),
                    self.lbl_seleccionado,
                    self.btn_quitar,
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=6,
            ),
            visible=False,
            padding=2,
        )

        self.controls = [
            self.chip_seleccion,
            self.txt_buscar,
            self.cont_sugerencias,
        ]

    def _al_escribir_texto(self, e):
        termino = self.txt_buscar.value.strip()
        if not termino:
            self.cont_sugerencias.visible = False
            self.update()
            return

        coincidencias = self.funcion_busqueda(termino)[: self.limite_resultados]
        self.col_sugerencias.controls.clear()

        if not coincidencias:
            self.col_sugerencias.controls.append(
                ft.ListTile(
                    title=ft.Text(
                        "No se encontraron resultados",
                        size=12,
                        color=ft.Colors.GREY_600,
                    ),
                    dense=True,
                )
            )
        else:
            for item in coincidencias:

                def click_item(ev, it=item):
                    self.seleccionar_item(it)

                subtitulo_texto = (
                    self.generador_subtitulo(item)
                    if self.generador_subtitulo
                    else None
                )
                trailing_texto = (
                    self.generador_trailing(item)
                    if self.generador_trailing
                    else None
                )

                tile = ft.ListTile(
                    title=ft.Text(
                        self.generador_titulo(item),
                        size=13,
                        weight=ft.FontWeight.W_500,
                    ),
                    subtitle=ft.Text(subtitulo_texto, size=11)
                    if subtitulo_texto
                    else None,
                    trailing=ft.Text(
                        trailing_texto,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_700,
                    )
                    if trailing_texto
                    else None,
                    on_click=click_item,
                    dense=True,
                )
                self.col_sugerencias.controls.append(tile)

        self.cont_sugerencias.visible = True
        self.update()

    def _al_presionar_enter(self, e):
        termino = self.txt_buscar.value.strip()
        if not termino:
            return

        coincidencias = self.funcion_busqueda(termino)
        if coincidencias:
            self.seleccionar_item(coincidencias[0])

    def seleccionar_item(self, item: Any):
        self.item_seleccionado = item
        self.cont_sugerencias.visible = False
        self.txt_buscar.value = ""

        if self.permitir_deseleccion:
            self.lbl_seleccionado.value = self.generador_titulo(item)
            self.chip_seleccion.visible = True
            self.btn_quitar.visible = True
            self.txt_buscar.visible = False

        self.update()

        if self.al_seleccionar:
            self.al_seleccionar(item)

    def limpiar_seleccion(self):
        self.item_seleccionado = None
        self.chip_seleccion.visible = False
        self.btn_quitar.visible = False
        self.txt_buscar.visible = True
        self.txt_buscar.value = ""
        self.cont_sugerencias.visible = False
        self.update()

        if self.al_limpiar:
            self.al_limpiar()