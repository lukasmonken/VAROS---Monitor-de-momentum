#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes do atualizar.py — rode com:  python3 testes.py

Por que estes testes existem: a parte mais delicada do projeto é a lógica de
datas (qual pregão serve de base para cada período) e a detecção de quebra de
série. As duas já foram corrigidas mais de uma vez, e um ajuste inocente numa
delas volta a quebrar em silêncio — o site continua abrindo, só com número
errado. Aqui as regras ficam escritas em forma executável.

Nada aqui vai à rede: o Yahoo é substituído por uma função falsa. Dá para rodar
offline, e a GitHub Action roda antes de publicar.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import atualizar as A  # noqa: E402

A.ESPERA_ENTRE_TENTATIVAS = 0     # nos testes não se espera entre tentativas


# --------------------------------------------------------------------------- #
# Ajudantes
# --------------------------------------------------------------------------- #

def serie(precos: dict[str, float]) -> pd.Series:
    """Série de fechamentos a partir de {"AAAA-MM-DD": preço}."""
    idx = pd.to_datetime(list(precos.keys()))
    return pd.Series(list(precos.values()), index=idx)


def serie_util(inicio: str, fim: str, preco=lambda i: 100.0 + i) -> pd.Series:
    """Série em todos os dias úteis do intervalo, com preço em função da posição."""
    idx = pd.bdate_range(inicio, fim)
    return pd.Series([preco(i) for i in range(len(idx))], index=idx)


def quadro_yahoo(tickers: list[str], dias: pd.DatetimeIndex) -> pd.DataFrame:
    """Imita o retorno do yf.download(group_by='column')."""
    campos = ["Close", "High", "Low", "Open", "Volume"]
    if len(tickers) == 1:
        # Com um ticker só, o yfinance devolve colunas de nível único.
        return pd.DataFrame(
            {c: np.linspace(10, 20, len(dias)) for c in campos}, index=dias)
    cols = pd.MultiIndex.from_product([campos, tickers])
    dados = np.tile(np.linspace(10, 20, len(dias)).reshape(-1, 1), (1, len(cols)))
    return pd.DataFrame(dados, index=dias, columns=cols)


# --------------------------------------------------------------------------- #
# 1) Âncoras de calendário
# --------------------------------------------------------------------------- #

def teste_inicio_de_semana_cai_sempre_no_domingo():
    """
    "Semana" mira o domingo da semana corrente para que o último pregão <= alvo
    seja a sexta anterior. Vale para qualquer dia da semana — inclusive segunda,
    quando "Semana" coincide com "1 dia" (não é erro, é o que a janela mede).
    """
    # Semana de 03/08/2026 (segunda) a 07/08/2026 (sexta).
    for dia in ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]:
        alvo = A._inicio_semana(pd.Timestamp(dia))
        assert alvo == pd.Timestamp("2026-08-02"), (dia, alvo)
        assert alvo.weekday() == 6, "o alvo tem de ser domingo"


def teste_fim_do_mes_passado():
    """"Mês atual" mira o último dia do mês anterior, inclusive na virada de ano."""
    casos = {
        "2026-08-05": "2026-07-31",
        "2026-03-01": "2026-02-28",   # 2026 não é bissexto
        "2024-03-10": "2024-02-29",   # 2024 é
        "2026-01-15": "2025-12-31",   # vira o ano
    }
    for hoje, esperado in casos.items():
        assert A._fim_mes_passado(pd.Timestamp(hoje)) == pd.Timestamp(esperado), hoje


# --------------------------------------------------------------------------- #
# 2) Qual pregão vira base de cada período
# --------------------------------------------------------------------------- #

def teste_base_de_cada_periodo():
    """
    A regra é "último pregão com data <= alvo", que resolve fim de semana e
    feriado sozinha. As datas-base abaixo estão escritas à mão a partir de
    05/08/2026 (quarta) — se alguém mexer na regra, elas denunciam.
    """
    s = serie_util("2025-06-02", "2026-08-05")
    retornos, motivos, preco = A.calcular_retornos(s, quebras=[])

    esperado = {
        "1d":  "2026-08-04",   # terça, o pregão anterior
        "sem": "2026-07-31",   # alvo domingo 02/08 -> sexta 31/07
        "mes": "2026-07-31",   # último pregão de julho
        "1m":  "2026-07-03",   # alvo domingo 05/07 -> sexta 03/07
        "2m":  "2026-06-05",
        "3m":  "2026-05-05",
        "6m":  "2026-02-05",
        "1a":  "2025-08-05",
    }
    for chave, data_base in esperado.items():
        p0 = float(s.loc[pd.Timestamp(data_base)])
        assert retornos[chave] == round(preco / p0 - 1, 6), (
            f"{chave}: base errada — esperava o pregão de {data_base}")
    assert motivos == {}, motivos
    assert preco == round(float(s.iloc[-1]), 2)


