from decimal import Decimal
from typing import Callable, List, Optional
import flet as ft

from components.buscador_autocompletado import BuscadorAutocompletado
from components.dialogo_base import DialogoModalBase
from database.productos_db import (
    actualizar_producto,
    agregar_categoria,
    agregar_producto,
    cambiar_estado_producto,
    obtener_categorias,
    obtener_todos_los_productos,
)


class InventarioView(ft.Container):
    """Vista modular para el catálogo de productos, paquetes/rejas,

    envases retornables y categorías.
    """

    def __init__(self, page: ft.Page, mostrar_mensaje: Callable[[str, str], None], es_admin:bool = True,):
        super().__init__(expand=True, padding=10)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje
        self.es_admin = es_admin

        # Estado interno
        self.id_producto_editar: Optional[int] = None
        self.id_producto_base_seleccionado: Optional[int] = None
        self.categoria_seleccionada: Optional[dict] = None
        self.filtro_estado_actual = "activos"

        self._crear_controles_formulario()
        self._crear_modales()
        self._crear_tabla()
        self._construir_ui()
        self.cargar_productos()

    def _crear_controles_formulario(self):
        # Campos básicos de producto
        self.txt_codigo = ft.TextField(label="Código de Barras / Clave Corta (Opcional)", expand=True)
        self.txt_nombre = ft.TextField(label="Nombre del Producto (Ej. Refresco 600ml Vidrio) *", expand=True)
        self.txt_precio_venta = ft.TextField(label="Precio Venta ($) *", width=160, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_precio_costo = ft.TextField(label="Precio Costo ($)", width=160, keyboard_type=ft.KeyboardType.NUMBER, value="0.0")
        self.txt_stock_actual = ft.TextField(label="Stock Actual", width=160, keyboard_type=ft.KeyboardType.NUMBER, value="0.0")
        self.txt_stock_minimo = ft.TextField(label="Stock Mínimo", width=160, keyboard_type=ft.KeyboardType.NUMBER, value="1.0")

        self.dd_tipo_unidad = ft.Dropdown(
            label="Unidad de Medida",
            width=180,
            options=[
                ft.dropdown.Option("pieza", "Pieza (Pza)"),
                ft.dropdown.Option("kg", "Kilogramo (Kg)"),
                ft.dropdown.Option("paquete", "Reja / Caja / Paquete"),
            ],
            value="pieza",
        )

        # Buscador de categorías
        self.buscador_categoria = BuscadorAutocompletado(
            hint_text="Buscar categoría (Ej. Refrescos, Botanas)...",
            icono_sugerencia=ft.Icons.FOLDER_SPECIAL,
            funcion_busqueda=self._buscar_categorias,
            generador_titulo=lambda c: c["nombre"],
            al_seleccionar=lambda c: setattr(self, "categoria_seleccionada", c),
            al_limpiar=lambda: setattr(self, "categoria_seleccionada", None),
        )

        # Retornables
        self.sw_es_retornable = ft.Switch(
            label="¿Es producto retornable (refresco / cerveza)?",
            value=False,
            on_change=self._al_cambiar_retornable,
        )
        self.txt_precio_envase = ft.TextField(
            label="Costo / Garantía del Envase ($)",
            value="0.0",
            width=220,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
        )

        # Reja / Paquete hijo
        self.chk_es_paquete = ft.Checkbox(
            label="¿Es una Reja / Paquete de otro producto?",
            value=False,
            on_change=self._al_cambiar_check_paquete,
        )
        self.buscador_producto_padre = BuscadorAutocompletado(
            hint_text="Escribe nombre o código del producto base...",
            icono_sugerencia=ft.Icons.LINK,
            funcion_busqueda=self._buscar_productos_base,
            generador_titulo=lambda p: p["nombre"],
            generador_subtitulo=lambda p: f"Stock: {p['stock_actual']} {p['tipo_unidad']} | Cód: {p['codigo_barras'] or '—'}",
            generador_trailing=lambda p: f"${p['precio_venta']:.2f}",
            al_seleccionar=self._al_seleccionar_producto_padre,
            al_limpiar=lambda: setattr(self, "id_producto_base_seleccionado", None),
        )
        self.txt_factor_conversion = ft.TextField(
            label="Piezas por Reja / Paquete",
            value="24",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.seccion_paquete_config = ft.Column(
            [
                ft.Text("Selecciona el producto individual que contiene:", size=12, weight=ft.FontWeight.W_500),
                self.buscador_producto_padre,
                self.txt_factor_conversion,
            ],
            spacing=6,
            visible=False,
        )

    def _crear_modales(self):
        # 1. MODAL NUEVA CATEGORÍA
        self.txt_nueva_cat_nombre = ft.TextField(label="Nombre de la nueva categoría *", autofocus=True)
        self.modal_nueva_categoria = DialogoModalBase(
            page=self.pagina,
            titulo="Nueva Categoría",
            icono=ft.Icons.CREATE_NEW_FOLDER,
            ancho=340,
            al_confirmar=self._guardar_nueva_categoria,
        )
        self.modal_nueva_categoria.set_contenido([self.txt_nueva_cat_nombre])

        # 2. MODAL REGISTRO / EDICIÓN DE PRODUCTO
        btn_nueva_cat = ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE,
            icon_color=ft.Colors.BLUE_700,
            tooltip="Crear nueva categoría",
            on_click=lambda e: (
                setattr(self.txt_nueva_cat_nombre, "value", ""),
                self.modal_nueva_categoria.abrir(),
            ),
        )

        seccion_cat_header = ft.Row(
            [
                ft.Text("Categoría del Producto:", size=12, weight=ft.FontWeight.W_500),
                btn_nueva_cat,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.modal_producto = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar / Editar Producto",
            icono=ft.Icons.INVENTORY,
            ancho=560,
            al_confirmar=self._guardar_producto,
        )
        self.modal_producto.set_contenido([
            ft.Row([self.txt_nombre]),
            ft.Row([self.txt_codigo]),
            ft.Divider(height=1),
            ft.Column([seccion_cat_header, self.buscador_categoria], spacing=4),
            ft.Row([self.dd_tipo_unidad]),
            ft.Divider(height=1),
            ft.Row([self.chk_es_paquete]),
            self.seccion_paquete_config,
            ft.Divider(height=1),
            ft.Row([self.sw_es_retornable]),
            ft.Row([self.txt_precio_envase]),
            ft.Divider(height=1),
            ft.Row([self.txt_precio_costo, self.txt_precio_venta]),
            ft.Row([self.txt_stock_actual, self.txt_stock_minimo]),
        ])

    def _crear_tabla(self):
        self.area_tabla = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    def _construir_ui(self):
        self.txt_filtro = ft.TextField(
            hint_text="Buscar por nombre, código o categoría...",
            expand=True,
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.cargar_productos(),
        )

        self.etiqueta_filtro = ft.Text("Solo Activos", size=14, weight=ft.FontWeight.W_500)
        self.menu_filtro = ft.PopupMenuButton(
            content=ft.Row([self.etiqueta_filtro, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=ft.Colors.GREY_700)]),
            items=[
                ft.PopupMenuItem(content=ft.Text("Solo Activos"), data="activos", on_click=self._al_cambiar_filtro_menu),
                ft.PopupMenuItem(content=ft.Text("⚠️ Stock Crítico"), data="critico", on_click=self._al_cambiar_filtro_menu),
                ft.PopupMenuItem(content=ft.Text("Descontinuados"), data="descontinuados", on_click=self._al_cambiar_filtro_menu),
                ft.PopupMenuItem(content=ft.Text("Todos"), data="todos", on_click=self._al_cambiar_filtro_menu),
            ],
        )

        contenedor_menu = ft.Container(
            content=self.menu_filtro,
            border=ft.Border.all(1, ft.Colors.GREY_400),
            border_radius=4,
            padding=ft.Padding(left=14, right=8, top=10, bottom=10),
            width=220,
        )

        btn_nuevo_prod = ft.Button(
            "Nuevo Producto",
            icon=ft.Icons.ADD,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
            visible=self.es_admin,
            on_click=lambda e: self.abrir_modal_nuevo(),
        )

        titulo_vista = "Inventario de Productos" if self.es_admin else "Consulta de Precios y Existencias"

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(titulo_vista, size=22, weight=ft.FontWeight.BOLD),
                        btn_nuevo_prod,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(),
                ft.Row([self.txt_filtro, contenedor_menu], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    content=self.area_tabla,
                    expand=True,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    padding=10,
                ),
            ],
            expand=True,
            spacing=10,
        )

    def _al_cambiar_filtro_menu(self, e):
        self.filtro_estado_actual = e.control.data
        etiquetas = {
            "activos": "Solo Activos",
            "critico": "⚠️ Stock Crítico",
            "descontinuados": "Descontinuados",
            "todos": "Todos los Productos",
        }
        self.etiqueta_filtro.value = etiquetas.get(self.filtro_estado_actual, "Solo Activos")
        self.pagina.update()
        self.cargar_productos()

    def _al_cambiar_retornable(self, e):
        self.txt_precio_envase.visible = self.sw_es_retornable.value
        self.pagina.update()

    def _al_cambiar_check_paquete(self, e):
        es_paq = self.chk_es_paquete.value
        self.seccion_paquete_config.visible = es_paq
        self.txt_stock_actual.visible = not es_paq
        self.txt_stock_minimo.visible = not es_paq
        self.dd_tipo_unidad.value = "paquete" if es_paq else "pieza"
        self.pagina.update()

    def _buscar_categorias(self, termino: str):
        cats = obtener_categorias()
        t = termino.lower()
        return [c for c in cats if t in (c["nombre"] or "").lower()]

    def _buscar_productos_base(self, termino: str):
        todos = obtener_todos_los_productos()
        t = termino.lower()
        return [
            p for p in todos
            if not p["id_producto_padre"] and int(p["activo"]) == 1
            and (t in (p["nombre"] or "").lower() or t in (p["codigo_barras"] or "").lower())
        ]

    def _al_seleccionar_producto_padre(self, prod):
        self.id_producto_base_seleccionado = prod["id_producto"]
        es_ret = bool(prod["es_retornable"])
        p_env_base = float(prod["precio_envase"] or 0.0)

        if es_ret:
            try:
                factor = int(self.txt_factor_conversion.value or "1")
            except ValueError:
                factor = 1
            self.sw_es_retornable.value = True
            self.txt_precio_envase.visible = True
            self.txt_precio_envase.value = str(p_env_base * factor)
        else:
            self.sw_es_retornable.value = False
            self.txt_precio_envase.visible = False
            self.txt_precio_envase.value = "0.0"
        self.pagina.update()

    def cargar_productos(self):
        termino = self.txt_filtro.value.strip().lower() if self.txt_filtro.value else ""
        todos = obtener_todos_los_productos()
        mapa_productos = {p["id_producto"]: p for p in todos}

        filas_nuevas = []

        for prod in todos:
            es_activo = int(prod["activo"]) == 1
            es_paquete = bool(prod["id_producto_padre"] and prod["factor_conversion"])

            if es_paquete:
                padre = mapa_productos.get(prod["id_producto_padre"])
                if padre:
                    cajas_disp = int(padre["stock_actual"] // prod["factor_conversion"])
                    stock_texto = f"{cajas_disp} rejas ({prod['factor_conversion']} pzas)"
                    es_stock_bajo = cajas_disp <= 1
                else:
                    stock_texto = "Sin vínculo"
                    es_stock_bajo = True
            else:
                stock_actual = float(prod["stock_actual"] or 0.0)
                stock_minimo = float(prod["stock_minimo"] or 1.0)
                es_stock_bajo = es_activo and (stock_actual <= stock_minimo)
                stock_texto = f"{stock_actual} {prod['tipo_unidad']}"

            nombre = prod["nombre"] or ""
            codigo = prod["codigo_barras"] or "—"
            cat_nombre = prod["categoria"] or "General"

            # Criterios de filtrado
            if self.filtro_estado_actual == "critico" and (not es_activo or not es_stock_bajo):
                continue
            elif self.filtro_estado_actual == "activos" and not es_activo:
                continue
            elif self.filtro_estado_actual == "descontinuados" and es_activo:
                continue

            if termino and termino not in f"{nombre} {codigo} {cat_nombre}".lower():
                continue

            es_ret = bool(prod["es_retornable"])
            p_env = float(prod["precio_envase"] or 0.0)

            badge_envase = (
                ft.Container(
                    content=ft.Text(f"🍾 Retornable (${p_env:.2f})", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.ORANGE_800,
                    padding=ft.Padding(6, 2, 6, 2),
                    border_radius=6,
                )
                if es_ret
                else ft.Text("No aplica", size=12, color=ft.Colors.GREY_600)
            )

            # Celdas base (visibles para cualquier rol)
            celdas = [
                ft.DataCell(ft.Text(codigo)),
                ft.DataCell(ft.Text(f"📦 {nombre}" if es_paquete else nombre, weight=ft.FontWeight.BOLD)),
                ft.DataCell(ft.Text(cat_nombre)),
            ]

            # Precio Costo solo visible para Administrador
            if self.es_admin:
                celdas.append(ft.DataCell(ft.Text(f"${prod['precio_costo']:.2f}")))

            celdas.extend([
                ft.DataCell(ft.Text(f"${prod['precio_venta']:.2f}")),
                ft.DataCell(badge_envase),
                ft.DataCell(
                    ft.Container(
                        content=ft.Text(
                            stock_texto,
                            color=ft.Colors.WHITE if es_stock_bajo else ft.Colors.BLACK,
                            weight=ft.FontWeight.BOLD if es_stock_bajo else ft.FontWeight.NORMAL,
                        ),
                        bgcolor=ft.Colors.RED_600 if es_stock_bajo else None,
                        padding=4 if es_stock_bajo else 0,
                        border_radius=4,
                    )
                ),
            ])

            # Estado y botones de edición solo visibles para Administrador
            if self.es_admin:
                btn_editar = ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_600,
                    tooltip="Editar producto",
                    on_click=lambda e, p=prod: self.abrir_modal_editar(p),
                )

                btn_estado = ft.IconButton(
                    icon=ft.Icons.VISIBILITY_OFF_OUTLINED if es_activo else ft.Icons.CHECK_CIRCLE_OUTLINE,
                    icon_color=ft.Colors.RED_500 if es_activo else ft.Colors.GREEN_600,
                    tooltip="Descontinuar" if es_activo else "Reactivar",
                    on_click=lambda e, p=prod, a=es_activo: self._alternar_estado_producto(p["id_producto"], a),
                )

                badge_estado = ft.Container(
                    content=ft.Text("Activo" if es_activo else "Descontinuado", size=12, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.GREEN_700 if es_activo else ft.Colors.GREY_600,
                    padding=6,
                    border_radius=10,
                )

                celdas.extend([
                    ft.DataCell(badge_estado),
                    ft.DataCell(ft.Row([btn_editar, btn_estado], spacing=0)),
                ])

            filas_nuevas.append(ft.DataRow(cells=celdas))

        # Configuración dinámica de columnas según permisos
        columnas = [
            ft.DataColumn(ft.Text("Código", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Categoría", weight=ft.FontWeight.BOLD)),
        ]

        if self.es_admin:
            columnas.append(ft.DataColumn(ft.Text("P. Costo", weight=ft.FontWeight.BOLD), numeric=True))

        columnas.extend([
            ft.DataColumn(ft.Text("P. Venta", weight=ft.FontWeight.BOLD), numeric=True),
            ft.DataColumn(ft.Text("Envase / Garantía", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Stock Disp.", weight=ft.FontWeight.BOLD), numeric=True),
        ])

        if self.es_admin:
            columnas.extend([
                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ])

        tabla = ft.DataTable(
            columns=columnas,
            rows=filas_nuevas,
            column_spacing=20,
            horizontal_margin=10,
        )
        self.area_tabla.controls = [ft.Row([tabla], scroll=ft.ScrollMode.AUTO)]
        self.pagina.update()

    def _alternar_estado_producto(self, id_producto: int, actualmente_activo: bool):
        nuevo_st = 0 if actualmente_activo else 1
        cambiar_estado_producto(id_producto, nuevo_st)
        self.mostrar_mensaje(
            "🚫 Producto descontinuado" if nuevo_st == 0 else "✅ Producto reactivado",
            ft.Colors.ORANGE_800 if nuevo_st == 0 else ft.Colors.GREEN_700,
        )
        self.cargar_productos()

    def abrir_modal_nuevo(self):
        self.id_producto_editar = None
        self.id_producto_base_seleccionado = None
        self.modal_producto.lbl_titulo.value = "Nuevo Producto"
        self.txt_nombre.value = ""
        self.txt_codigo.value = ""
        self.txt_precio_venta.value = ""
        self.txt_precio_costo.value = "0.0"
        self.txt_stock_actual.value = "0.0"
        self.txt_stock_minimo.value = "1.0"
        self.dd_tipo_unidad.value = "pieza"

        self.sw_es_retornable.value = False
        self.txt_precio_envase.value = "0.0"
        self.txt_precio_envase.visible = False

        self.chk_es_paquete.value = False
        self.seccion_paquete_config.visible = False
        self.txt_stock_actual.visible = True
        self.txt_stock_minimo.visible = True

        self.buscador_categoria.limpiar_seleccion()
        self.buscador_producto_padre.limpiar_seleccion()

        cats = obtener_categorias()
        if cats:
            self.buscador_categoria.seleccionar_item(cats[0])

        self.modal_producto.abrir()

    def abrir_modal_editar(self, prod):
        self.id_producto_editar = prod["id_producto"]
        self.modal_producto.lbl_titulo.value = f"Editar: {prod['nombre']}"
        self.txt_nombre.value = prod["nombre"]
        self.txt_codigo.value = prod["codigo_barras"] or ""
        self.txt_precio_venta.value = str(prod["precio_venta"])
        self.txt_precio_costo.value = str(prod["precio_costo"])
        self.txt_stock_actual.value = str(prod["stock_actual"])
        self.txt_stock_minimo.value = str(prod["stock_minimo"])
        self.dd_tipo_unidad.value = prod["tipo_unidad"]

        # Configurar categoría
        id_cat = prod["id_categoria"] or 1
        cat_nom = prod["categoria"] or "General"
        self.buscador_categoria.seleccionar_item({"id_categoria": id_cat, "nombre": cat_nom})

        # Configurar retornable
        es_ret = bool(prod["es_retornable"])
        self.sw_es_retornable.value = es_ret
        self.txt_precio_envase.value = str(prod["precio_envase"] or 0.0)
        self.txt_precio_envase.visible = es_ret

        # Configurar paquete
        es_paq = bool(prod["id_producto_padre"] and prod["factor_conversion"])
        self.chk_es_paquete.value = es_paq
        self.seccion_paquete_config.visible = es_paq
        self.txt_stock_actual.visible = not es_paq
        self.txt_stock_minimo.visible = not es_paq

        if es_paq:
            self.id_producto_base_seleccionado = prod["id_producto_padre"]
            self.txt_factor_conversion.value = str(prod["factor_conversion"])
            todos = obtener_todos_los_productos()
            padre = next((p for p in todos if p["id_producto"] == prod["id_producto_padre"]), None)
            if padre:
                self.buscador_producto_padre.seleccionar_item(padre)
        else:
            self.id_producto_base_seleccionado = None
            self.buscador_producto_padre.limpiar_seleccion()

        self.modal_producto.abrir()

    def _guardar_nueva_categoria(self, e):
        nom = self.txt_nueva_cat_nombre.value.strip()
        if not nom:
            self.mostrar_mensaje("Escribe el nombre de la categoría", ft.Colors.RED_600)
            return

        try:
            nuevo_id = agregar_categoria(nombre=nom)
            self.modal_nueva_categoria.cerrar()
            self.buscador_categoria.seleccionar_item({"id_categoria": nuevo_id, "nombre": nom})
            self.mostrar_mensaje(f" Categoría '{nom}' creada", ft.Colors.GREEN_700)
        except Exception:
            self.mostrar_mensaje(" La categoría ya existe o es inválida", ft.Colors.RED_600)

    def _guardar_producto(self, e):
        nombre = self.txt_nombre.value.strip() if self.txt_nombre.value else ""
        codigo = self.txt_codigo.value.strip() if self.txt_codigo.value else ""

        if not nombre:
            self.mostrar_mensaje("El nombre del producto es obligatorio", ft.Colors.RED_600)
            return

        if not self.categoria_seleccionada:
            self.mostrar_mensaje("Debes seleccionar una categoría", ft.Colors.RED_600)
            return

        try:
            precio_v = float(self.txt_precio_venta.value)
            precio_c = float(self.txt_precio_costo.value or "0")
            stock_act = float(self.txt_stock_actual.value or "0")
            stock_min = float(self.txt_stock_minimo.value or "1")
            precio_env = float(self.txt_precio_envase.value or "0") if self.sw_es_retornable.value else 0.0
        except ValueError:
            self.mostrar_mensaje("Verifica que precios y stock sean numéricos", ft.Colors.RED_600)
            return

        id_cat = self.categoria_seleccionada["id_categoria"]
        id_padre = None
        factor_conv = None

        if self.chk_es_paquete.value:
            if not self.id_producto_base_seleccionado:
                self.mostrar_mensaje("Selecciona el producto individual base", ft.Colors.RED_600)
                return
            id_padre = self.id_producto_base_seleccionado
            try:
                factor_conv = int(self.txt_factor_conversion.value or "24")
            except ValueError:
                factor_conv = 24
            tipo_u = "paquete"
            stock_act = 0.0
        else:
            tipo_u = self.dd_tipo_unidad.value

        es_ret = 1 if self.sw_es_retornable.value else 0

        try:
            if self.id_producto_editar is None:
                agregar_producto(
                    nombre=nombre,
                    precio_venta=precio_v,
                    codigo_barras=codigo if codigo else None,
                    tipo_unidad=tipo_u,
                    precio_costo=precio_c,
                    stock_actual=stock_act,
                    stock_minimo=stock_min,
                    id_categoria=id_cat,
                    id_producto_padre=id_padre,
                    factor_conversion=factor_conv,
                    es_retornable=es_ret,
                    precio_envase=precio_env,
                )
                self.mostrar_mensaje(" Producto registrado", ft.Colors.GREEN_700)
            else:
                actualizar_producto(
                    id_producto=self.id_producto_editar,
                    nombre=nombre,
                    precio_venta=precio_v,
                    codigo_barras=codigo if codigo else None,
                    tipo_unidad=tipo_u,
                    precio_costo=precio_c,
                    stock_actual=stock_act,
                    stock_minimo=stock_min,
                    id_categoria=id_cat,
                    id_producto_padre=id_padre,
                    factor_conversion=factor_conv,
                    es_retornable=es_ret,
                    precio_envase=precio_env,
                )
                self.mostrar_mensaje(" Producto actualizado", ft.Colors.GREEN_700)

            self.modal_producto.cerrar()
            self.cargar_productos()
        except Exception as err:
            self.mostrar_mensaje(f" Error al guardar: {err}", ft.Colors.RED_600)