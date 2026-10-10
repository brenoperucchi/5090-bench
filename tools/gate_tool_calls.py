#!/usr/bin/env python3
"""Gate de PROTOCOLO de tool_calls no Strata de produção existente (pedido do llm-exec, 09/10/2026; rev. 2 após REQUEST_CHANGES).

Mede só compatibilidade básica do protocolo OpenAI de ferramentas. Não prova que `n` corresponde ao índice pedido (isso vai só como
metadado `n_confere`, sem reprovar), nem qualidade de código, nem desempenho. Nunca executa ferramenta: `obter_valor` existe só
no pedido, e o resultado `role=tool` é sintético.

Regras (do llm-exec):
  - servidor EXISTENTE, alvo único: POST http://192.168.0.125:18199/v1/chat/completions, model swift-1.5-iq3_xxs;
    sem rodada.py, comandos remotos, load/unload/restart, nem outro servidor;
  - Bearer lido de /home/brenoperucchi/.config/strata/prod-lan.key; o valor nunca é impresso nem gravado;
  - transporte confinado: opener próprio SEM proxy de ambiente e que RECUSA todo redirect (a chave só vai ao destino);
  - até 6 chamadas sequenciais (uso 5), max_tokens 256, thinking false, stream false, pausa 2 s, SEM retry, interrompe na 1ª falha;
  - orçamento de tempo em relógio monotônico: não começa chamada nova sem tempo restante; timeout por chamada <= 90 s e resposta
    limitada em bytes. O timeout é de socket (inatividade): o orçamento total é melhor esforço, não limite rígido;
  - o registro é uma PROJEÇÃO tipada: códigos de erro estáticos, contadores de tokens inteiros conhecidos, finish_reason de um enum.
    Nenhum texto do modelo, nome de chave, valor ou corpo de erro entra no registro.

SEM `--executar` o script só mostra o plano e NÃO faz nenhuma chamada de rede.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://192.168.0.125:18199/v1/chat/completions"
MODELO = "swift-1.5-iq3_xxs"
CHAVE = Path("/home/brenoperucchi/.config/strata/prod-lan.key")
MAX_CHAMADAS = 6
MAX_TOKENS = 256
PAUSA_S = 2.0
TIMEOUT_CHAMADA_S = 90
ORCAMENTO_S = 540                       # janela de 10 min menos folga
MAX_RESPOSTA_BYTES = 262144
FINISH_CONHECIDOS = {"stop", "length", "tool_calls", "content_filter", "function_call"}
TOKENS_CONHECIDOS = ("prompt_tokens", "completion_tokens", "total_tokens")

FERRAMENTA = {"type": "function", "function": {
    "name": "obter_valor",
    "description": "Devolve o valor numérico guardado para o índice n. Ferramenta fictícia do gate.",
    "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False}}}
NOME = FERRAMENTA["function"]["name"]
NOMES = {NOME}
RESULTADO_SINTETICO = {"valor": 4242}          # o texto final precisa citar este número


# ---------- validação: só tipos explícitos e CÓDIGOS ESTÁTICOS (nada do que o servidor devolveu entra nos códigos) ----------
def _msg(resp):
    """(choice, message, erro) com tipos conferidos."""
    if not isinstance(resp, dict): return None, None, "RAIZ_NAO_OBJETO"
    ch = resp.get("choices")
    if not isinstance(ch, list) or not ch: return None, None, "CHOICES_INVALIDO"
    if not isinstance(ch[0], dict): return None, None, "CHOICE_NAO_OBJETO"
    m = ch[0].get("message")
    if not isinstance(m, dict): return None, None, "MESSAGE_NAO_OBJETO"
    return ch[0], m, None


def valida_args(args_json, schema):
    """arguments: string JSON de um objeto que respeita o schema FECHADO. Códigos estáticos."""
    if not isinstance(args_json, str): return ["ARGS_NAO_STRING"]
    try: obj = json.loads(args_json)
    except ValueError: return ["ARGS_JSON_INVALIDO"]
    if not isinstance(obj, dict): return ["ARGS_NAO_OBJETO"]
    p, props = [], schema.get("properties", {})
    for k in schema.get("required", []):
        if k not in obj: p.append("ARGS_OBRIGATORIO_AUSENTE")
    for k, v in obj.items():
        if k not in props:
            if schema.get("additionalProperties") is False: p.append("ARGS_CHAVE_FORA_DO_SCHEMA")
            continue
        if props[k].get("type") == "integer" and (not isinstance(v, int) or isinstance(v, bool)): p.append("ARGS_TIPO_ERRADO")
    return sorted(set(p))


def valida_chamada(resp, forcada=None):
    """Resposta que DEVE trazer EXATAMENTE UMA tool_call, de role assistant. Devolve (problemas, tool_call|None)."""
    ch, m, erro = _msg(resp)
    if erro: return [erro], None
    p = []
    if m.get("role") != "assistant": p.append("ROLE_NAO_ASSISTANT")
    tcs = m.get("tool_calls")
    tc = None
    if not isinstance(tcs, list) or not tcs: p.append("SEM_TOOL_CALLS")
    elif len(tcs) != 1: p.append("N_CHAMADAS_DIFERENTE_DE_1")
    elif not isinstance(tcs[0], dict): p.append("TOOL_CALL_NAO_OBJETO")
    else:
        tc = tcs[0]
        i = tc.get("id")
        if not isinstance(i, str) or not i.strip(): p.append("ID_AUSENTE_OU_VAZIO")
        if tc.get("type") != "function": p.append("TYPE_NAO_FUNCTION")
        f = tc.get("function")
        if not isinstance(f, dict): p.append("FUNCTION_NAO_OBJETO")
        else:
            nome = f.get("name")
            if not isinstance(nome, str) or nome not in NOMES: p.append("NOME_FORA_DA_OFERTA")
            elif forcada and nome != forcada: p.append("NOME_DIFERENTE_DO_FORCADO")
            p += valida_args(f.get("arguments"), FERRAMENTA["function"]["parameters"])
    if ch.get("finish_reason") != "tool_calls": p.append("FINISH_NAO_TOOL_CALLS")
    c = m.get("content")
    if c is not None and not isinstance(c, str): p.append("CONTENT_INVALIDO")
    return sorted(set(p)), (tc if not p else None)


def valida_sem_chamada(resp, deve_citar=None):
    """Resposta de texto de role assistant, sem tool_calls (retorno da ferramenta ou tool_choice none)."""
    ch, m, erro = _msg(resp)
    if erro: return [erro]
    p = []
    if m.get("role") != "assistant": p.append("ROLE_NAO_ASSISTANT")
    if m.get("tool_calls"): p.append("TOOL_CALLS_INDEVIDO")
    c = m.get("content")
    if not isinstance(c, str) or not c.strip(): p.append("SEM_TEXTO")
    elif deve_citar is not None and str(deve_citar) not in c: p.append("NAO_CITA_RESULTADO")
    if ch.get("finish_reason") != "stop": p.append("FINISH_NAO_STOP")
    return sorted(set(p))


def projeta(resp):
    """Projeção tipada do que entra no registro: finish de um enum e contadores de tokens inteiros conhecidos."""
    ch, m, _ = _msg(resp)
    fin = ch.get("finish_reason") if ch else None
    fin = fin if isinstance(fin, str) and fin in FINISH_CONHECIDOS else (None if fin is None else "outro")
    u = resp.get("usage") if isinstance(resp, dict) else None
    tokens = {}
    if isinstance(u, dict):
        for k in TOKENS_CONHECIDOS:
            v = u.get(k)
            if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**9: tokens[k] = v
    n_tc = len(m["tool_calls"]) if m and isinstance(m.get("tool_calls"), list) else 0
    return fin, tokens, min(n_tc, 99)


def n_confere(tc, pedido):
    try: return json.loads(tc["function"]["arguments"]).get("n") == pedido
    except Exception: return None


# ---------- pedidos ----------
def corpo(mensagens, tool_choice=None):
    b = {"model": MODELO, "messages": mensagens, "tools": [FERRAMENTA], "max_tokens": MAX_TOKENS, "stream": False,
         "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
    if tool_choice is not None: b["tool_choice"] = tool_choice
    return b


def pedido_usuario(n):
    return [{"role": "user", "content": f"Use a ferramenta obter_valor com n={n} e me diga o valor."}]


def mensagens_de_retorno(n, tc_real):
    """Retorno reenviando a chamada REAL já validada (exatamente uma) e um resultado SINTÉTICO em role=tool (nada é executado)."""
    return pedido_usuario(n) + [
        {"role": "assistant", "content": None, "tool_calls": [tc_real]},
        {"role": "tool", "tool_call_id": tc_real["id"], "content": json.dumps(RESULTADO_SINTETICO)}]


# ---------- transporte confinado ----------
class _SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None          # 3xx vira HTTPError: nada é reenviado a outro destino


def post_real(chave, url=URL):
    """post(payload, timeout) -> (status, json|None, ms). Uma tentativa, sem proxy de ambiente, sem redirect, resposta limitada."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _SemRedirect())

    def post(payload, timeout):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
        t0 = time.monotonic()
        ms = lambda: round((time.monotonic() - t0) * 1000)
        try:
            with opener.open(req, timeout=timeout) as r:
                bruto = r.read(MAX_RESPOSTA_BYTES + 1)
                if len(bruto) > MAX_RESPOSTA_BYTES: return r.status, "GRANDE", ms()
                try: return r.status, json.loads(bruto), ms()
                except ValueError: return r.status, "JSON", ms()
        except urllib.error.HTTPError as e: return int(e.code), None, ms()
        except Exception: return 0, "REDE", ms()
    return post


