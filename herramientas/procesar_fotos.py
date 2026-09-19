"""Recorta el fondo blanco de las fotos de estudio y genera .webp + .png.

Uso:
    python herramientas/procesar_fotos.py mayonesa limon parrillada

Para cada nombre lee  originales/<nombre>-frente-nuevo.png
y escribe en la raiz  <nombre>.webp  y  <nombre>.png

El fondo se quita por relleno desde los bordes, no por color: las bolsas de
Carita Feliz y Fosforito tienen blanco propio en el diseno y un filtro por
color se los borraria dejando huecos.
"""
from PIL import Image, ImageFilter
import numpy as np
from collections import deque
import sys, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALTO_FINAL = 1000          # alto de salida, igual para todos
# El fondo de estudio es blanco puro exacto (255,255,255) y el blanco propio de
# las bolsas nunca sube de 249. Con tolerancia alta el relleno se comia Carita
# Feliz entera, asi que se deja apenas en 2: solo el blanco perfecto es fondo.
TOLERANCIA = 2
PADDING = 6                # margen transparente que se deja alrededor


def _rellenar(mask, semillas):
    """Marca la region de `mask` conectada a las semillas (relleno por lineas)."""
    h, w = mask.shape
    visto = np.zeros((h, w), dtype=bool)
    pila = deque(semillas)
    while pila:
        x, y = pila.pop()
        if visto[y, x] or not mask[y, x]:
            continue
        # se expande el tramo horizontal completo de una vez
        xi = x
        while xi > 0 and mask[y, xi - 1] and not visto[y, xi - 1]:
            xi -= 1
        xd = x
        while xd < w - 1 and mask[y, xd + 1] and not visto[y, xd + 1]:
            xd += 1
        visto[y, xi:xd + 1] = True
        for vy in (y - 1, y + 1):
            if 0 <= vy < h:
                pend = np.where(mask[vy, xi:xd + 1] & ~visto[vy, xi:xd + 1])[0]
                if pend.size:
                    # basta un punto por tramo contiguo
                    cortes = np.where(np.diff(pend) > 1)[0]
                    for idx in np.split(pend, cortes + 1):
                        pila.append((xi + int(idx[0]), vy))
    return visto


def procesar(origen, destino_id):
    im = Image.open(origen).convert('RGB')
    a = np.asarray(im).astype(np.int16)
    h, w = a.shape[:2]

    # 1. fondo = blanco casi puro conectado con el borde (el interior no se toca)
    casi_blanco = (255 - a).max(axis=2) <= TOLERANCIA
    bordes = ([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] +
              [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    fondo = _rellenar(casi_blanco, bordes)

    # 2. de lo que queda, solo la mancha grande: se descartan motas sueltas
    objeto = ~fondo
    principal = _rellenar(objeto, [(w // 2, h // 2)]) if objeto[h // 2, w // 2] else objeto

    # 3. se encoge 2px y se suaviza: con tolerancia baja queda una orla de
    #    antialiasing blanquecina en el contorno, y sobre negro se notaria
    capa = Image.fromarray(np.where(principal, 255, 0).astype(np.uint8), 'L')
    capa = capa.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
    salida = im.convert('RGBA')
    salida.putalpha(capa)

    # 4. recorte al contenido, con un poco de aire
    x0, y0, x1, y1 = capa.point(lambda v: 255 if v > 8 else 0).getbbox()
    salida = salida.crop((max(0, x0 - PADDING), max(0, y0 - PADDING),
                          min(w, x1 + PADDING), min(h, y1 + PADDING)))

    # 5. escala a alto fijo para que todos pesen y midan parejo
    ratio = ALTO_FINAL / salida.height
    salida = salida.resize((round(salida.width * ratio), ALTO_FINAL), Image.LANCZOS)

    ruta_webp = os.path.join(RAIZ, destino_id + '.webp')
    ruta_png = os.path.join(RAIZ, destino_id + '.png')
    salida.save(ruta_webp, 'WEBP', quality=82, method=6)
    salida.quantize(colors=256, method=Image.FASTOCTREE).save(ruta_png, optimize=True)
    return salida.size, os.path.getsize(ruta_webp) // 1024, os.path.getsize(ruta_png) // 1024


if __name__ == '__main__':
    nombres = sys.argv[1:]
    if not nombres:
        sys.exit(__doc__)
    print(f'{"archivo":20} {"medidas":>12}  {"webp":>7} {"png":>7}')
    for n in nombres:
        origen = os.path.join(RAIZ, 'originales', f'{n}-frente-nuevo.png')
        if not os.path.exists(origen):
            print(f'{n:20} FALTA {origen}')
            continue
        (ancho, alto), kw, kp = procesar(origen, n)
        print(f'{n:20} {ancho:5}x{alto:<6} {kw:5} KB {kp:5} KB')
        sys.stdout.flush()
