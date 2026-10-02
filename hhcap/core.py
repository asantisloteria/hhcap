"""Estado, configuración y cálculo de jornada. Solo stdlib (Python >= 3.8)."""
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from .festivos import festivos_chile

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]

CONFIG_DEFAULT = {
    "jornada": {
        "lun": ["08:15", "17:45"],
        "mar": ["08:15", "17:45"],
        "mie": ["08:15", "17:45"],
        "jue": ["08:15", "17:45"],
        "vie": ["08:15", "13:35"],
    },
    "festivos_extra": [],
    "festivos_quitar": [],
    "idle_minutos": 15,
    "extra_max_horas": 14,
}

EN_HORARIO = "en_horario"
FUERA_SIN_MARCA = "fuera_sin_marca"
EXTRA_ABIERTA = "extra_abierta"
EXTRA_POR_CERRAR = "extra_por_cerrar"


def home():
    return Path(os.environ.get("HHCAP_HOME") or Path.home() / ".hhcap")


def ahora():
    v = os.environ.get("HHCAP_NOW")
    if v:
        return datetime.fromisoformat(v).replace(tzinfo=None, microsecond=0)
    real = datetime.now().replace(microsecond=0)
    sim = simulacion(real)
    return real + timedelta(seconds=sim["desfase"]) if sim else real


def simulacion(real=None):
    """Desfase de reloj activo (`hhcap simular`), o None. Vence solo."""
    real = real or datetime.now()
    try:
        with open(home() / "simulacion.json", encoding="utf-8") as f:
            sim = json.load(f)
    except (FileNotFoundError, ValueError):
        return None
    return sim if real < datetime.fromisoformat(sim["vence"]) else None


def _leer_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _escribir_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(p))


def cargar_config():
    cfg = dict(CONFIG_DEFAULT)
    cfg.update(_leer_json(home() / "config.json", {}))
    return cfg


def guardar_config(cfg):
    _escribir_json(home() / "config.json", cfg)


def cargar_state():
    return _leer_json(home() / "state.json", {"extra": None})


def guardar_state(st):
    _escribir_json(home() / "state.json", st)


def registrar(evento, **datos):
    p = home() / "events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    datos = {"ts": ahora().isoformat(), "evento": evento, **datos}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(datos, ensure_ascii=False) + "\n")


def leer_eventos():
    p = home() / "events.jsonl"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# --- Jornada ---------------------------------------------------------------

def _hm(s, d):
    h, m = s.split(":")
    return datetime.combine(d, datetime.min.time()).replace(hour=int(h), minute=int(m))


def es_festivo(d, cfg):
    if d.isoformat() in cfg.get("festivos_quitar", []):
        return False
    return d in festivos_chile(d.year) or d.isoformat() in cfg.get("festivos_extra", [])


def jornada_del_dia(d, cfg):
    """(inicio, fin) de la jornada de ese día, o None si no es hábil."""
    j = cfg["jornada"].get(DIAS[d.weekday()])
    if not j or es_festivo(d, cfg):
        return None
    return _hm(j[0], d), _hm(j[1], d)


def tipo_extra(d, cfg):
    return "50%" if cfg["jornada"].get(DIAS[d.weekday()]) and not es_festivo(d, cfg) else "100%"


def en_jornada(t, cfg):
    j = jornada_del_dia(t.date(), cfg)
    return bool(j and j[0] <= t < j[1])


def tramos_extra(inicio, fin, cfg):
    """Parte [inicio, fin) en tramos fuera de jornada, cortando en medianoche y en la jornada.

    Devuelve [(desde, hasta, tipo)]."""
    out = []
    t = inicio
    while t < fin:
        d = t.date()
        corte = min(fin, datetime.combine(d + timedelta(days=1), datetime.min.time()))
        j = jornada_del_dia(d, cfg)
        piezas = [(t, corte)]
        if j:
            piezas = [(a, b) for a, b in [(t, min(corte, j[0])), (max(t, j[1]), corte)] if a < b]
        tipo = tipo_extra(d, cfg)
        out.extend((a, b, tipo) for a, b in piezas)
        t = corte
    return out


# --- Estado ----------------------------------------------------------------

def _extra_vencida(extra, t, cfg):
    return t - datetime.fromisoformat(extra["inicio"]) > timedelta(hours=cfg["extra_max_horas"])


