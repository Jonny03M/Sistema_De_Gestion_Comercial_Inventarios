from decimal import Decimal
from typing import Callable, List, Optional
import flet as ft

from components.buscador_autocompletado import BuscadorAutocompletado
from components.dialogo_base import DialogoModalBase
from components.selector_fechas import SelectorRangoFechas
from database.productos_db import obtener_todos_los_productos
from database.ventas_db import (
    actualizar_proveedor,
    agregar_proveedor,
    obtener_detalle_compra_por_id,
    obtener_historial_compras_filtrado,
    obtener_todos_los_proveedores,
    registrar_compra_mercancia,
)


class ComprasView(ft.Container):
    """Vista modular para gestión de proveedores, compras y recepción de mercancía."""

    def __init__(self, page: ft.Page, mostrar_mensaje: Callable[[str, str], None],es_admin: bool = True,):
        super().__init__(expand=True, padding=10)
        self.pagina = page
        self.mostrar_mensaje = mostrar_mensaje
        self.es_admin = es_admin

        # Estado interno
        self.id_proveedor_editar: Optional[int] = None
        self.proveedor_seleccionado_compra: Optional[dict] = None
        self.producto_seleccionado_compra: Optional[dict] = None
        self.items_nueva_compra: List[dict] = []

        self._crear_tablas()
        self._crear_modales()
        self._construir_ui()
        self.cargar_datos()

    def _crear_tablas(self):
        # 1. Tabla Historial Compras
        self.tabla_compras = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("# Compra", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Fecha / Hora", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Proveedor", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Factura", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True,
            column_spacing=20,
            horizontal_margin=10,
        )

        # 2. Tabla Directorio Proveedores
        self.tabla_proveedores = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Empresa / Proveedor", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Contacto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Teléfono", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            expand=True,
            column_spacing=20,
            horizontal_margin=10,
        )

        # 3. Tabla Detalle de Compra (Modal)
        self.tabla_detalles_compra = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cant.", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Costo U.", weight=ft.FontWeight.BOLD), numeric=True),
                ft.DataColumn(ft.Text("Subtotal", weight=ft.FontWeight.BOLD), numeric=True),
            ],
            rows=[],
            column_spacing=16,
            horizontal_margin=10,
        )

        # 4. Tabla Items Entrada de Mercancía
        self.tabla_items_compra = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Producto")),
                ft.DataColumn(ft.Text("Cant."), numeric=True),
                ft.DataColumn(ft.Text("Costo U."), numeric=True),
                ft.DataColumn(ft.Text("Subtotal"), numeric=True),
                ft.DataColumn(ft.Text("Quitar")),
            ],
            rows=[],
            expand=True,
            column_spacing=14,
            horizontal_margin=8,
        )

    def _crear_modales(self):
        # MODAL 1: REGISTRAR / EDITAR PROVEEDOR
        self.txt_prov_empresa = ft.TextField(label="Nombre de la Empresa / Distribuidor *", expand=True)
        self.txt_prov_contacto = ft.TextField(label="Nombre del Agente / Contacto", expand=True)
        self.txt_prov_telefono = ft.TextField(label="Teléfono / Celular", expand=True)

        self.modal_proveedor = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Proveedor",
            icono=ft.Icons.BUSINESS,
            ancho=450,
            al_confirmar=self._guardar_proveedor,
        )
        self.modal_proveedor.set_contenido([
            self.txt_prov_empresa,
            self.txt_prov_contacto,
            self.txt_prov_telefono,
        ])

        # MODAL 2: DETALLE DE FACTURA / COMPRA
        self.lbl_compra_id = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
        self.lbl_compra_fecha = ft.Text("", size=12, color=ft.Colors.GREY_700)
        self.lbl_compra_proveedor = ft.Text("", size=13)
        self.lbl_compra_total = ft.Text("", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)

        self.modal_detalle = DialogoModalBase(
            page=self.pagina,
            titulo="Detalle de Factura",
            icono=ft.Icons.LOCAL_SHIPPING,
            ancho=540,
            mostrar_boton_confirmar=False,
        )
        self.modal_detalle.set_contenido([
            self.lbl_compra_id,
            self.lbl_compra_fecha,
            ft.Divider(height=1),
            self.lbl_compra_proveedor,
            ft.Divider(height=1),
            ft.Text("Mercancía Ingresada:", size=13, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column(
                    [ft.Row([self.tabla_detalles_compra], scroll=ft.ScrollMode.AUTO, expand=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                height=200,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=8,
                padding=4,
            ),
            ft.Divider(height=1),
            ft.Row(
                [ft.Text("Total de la Compra:", size=16, weight=ft.FontWeight.BOLD), self.lbl_compra_total],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        ])

        # MODAL 3: REGISTRAR ENTRADA / NUEVA COMPRA
        self.buscador_prov_compra = BuscadorAutocompletado(
            hint_text="Buscar proveedor (Ej. Bimbo, Sabritas)...",
            icono_sugerencia=ft.Icons.BUSINESS,
            funcion_busqueda=self._buscar_proveedores,
            generador_titulo=lambda p: p["nombre_empresa"],
            generador_subtitulo=lambda p: f"Contacto: {p['contacto_nombre'] or 'N/A'} | Tel: {p['telefono'] or 'N/A'}",
            al_seleccionar=lambda p: setattr(self, "proveedor_seleccionado_compra", p),
            al_limpiar=lambda: setattr(self, "proveedor_seleccionado_compra", None),
        )

        self.buscador_prod_compra = BuscadorAutocompletado(
            hint_text="Buscar producto por código o nombre...",
            icono_sugerencia=ft.Icons.INVENTORY_2,
            funcion_busqueda=self._buscar_productos_compra,
            generador_titulo=lambda p: p["nombre"],
            generador_subtitulo=lambda p: f"Stock actual: {p['stock_actual']} {p['tipo_unidad']}",
            generador_trailing=lambda p: f"Costo: ${p['precio_costo']:.2f}",
            al_seleccionar=self._al_seleccionar_producto_compra,
            al_limpiar=lambda: setattr(self, "producto_seleccionado_compra", None),
        )

        self.txt_compra_cant = ft.TextField(label="Cantidad recibida", value="1", width=140, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_compra_costo = ft.TextField(label="Costo Unitario ($)", value="0.0", width=140, keyboard_type=ft.KeyboardType.NUMBER)
        self.lbl_total_nueva_compra = ft.Text("$0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)

        self.modal_nueva_compra = DialogoModalBase(
            page=self.pagina,
            titulo="Registrar Entrada de Mercancía",
            icono=ft.Icons.POST_ADD,
            color_icono=ft.Colors.GREEN_700,
            ancho=580,
            texto_confirmar="Registrar Compra",
            icono_confirmar=ft.Icons.CHECK,
            al_confirmar=self._guardar_compra_final,
        )
        self.modal_nueva_compra.set_contenido([
            ft.Text("Proveedor que entrega:", size=12, weight=ft.FontWeight.W_500),
            self.buscador_prov_compra,
            ft.Divider(height=1),
            ft.Text("Producto recibido:", size=12, weight=ft.FontWeight.W_500),
            self.buscador_prod_compra,
            ft.Row(
                [
                    self.txt_compra_cant,
                    self.txt_compra_costo,
                    ft.Button(
                        "Agregar",
                        icon=ft.Icons.ADD_SHOPPING_CART,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                        on_click=self._agregar_item_a_compra,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(height=1),
            ft.Text("Lista de Entrada:", size=13, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column(
                    [ft.Row([self.tabla_items_compra], scroll=ft.ScrollMode.AUTO, expand=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                height=160,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=8,
                padding=4,
            ),
            ft.Divider(height=1),
            ft.Row(
                [ft.Text("Total de Factura:", size=16, weight=ft.FontWeight.BOLD), self.lbl_total_nueva_compra],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        ])

    def _construir_ui(self):
        self.lbl_resumen_filtro = ft.Text("Periodo: Hoy", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)
        self.lbl_total_gastado = ft.Text("$0.00", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_800)

        self.selector_fechas = SelectorRangoFechas(
            page=self.pagina,
            al_cambiar_rango=self._al_cambiar_periodo,
        )

        contenedor_historial = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Historial de Compras / Facturas:", size=15, weight=ft.FontWeight.BOLD),
                                    ft.Row([self.lbl_resumen_filtro, self.lbl_total_gastado], spacing=10),
                                ],
                                spacing=2,
                            ),
                            ft.Button(
                                "Registrar Entrada",
                                icon=ft.Icons.ADD_SHOPPING_CART,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                                on_click=lambda e: self.abrir_modal_nueva_compra(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        content=ft.Column(
                            [ft.Row([self.tabla_compras], scroll=ft.ScrollMode.AUTO, expand=True)],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=8,
            ),
            col={"xs": 12, "lg": 7},
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
            height=480,
        )

        contenedor_provs = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Directorio de Proveedores:", size=15, weight=ft.FontWeight.BOLD),
                            ft.Button(
                                "Nuevo Proveedor",
                                icon=ft.Icons.PERSON_ADD_ALT,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                                on_click=lambda e: self.abrir_modal_nuevo_prov(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        content=ft.Column(
                            [ft.Row([self.tabla_proveedores], scroll=ft.ScrollMode.AUTO, expand=True)],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=8,
            ),
            col={"xs": 12, "lg": 5},
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
            height=480,
        )

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Proveedores y Recepción de Mercancía", size=20, weight=ft.FontWeight.BOLD),
                        self.selector_fechas,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                ),
                ft.Divider(),
                ft.ResponsiveRow(
                    controls=[contenedor_historial, contenedor_provs],
                    spacing=12,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

    def _al_cambiar_periodo(self, f_ini: str, f_fin: str, descripcion: str):
        self.lbl_resumen_filtro.value = descripcion
        self.cargar_datos(f_ini, f_fin)

    def cargar_datos(self, f_ini: Optional[str] = None, f_fin: Optional[str] = None):
        if not f_ini:
            f_ini = self.selector_fechas.fecha_inicio
            f_fin = self.selector_fechas.fecha_fin

        # 1. Cargar Compras
        self.tabla_compras.rows.clear()
        compras = obtener_historial_compras_filtrado(f_ini, f_fin)
        suma_total = sum(c["total"] for c in compras)
        self.lbl_total_gastado.value = f"Inversión: ${suma_total:.2f}"

        for c in compras:
            btn_ver = ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                icon_color=ft.Colors.BLUE_700,
                tooltip="Ver artículos comprados",
                on_click=lambda e, id_c=c["id_compra"]: self.abrir_detalle_compra(id_c),
            )
            self.tabla_compras.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{c['id_compra']}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(c["fecha_hora"] or "—")),
                        ft.DataCell(ft.Text(c["proveedor"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"${c['total']:.2f}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(btn_ver),
                    ]
                )
            )

        # 2. Cargar Proveedores
        self.tabla_proveedores.rows.clear()
        provs = obtener_todos_los_proveedores()
        for p in provs:
            btn_edit = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_600,
                tooltip="Editar proveedor",
                visible=self.es_admin,
                on_click=lambda e, p_data=p: self.abrir_modal_editar_prov(p_data),
            )
            self.tabla_proveedores.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{p['id_proveedor']}")),
                        ft.DataCell(ft.Text(p["nombre_empresa"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(p["contacto_nombre"] or "—")),
                        ft.DataCell(ft.Text(p["telefono"] or "—")),
                        ft.DataCell(btn_edit),
                    ]
                )
            )

        self.pagina.update()

    def _buscar_proveedores(self, termino: str):
        provs = obtener_todos_los_proveedores()
        t = termino.lower()
        return [p for p in provs if t in (p["nombre_empresa"] or "").lower() or t in (p["contacto_nombre"] or "").lower()]

    def _buscar_productos_compra(self, termino: str):
        todos = obtener_todos_los_productos()
        t = termino.lower()
        return [
            p for p in todos
            if not p["id_producto_padre"] and int(p["activo"]) == 1
            and (t in (p["nombre"] or "").lower() or t in (p["codigo_barras"] or "").lower())
        ]

    def _al_seleccionar_producto_compra(self, prod):
        self.producto_seleccionado_compra = prod
        self.txt_compra_costo.value = str(prod["precio_costo"])
        self.txt_compra_cant.value = "1"
        self.pagina.update()

    def _agregar_item_a_compra(self, e):
        p = self.producto_seleccionado_compra
        if not p:
            self.mostrar_mensaje("Busca y selecciona un producto primero", ft.Colors.RED_600)
            return

        try:
            cant = float(self.txt_compra_cant.value)
            costo = float(self.txt_compra_costo.value)
            if cant <= 0 or costo < 0:
                self.mostrar_mensaje("Cantidad y costo deben ser mayores a cero", ft.Colors.RED_600)
                return
        except ValueError:
            self.mostrar_mensaje("Ingresa valores numéricos válidos", ft.Colors.RED_600)
            return

        self.items_nueva_compra.append({
            "id_producto": p["id_producto"],
            "nombre": p["nombre"],
            "tipo_unidad": p["tipo_unidad"],
            "cantidad": cant,
            "precio_costo_unitario": costo,
            "subtotal": cant * costo,
        })

        self.buscador_prod_compra.limpiar_seleccion()
        self.producto_seleccionado_compra = None
        self.txt_compra_cant.value = "1"
        self.txt_compra_costo.value = "0.0"
        self._refrescar_tabla_items_compra()

    def _refrescar_tabla_items_compra(self):
        self.tabla_items_compra.rows.clear()
        tot = 0.0

        for idx, it in enumerate(self.items_nueva_compra):
            tot += it["subtotal"]
            btn_quitar = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_600,
                on_click=lambda e, i=idx: (self.items_nueva_compra.pop(i), self._refrescar_tabla_items_compra()),
            )
            self.tabla_items_compra.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(it["nombre"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"{it['cantidad']} {it['tipo_unidad']}")),
                        ft.DataCell(ft.Text(f"${it['precio_costo_unitario']:.2f}")),
                        ft.DataCell(ft.Text(f"${it['subtotal']:.2f}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(btn_quitar),
                    ]
                )
            )

        self.lbl_total_nueva_compra.value = f"${tot:.2f}"
        self.pagina.update()

    def abrir_detalle_compra(self, id_compra: int):
        data = obtener_detalle_compra_por_id(id_compra)
        compra = data.get("compra")
        detalles = data.get("detalles", [])

        if not compra:
            self.mostrar_mensaje("No se pudo cargar la información de la compra", ft.Colors.RED_600)
            return

        self.lbl_compra_id.value = f"Entrada / Compra #{compra['id_compra']}"
        self.lbl_compra_fecha.value = f"📅 {compra['fecha_hora']}"
        self.lbl_compra_proveedor.value = f"🏢 Proveedor: {compra['proveedor']} | Tel: {compra['telefono'] or 'N/A'}"
        self.lbl_compra_total.value = f"${compra['total']:.2f}"

        self.tabla_detalles_compra.rows.clear()
        for art in detalles:
            self.tabla_detalles_compra.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{art['cantidad']} {art['tipo_unidad']}")),
                        ft.DataCell(ft.Text(art["nombre"], weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(f"${art['precio_costo_unitario']:.2f}")),
                        ft.DataCell(ft.Text(f"${art['subtotal']:.2f}", weight=ft.FontWeight.BOLD)),
                    ]
                )
            )

        self.modal_detalle.abrir()

    def abrir_modal_nueva_compra(self):
        provs = obtener_todos_los_proveedores()
        if not provs:
            self.mostrar_mensaje("Registra primero un proveedor en el catálogo de la derecha", ft.Colors.ORANGE_800)
            return

        self.items_nueva_compra.clear()
        self.proveedor_seleccionado_compra = None
        self.producto_seleccionado_compra = None
        self.buscador_prov_compra.limpiar_seleccion()
        self.buscador_prod_compra.limpiar_seleccion()
        self._refrescar_tabla_items_compra()
        self.modal_nueva_compra.abrir()

    def _guardar_compra_final(self, e):
        if not self.proveedor_seleccionado_compra:
            self.mostrar_mensaje("Selecciona la empresa proveedora", ft.Colors.RED_600)
            return

        if not self.items_nueva_compra:
            self.mostrar_mensaje("Agrega al menos un producto a la compra", ft.Colors.RED_600)
            return

        try:
            id_prov = self.proveedor_seleccionado_compra["id_proveedor"]
            id_c = registrar_compra_mercancia(id_prov, self.items_nueva_compra)
            self.modal_nueva_compra.cerrar()
            self.cargar_datos()
            self.mostrar_mensaje(f"Entrada #{id_c} registrada. Stock e inventario actualizados", ft.Colors.GREEN_700)
        except Exception as err:
            self.mostrar_mensaje(f"Error al registrar: {err}", ft.Colors.RED_600)

    def abrir_modal_nuevo_prov(self):
        self.id_proveedor_editar = None
        self.modal_proveedor.lbl_titulo.value = "Nuevo Proveedor"
        self.txt_prov_empresa.value = ""
        self.txt_prov_contacto.value = ""
        self.txt_prov_telefono.value = ""
        self.modal_proveedor.abrir()

    def abrir_modal_editar_prov(self, p_data):
        self.id_proveedor_editar = p_data["id_proveedor"]
        self.modal_proveedor.lbl_titulo.value = f"Editar: {p_data['nombre_empresa']}"
        self.txt_prov_empresa.value = p_data["nombre_empresa"]
        self.txt_prov_contacto.value = p_data["contacto_nombre"] or ""
        self.txt_prov_telefono.value = p_data["telefono"] or ""
        self.modal_proveedor.abrir()

    def _guardar_proveedor(self, e):
        emp = self.txt_prov_empresa.value.strip() if self.txt_prov_empresa.value else ""
        cont = self.txt_prov_contacto.value.strip() if self.txt_prov_contacto.value else ""
        tel = self.txt_prov_telefono.value.strip() if self.txt_prov_telefono.value else ""

        if not emp:
            self.mostrar_mensaje("El nombre de la empresa es obligatorio", ft.Colors.RED_600)
            return

        try:
            if self.id_proveedor_editar is None:
                agregar_proveedor(emp, cont, tel)
                self.mostrar_mensaje(f"Proveedor '{emp}' registrado", ft.Colors.GREEN_700)
            else:
                actualizar_proveedor(self.id_proveedor_editar, emp, cont, tel)
                self.mostrar_mensaje("Proveedor actualizado", ft.Colors.GREEN_700)

            self.modal_proveedor.cerrar()
            self.cargar_datos()
        except Exception as err:
            self.mostrar_mensaje(f"Error: {err}", ft.Colors.RED_600)