def teste_feriado_na_ponta_da_janela():
    """
    Com o pregão-alvo ausente (feriado do papel, pregão sem negócio), a base
    anda para trás até o último fechamento existente — nunca para a frente.
    """
    s = serie({
        "2026-07-30": 100.0,
        "2026-07-31": 110.0,   # sexta, último pregão de julho
        # 03/08 e 04/08 sem negócio (buraco de propósito)
        "2026-08-05": 121.0,
    })
    retornos, _motivos, _preco = A.calcular_retornos(s, quebras=[])
    # "1 dia" mira 04/08, que não existe -> cai em 31/07.
    assert retornos["1d"] == round(121.0 / 110.0 - 1, 6), retornos["1d"]
    # "Mês atual" mira 31/07 e acerta em cheio.
    assert retornos["mes"] == round(121.0 / 110.0 - 1, 6)


def teste_ipo_recente_nao_inventa_retorno():
    """Ação sem histórico na janela pedida fica sem valor, com motivo declarado."""
    s = serie_util("2026-07-01", "2026-08-05")     # ~5 semanas de vida
    retornos, motivos, _ = A.calcular_retornos(s, quebras=[])
    for chave in ["2m", "3m", "6m", "1a"]:
        assert retornos[chave] is None, chave
        assert motivos[chave] == "sem-historico", chave
    assert retornos["1d"] is not None and "1d" not in motivos


def teste_preco_base_zerado_nao_vira_divisao_por_zero():
    s = serie({"2026-08-03": 0.0, "2026-08-04": 0.0, "2026-08-05": 10.0})
    retornos, motivos, _ = A.calcular_retornos(s, quebras=[])
    assert retornos["1d"] is None and motivos["1d"] == "sem-historico"


# --------------------------------------------------------------------------- #
# 3) Quebra de série
# --------------------------------------------------------------------------- #

def teste_detecta_quebra_do_tipo_xpml11():
    """
    Caso real: 14,19 -> 0,1376 -> 104,12. São três saltos grandes; a data
    devolvida é sempre a do pregão DEPOIS do salto.
    """
    s = serie({
        "2026-01-13": 14.19,
        "2026-01-14": 0.1376,
        "2026-01-15": 0.1380,
        "2026-01-16": 104.12,
        "2026-01-19": 105.00,
    })
    quebras = A.detectar_quebras(s)
    assert pd.Timestamp("2026-01-14") in quebras
    assert pd.Timestamp("2026-01-16") in quebras
    assert pd.Timestamp("2026-01-19") not in quebras, "alta de 0,8% não é quebra"


def teste_penny_stock_volatil_nao_e_quebra():
    """
    A RCSL4 caiu 55% num pregão e reverteu ao longo dos dias seguintes: é
    volatilidade de penny stock, e o retorno continua valendo. O limite é alto
    de propósito.
    """
    s = serie({
        "2026-03-02": 1.00,
        "2026-03-03": 0.45,   # -55%: fica abaixo do limite de 60%
        "2026-03-04": 0.55,   # +22%
        "2026-03-05": 0.70,   # +27%
    })
    assert A.detectar_quebras(s) == []


def teste_salto_grande_para_cima_tambem_e_quebra():
    """
    O critério é o tamanho do salto, não a direção — um +80% num pregão é
    tratado como quebra do mesmo jeito que uma queda equivalente. Vale saber
    porque uma recuperação violenta de penny stock cai nessa regra.
    """
    s = serie({"2026-03-02": 1.00, "2026-03-03": 1.80})
    assert A.detectar_quebras(s) == [pd.Timestamp("2026-03-03")]


def teste_serie_curta_ou_vazia():
    assert A.detectar_quebras(pd.Series(dtype=float)) == []
    assert A.detectar_quebras(serie({"2026-08-05": 10.0})) == []
    vazia = pd.Series(dtype=float)
    retornos, motivos, preco = A.calcular_retornos(vazia, quebras=[])
    assert preco is None
    assert all(v is None for v in retornos.values())
    assert all(m == "sem-historico" for m in motivos.values())


