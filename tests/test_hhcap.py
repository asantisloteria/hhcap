import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hhcap import core, hook  # noqa: E402
from hhcap.festivos import festivos_chile  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["HHCAP_HOME"] = self.dir

    def tearDown(self):
        shutil.rmtree(self.dir)
        os.environ.pop("HHCAP_NOW", None)

    def at(self, iso):
        os.environ["HHCAP_NOW"] = iso

    def hook(self, evento, prompt="hola"):
        sys.stdin = io.StringIO(json.dumps({"prompt": prompt}))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = hook.main(evento)
        sys.stdin = sys.__stdin__
        self.assertEqual(rc, 0)
        return json.loads(out.getvalue()) if out.getvalue().strip() else None


class Festivos(unittest.TestCase):
    def test_2026(self):
        fs = festivos_chile(2026)
        for d in ["2026-04-03", "2026-04-04", "2026-06-21", "2026-06-29", "2026-10-12", "2026-10-31", "2026-12-08"]:
            self.assertIn(date.fromisoformat(d), fs, d)

    def test_traslados(self):
        self.assertIn(date(2024, 6, 29), festivos_chile(2024))   # sábado: no se mueve
        self.assertIn(date(2023, 6, 26), festivos_chile(2023))   # jueves 29 -> lunes 26
        self.assertIn(date(2025, 10, 31), festivos_chile(2025))  # viernes: no se mueve
        self.assertIn(date(2023, 10, 27), festivos_chile(2023))  # martes 31 -> viernes 27
        self.assertIn(date(2023, 1, 2), festivos_chile(2023))    # 1 de enero domingo
        self.assertIn(date(2024, 9, 20), festivos_chile(2024))   # 20 viernes también es feriado

    def test_solsticio(self):
        esperado = {2022: 21, 2023: 21, 2024: 20, 2025: 20, 2026: 21, 2027: 21, 2028: 20}
        for y, d in esperado.items():
            self.assertIn(date(y, 6, d), festivos_chile(y), y)


class Estado(Base):
    def test_estados_por_hora(self):
        casos = {
            "2026-10-01T08:14": core.FUERA_SIN_MARCA,
            "2026-10-01T08:15": core.EN_HORARIO,
            "2026-10-01T17:44": core.EN_HORARIO,
            "2026-10-01T17:45": core.FUERA_SIN_MARCA,
            "2026-10-02T13:34": core.EN_HORARIO,
            "2026-10-02T13:35": core.FUERA_SIN_MARCA,
            "2026-10-03T10:00": core.FUERA_SIN_MARCA,  # sábado
            "2026-10-12T10:00": core.FUERA_SIN_MARCA,  # festivo
        }
        for t, e in casos.items():
            self.at(t)
            self.assertEqual(core.calcular()["estado"], e, t)

    def test_tipo(self):
        # Antes un día no hábil iba al 100%. SAP dice otra cosa: sábado común y
        # feriado no irrenunciable van al 50%. Ver la clase Recargo.
        cfg = core.cargar_config()
        self.assertEqual(core.tipo_extra(date(2026, 10, 2), cfg), "50%")
        self.assertEqual(core.tipo_extra(date(2026, 10, 3), cfg), "50%")
        self.assertEqual(core.tipo_extra(date(2026, 10, 12), cfg), "50%")

    def test_ciclo_y_tramos(self):
        self.at("2026-10-02T19:00")
        ok, _ = core.marcar_entrada("18:55")
        self.assertTrue(ok)
        self.assertEqual(core.calcular()["estado"], core.EXTRA_ABIERTA)
        self.at("2026-10-03T01:00")
        ok, _ = core.marcar_salida("00:40")
        self.assertTrue(ok)
        _, filas = core.bloques_semana(date(2026, 10, 2))
        self.assertEqual([(f["fecha"], f["minutos"], f["tipo"]) for f in filas],
                         [("2026-10-02", 305, "50%"), ("2026-10-03", 40, "50%")])

    def test_tramo_cruza_a_irrenunciable(self):
        # Lo que la prueba de arriba cubría con el sábado: un bloque que cruza la
        # medianoche hacia un día al 100% se parte y cambia de tipo. 18-sep-2026
        # es viernes e irrenunciable.
        cfg = core.cargar_config()
        t = core.tramos_extra(datetime(2026, 9, 17, 22, 0), datetime(2026, 9, 18, 1, 0), cfg)
        self.assertEqual([(a.day, b.hour, tipo) for a, b, tipo in t], [(17, 0, "50%"), (18, 1, "100%")])

    def test_tramo_excluye_jornada(self):
        cfg = core.cargar_config()
        t = core.tramos_extra(datetime(2026, 10, 1, 7, 0), datetime(2026, 10, 1, 19, 0), cfg)
        self.assertEqual([(a.hour, a.minute, b.hour, b.minute) for a, b, _ in t], [(7, 0, 8, 15), (17, 45, 19, 0)])

    def test_no_abre_en_horario(self):
        self.at("2026-10-01T10:00")
        ok, _ = core.marcar_entrada()
        self.assertFalse(ok)

    def test_extra_vencida(self):
        self.at("2026-10-03T15:00")
        core.marcar_entrada()
        self.at("2026-10-05T07:00")
        r = core.calcular()
        self.assertEqual(r["estado"], core.FUERA_SIN_MARCA)
        self.assertTrue(r["aviso"])
        ok, _ = core.marcar_entrada()
        self.assertTrue(ok)
        olvidadas = [e for e in core.leer_eventos() if e.get("motivo") == "olvidada"]
        self.assertEqual(len(olvidadas), 1)

    def test_salida_usa_ultimo_uso_si_por_cerrar(self):
        self.at("2026-10-02T19:00")
        core.marcar_entrada()
        st = core.cargar_state()
        st["extra"].update(por_cerrar=True, ultimo_uso="2026-10-02T20:10:00")
        core.guardar_state(st)
        self.assertEqual(core.calcular()["estado"], core.EXTRA_POR_CERRAR)
        self.at("2026-10-02T21:00")
        core.marcar_salida()
        self.assertEqual(core.leer_eventos()[-1]["fin"], "2026-10-02T20:10:00")


