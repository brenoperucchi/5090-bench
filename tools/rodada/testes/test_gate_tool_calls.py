"""Testes do gate de tool_calls (tools/gate_tool_calls.py), rev. 2.

Nenhum teste fala com o Strata: os de roteiro usam um `post` falso; os de transporte usam servidores HTTP em 127.0.0.1 porta efêmera.
"""
import contextlib
import http.server
import io
import json
import os
import sys
import threading
import unittest
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import gate_tool_calls as g  # noqa: E402

MARCADOR = "MARCADOR-SECRETO-XYZ"


def tc(id_="call_1", nome="obter_valor", args='{"n": 3}', tipo="function"):
    return {"id": id_, "type": tipo, "function": {"name": nome, "arguments": args}}


def resp_tools(*calls, content=None, finish="tool_calls", role="assistant", usage=None):
    return {"choices": [{"message": {"role": role, "content": content, "tool_calls": list(calls)}, "finish_reason": finish}],
            "usage": usage if usage is not None else {"prompt_tokens": 90, "completion_tokens": 20, "total_tokens": 110}}


def resp_texto(texto, finish="stop", role="assistant"):
    return {"choices": [{"message": {"role": role, "content": texto}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 90, "completion_tokens": 12, "total_tokens": 102}}


def roteiro_ok():
    return [resp_tools(tc("call_a", args='{"n": 3}')), resp_tools(tc("call_b", args='{"n": 7}')), resp_tools(tc("call_c", args='{"n": 5}')),
            resp_texto("O valor para n=3 é 4242."), resp_texto("Posso ajudar sem usar ferramentas.")]


class Post:
    def __init__(self, respostas, status=200):
        self.respostas, self.status, self.payloads, self.timeouts = list(respostas), status, [], []

    def __call__(self, payload, timeout=None):
        self.payloads.append(payload); self.timeouts.append(timeout)
        if not self.respostas: raise AssertionError("chamada além do roteiro")
        r = self.respostas.pop(0)
        return (r[0], r[1], 5) if isinstance(r, tuple) else (self.status, r, 5)


def rodar(respostas, **kw):
    post = Post(respostas); pausas = []
    return g.rodar(post, dormir=pausas.append, **kw), post, pausas


class Validacao(unittest.TestCase):
    def test_tool_valido_com_content_nulo_e_com_texto(self):
        self.assertEqual(g.valida_chamada(resp_tools(tc()))[0], [])
        self.assertEqual(g.valida_chamada(resp_tools(tc(), content="Vou consultar."))[0], [])

    def test_json_invalido_e_args_fora_do_schema(self):
        self.assertIn("ARGS_JSON_INVALIDO", g.valida_chamada(resp_tools(tc(args='{"n": ')))[0])
        for args in ('{"n": "3"}', '{"n": true}', '{"n": 3, "x": 1}', '{}', '[3]', '3'):
            self.assertTrue(g.valida_chamada(resp_tools(tc(args=args)))[0], args)

    def test_nome_fora_da_oferta_id_ausente_type_e_finish(self):
        self.assertIn("NOME_FORA_DA_OFERTA", g.valida_chamada(resp_tools(tc(nome="executar_shell")))[0])
        self.assertIn("ID_AUSENTE_OU_VAZIO", g.valida_chamada(resp_tools(tc(id_="")))[0])
        self.assertIn("ID_AUSENTE_OU_VAZIO", g.valida_chamada(resp_tools(tc(id_="   ")))[0])
        self.assertIn("TYPE_NAO_FUNCTION", g.valida_chamada(resp_tools(tc(tipo="tool")))[0])
        self.assertIn("FINISH_NAO_TOOL_CALLS", g.valida_chamada(resp_tools(tc(), finish="stop"))[0])
        self.assertIn("SEM_TOOL_CALLS", g.valida_chamada(resp_texto("oi"))[0])

    def test_role_user_reprova(self):
        self.assertIn("ROLE_NAO_ASSISTANT", g.valida_chamada(resp_tools(tc(), role="user"))[0])
        self.assertIn("ROLE_NAO_ASSISTANT", g.valida_sem_chamada(resp_texto("4242", role="user"), 4242))

    def test_multiplas_chamadas_reprovam(self):
        p, t = g.valida_chamada(resp_tools(tc("a"), tc("b")))
        self.assertIn("N_CHAMADAS_DIFERENTE_DE_1", p); self.assertIsNone(t)

    def test_none_indevido_e_retorno(self):
        self.assertIn("TOOL_CALLS_INDEVIDO", g.valida_sem_chamada(resp_tools(tc())))
        self.assertEqual(g.valida_sem_chamada(resp_texto("Deu 4242."), 4242), [])
        self.assertIn("NAO_CITA_RESULTADO", g.valida_sem_chamada(resp_texto("Deu zero."), 4242))
        self.assertIn("SEM_TEXTO", g.valida_sem_chamada(resp_texto("  ")))
        self.assertIn("FINISH_NAO_STOP", g.valida_sem_chamada(resp_texto("texto", finish="length")))


class Malformados(unittest.TestCase):
    """Envelopes malformados: nunca AttributeError/TypeError; sempre relatório de falha e parada no passo atual."""
    CASOS = {
        "raiz lista": [], "raiz string": "x", "raiz nula": None,
        "choices ausente": {}, "choices vazio": {"choices": []}, "choices string": {"choices": "x"},
        "choices [null]": {"choices": [None]}, "choices [str]": {"choices": ["x"]},
        "message nula": {"choices": [{"message": None, "finish_reason": "tool_calls"}]},
        "message lista": {"choices": [{"message": [], "finish_reason": "tool_calls"}]},
        "tool_calls [null]": {"choices": [{"message": {"role": "assistant", "tool_calls": [None]}, "finish_reason": "tool_calls"}]},
        "tool_calls [str]": {"choices": [{"message": {"role": "assistant", "tool_calls": ["x"]}, "finish_reason": "tool_calls"}]},
        "tool_calls string": {"choices": [{"message": {"role": "assistant", "tool_calls": "x"}, "finish_reason": "tool_calls"}]},
        "function nula": {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "a", "type": "function", "function": None}]},
                                       "finish_reason": "tool_calls"}]},
        "name lista": {"choices": [{"message": {"role": "assistant", "tool_calls": [tc(nome=["obter_valor"])]}, "finish_reason": "tool_calls"}]},
        "arguments objeto": {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "a", "type": "function",
                             "function": {"name": "obter_valor", "arguments": {"n": 3}}}]}, "finish_reason": "tool_calls"}]},
        "finish lista": {"choices": [{"message": {"role": "assistant", "tool_calls": [tc()]}, "finish_reason": ["tool_calls"]}]},
    }

    def test_validadores_nao_levantam_e_reprovam(self):
        for nome, r in self.CASOS.items():
            with self.subTest(nome):
                self.assertTrue(g.valida_chamada(r)[0]); self.assertTrue(g.valida_sem_chamada(r)); g.projeta(r)

    def test_roteiro_reporta_e_para_no_passo_atual(self):
        for nome, r in self.CASOS.items():
            with self.subTest(nome):
                res, post, _ = rodar([r])
                self.assertFalse(res["aprovado"]); self.assertEqual(res["chamadas"], 1); self.assertEqual(len(post.payloads), 1)
                self.assertEqual(res["interrompido_em"], "1-auto"); self.assertTrue(res["passos"][0]["problemas"])

    def test_excecao_no_validador_vira_falha_agregada(self):
        with mock.patch.object(g, "valida_chamada", side_effect=ValueError(MARCADOR)):
            res, post, _ = rodar(roteiro_ok())
        self.assertFalse(res["aprovado"]); self.assertEqual(res["passos"][0]["problemas"], ["VALIDACAO_EXCECAO"])
        self.assertNotIn(MARCADOR, json.dumps(res)); self.assertEqual(len(post.payloads), 1)

    def test_resposta_nao_json_grande_e_http(self):
        for status, corpo, esperado in ((200, "JSON", "RESPOSTA_NAO_JSON"), (200, "GRANDE", "RESPOSTA_GRANDE_DEMAIS"),
                                        (500, None, "HTTP_NAO_200"), (302, None, "HTTP_NAO_200"), (0, "REDE", "ERRO_REDE")):
            with self.subTest(status=status, corpo=corpo):
                res, _, _ = rodar([(status, corpo)])
                self.assertEqual(res["passos"][0]["problemas"], [esperado]); self.assertEqual(res["chamadas"], 1)


