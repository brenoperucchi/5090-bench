"""Testes unitários e de regressão da rodada única de benchmark. Rodam antes de toda rodada (rodada.py aborta sem
tocar no servidor se algum falhar). Não usam rede, GPU nem o host Windows.

    python3 -m unittest discover -s tools/rodada/testes -q
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/rodada"))
import rodada  # noqa: E402

PAINEL = ROOT / "results/painel/benchmarks.json"


class Feito(unittest.TestCase):
    """O que já foi medido não roda de novo; o que está incompleto roda."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "privado").mkdir()
        self.c = {"label": "x"}

    def test_velocidade_precisa_dos_dois_arquivos(self):
        self.assertFalse(rodada.feito("velocidade", self.c, self.dir))
        (self.dir / "x.json").write_text("{}")
        self.assertFalse(rodada.feito("velocidade", self.c, self.dir))   # falta a sonda
        (self.dir / "x-probes.json").write_text("{}")
        self.assertTrue(rodada.feito("velocidade", self.c, self.dir))

    def test_mfc_incompleto_roda_de_novo(self):
        f = self.dir / "privado" / "mfc-x.correcao.json"
        f.write_text(json.dumps({"tentativas_faltando": 3}))
        self.assertFalse(rodada.feito("mfc", self.c, self.dir))
        f.write_text(json.dumps({"tentativas_faltando": 0}))
        self.assertTrue(rodada.feito("mfc", self.c, self.dir))

    def test_mfc_correcao_corrompida_nao_conta(self):
        (self.dir / "privado" / "mfc-x.correcao.json").write_text("{quebrado")
        self.assertFalse(rodada.feito("mfc", self.c, self.dir))

    def test_mesa_exige_12_respostas(self):
        f = self.dir / "privado" / "mesa-x.txt"
        f.write_text("rodada-x   9   0   5.0   5.0\n")
        self.assertFalse(rodada.feito("guardian", self.c, self.dir))
        f.write_text("rodada-x   12   0   5.0   5.0\n")
        self.assertTrue(rodada.feito("guardian", self.c, self.dir))


class Versao(unittest.TestCase):
    def test_versao_do_motor_casa_com_release(self):
        # 0.1.40.1: o motor informa "Strata 0.1.40" (rodada de 06/10 pulou a config padrão por isso)
        src = (ROOT / "tools/rodada/rodada.py").read_text(encoding="utf-8")
        self.assertIn('".".join(plano["versao"].split(".")[:3])', src)
        self.assertIn('0.1.40+: /props também exige a chave', src)


class Deterministico(unittest.TestCase):
    def test_feito_pelo_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "privado").mkdir()
            self.assertFalse(rodada.feito("deterministico", {"label": "x"}, d))
            (d / "privado" / "det-x.json").write_text("{}")
            self.assertTrue(rodada.feito("deterministico", {"label": "x"}, d))

    def test_roda_por_ultimo(self):
        # sobe a variante determinística: o que vier depois rodaria na config errada
        ordem = sorted(["deterministico", "velocidade", "mfc"], key=lambda t: t == "deterministico")
        self.assertEqual(ordem[-1], "deterministico")
        src = (ROOT / "tools/rodada/rodada.py").read_text(encoding="utf-8")
        self.assertIn('key=lambda t: t == "deterministico"', src)


class Plano(unittest.TestCase):
    """Regressão do incidente de 04/10 13:22: --testes velocidade não pode disparar outro teste."""

    def falta(self, testes):
        plano = {"versao": "9.9.9", "configs": [{"label": "a", "origin": "setup-default", "cfg": "E:\\a.json"},
                                                 {"label": "b", "origin": "custom-2", "cfg": "E:\\b.json",
                                                  "testes": ["guardian-raciocinio"]}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.json"; p.write_text(json.dumps(plano))
            with mock.patch.object(rodada, "ROOT", Path(d)), mock.patch.object(rodada, "ps") as ps, \
                    mock.patch.object(sys, "argv", ["rodada.py", str(p), "--testes", testes, "--verificar"]):
                out = []
                with mock.patch("builtins.print", lambda *a, **k: out.append(a)):
                    rodada.main()
                ps.assert_not_called()                       # --verificar nunca toca no servidor
        return out[0][1]

    def test_filtro_vale_para_teste_proprio_da_config(self):
        self.assertEqual(self.falta("velocidade"), {"a": ["velocidade"]})

    def test_extra_so_na_config_que_pede(self):
        f = self.falta(",".join(rodada.TESTES + rodada.EXTRAS))
        self.assertNotIn("guardian-raciocinio", f["a"])
        self.assertEqual(f["b"], ["guardian-raciocinio"])


class Painel(unittest.TestCase):
    """Regressões do arquivo da /benchmarks (gerado agora, validado contra o contrato do gateway)."""

    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "tools/build_benchmarks_json.py"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr          # contrato violado = falha
        cls.d = json.loads(PAINEL.read_text(encoding="utf-8"))

    def test_sem_caminho_absoluto_nem_host(self):
        s = json.dumps(self.d)
        for proibido in ("/home/", "E:\\\\", "192.168.", "C:\\\\"):
            self.assertNotIn(proibido, s)

    def test_velocidade_nao_mistura_instrumento(self):
        # erro de 04/10: prompts públicos 2,7K postos na coluna "curto" (27 tokens) -> Δ +1.361% falso
        for r in self.d["velocidade"]:
            self.assertNotIn("prompts públicos", r.get("variante", ""), r["label"])
            if r.get("leitura_curto") and r.get("leitura_medio"):
                self.assertLess(r["leitura_curto"], r["leitura_medio"], r["label"])

    def test_sonda_na_mesma_linha(self):
        labels = [r["label"] for r in self.d["strata_space"]]
        self.assertFalse([l for l in labels if "-probes ·" in l and l.replace("-probes", "") in labels])

    def test_versao_so_de_fonte_observada(self):
        for r in self.d["strata_space"]:
            if "versao" in r:
                self.assertEqual("Strata " + r["versao"], r.get("build"), r["label"])

    def test_gprobe_so_em_ms(self):
        # contrato T223: gprobe150/300/450 só como leitura_ms_/wall_ms_ (mediana), nunca tok/s nem misturado ao probe antigo
        for r in self.d["strata_space"]:
            for k in r:
                if "gprobe" in k:
                    self.assertTrue(k.startswith(("leitura_ms_gprobe", "wall_ms_gprobe")), k)
                    self.assertGreaterEqual(r[k], 0)

    def test_uma_gpu_no_v1(self):
        self.assertEqual(len(self.d["gpus"]), 1)


if __name__ == "__main__":
    unittest.main()