# ---------- roteiro ----------
def rodar(post, dormir=time.sleep, relogio=time.monotonic):
    """Executa o roteiro com `post(payload, timeout) -> (status, json, ms)`. Sem retry; interrompe na primeira falha."""
    registro, chamadas, tc_real, t_ini, motivo = [], 0, None, relogio(), None

    def passo(nome, payload, valida, pedido=None):
        nonlocal chamadas, motivo, tc_real
        if chamadas >= MAX_CHAMADAS: motivo = "LIMITE_CHAMADAS"; return False
        if chamadas:
            if relogio() - t_ini + PAUSA_S >= ORCAMENTO_S: motivo = "ORCAMENTO_ESGOTADO"; return False
            dormir(PAUSA_S)
        restante = ORCAMENTO_S - (relogio() - t_ini)
        if restante <= 1: motivo = "ORCAMENTO_ESGOTADO"; return False
        chamadas += 1
        status, resp, ms = post(payload, min(TIMEOUT_CHAMADA_S, restante))
        probs, tc = [], None
        if status != 200: probs = ["HTTP_NAO_200" if status else "ERRO_REDE"]
        elif resp == "GRANDE": probs = ["RESPOSTA_GRANDE_DEMAIS"]
        elif resp in ("JSON", "REDE"): probs = ["RESPOSTA_NAO_JSON"]
        else:
            try:
                r = valida(resp)
                probs, tc = (r[0], r[1]) if isinstance(r, tuple) else (r, None)
            except Exception: probs = ["VALIDACAO_EXCECAO"]          # nunca aborta sem relatório
        try: fin, tokens, n_tc = projeta(resp) if isinstance(resp, dict) else (None, {}, 0)
        except Exception: fin, tokens, n_tc = None, {}, 0
        reg = {"passo": nome, "ok": not probs, "problemas": probs, "status": status if isinstance(status, int) and 0 <= status < 1000 else 0,
               "latencia_ms": ms if isinstance(ms, int) else 0, "finish_reason": fin, "n_tool_calls": n_tc, "tokens": tokens}
        if pedido is not None and tc is not None: reg["n_confere"] = n_confere(tc, pedido)
        registro.append(reg)
        if not probs and nome == "1-auto": tc_real = tc
        return not probs

    ok = passo("1-auto", corpo(pedido_usuario(3), "auto"), valida_chamada, 3)
    if ok: ok = passo("2-auto-repeticao", corpo(pedido_usuario(7), "auto"), valida_chamada, 7)
    if ok: ok = passo("3-forcada", corpo(pedido_usuario(5), {"type": "function", "function": {"name": NOME}}),
                      lambda x: valida_chamada(x, NOME), 5)
    if ok: ok = passo("4-retorno-tool", corpo(mensagens_de_retorno(3, tc_real), "auto"),
                      lambda x: valida_sem_chamada(x, RESULTADO_SINTETICO["valor"]))
    if ok: ok = passo("5-tool-choice-none", corpo(pedido_usuario(3), "none"), valida_sem_chamada)
    interrompido = None if ok else (registro[-1]["passo"] if registro and not registro[-1]["ok"] else "inicio")
    return {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "alvo": "producao-existente", "modelo": MODELO,
            "chamadas": chamadas, "aprovado": ok and chamadas == 5, "interrompido_em": interrompido, "motivo": motivo,
            "orcamento_s": ORCAMENTO_S, "passos": registro,
            "nota": "protocolo apenas; n_confere e latência são metadados (concorrência normal continua); sem texto do modelo"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true", help="faz as chamadas de verdade; SEM isto não há rede")
    a = ap.parse_args()
    if not a.executar:
        print("PLANO (nenhuma chamada feita; use --executar numa JANELA ABERTA):")
        print(f"  alvo {URL} model {MODELO}; até {MAX_CHAMADAS} chamadas, max_tokens {MAX_TOKENS}, pausa {PAUSA_S:g}s, sem retry")
        print(f"  orçamento {ORCAMENTO_S}s, timeout por chamada {TIMEOUT_CHAMADA_S}s, sem proxy e sem redirect")
        for s in ("1 auto n=3", "2 auto n=7 (repetição)", "3 forçada n=5", "4 retorno role=tool sintético (chamada real do passo 1)", "5 tool_choice none"):
            print("  -", s)
        return
    chave = CHAVE.read_text().strip()
    res = rodar(post_real(chave))
    saida = ROOT / "results/gate-tools"; saida.mkdir(parents=True, exist_ok=True)
    f = saida / f"gate-tool-calls-{time.strftime('%Y%m%dT%H%M%S')}.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("aprovado", "chamadas", "interrompido_em", "motivo")}), "->", f)
    sys.exit(0 if res["aprovado"] else 1)


if __name__ == "__main__":
    main()