def teste_periodo_que_atravessa_quebra_fica_sem_valor():
    """
    Preços dos dois lados de uma quebra não são a mesma unidade. Todo período
    que atravessa a data é anulado; os que ficam depois dela seguem valendo.
    """
    s = serie_util("2025-06-02", "2026-08-05")
    quebras = [pd.Timestamp("2026-07-15")]     # entre "1m" e "2m"
    retornos, motivos, _ = A.calcular_retornos(s, quebras)
    for chave in ["1m", "2m", "3m", "6m", "1a"]:
        assert retornos[chave] is None, chave
        assert motivos[chave] == "quebra", chave
    # A quebra é anterior à base destes; eles não a atravessam.
    for chave in ["1d", "sem", "mes"]:
        assert retornos[chave] is not None, chave


# --------------------------------------------------------------------------- #
# 4) Escolha da carteira da B3
# --------------------------------------------------------------------------- #

def teste_carteira_mais_recente_ignora_mtime():
    """
    No GitHub Action o checkout grava todos os arquivos no mesmo instante. Com
    duas carteiras do mesmo índice na pasta, quem manda é a data que a B3
    carimba na 1ª linha do CSV — nunca o mtime, nem a ordem do glob.
    """
    tmp = tempfile.mkdtemp()
    original = A.PASTA_CARTEIRAS
    try:
        A.PASTA_CARTEIRAS = tmp
        velho = os.path.join(tmp, "IBOVDia_21-07-26.csv")
        novo = os.path.join(tmp, "IBOVDia_05-09-26.csv")
        with open(velho, "w", encoding="latin-1") as f:
            f.write("IBOV - Carteira do Dia 21/07/26\n"
                    "Código;Ação;Tipo;Qtde. Teórica;Part. (%)\n"
                    "ALOS3;ALLOS;ON NM;478.558.715;0,543;\n"
                    "PETR4;PETROBRAS;PN N2;1.000;1,000;\n")
        with open(novo, "w", encoding="latin-1") as f:
            f.write("IBOV - Carteira do Dia 05/09/26\n"
                    "Código;Ação;Tipo;Qtde. Teórica;Part. (%)\n"
                    "PETR4;PETROBRAS;PN N2;1.000;1,000;\n")
        for caminho in (velho, novo):
            os.utime(caminho, (1_700_000_000, 1_700_000_000))   # mtime idêntico

        assert A.data_da_carteira(velho) == datetime(2026, 7, 21)
        escolhido, data = A.carteira_mais_recente("IBOVDia")
        assert escolhido == novo and data == datetime(2026, 9, 5)
        assert "ALOS3" not in A.ler_carteira(escolhido), "leu a carteira velha"

        # Arquivo sem data legível não pode ganhar por ter mtime mais novo.
        sem_data = os.path.join(tmp, "IBOVDia_extra.csv")
        with open(sem_data, "w", encoding="latin-1") as f:
            f.write("IBOV - Carteira do Dia\nCódigo;Ação\nVALE3;VALE\n")
        os.utime(sem_data, (1_900_000_000, 1_900_000_000))
        assert A.data_da_carteira(sem_data) is None
        assert A.carteira_mais_recente("IBOVDia")[0] == novo

        # Índice sem CSV nenhum.
        assert A.carteira_mais_recente("NADADia") is None
    finally:
        A.PASTA_CARTEIRAS = original
        shutil.rmtree(tmp)


def teste_data_da_carteira_pelo_nome_do_arquivo():
    """Sem a linha da B3, a data sai do nome — e sem nenhuma das duas, é None."""
    tmp = tempfile.mkdtemp()
    try:
        caminho = os.path.join(tmp, "IBOVDia_03-08-26.csv")
        with open(caminho, "w", encoding="latin-1") as f:
            f.write("cabeçalho sem data\nCódigo;Ação\n")
        assert A.data_da_carteira(caminho) == datetime(2026, 8, 3)
    finally:
        shutil.rmtree(tmp)


# --------------------------------------------------------------------------- #
# 5) Resposta parcial do Yahoo
# --------------------------------------------------------------------------- #

