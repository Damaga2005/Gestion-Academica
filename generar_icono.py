"""
Genera el icono propio de la app (icono.ico) con Pillow: un gorro de graduación
simple sobre fondo azul, en varias resoluciones. No depende de fuentes del
sistema (todo son formas geométricas), así que es reproducible en cualquier
máquina donde se quiera reempaquetar la app.

Ejecutar con: python generar_icono.py
"""

import os

from PIL import Image, ImageDraw

TAMANO_BASE = 1024
COLOR_FONDO = "#0071e3"   # --ds-color-accent de static/css/design-system.css
COLOR_GORRO = "#f5f5f7"   # --ds-color-background (claro) / --ds-color-text-primary (oscuro)
COLOR_BORLA = "#ff9f0a"   # --ds-color-warning de static/css/design-system.css


def dibujar_icono():
    img = Image.new("RGBA", (TAMANO_BASE, TAMANO_BASE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margen = int(TAMANO_BASE * 0.04)
    draw.rounded_rectangle(
        [margen, margen, TAMANO_BASE - margen, TAMANO_BASE - margen],
        radius=int(TAMANO_BASE * 0.18),
        fill=COLOR_FONDO,
    )

    cx, cy = TAMANO_BASE // 2, int(TAMANO_BASE * 0.40)
    w, h = int(TAMANO_BASE * 0.34), int(TAMANO_BASE * 0.17)

    # Base del gorro (semiesfera bajo el rombo, la parte que cubre la cabeza)
    draw.ellipse(
        [cx - w * 0.62, cy + h * 0.15, cx + w * 0.62, cy + h * 1.55],
        fill=COLOR_GORRO,
    )

    # Rombo plano superior (mortarboard)
    draw.polygon(
        [(cx, cy - h), (cx + w, cy), (cx, cy + h), (cx - w, cy)],
        fill=COLOR_GORRO,
    )

    # Borla: cordón + bolita, cayendo desde el centro del rombo
    borla_x0, borla_y0 = cx, cy
    borla_x1, borla_y1 = cx + int(w * 0.55), cy + int(h * 2.6)
    draw.line([(borla_x0, borla_y0), (borla_x1, borla_y1)], fill=COLOR_BORLA, width=int(TAMANO_BASE * 0.018))
    radio_bolita = int(TAMANO_BASE * 0.035)
    draw.ellipse(
        [borla_x1 - radio_bolita, borla_y1 - radio_bolita, borla_x1 + radio_bolita, borla_y1 + radio_bolita],
        fill=COLOR_BORLA,
    )

    return img


def main():
    img = dibujar_icono()

    directorio = os.path.abspath(os.path.dirname(__file__))
    ruta_png = os.path.join(directorio, "icono_preview.png")
    ruta_ico = os.path.join(directorio, "icono.ico")

    img.save(ruta_png)
    img.save(
        ruta_ico,
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Generado {ruta_ico} y {ruta_png}")


if __name__ == "__main__":
    main()
