"""Festivos nacionales de Chile calculados por regla (sin red ni dependencias).

Cubre los feriados nacionales permanentes. Los irrenunciables por elecciones o
feriados regionales se agregan en config.json (`festivos_extra`), y un feriado
calculado mal se puede anular con `festivos_quitar`.
"""
import math
from datetime import date, timedelta
from functools import lru_cache

FIJOS = [(1, 1), (5, 1), (5, 21), (7, 16), (8, 15), (9, 18), (9, 19), (11, 1), (12, 8), (12, 25)]


def _pascua(y):
    # Algoritmo de Meeus/Jones/Butcher (calendario gregoriano).
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, mes, dia)


def _lunes_mas_cercano(d):
    # Ley 19.668: mar/mié/jue -> lunes anterior; vie -> lunes siguiente.
    wd = d.weekday()
    if wd in (1, 2, 3):
        return d - timedelta(days=wd)
    if wd == 4:
        return d + timedelta(days=3)
    return d


def _solsticio_invierno(y):
    # Solsticio de junio (Meeus, cap. 27, años 2000-3000) en hora de Chile (UTC-4).
    t = (y - 2000) / 1000.0
    jde0 = 2451716.56767 + 365241.62603 * t + 0.00325 * t**2 + 0.00888 * t**3 - 0.00030 * t**4
    tc = (jde0 - 2451545.0) / 36525
    w = math.radians(35999.373 * tc - 2.47)
    dl = 1 + 0.0334 * math.cos(w) + 0.0007 * math.cos(2 * w)
    terms = [
        (485, 324.96, 1934.136), (203, 337.23, 32964.467), (199, 342.08, 20.186),
        (182, 27.85, 445267.112), (156, 73.14, 45036.886), (136, 171.52, 22518.443),
        (77, 222.54, 65928.934), (74, 296.72, 3034.906), (70, 243.58, 9037.513),
        (58, 119.81, 33718.147), (52, 297.17, 150.678), (50, 21.02, 2281.226),
        (45, 247.54, 29929.562), (44, 325.15, 31555.956), (29, 60.93, 4443.417),
        (18, 155.12, 67555.328), (17, 288.79, 4562.452), (16, 198.04, 62894.029),
        (14, 199.76, 31436.921), (12, 95.39, 14577.848), (12, 287.11, 31931.756),
        (12, 320.81, 34777.259), (9, 227.73, 1222.114), (8, 15.45, 16859.074),
    ]
    s = sum(a * math.cos(math.radians(b + c * tc)) for a, b, c in terms)
    jde = jde0 + 0.00001 * s / dl - 4 / 24.0  # TT ~ UTC (diferencia de segundos), luego UTC-4
    return date(2000, 1, 1) + timedelta(days=int(math.floor(jde - 2451544.5)))


@lru_cache(maxsize=16)
def festivos_chile(y):
    fs = {date(y, m, d): n for (m, d), n in zip(FIJOS, [
        "Año Nuevo", "Día del Trabajo", "Glorias Navales", "Virgen del Carmen", "Asunción",
        "Independencia", "Glorias del Ejército", "Todos los Santos", "Inmaculada Concepción", "Navidad"])}
    p = _pascua(y)
    fs[p - timedelta(days=2)] = "Viernes Santo"
    fs[p - timedelta(days=1)] = "Sábado Santo"
    fs[_lunes_mas_cercano(date(y, 6, 29))] = "San Pedro y San Pablo"
    fs[_lunes_mas_cercano(date(y, 10, 12))] = "Encuentro de Dos Mundos"
    fs[_solsticio_invierno(y)] = "Pueblos Indígenas"
    ev = date(y, 10, 31)
    if ev.weekday() == 1:
        ev = date(y, 10, 27)
    elif ev.weekday() == 2:
        ev = date(y, 11, 2)
    fs[ev] = "Iglesias Evangélicas"
    if date(y, 1, 1).weekday() == 6:
        fs[date(y, 1, 2)] = "Feriado Año Nuevo"
    if date(y, 9, 18).weekday() == 1:
        fs[date(y, 9, 17)] = "Fiestas Patrias"
    if date(y, 9, 20).weekday() == 4:
        fs[date(y, 9, 20)] = "Fiestas Patrias"
    return fs
