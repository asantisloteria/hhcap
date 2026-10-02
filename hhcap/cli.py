import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Camino rápido para los hooks: sin argparse.
    if len(argv) == 2 and argv[0] == "hook" and argv[1] in ("prompt", "session"):
        from .hook import main as hook_main
        return hook_main(argv[1])
    if argv[:2] == ["status", "--hook"]:
        from .hook import main as hook_main
        return hook_main("prompt")
    return _cli(argv)


def _cli(argv):
    import argparse
    import json
    import os
    import shutil
    from datetime import date
    from pathlib import Path

    from . import __version__, core

    ap = argparse.ArgumentParser(prog="hhcap", description="Captador de horas extras.")
    ap.add_argument("--version", action="version", version="hhcap " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("status", help="estado actual")
    s.add_argument("--json", action="store_true")
    s.add_argument("--hook", action="store_true", help="modo hook UserPromptSubmit")

    for nombre, ayuda in (("marque-entrada", "ya marqué entrada en GeoVictoria"),
                          ("marque-salida", "ya marqué salida en GeoVictoria")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--a", metavar="HH:MM", help="hora real de la marca (por defecto: ahora)")
        p.add_argument("--motivo", help="justificación (va al Comentario de SAP)")

    mo = sub.add_parser("motivo", help="justificación de la hora extra abierta o del último bloque")
    mo.add_argument("texto")
    mo.add_argument("--bloque", metavar="YYYY-MM-DDTHH:MM", help="inicio del bloque a corregir")

    c = sub.add_parser("config", help="ver/editar config.json")
    c.add_argument("--jornada", metavar="DIA=HH:MM-HH:MM", action="append",
                   help="ej. vie=08:15-13:35; DIA= (vacío) lo deja como no hábil")
    c.add_argument("--festivo", metavar="YYYY-MM-DD", action="append", help="agrega festivo extra")
    c.add_argument("--no-festivo", metavar="YYYY-MM-DD", action="append", help="anula un festivo calculado")
    c.add_argument("--set", metavar="CLAVE=VALOR", action="append", help="idle_minutos, extra_max_horas")
    c.add_argument("--path", action="store_true", help="muestra la carpeta de datos")

    r = sub.add_parser("reporte", help="reporte de horas extras confirmadas")
    r.add_argument("--semana", action="store_true", help="semana lun-dom (por defecto)")
    r.add_argument("--fecha", help="un día de la semana a reportar (YYYY-MM-DD); por defecto hoy")
    r.add_argument("--csv", action="store_true")
    r.add_argument("--mes", action="store_true", help="el mes que contiene --fecha")
    r.add_argument("--desde", help="YYYY-MM-DD (con --hasta)")
    r.add_argument("--hasta", help="YYYY-MM-DD")
    r.add_argument("--json", action="store_true")
    r.add_argument("-o", "--salida", help="escribe el CSV en este archivo (UTF-8 con BOM, ';', para Excel)")

    f = sub.add_parser("festivos", help="lista los festivos del año")
    f.add_argument("--anio", type=int)

    h = sub.add_parser("hook", help="hooks de Claude Code")
    h.add_argument("accion", choices=["prompt", "session", "install", "uninstall", "print"])
    h.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))

    sub.add_parser("menu", help="abre el indicador de barra de menú / bandeja")

    sub.add_parser("update", help="actualiza hhcap a la última versión publicada")

    sm = sub.add_parser("simular", help="adelanta el reloj de hhcap para probar (vence solo)")
    sm.add_argument("hora", nargs="?", help="HH:MM o YYYY-MM-DDTHH:MM; sin argumento muestra el estado")
    sm.add_argument("--minutos", type=int, default=30, help="duración de la simulación (default 30)")
    sm.add_argument("--off", action="store_true", help="termina la simulación")

    a = ap.parse_args(argv)
    if not a.cmd:
        a.cmd, a.json, a.hook = "status", False, False

    if a.cmd == "status":
        if a.hook:
            from .hook import main as hook_main
            return hook_main("prompt")
        st = core.calcular()
        if a.json:
            print(json.dumps(st, ensure_ascii=False))
        else:
            print(_texto_estado(st, core))
        return 0

    if a.cmd in ("marque-entrada", "marque-salida"):
        fn = core.marcar_entrada if a.cmd == "marque-entrada" else core.marcar_salida
        ok, msg = fn(a.a, a.motivo)
        print(msg)
        return 0 if ok else 1

    if a.cmd == "motivo":
        ok, msg = core.poner_motivo(a.texto, a.bloque)
        print(msg)
        return 0 if ok else 1

    if a.cmd == "config":
        cfg = core.cargar_config()
        if a.path:
            print(core.home())
            return 0
        cambiado = False
        for j in a.jornada or []:
            dia, _, rango = j.partition("=")
            if dia not in core.DIAS:
                ap.error("día inválido: %s (usa %s)" % (dia, ", ".join(core.DIAS)))
            if rango:
                cfg["jornada"][dia] = rango.split("-")
            else:
                cfg["jornada"].pop(dia, None)
            cambiado = True
        for d in a.festivo or []:
            date.fromisoformat(d)
            cfg["festivos_extra"] = sorted(set(cfg["festivos_extra"]) | {d})
            cambiado = True
        for d in a.no_festivo or []:
            date.fromisoformat(d)
            cfg["festivos_quitar"] = sorted(set(cfg["festivos_quitar"]) | {d})
            cambiado = True
        for kv in a.set or []:
            k, _, v = kv.partition("=")
            if k not in ("idle_minutos", "extra_max_horas"):
                ap.error("clave no editable: %s" % k)
            cfg[k] = int(v)
            cambiado = True
        if cambiado:
            core.guardar_config(cfg)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "reporte":
        from datetime import timedelta
        dia = date.fromisoformat(a.fecha) if a.fecha else core.ahora().date()
        if a.desde and a.hasta:
            d1, d2 = date.fromisoformat(a.desde), date.fromisoformat(a.hasta)
            titulo = "Del %s al %s" % (d1.strftime("%d/%m/%Y"), d2.strftime("%d/%m/%Y"))
        elif a.mes:
            d1 = dia.replace(day=1)
            d2 = (d1 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            titulo = "Mes %s" % d1.strftime("%m/%Y")
        else:
            d1 = dia - timedelta(days=dia.weekday())
            d2 = d1 + timedelta(days=6)
            titulo = "Semana del %s" % d1.strftime("%d/%m/%Y")
        filas = core.bloques_rango(d1, d2)
        tot = {"50%": 0, "100%": 0}
        for x in filas:
            tot[x["tipo"]] += x["minutos"] or 0
        if a.json:
            dias = [(d1 + timedelta(days=i)).isoformat() for i in range((d2 - d1).days + 1)]
            print(json.dumps({"desde": d1.isoformat(), "hasta": d2.isoformat(), "dias": dias,
                              "filas": filas, "totales": tot}, ensure_ascii=False))
            return 0
        if a.csv or a.salida:
            import csv
            f = open(a.salida, "w", encoding="utf-8-sig", newline="") if a.salida else sys.stdout
            w = csv.writer(f, delimiter=";")
            w.writerow(["fecha", "dia", "desde", "hasta", "duracion", "tipo", "motivo", "nota"])
            for x in filas:
                d = date.fromisoformat(x["fecha"])
                w.writerow([d.strftime("%d-%m-%Y"), core.DIAS[d.weekday()], x["desde"], x["hasta"] or "",
                            core.fmt_min(x["minutos"]) if x["minutos"] is not None else "", x["tipo"], x["motivo"], x["nota"]])
            w.writerow([])
            w.writerow(["total 50%", "", "", "", core.fmt_min(tot["50%"]), "", ""])
            w.writerow(["total 100%", "", "", "", core.fmt_min(tot["100%"]), "", ""])
            if a.salida:
                f.close()
                print("Guardado: %s" % a.salida)
            return 0
        print(titulo)
        if not filas:
            print("  (sin horas extras confirmadas)")
        for x in filas:
            dur = core.fmt_min(x["minutos"]) if x["minutos"] is not None else "  ?  "
            print("  %s  %s–%s  %6s  %4s  %s" % (x["fecha"], x["desde"], x["hasta"] or "?????", dur, x["tipo"],
                                                 " · ".join(v for v in (x["motivo"], x["nota"]) if v)))
        for t in ("50%", "100%"):
            if tot[t]:
                print("  Total %s: %s" % (t, core.fmt_min(tot[t])))
        return 0
    if a.cmd == "festivos":
        from .festivos import festivos_chile
        anio = a.anio or core.ahora().year
        cfg = core.cargar_config()
        fs = dict(festivos_chile(anio))
        for d in cfg["festivos_extra"]:
            if d.startswith(str(anio)):
                fs[date.fromisoformat(d)] = "(config)"
        for d, n in sorted(fs.items()):
            quitado = " [anulado en config]" if d.isoformat() in cfg["festivos_quitar"] else ""
            print("%s %s  %s%s" % (d.isoformat(), core.DIAS[d.weekday()], n, quitado))
        return 0

    if a.cmd == "hook":
        from . import hook
        if a.accion in ("prompt", "session"):
            return hook.main(a.accion)
        cmd = _comando_hhcap()
        if a.accion == "print":
            print(json.dumps({"hooks": hook.hooks_config(cmd)}, ensure_ascii=False, indent=2))
            return 0
        p = Path(a.settings)
        settings = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        # El respaldo se hace una sola vez: guarda la configuración de antes de hhcap.
        if p.exists() and not Path(str(p) + ".bak-hhcap").exists():
            shutil.copy2(str(p), str(p) + ".bak-hhcap")
        settings = hook.fusionar(settings, cmd) if a.accion == "install" else hook.quitar(settings)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if a.accion == "install":
            print(_banner())
        print("%s: %s (respaldo en %s.bak-hhcap)" % ("Hooks instalados" if a.accion == "install" else "Hooks quitados", p, p))
        return 0

    if a.cmd == "menu":
        return _abrir_menu()

    if a.cmd == "update":
        return _actualizar()

    if a.cmd == "simular":
        from datetime import datetime, timedelta
        p = core.home() / "simulacion.json"
        if a.off:
            if p.exists():
                p.unlink()
            print("Simulación terminada. Reloj real: %s" % core.ahora().strftime("%a %d/%m %H:%M"))
            return 0
        if a.hora:
            real = datetime.now().replace(microsecond=0)
            destino = (datetime.fromisoformat(a.hora) if "T" in a.hora
                       else datetime.combine(real.date(), datetime.strptime(a.hora, "%H:%M").time()))
            vence = real + timedelta(minutes=a.minutos)
            core._escribir_json(p, {"desfase": int((destino - real).total_seconds()), "vence": vence.isoformat()})
        sim = core.simulacion()
        if not sim:
            print("Sin simulación activa.")
            return 0
        print("Simulando: reloj de hhcap en %s (vence a las %s reales; `hhcap simular --off` para terminar)" % (
            core.ahora().strftime("%a %d/%m %H:%M"), sim["vence"][11:16]))
        return 0


def _banner():
    from pathlib import Path
    try:
        return (Path(__file__).parent / "banner.txt").read_text(encoding="utf-8")
    except OSError:
        return ""


def _texto_estado(st, core):
    iconos = {core.EN_HORARIO: "🟢 En horario", core.FUERA_SIN_MARCA: "🔴 Fuera de horario, sin marca",
              core.EXTRA_ABIERTA: "🟡 Hora extra abierta", core.EXTRA_POR_CERRAR: "🟠 Hora extra por cerrar"}
    lineas = [iconos[st["estado"]]]
    if core.simulacion():
        lineas[0] += "  [SIMULADO %s]" % st["ahora"][11:16]
    if st.get("jornada"):
        lineas.append("Jornada hoy: %s–%s" % tuple(st["jornada"]))
    else:
        lineas.append("Hoy no es día hábil (horas al 100%)")
    if st["estado"] in (core.EXTRA_ABIERTA, core.EXTRA_POR_CERRAR):
        lineas.append("Desde %s (%s, %s)" % (st["extra"]["inicio"][11:16], core.fmt_min(st["minutos"]), st["tipo"]))
    if st["estado"] == core.FUERA_SIN_MARCA:
        lineas.append("Marca entrada en GeoVictoria y ejecuta: hhcap marque-entrada")
    if st.get("aviso"):
        lineas.append("⚠ " + st["aviso"])
    return "\n".join(lineas)


def _comando_hhcap():
    """Comando absoluto para invocar hhcap desde un hook (no depende del PATH de Claude Code)."""
    import os
    import shutil
    # Sin realpath: /opt/homebrew/bin/hhcap es estable; la ruta del Cellar cambia en cada versión.
    w = shutil.which("hhcap")
    if w:
        return '"%s"' % w if " " in w else w
    exe = sys.executable
    return '"%s" -m hhcap' % exe if " " in exe else "%s -m hhcap" % exe


def _actualizar():
    import os
    import subprocess
    from pathlib import Path
    from . import __version__
    aqui = Path(__file__).resolve()
    if "/Cellar/" in str(aqui):
        pasos = [["brew", "update", "--quiet"], ["brew", "upgrade", "hhcap"]]
    elif (aqui.parents[1] / ".git").exists():
        pasos = [["git", "-C", str(aqui.parents[1]), "pull", "--ff-only"]]
    else:
        pasos = [["pipx", "upgrade", "hhcap"]]
    print("hhcap %s → buscando actualización..." % __version__)
    for p in pasos:
        if subprocess.call(p) != 0:
            print("Falló: %s" % " ".join(p), file=sys.stderr)
            return 1
    if sys.platform == "darwin" and subprocess.call(["pgrep", "-x", "hhcap-menu"], stdout=subprocess.DEVNULL) == 0:
        subprocess.call(["pkill", "-x", "hhcap-menu"])
        _abrir_menu()
    subprocess.call(["hhcap", "--version"])
    return 0


def _abrir_menu():
    import os
    import shutil
    import subprocess
    if sys.platform == "darwin":
        b = shutil.which("hhcap-menu")
        if not b:
            print("No encuentro hhcap-menu en el PATH. Compílalo con: make menu", file=sys.stderr)
            return 1
        subprocess.Popen([b], start_new_session=True)
    elif os.name == "nt":
        ps1 = os.path.join(os.path.dirname(__file__), "tray", "hhcap-tray.ps1")
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
                          "-File", ps1], creationflags=0x08000000)
    else:
        print("Indicador no disponible en esta plataforma.", file=sys.stderr)
        return 1
    return 0
