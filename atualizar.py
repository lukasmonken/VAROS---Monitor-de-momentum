#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Momentum — atualizador de dados (VAROS)
==================================================

O que este script faz:
  1. Lê as carteiras dos índices na pasta ./carteiras (arquivos CSV da B3).
  2. Consulta o Yahoo Finance o histórico de preços de cada ação.
  3. Calcula quanto cada ação subiu/caiu em 7d, 15d, 30d, 2m, 3m, 6m e 1 ano.
  4. Grava tudo em "dados.js", que é lido pela interface (index.html).

Como usar:
  $ python3 atualizar.py

Para atualizar as carteiras (quando a B3 mudar a composição de um índice):
  baixe o novo CSV em https://www.b3.com.br (Índices > Carteira do dia)
  e jogue o arquivo dentro da pasta ./carteiras (pode substituir o antigo).
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta

try:
    import pandas as pd
    import yfinance as yf
    from dateutil.relativedelta import relativedelta
except ImportError as e:
    print("Faltam bibliotecas. Rode:  pip install -r requirements.txt")
    print("Detalhe:", e)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_CARTEIRAS = os.path.join(AQUI, "carteiras")

# Nome amigável e prefixo do arquivo da B3 para cada índice.
INDICES = {
    "IBOV": {"nome": "Ibovespa",              "prefixo": "IBOVDia"},
    "IBXX": {"nome": "IBrX 100",              "prefixo": "IBXXDia"},
    "IDIV": {"nome": "Índice Dividendos",     "prefixo": "IDIVDia"},
    "SMLL": {"nome": "Small Caps",            "prefixo": "SMLLDia"},
}

# Períodos de momentum. A função recebe a última data disponível e devolve
# a data-alvo lá atrás; comparamos o fechamento de hoje com o de lá.
PERIODOS = {
    "7d":  ("7 dias",  lambda d: d - timedelta(days=7)),
    "15d": ("15 dias", lambda d: d - timedelta(days=15)),
    "30d": ("30 dias", lambda d: d - timedelta(days=30)),
    "2m":  ("2 meses", lambda d: d - relativedelta(months=2)),
    "3m":  ("3 meses", lambda d: d - relativedelta(months=3)),
    "6m":  ("6 meses", lambda d: d - relativedelta(months=6)),
    "1a":  ("1 ano",   lambda d: d - relativedelta(years=1)),
}

# Quantos fechamentos guardar para desenhar o mini-gráfico (sparkline).
PONTOS_SPARKLINE = 130  # ~6 meses de pregões

# Volume relativo (surto de negociação): compara a média dos últimos
# VOL_JANELA_RECENTE pregões com a média dos VOL_JANELA_BASE pregões anteriores.
VOL_JANELA_RECENTE = 5    # pregões "recentes"
VOL_JANELA_BASE = 60      # pregões de referência (o "normal" da ação)


# --------------------------------------------------------------------------- #
# 1) Ler as carteiras da B3
# --------------------------------------------------------------------------- #

def arquivo_mais_recente(prefixo: str) -> str | None:
    """Acha o CSV mais recente de um índice dentro de ./carteiras."""
    padrao = os.path.join(PASTA_CARTEIRAS, f"{prefixo}*.csv")
    arquivos = glob.glob(padrao)
    if not arquivos:
        return None
    # Mais recente pela data de modificação do arquivo.
    return max(arquivos, key=os.path.getmtime)


def ler_carteira(caminho: str) -> dict[str, str]:
    """
    Lê um CSV de carteira da B3 e devolve {ticker: nome_da_empresa}.
    O arquivo é ';'-separado, codificação latin-1, com 2 linhas de cabeçalho
    e 2 linhas de rodapé ("Quantidade Teórica Total" e "Redutor").
    """
    with open(caminho, encoding="latin-1") as f:
        linhas = f.read().splitlines()

    acoes: dict[str, str] = {}
    for linha in linhas[2:]:  # pula as 2 linhas de cabeçalho
        campos = linha.split(";")
        if not campos or not campos[0].strip():
            continue
        codigo = campos[0].strip().upper()
        # Ticker B3 válido: 4 letras + 1 ou 2 dígitos (PETR4, BPAC11, TAEE11...)
        if not re.fullmatch(r"[A-Z]{4}\d{1,2}", codigo):
            continue  # ignora rodapé ("Quantidade...", "Redutor")
        nome = campos[1].strip() if len(campos) > 1 else codigo
        acoes[codigo] = nome
    return acoes


