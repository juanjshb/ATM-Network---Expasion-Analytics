from __future__ import annotations


PROVINCE_REGION_MAP = {
    "distrito nacional": ("Distrito Nacional", "Ozama"),
    "santo domingo": ("Santo Domingo", "Ozama"),
    "santiago": ("Santiago", "Cibao Norte"),
    "la altagracia": ("La Altagracia", "Yuma"),
    "punta cana": ("La Altagracia", "Yuma"),
    "higuey": ("La Altagracia", "Yuma"),
    "la romana": ("La Romana", "Yuma"),
    "san pedro de macoris": ("San Pedro de Macoris", "Higuamo"),
    "san cristobal": ("San Cristobal", "Valdesia"),
    "puerto plata": ("Puerto Plata", "Cibao Norte"),
    "la vega": ("La Vega", "Cibao Sur"),
    "moca": ("Espaillat", "Cibao Norte"),
    "bonao": ("Monsenor Nouel", "Cibao Sur"),
    "san francisco de macoris": ("Duarte", "Cibao Nordeste"),
    "bani": ("Peravia", "Valdesia"),
    "azua": ("Azua", "Valdesia"),
}


def infer_province_region(*parts: str | None) -> tuple[str | None, str | None]:
    text = " ".join(part or "" for part in parts).lower()
    for keyword, value in PROVINCE_REGION_MAP.items():
        if keyword in text:
            return value
    return None, None

