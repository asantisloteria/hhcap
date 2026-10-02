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
        cfg = core.cargar_config()
        self.assertEqual(core.tipo_extra(date(2026, 10, 2), cfg), "50%")
        self.assertEqual(core.tipo_extra(date(2026, 10, 3), cfg), "100%")
        self.assertEqual(core.tipo_extra(date(2026, 10, 12), cfg), "100%")

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
                         [("2026-10-02", 305, "50%"), ("2026-10-03", 40, "100%")])

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


if __name__ == "__main__":
    unittest.main()