class Projecao(unittest.TestCase):
    def test_marcadores_nunca_aparecem_no_registro(self):
        r = roteiro_ok()
        r[0] = resp_tools(tc("call_a", args=json.dumps({"n": 3, MARCADOR + "_CHAVE": 1})),
                          usage={"prompt_tokens": 90, "extra": MARCADOR, MARCADOR + "_K": 7})
        r[1]["choices"][0]["finish_reason"] = MARCADOR + "_FINISH"
        res, _, _ = rodar(r)
        self.assertNotIn(MARCADOR, json.dumps(res))                       # passo 1 reprovou por chave extra; nada vaza
        res2, _, _ = rodar([resp_tools(tc(), usage={"prompt_tokens": 1, "extra": MARCADOR}), resp_tools(tc(), finish=MARCADOR)])
        self.assertNotIn(MARCADOR, json.dumps(res2))
        self.assertEqual(res2["passos"][0]["tokens"], {"prompt_tokens": 1})
        self.assertEqual(res2["passos"][1]["finish_reason"], "outro")

    def test_tokens_so_inteiros_nao_negativos_e_sem_bool(self):
        u = {"prompt_tokens": True, "completion_tokens": -1, "total_tokens": "9"}
        self.assertEqual(g.projeta(resp_tools(tc(), usage=u))[1], {})
        self.assertEqual(g.projeta(resp_tools(tc(), usage={"prompt_tokens": 5, "completion_tokens": 0}))[1], {"prompt_tokens": 5, "completion_tokens": 0})

    def test_registro_so_tem_campos_conhecidos_e_problemas_sao_codigos(self):
        res, _, _ = rodar(roteiro_ok())
        for passo in res["passos"]:
            self.assertLessEqual(set(passo), {"passo", "ok", "problemas", "status", "latencia_ms", "finish_reason", "n_tool_calls", "tokens", "n_confere"})
        res, _, _ = rodar([resp_tools(tc(nome=MARCADOR, args='{"n": "x"}'))])
        for p in res["passos"][0]["problemas"]: self.assertRegex(p, r"^[A-Z_]+$")

    def test_n_confere_e_so_metadado(self):
        r = roteiro_ok(); r[0] = resp_tools(tc("call_a", args='{"n": 99}'))
        res, _, _ = rodar(r)
        self.assertTrue(res["aprovado"]); self.assertIs(res["passos"][0]["n_confere"], False); self.assertIs(res["passos"][1]["n_confere"], True)


