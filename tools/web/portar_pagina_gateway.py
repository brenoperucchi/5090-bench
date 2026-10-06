#!/usr/bin/env python3
"""Porta a página /benchmarks do llm-gateway (HTML/CSS/JS das T209/T212/T218, cedidos pelo llm-exec) para a página
estática do llm-bench (web/index.html, servida pelo http-server comum em http://127.0.0.1:8088/benchmarks/).
Adaptações, cada uma conferida (o script falha se o trecho original não existir mais):
  - dados de /benchmarks/data/catalog.json (gerado por tools/build_benchmarks_json.py) em vez da API do gateway;
  - o estado da tela vai no hash (#!<caminho virtual>): o servidor estático não tem rota /benchmarks/gpu/lista;
  - navbar comum /_comum/nav.js no lugar da navbar do gateway;
  - interpretação por IA desligada até o gateway liberar POST vindo da 8088 (unidade revisada do llm-exec);
  - "URL do comparativo JSON" aponta para a API do gateway (8080), que continua existindo.
Uso: python3 tools/web/portar_pagina_gateway.py <html do gateway> web/index.html"""
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
s = src.read_text(encoding="utf-8")


def troca(antigo, novo, n=1):
    global s
    achados = s.count(antigo)
    if achados != n:
        sys.exit(f"trecho esperado {n}x e achado {achados}x: {antigo[:80]!r}")
    s = s.replace(antigo, novo)


SHIM = ("const V={get(){const h=location.hash;if(h.startsWith('#!'))return decodeURIComponent(h.slice(2));"
        "return document.documentElement.lang==='en'?'/benchmarks/en/gpu/lista':'/benchmarks/gpu/lista'},real(p){return location.pathname+'#!'+encodeURIComponent(p)}};")
s = re.sub(r'<nav class="gateway-nav".*?</nav>', '', s, count=1, flags=re.S)
troca("<script>", "<script src=\"/_comum/nav.js\"></script><script>" + SHIM)
troca("fetch('/api/benchmarks/catalog',{cache:'no-store'})", "fetch('/benchmarks/data/catalog.json',{cache:'no-store'})")
troca("new URL('/api/benchmarks/compare',location.origin)", "new URL('http://127.0.0.1:8080/api/benchmarks/compare')")
troca("new URLSearchParams(location.hash.slice(1))", "new URLSearchParams(V.get().split('#')[1]||'')")
troca("location.pathname===path.split('#')[0]", "V.get().split('#')[0]===path.split('#')[0]")
troca("location.pathname+location.hash!==path", "V.get()!==path")
troca("history[replace||onlyAnchor?'replaceState':'pushState'](null,'',path)",
      "history[replace||onlyAnchor?'replaceState':'pushState'](null,'',V.real(path))")
troca("history.replaceState(null,'','/benchmarks/'+active+'/lista#v=invalid')",
      "history.replaceState(null,'',V.real('/benchmarks/'+active+'/lista#v=invalid'))")
troca("decodeBrowserView(location.href)", "decodeBrowserView('http://localhost'+V.get())")
# idioma: cada idioma é uma página estática (/benchmarks/ e /benchmarks/en/); trocar de idioma = ir à outra página com o
# mesmo estado no hash. Nunca recarregar a mesma página (era um laço: o HTML fixo não muda de idioma).
troca("location.assign(encodeBrowserView(state))",
      "location.assign((state.lang==='en'?'/benchmarks/en/':'/benchmarks/')+'#!'+encodeURIComponent(encodeBrowserView(state)))")
troca("{location.reload();return}",
      "{location.replace((state.lang==='en'?'/benchmarks/en/':'/benchmarks/')+location.hash);return}")
troca("history.pushState(null,'','/benchmarks/gpu/lista')", "history.pushState(null,'',V.real('/benchmarks/gpu/lista'))")
# interpretação: desligada nesta página até a unidade do gateway com CORS/OPTIONS estrito
troca("button.disabled=!['127.0.0.1','localhost','[::1]'].includes(location.hostname);if(button.disabled)",
      "button.disabled=true;if(button.disabled)")
s = s.replace("interpretationText('Disponível somente no acesso local;",
              "interpretationText('Indisponível nesta página por enquanto (aguarda liberação no gateway);", 1)
s = s.replace("<title>Benchmarks · LLM Gateway</title>", "<title>Benchmarks · llm-bench</title>", 1)
# interpretação em inglês: mesma regra (botão desligado)
s = s.replace("interpretationText('Disponível somente no acesso local;", "interpretationText('Indisponível nesta página por enquanto (aguarda liberação no gateway);", 1)
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(s, encoding="utf-8")
print("ok", dst, len(s))