def carregar_indices() -> dict[str, dict]:
    """Monta {codigo_indice: {nome, acoes:{ticker:nome}}} a partir dos CSVs."""
    resultado = {}
    for cod, info in INDICES.items():
        caminho = arquivo_mais_recente(info["prefixo"])
        if not caminho:
            print(f"  ! Nenhum CSV encontrado para {cod} "
                  f"(esperado {info['prefixo']}*.csv em carteiras/) — pulando.")
            continue
        acoes = ler_carteira(caminho)
        resultado[cod] = {"nome": info["nome"], "acoes": acoes}
        print(f"  • {cod:5s} {info['nome']:20s} {len(acoes):3d} ações "
              f"({os.path.basename(caminho)})")
    return resultado


# --------------------------------------------------------------------------- #
# 2) Baixar preços do Yahoo Finance
# --------------------------------------------------------------------------- #

def baixar_precos(tickers_yahoo: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Baixa ~400 dias de dados diários para todos os tickers de uma vez.
    Devolve (fechamento_ajustado, volume) — cada um um DataFrame com uma
    coluna por ticker. O volume vem do mesmo download (sem consulta extra).
    """
    inicio = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    fim = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    dados = yf.download(
        tickers_yahoo,
        start=inicio,
        end=fim,
        interval="1d",
        auto_adjust=True,     # 'Close' já vem ajustado por proventos/splits
        progress=False,
        threads=True,
        group_by="column",
    )

    if dados is None or dados.empty:
        raise RuntimeError("O Yahoo não retornou dados. Verifique a internet.")

    # Com vários tickers, dados["Close"] é um DataFrame (uma coluna por ticker).
    # Com 1 ticker só, vira uma Series — normalizamos para DataFrame.
    def _tabela(campo: str) -> pd.DataFrame:
        t = dados[campo]
        if isinstance(t, pd.Series):
            t = t.to_frame(name=tickers_yahoo[0])
        if getattr(t.index, "tz", None) is not None:
            t.index = t.index.tz_localize(None)
        return t

    return _tabela("Close"), _tabela("Volume")


# --------------------------------------------------------------------------- #
# 3) Calcular os retornos de momentum
# --------------------------------------------------------------------------- #

def calcular_retornos(serie: pd.Series) -> tuple[dict, float, list]:
    """
    Para uma série de preços de UMA ação, devolve:
      - retornos: {periodo: variação_decimal ou None}
      - preco_atual: último fechamento
      - sparkline: últimos N fechamentos (para o mini-gráfico)
    """
    serie = serie.dropna()
    if serie.empty:
        return {p: None for p in PERIODOS}, None, []

    data_atual = serie.index[-1]
    preco_atual = float(serie.iloc[-1])

    retornos: dict[str, float | None] = {}
    for chave, (_rotulo, calc_data) in PERIODOS.items():
        alvo = pd.Timestamp(calc_data(data_atual))
        # Se a ação nem existia nessa data (IPO recente), não há retorno.
        if alvo < serie.index[0]:
            retornos[chave] = None
            continue
        # asof pega o último pregão <= data-alvo (resolve feriado/fim de semana).
        preco_passado = serie.asof(alvo)
        if pd.isna(preco_passado) or preco_passado == 0:
            retornos[chave] = None
        else:
            retornos[chave] = round(preco_atual / float(preco_passado) - 1, 6)

    sparkline = [round(float(v), 2) for v in serie.iloc[-PONTOS_SPARKLINE:]]
    return retornos, round(preco_atual, 2), sparkline


def calcular_volume(vol: pd.Series, preco: pd.Series) -> tuple[float | None, float | None]:
    """
    Para UMA ação, devolve:
      - rvol: volume relativo = média recente / média de referência
              (1,0 = normal; 2,0 = negociando o dobro do usual; None se faltar dado)
      - vol_rs: volume financeiro médio recente, em R$/dia (para leitura de liquidez)
    """
    vol = vol.dropna()
    if len(vol) < 15:
        return None, None

    recente = float(vol.iloc[-VOL_JANELA_RECENTE:].mean())

    # Referência: os VOL_JANELA_BASE pregões ANTERIORES aos recentes.
    base_win = vol.iloc[-(VOL_JANELA_BASE + VOL_JANELA_RECENTE):-VOL_JANELA_RECENTE]
    if len(base_win) < 10:
        base_win = vol.iloc[:-VOL_JANELA_RECENTE]
    base = float(base_win.mean()) if len(base_win) else float("nan")

    rvol = None
    if base == base and base > 0:  # base não-NaN e positiva
        rvol = round(recente / base, 2)

    # Volume financeiro (R$) médio dos pregões recentes: volume x preço.
    financeiro = (vol * preco).dropna()
    vol_rs = None
    if len(financeiro):
        vol_rs = round(float(financeiro.iloc[-VOL_JANELA_RECENTE:].mean()), 0)

    return rvol, vol_rs


# --------------------------------------------------------------------------- #
# 4) Orquestração
# --------------------------------------------------------------------------- #

def main() -> None:
    print("=" * 62)
    print("  MONITOR DE MOMENTUM — atualização de dados")
    print("=" * 62)

    print("\n[1/3] Lendo carteiras dos índices...")
    indices = carregar_indices()
    if not indices:
        print("\nNenhuma carteira encontrada. Coloque os CSVs da B3 em "
              "carteiras/ e rode de novo.")
        sys.exit(1)

    # Conjunto único de tickers (várias ações aparecem em mais de um índice).
    tickers_b3 = sorted({t for idx in indices.values() for t in idx["acoes"]})
    tickers_yahoo = [f"{t}.SA" for t in tickers_b3]
    print(f"\n[2/3] Baixando cotações de {len(tickers_b3)} ações no Yahoo "
          f"Finance (pode levar ~1 min)...")
    close, volume = baixar_precos(tickers_yahoo)

    print("\n[3/3] Calculando momentum...")
    # Calcula os retornos de cada ticker uma única vez.
    por_ticker: dict[str, dict] = {}
    sem_dados: list[str] = []
    for t in tickers_b3:
        col = f"{t}.SA"
        if col not in close.columns:
            sem_dados.append(t)
            por_ticker[t] = {"retornos": {p: None for p in PERIODOS},
                             "preco": None, "spark": [], "rvol": None, "vol_rs": None}
            continue
        retornos, preco, spark = calcular_retornos(close[col])
        rvol, vol_rs = (None, None)
        if col in volume.columns:
            rvol, vol_rs = calcular_volume(volume[col], close[col])
        if preco is None:
            sem_dados.append(t)
        por_ticker[t] = {"retornos": retornos, "preco": preco, "spark": spark,
                         "rvol": rvol, "vol_rs": vol_rs}

    # Monta a estrutura final por índice.
    data_ref = None
    if not close.empty:
        data_ref = close.index[-1].strftime("%d/%m/%Y")

    saida = {
        "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_pregao": data_ref,
        "periodos": {k: v[0] for k, v in PERIODOS.items()},
        "indices": {},
    }
    for cod, idx in indices.items():
        lista = []
        for ticker, nome in idx["acoes"].items():
            d = por_ticker.get(ticker, {})
            lista.append({
                "ticker": ticker,
                "nome": nome,
                "preco": d.get("preco"),
                "retornos": d.get("retornos", {p: None for p in PERIODOS}),
                "spark": d.get("spark", []),
                "rvol": d.get("rvol"),
                "vol_rs": d.get("vol_rs"),
            })
        saida["indices"][cod] = {"nome": idx["nome"], "acoes": lista}

    # Grava em dois formatos:
    #   dados.js   -> para abrir o index.html com 2 cliques (sem servidor)
    #   dados.json -> para quem for hospedar num servidor
    caminho_json = os.path.join(AQUI, "dados.json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False)

    caminho_js = os.path.join(AQUI, "dados.js")
    with open(caminho_js, "w", encoding="utf-8") as f:
        f.write("window.DADOS_MOMENTUM = ")
        json.dump(saida, f, ensure_ascii=False)
        f.write(";\n")

    print("\n" + "=" * 62)
    print(f"  Pronto! Pregão de referência: {data_ref}")
    print(f"  Gerado: dados.js e dados.json")
    if sem_dados:
        print(f"  Aviso: sem cotação para {len(sem_dados)} ticker(s): "
              f"{', '.join(sem_dados)}")
    print(f"\n  Agora abra o arquivo index.html no navegador.")
    print("=" * 62)


if __name__ == "__main__":
    main()
