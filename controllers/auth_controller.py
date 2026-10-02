from typing import Optional
from database.usuarios_db import validar_login


class AuthController:
    """Controlador que gestiona la sesión activa del usuario y sus permisos."""

    def __init__(self):
        self.id_empleado: Optional[int] = None
        self.nombre_completo: str = ""
        self.usuario: str = ""
        self.puesto: str = ""

    @property
    def esta_autenticado(self) -> bool:
        return self.id_empleado is not None

    @property
    def es_admin(self) -> bool:
        return self.puesto == "Administrador"

    def iniciar_sesion(self, usuario: str, password_texto: str) -> bool:
        """Valida credenciales contra la base de datos y establece la sesión."""
        usuario_limpio = usuario.strip()
        pwd_limpia = password_texto.strip()

        if not usuario_limpio or not pwd_limpia:
            return False

        registro = validar_login(usuario_limpio, pwd_limpia)
        if registro:
            self.id_empleado = registro["id_empleado"]
            self.nombre_completo = f"{registro['nombre']} {registro['apellido']}"
            self.puesto = registro["puesto"]
            self.usuario = usuario_limpio
            return True

        return False

    def cerrar_sesion(self):
        """Limpia los datos del empleado activo."""
        self.id_empleado = None
        self.nombre_completo = ""
        self.usuario = ""
        self.puesto = ""