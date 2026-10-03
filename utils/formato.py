from typing import Union


def formatear_stock(stock: Union[float, int, str], unidad: str = "kg") -> str:
    """
    Formatea cantidades de stock eliminando imprecisiones de coma flotante (IEEE 754).
    Ejemplos:
      - 5.0 -> '5 kg' o '5 pza'
      - 4.9299999999999999 -> '4.93 kg'
      - 0.400 -> '0.4 kg'
    """
    try:
        val = round(float(stock), 3)
    except (ValueError, TypeError):
        return f"0 {unidad}".strip()

    if val.is_integer():
        return f"{int(val)} {unidad}".strip()
    
    # Formatea a 3 decimales quitando ceros innecesarios al final
    val_str = f"{val:.3f}".rstrip("0").rstrip(".")
    return f"{val_str} {unidad}".strip()