class Roteiro(unittest.TestCase):
    def test_fluxo_valido_faz_5_chamadas_com_pausa_de_2s(self):
        res, post, pausas = rodar(roteiro_ok())
        self.assertTrue(res["aprovado"]); self.assertEqual(res["chamadas"], 5); self.assertIsNone(res["interrompido_em"])
        self.assertEqual(pausas, [2.0] * 4); self.assertLessEqual(res["chamadas"], g.MAX_CHAMADAS)

    def test_parametros_de_cada_pedido(self):
        _, post, _ = rodar(roteiro_ok())
        for p in post.payloads:
            self.assertEqual((p["model"], p["max_tokens"], p["stream"]), ("swift-1.5-iq3_xxs", 256, False))
            self.assertFalse(p["chat_template_kwargs"]["enable_thinking"])
            self.assertEqual([t["function"]["name"] for t in p["tools"]], ["obter_valor"])
        self.assertEqual([p["tool_choice"] for p in post.payloads][3:], ["auto", "none"])
        self.assertEqual(post.payloads[2]["tool_choice"], {"type": "function", "function": {"name": "obter_valor"}})

    def test_retorno_usa_a_chamada_real(self):
        _, post, _ = rodar(roteiro_ok())
        msgs = post.payloads[3]["messages"]
        self.assertEqual(msgs[-2]["tool_calls"], [tc("call_a", args='{"n": 3}')])
        self.assertEqual((msgs[-1]["role"], msgs[-1]["tool_call_id"]), ("tool", "call_a"))
        self.assertEqual(json.loads(msgs[-1]["content"]), g.RESULTADO_SINTETICO)

    def test_falha_interrompe_sem_retry(self):
        res, post, _ = rodar([resp_tools(tc("call_a")), resp_tools(tc("call_b", args='{"n": ')), *roteiro_ok()[2:]])
        self.assertEqual((res["aprovado"], res["chamadas"], res["interrompido_em"]), (False, 2, "2-auto-repeticao"))
        self.assertEqual(len(post.payloads), 2)

    def test_role_errado_e_multiplas_chamadas_param_sem_followup(self):
        for ruim in (resp_tools(tc("a"), role="user"), resp_tools(tc("a"), tc("b"))):
            res, post, _ = rodar([ruim, *roteiro_ok()[1:]])
            self.assertFalse(res["aprovado"]); self.assertEqual(len(post.payloads), 1)

    def test_none_indevido_e_retorno_sem_resultado(self):
        r = roteiro_ok(); r[4] = resp_tools(tc("z"))
        self.assertEqual(rodar(r)[0]["interrompido_em"], "5-tool-choice-none")
        r = roteiro_ok(); r[3] = resp_texto("Não sei.")
        self.assertEqual(rodar(r)[0]["interrompido_em"], "4-retorno-tool")

    def test_limite_de_chamadas(self):
        self.assertEqual(g.MAX_CHAMADAS, 6)
        with mock.patch.object(g, "MAX_CHAMADAS", 3):
            res, post, _ = rodar(roteiro_ok())
        self.assertEqual((res["aprovado"], res["chamadas"], res["motivo"]), (False, 3, "LIMITE_CHAMADAS"))