def calcular(t=None, cfg=None, st=None):
    t = t or ahora()
    cfg = cfg or cargar_config()
    st = st if st is not None else cargar_state()
    extra = st.get("extra")
    r = {"ahora": t.isoformat(), "tipo": tipo_extra(t.date(), cfg), "extra": extra, "aviso": None}
    j = jornada_del_dia(t.date(), cfg)
    if j:
        r["jornada"] = [j[0].strftime("%H:%M"), j[1].strftime("%H:%M")]

    if extra and _extra_vencida(extra, t, cfg):
        r["aviso"] = ("Hay una hora extra abierta desde %s sin salida confirmada. "
                      "Ciérrala con `hhcap marque-salida --a HH:MM` o quedará como salida sin confirmar." % extra["inicio"][:16].replace("T", " "))
        extra = None
        r["extra_vencida"] = True

    if en_jornada(t, cfg):
        r["estado"] = EN_HORARIO
        if extra:
            r["aviso"] = "Hora extra abierta desde %s: confirma la salida con `hhcap marque-salida`." % extra["inicio"][11:16]
    elif extra:
        r["estado"] = EXTRA_POR_CERRAR if extra.get("por_cerrar") else EXTRA_ABIERTA
        r["minutos"] = int((t - datetime.fromisoformat(extra["inicio"])).total_seconds() // 60)
    else:
        r["estado"] = FUERA_SIN_MARCA
    return r


def _parse_hora(s, t):
    """'HH:MM' -> datetime de hoy (o de ayer si quedaría en el futuro); también acepta ISO."""
    if "T" in s or len(s) > 5:
        return datetime.fromisoformat(s).replace(tzinfo=None, microsecond=0)
    v = _hm(s, t.date())
    return v - timedelta(days=1) if v > t else v


def marcar_entrada(hora=None):
    t = ahora()
    cfg, st = cargar_config(), cargar_state()
    r = calcular(t, cfg, st)
    if r.get("extra_vencida"):
        cerrar_extra(st, t, olvidada=True)
    elif st.get("extra"):
        return False, "Ya hay una hora extra abierta desde %s." % st["extra"]["inicio"][11:16]
    inicio = _parse_hora(hora, t) if hora else t
    if en_jornada(inicio, cfg) and en_jornada(t, cfg):
        return False, "Estás dentro de la jornada; no corresponde abrir hora extra."
    st["extra"] = {"inicio": inicio.isoformat(), "confirmado_en": t.isoformat()}
    guardar_state(st)
    registrar("confirma_entrada", inicio=inicio.isoformat())
    return True, "Hora extra abierta desde %s (%s)." % (inicio.strftime("%H:%M"), tipo_extra(inicio.date(), cfg))


def cerrar_extra(st, t, fin=None, olvidada=False):
    extra = st["extra"]
    datos = {"inicio": extra["inicio"], "fin": fin.isoformat() if fin else None}
    if olvidada:
        datos["motivo"] = "olvidada"
    registrar("confirma_salida", **datos)
    st["extra"] = None
    guardar_state(st)


def marcar_salida(hora=None):
    t = ahora()
    cfg, st = cargar_config(), cargar_state()
    extra = st.get("extra")
    if not extra:
        return False, "No hay hora extra abierta."
    if hora:
        fin = _parse_hora(hora, t)
    elif extra.get("por_cerrar") and extra.get("ultimo_uso"):
        fin = datetime.fromisoformat(extra["ultimo_uso"])
    else:
        fin = t
    inicio = datetime.fromisoformat(extra["inicio"])
    if fin <= inicio:
        return False, "La salida (%s) no puede ser anterior a la entrada (%s)." % (fin, inicio)
    cerrar_extra(st, t, fin)
    mins = sum((b - a).total_seconds() for a, b, _ in tramos_extra(inicio, fin, cfg)) // 60
    return True, "Hora extra cerrada: %s → %s (%s fuera de jornada)." % (
        inicio.strftime("%d/%m %H:%M"), fin.strftime("%H:%M"), fmt_min(mins))


def fmt_min(m):
    m = int(m)
    return "%d:%02d" % (m // 60, m % 60)


# --- Reporte ---------------------------------------------------------------

def bloques_semana(dia):
    """Bloques cerrados con inicio en la semana (lun-dom) que contiene `dia`."""
    lunes = dia - timedelta(days=dia.weekday())
    desde = datetime.combine(lunes, datetime.min.time())
    hasta = desde + timedelta(days=7)
    cfg = cargar_config()
    filas = []
    for e in leer_eventos():
        if e["evento"] != "confirma_salida":
            continue
        ini = datetime.fromisoformat(e["inicio"])
        if not (desde <= ini < hasta):
            continue
        if not e.get("fin"):
            filas.append({"fecha": ini.date().isoformat(), "desde": ini.strftime("%H:%M"), "hasta": None,
                          "minutos": None, "tipo": tipo_extra(ini.date(), cfg), "nota": "salida sin confirmar"})
            continue
        for a, b, tipo in tramos_extra(ini, datetime.fromisoformat(e["fin"]), cfg):
            filas.append({"fecha": a.date().isoformat(), "desde": a.strftime("%H:%M"),
                          "hasta": "24:00" if b.time() == datetime.min.time() and b > a else b.strftime("%H:%M"),
                          "minutos": int((b - a).total_seconds() // 60), "tipo": tipo, "nota": ""})
    return lunes, filas