class Motivo(Base):
    def test_motivo_en_salida_y_correccion(self):
        self.at("2026-10-02T19:00")
        core.marcar_entrada()
        core.poner_motivo("deploy nocturno")
        self.at("2026-10-03T00:45")
        core.marcar_salida("00:30")
        _, filas = core.bloques_semana(date(2026, 10, 2))
        self.assertEqual({f["motivo"] for f in filas}, {"deploy nocturno"})
        ok, _ = core.poner_motivo("deploy y rollback nocturno")
        self.assertTrue(ok)
        _, filas = core.bloques_semana(date(2026, 10, 2))
        self.assertEqual({f["motivo"] for f in filas}, {"deploy y rollback nocturno"})

    def test_motivo_por_bloque(self):
        for ini, fin in (("2026-10-02T19:00", "2026-10-02T20:00"), ("2026-10-03T10:00", "2026-10-03T11:00")):
            self.at(ini)
            core.marcar_entrada()
            self.at(fin)
            core.marcar_salida(motivo="b" + ini[-5:])
        core.poner_motivo("corregido", inicio="2026-10-02T19:00")
        _, filas = core.bloques_semana(date(2026, 10, 2))
        self.assertEqual([f["motivo"] for f in filas], ["corregido", "b10:00"])


class Hooks(Base):
    def test_bloquea_fuera_sin_marca(self):
        self.at("2026-10-02T19:00")
        self.assertIs(self.hook("prompt")["continue"], False)

    def test_deja_pasar_bang(self):
        self.at("2026-10-02T19:00")
        self.assertIsNone(self.hook("prompt", "! hhcap marque-entrada"))

    def test_pasa_en_horario_y_con_extra(self):
        self.at("2026-10-02T10:00")
        self.assertIsNone(self.hook("prompt"))
        self.at("2026-10-02T19:00")
        core.marcar_entrada()
        self.assertIsNone(self.hook("prompt"))

    def test_session_nunca_bloquea(self):
        self.at("2026-10-02T19:00")
        r = self.hook("session")
        self.assertNotIn("decision", r)
        self.assertIn("systemMessage", r)

    def test_falla_abierto(self):
        self.at("2026-10-02T19:00")
        Path(self.dir, "config.json").write_text("{roto")
        self.assertIsNone(self.hook("prompt"))

    def test_fusionar_idempotente_y_respeta_otros(self):
        s = {"model": "opus", "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "otro"}]}]}}
        s = hook.fusionar(s, "/x/hhcap")
        s = hook.fusionar(s, "/y/hhcap")
        cmds = [h["command"] for g in s["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertEqual(cmds, ["otro", "/y/hhcap hook prompt"])
        s = hook.quitar(s)
        self.assertEqual(s, {"model": "opus", "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "otro"}]}]}})


class Recargo(Base):
    """El 100% es para irrenunciables y Semana Santa, como lo paga SAP."""

    def tipo(self, iso):
        return core.tipo_extra(date.fromisoformat(iso), core.cargar_config())

    def test_irrenunciables_al_100(self):
        for d in ["2026-01-01", "2026-05-01", "2026-09-18", "2026-09-19", "2026-12-25"]:
            self.assertEqual(self.tipo(d), "100%", d)

    def test_semana_santa_al_100(self):
        # Pascua 2026: domingo 5 de abril.
        for d in ["2026-04-03", "2026-04-04", "2026-04-05"]:
            self.assertEqual(self.tipo(d), "100%", d)
        self.assertEqual(self.tipo("2026-04-06"), "50%")  # el lunes siguiente no

    def test_lo_demas_al_50(self):
        for d in ["2026-10-03",   # sábado común
                  "2026-10-04",   # domingo común
                  "2026-10-12",   # feriado que no es irrenunciable
                  "2026-09-20",   # domingo después de Fiestas Patrias
                  "2026-09-22"]:  # día hábil
            self.assertEqual(self.tipo(d), "50%", d)

    def test_dias_extra_y_domingo_configurables(self):
        cfg = core.cargar_config()
        cfg["dias_100_extra"] = ["2026-11-15"]  # p. ej. una elección
        cfg["domingo_100"] = True
        core.guardar_config(cfg)
        self.assertEqual(self.tipo("2026-11-15"), "100%")
        self.assertEqual(self.tipo("2026-10-04"), "100%")
        self.assertEqual(self.tipo("2026-10-03"), "50%")


class UsoPersonal(Base):
    """«No voy a trabajar, pero voy a usar la IA.»"""

    def test_fuera_de_horario_deja_pasar_sin_contar(self):
        self.at("2026-10-03T18:30")
        self.assertIsNotNone(self.hook("prompt"))  # sin marca: bloquea
        ok, _ = core.activar_personal()
        self.assertTrue(ok)
        self.assertEqual(core.calcular()["estado"], core.USO_PERSONAL)
        self.assertIsNone(self.hook("prompt"))     # deja pasar, sin mensaje
        _, filas = core.bloques_semana(date(2026, 10, 3))
        self.assertEqual(filas, [])                # y no cuenta nada

    def test_vence_y_vuelve_a_preguntar(self):
        self.at("2026-10-03T18:30")
        core.activar_personal(hasta="20:00")
        self.at("2026-10-03T19:59")
        self.assertEqual(core.calcular()["estado"], core.USO_PERSONAL)
        self.at("2026-10-03T20:00")
        self.assertEqual(core.calcular()["estado"], core.FUERA_SIN_MARCA)

    def test_por_omision_dura_hasta_fin_del_dia(self):
        self.at("2026-10-03T18:30")
        core.activar_personal()
        self.at("2026-10-03T23:59")
        self.assertEqual(core.calcular()["estado"], core.USO_PERSONAL)
        self.at("2026-10-04T00:00")
        self.assertEqual(core.calcular()["estado"], core.FUERA_SIN_MARCA)

    def test_hasta_una_hora_ya_pasada_es_de_manana(self):
        self.at("2026-10-03T23:00")
        core.activar_personal(hasta="01:00")
        self.at("2026-10-04T00:30")
        self.assertEqual(core.calcular()["estado"], core.USO_PERSONAL)

    def test_no_pisa_una_extra_abierta(self):
        self.at("2026-10-03T18:30")
        core.marcar_entrada("18:22")
        ok, msg = core.activar_personal()
        self.assertFalse(ok)
        self.assertIn("descartar-extra", msg)
        self.assertEqual(core.calcular()["estado"], core.EXTRA_ABIERTA)

    def test_descartar_la_extra_abierta_no_la_reporta(self):
        self.at("2026-10-03T18:30")
        core.marcar_entrada("18:22")
        ok, _ = core.activar_personal(descartar_extra=True)
        self.assertTrue(ok)
        self.assertEqual(core.calcular()["estado"], core.USO_PERSONAL)
        _, filas = core.bloques_semana(date(2026, 10, 3))
        self.assertEqual(filas, [])
        self.assertIn("descarta_extra", [e["evento"] for e in core.leer_eventos()])

    def test_en_jornada_no_aplica(self):
        self.at("2026-10-01T10:00")
        ok, _ = core.activar_personal()
        self.assertFalse(ok)

    def test_marcar_entrada_termina_el_uso_personal(self):
        self.at("2026-10-03T18:30")
        core.activar_personal()
        ok, _ = core.marcar_entrada()
        self.assertTrue(ok)
        self.assertEqual(core.calcular()["estado"], core.EXTRA_ABIERTA)
        self.at("2026-10-03T19:30")
        core.marcar_salida()
        self.assertEqual(core.calcular()["estado"], core.FUERA_SIN_MARCA)

    def test_terminar_a_mano(self):
        self.at("2026-10-03T18:30")
        core.activar_personal()
        ok, _ = core.desactivar_personal()
        self.assertTrue(ok)
        self.assertEqual(core.calcular()["estado"], core.FUERA_SIN_MARCA)
        ok, _ = core.desactivar_personal()
        self.assertFalse(ok)

    def test_el_bloqueo_ofrece_la_salida(self):
        self.at("2026-10-03T18:30")
        out = self.hook("prompt")
        self.assertIn("hhcap uso-personal", out["stopReason"])

    def test_session_avisa_que_no_cuenta(self):
        self.at("2026-10-03T18:30")
        core.activar_personal(hasta="21:00")
        out = self.hook("session")
        self.assertIn("Uso personal hasta las 21:00", out["systemMessage"])


if __name__ == "__main__":
    unittest.main()