class Orcamento(unittest.TestCase):
    def relogio(self, passo_s):
        t = [0.0]
        def agora():
            t[0] += passo_s; return t[0]
        return agora

    def test_orcamento_cabe_em_10_min_no_pior_caso(self):
        self.assertLessEqual(g.ORCAMENTO_S, 600); self.assertLessEqual(g.TIMEOUT_CHAMADA_S, 90)

    def test_nao_inicia_chamada_apos_esgotar_orcamento(self):
        res, post, _ = rodar(roteiro_ok(), relogio=self.relogio(200))          # cada leitura do relógio avança 200 s
        self.assertFalse(res["aprovado"]); self.assertEqual(res["motivo"], "ORCAMENTO_ESGOTADO"); self.assertLess(res["chamadas"], 5)

    def test_timeout_por_chamada_limitado_e_decrescente(self):
        res, post, _ = rodar(roteiro_ok(), relogio=self.relogio(1))
        self.assertTrue(res["aprovado"])
        self.assertTrue(all(t <= g.TIMEOUT_CHAMADA_S for t in post.timeouts))

    def test_ultimo_timeout_nao_passa_do_restante(self):
        with mock.patch.object(g, "ORCAMENTO_S", 100):
            res, post, _ = rodar(roteiro_ok(), relogio=self.relogio(15))
        for t in post.timeouts: self.assertLessEqual(t, 100)


class Servidor:
    """Servidor HTTP local que registra o que recebe e responde como configurado."""
    def __init__(self, status=200, corpo=b"{}", location=None):
        self.visto, outer = [], self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
                outer.visto.append((self.command, self.headers.get("Authorization")))
                self.send_response(status)
                if location: self.send_header("Location", location)
                self.send_header("Content-Length", str(len(corpo))); self.end_headers(); self.wfile.write(corpo)

            do_GET = do_POST
            def log_message(self, *a): pass
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1/chat/completions"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def fechar(self): self.srv.shutdown(); self.srv.server_close()