def teste_repete_download_so_do_que_faltou():
    """A 2ª tentativa pede apenas os tickers ausentes, não a lista inteira."""
    tickers = [f"AAA{i}.SA" for i in range(100)]
    dias = pd.bdate_range("2025-09-01", periods=300)
    chamadas = []
    original = A.yf.download
    try:
        def falso(lista, **kw):
            lista = list(lista)
            chamadas.append(lista)
            entregues = lista[40:] if len(chamadas) == 1 else lista
            return quadro_yahoo(entregues, dias)
        A.yf.download = falso
        close, volume = A.baixar_precos(tickers)
    finally:
        A.yf.download = original

    assert [len(c) for c in chamadas] == [100, 40], chamadas
    assert A.sem_cotacao(close, tickers) == []
    assert len(close.columns) == 100 and len(volume.columns) == 100


def teste_yahoo_vazio_tenta_de_novo_e_depois_desiste():
    tickers = [f"AAA{i}.SA" for i in range(10)]
    dias = pd.bdate_range("2025-09-01", periods=300)
    original = A.yf.download
    try:
        tentativas = []

        def volta_na_terceira(lista, **kw):
            tentativas.append(1)
            if len(tentativas) < 3:
                return pd.DataFrame()
            return quadro_yahoo(list(lista), dias)
        A.yf.download = volta_na_terceira
        close, _ = A.baixar_precos(tickers)
        assert len(tentativas) == 3 and A.sem_cotacao(close, tickers) == []

        A.yf.download = lambda lista, **kw: pd.DataFrame()
        try:
            A.baixar_precos(tickers)
            raise AssertionError("deveria ter levantado RuntimeError")
        except RuntimeError:
            pass
    finally:
        A.yf.download = original


def _rodar_main(fracao_ausente: float) -> tuple[int | None, list[str]]:
    """
    Roda o main() com um Yahoo que nunca entrega um conjunto fixo de tickers,
    num diretório de saída temporário. Devolve (código de saída, arquivos
    gravados). A saída da tela fica engolida para o relatório não virar sopa.
    """
    tmp = tempfile.mkdtemp()
    onde, download = A.AQUI, A.yf.download
    proibidos: set[str] = set()
    try:
        A.AQUI = tmp

        def falso(lista, **kw):
            lista = list(lista)
            if not proibidos:      # define na 1ª chamada, sobre a lista cheia
                proibidos.update(lista[:int(len(lista) * fracao_ausente)])
            entregues = [t for t in lista if t not in proibidos]
            if not entregues:
                return pd.DataFrame()
            return quadro_yahoo(entregues, pd.bdate_range("2025-09-01", periods=300))
        A.yf.download = falso

        codigo = None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                A.main()
        except SystemExit as e:
            codigo = e.code
        return codigo, sorted(os.listdir(tmp))
    finally:
        A.AQUI, A.yf.download = onde, download
        shutil.rmtree(tmp)


def teste_resposta_parcial_nao_grava_nada():
    """
    Com muito ticker ausente, o script sai com erro ANTES de gravar — a Action
    não publica e o site do dia anterior continua no ar.
    """
    codigo, arquivos = _rodar_main(0.30)
    assert codigo == 1, f"deveria abortar, saiu com {codigo}"
    assert arquivos == [], f"gravou arquivo mesmo abortando: {arquivos}"


def teste_poucos_ausentes_seguem_publicando():
    """Papel suspenso ou recém-listado não pode derrubar a publicação do dia."""
    codigo, arquivos = _rodar_main(0.02)
    assert codigo is None, f"abortou sem precisar (saída {codigo})"
    assert arquivos == ["dados.js", "dados.json"], arquivos


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #

def main() -> int:
    testes = [v for k, v in sorted(globals().items()) if k.startswith("teste_")]
    print(f"Rodando {len(testes)} testes do atualizar.py\n")
    falhas = 0
    for t in testes:
        # O que o atualizar.py imprime só interessa quando o teste quebra;
        # no caminho normal ele embaralharia o relatório.
        saida = io.StringIO()
        try:
            with contextlib.redirect_stdout(saida):
                t()
        except Exception:
            falhas += 1
            print(f"  FALHOU  {t.__name__}")
            print("          " + (t.__doc__ or "").strip().splitlines()[0])
            traceback.print_exc()
            if saida.getvalue().strip():
                print("          --- saída do script durante o teste ---")
                for linha in saida.getvalue().splitlines():
                    print("          " + linha)
            print()
        else:
            print(f"  ok      {t.__name__}")

    print()
    if falhas:
        print(f"{falhas} teste(s) falharam.")
        return 1
    print("Todos os testes passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
