"""Hooks de Claude Code. Fallan abierto: ante cualquier error no bloquean."""
import json
import sys

# Claude Code no interpreta colores ANSI en stopReason: se muestran como texto. Sin colores.
R = A = V = C = G = B = X = ""

BLOQUEO = ("{B}{R}⏰ Fuera de horario{X} {A}· horas extras al {tipo}{X}\n"
           "\n"
           "  {V}✔ ¿Ya marcaste en GeoVictoria?{X}   {B}{C}! hhcap marque-entrada{X}\n"
           "  {A}◷ ¿Marcaste a otra hora?{X}         {C}! hhcap marque-entrada --a HH:MM{X}\n"
           "  {C}☾ ¿No vas a trabajar, solo usar la IA?{X}  {C}! hhcap uso-personal{X}\n"
           "  {G}✘ ¿No has marcado? Hazlo primero en la app de GeoVictoria.{X}")


def _avisar_menu(tipo):
    """HHCap.app vigila este archivo: despliega el globo bajo la pastilla y envía la notificación."""
    from .core import _escribir_json, ahora, home
    _escribir_json(home() / "bloqueo.json", {"ts": ahora().isoformat(), "tipo": tipo})


def _leer_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def prompt():
    """UserPromptSubmit: bloquea si estamos fuera de horario sin hora extra abierta."""
    from .core import FUERA_SIN_MARCA, calcular
    data = _leer_stdin()
    if str(data.get("prompt", "")).lstrip().startswith("!"):
        return
    r = calcular()
    if r["estado"] == FUERA_SIN_MARCA:
        reason = BLOQUEO.format(tipo=r["tipo"], R=R, A=A, V=V, C=C, G=G, B=B, X=X)
        if r.get("aviso"):
            reason += "\n  " + A + "⚠ " + r["aviso"] + X
        from .core import simulacion
        if simulacion():
            reason += "\n  " + G + "[simulado: %s · ! hhcap simular --off]" % r["ahora"][11:16] + X
        _avisar_menu(r["tipo"])
        print(json.dumps({"continue": False, "stopReason": reason}, ensure_ascii=False))
    elif r.get("aviso"):
        print(json.dumps({"systemMessage": r["aviso"]}, ensure_ascii=False))


def session():
    """SessionStart: solo avisa, nunca bloquea."""
    from .core import EXTRA_ABIERTA, EXTRA_POR_CERRAR, FUERA_SIN_MARCA, USO_PERSONAL, calcular, fmt_min
    _leer_stdin()
    r = calcular()
    msg = None
    if r["estado"] == FUERA_SIN_MARCA:
        msg = "⏰ Fuera de horario: marca entrada en GeoVictoria y ejecuta `! hhcap marque-entrada` antes de seguir."
    elif r["estado"] == EXTRA_ABIERTA:
        msg = "🟡 Hora extra abierta desde %s (%s)." % (r["extra"]["inicio"][11:16], fmt_min(r["minutos"]))
    elif r["estado"] == EXTRA_POR_CERRAR:
        msg = "🟠 Hora extra pendiente de cierre: marca salida en GeoVictoria y ejecuta `! hhcap marque-salida`."
    elif r["estado"] == USO_PERSONAL:
        msg = ("🔵 Uso personal hasta las %s: la IA no cuenta como hora extra. "
               "Si vas a trabajar, marca entrada y ejecuta `! hhcap marque-entrada`." % r["personal"]["hasta"][11:16])
    if r.get("aviso"):
        msg = (msg + "\n" if msg else "") + r["aviso"]
    if msg:
        print(json.dumps({"systemMessage": msg}, ensure_ascii=False))


def main(evento):
    try:
        {"prompt": prompt, "session": session}[evento]()
    except Exception as e:  # fail-open
        try:
            sys.stderr.write("hhcap hook: %s\n" % e)
        except Exception:
            pass
    return 0


# --- Instalación en ~/.claude/settings.json ---------------------------------

def hooks_config(cmd):
    return {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": cmd + " hook prompt", "timeout": 5}]}],
        "SessionStart": [{"hooks": [{"type": "command", "command": cmd + " hook session", "timeout": 5}]}],
    }


def fusionar(settings, cmd):
    """Agrega los hooks de hhcap sin tocar los demás; idempotente."""
    hooks = settings.setdefault("hooks", {})
    for evento, entradas in hooks_config(cmd).items():
        actuales = [g for g in hooks.get(evento, [])
                    if not any("hhcap" in h.get("command", "") for h in g.get("hooks", []))]
        hooks[evento] = actuales + entradas
    return settings


def quitar(settings):
    hooks = settings.get("hooks", {})
    for evento in ("UserPromptSubmit", "SessionStart"):
        if evento in hooks:
            hooks[evento] = [g for g in hooks[evento]
                             if not any("hhcap" in h.get("command", "") for h in g.get("hooks", []))]
            if not hooks[evento]:
                del hooks[evento]
    if not hooks:
        settings.pop("hooks", None)
    return settings