class Transporte(unittest.TestCase):
    def test_redirect_nao_e_seguido_e_a_chave_nao_vaza(self):
        for codigo in (301, 302, 303, 307, 308):
            with self.subTest(codigo=codigo):
                destino = Servidor(); origem = Servidor(status=codigo, location=destino.url)
                try:
                    status, corpo, _ = g.post_real("CHAVE-DE-TESTE", origem.url)({"x": 1}, 5)
                finally: origem.fechar(); destino.fechar()
                self.assertEqual(status, codigo); self.assertEqual(len(origem.visto), 1)    # uma única tentativa
                self.assertEqual(destino.visto, [])                                          # nada reenviado ao outro destino

    def test_proxy_de_ambiente_e_ignorado(self):
        proxy = Servidor(); alvo = Servidor(corpo=b'{"ok": true}')
        env = {"http_proxy": proxy.url.rsplit("/v1", 1)[0], "HTTP_PROXY": proxy.url.rsplit("/v1", 1)[0], "no_proxy": "", "NO_PROXY": ""}
        try:
            with mock.patch.dict(os.environ, env):
                status, corpo, _ = g.post_real("CHAVE-DE-TESTE", alvo.url.replace("127.0.0.1", "localhost"))({"x": 1}, 5)
        finally: proxy.fechar(); alvo.fechar()
        self.assertEqual((status, corpo), (200, {"ok": True})); self.assertEqual(proxy.visto, []); self.assertEqual(len(alvo.visto), 1)

    def test_chave_vai_so_no_cabecalho_ao_destino(self):
        alvo = Servidor(corpo=b'{"ok": true}')
        try: g.post_real("CHAVE-DE-TESTE", alvo.url)({"x": 1}, 5)
        finally: alvo.fechar()
        self.assertEqual(alvo.visto, [("POST", "Bearer CHAVE-DE-TESTE")])

    def test_resposta_grande_e_nao_json(self):
        grande = Servidor(corpo=b"x" * (g.MAX_RESPOSTA_BYTES + 10)); texto = Servidor(corpo=b"nao e json")
        try:
            self.assertEqual(g.post_real("k", grande.url)({}, 5)[:2], (200, "GRANDE"))
            self.assertEqual(g.post_real("k", texto.url)({}, 5)[:2], (200, "JSON"))
        finally: grande.fechar(); texto.fechar()

    def test_erro_de_rede_vira_codigo_estatico(self):
        s = Servidor(); url = s.url; s.fechar()
        self.assertEqual(g.post_real("k", url)({}, 2)[:2], (0, "REDE"))


class Seguranca(unittest.TestCase):
    def test_sem_executar_nao_ha_rede(self):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["gate_tool_calls.py"]), mock.patch.object(g, "post_real", side_effect=AssertionError("rede")), \
                contextlib.redirect_stdout(saida):
            g.main()
        self.assertIn("nenhuma chamada feita", saida.getvalue())

    def test_alvo_fixo_e_chave_so_por_arquivo(self):
        import ast
        self.assertEqual(g.URL, "http://192.168.0.125:18199/v1/chat/completions")
        self.assertEqual(str(g.CHAVE), "/home/brenoperucchi/.config/strata/prod-lan.key")
        arvore = ast.parse((ROOT / "tools/gate_tool_calls.py").read_text(encoding="utf-8"))
        importados = {n.names[0].name.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.Import)} | \
                     {n.module.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(importados & {"subprocess", "os", "socket", "paramiko", "rodada"}, importados)
        urls = [n.value for n in ast.walk(arvore) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("http")]
        self.assertEqual(urls, [g.URL])

    def test_transporte_usa_opener_sem_proxy_e_sem_redirect(self):
        fonte = (ROOT / "tools/gate_tool_calls.py").read_text(encoding="utf-8")
        self.assertIn("ProxyHandler({})", fonte); self.assertIn("_SemRedirect", fonte); self.assertNotIn("urlopen(", fonte)


if __name__ == "__main__":
    unittest.main()
