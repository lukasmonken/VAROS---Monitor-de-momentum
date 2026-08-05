#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Momentum — atualizador de dados (VAROS)
==================================================

O que este script faz:
  1. Lê as carteiras dos índices na pasta ./carteiras (arquivos CSV da B3).
  2. Consulta o Yahoo Finance o histórico de preços de cada ação.
  3. Calcula quanto cada ação subiu/caiu em 1 dia, na semana e no mês correntes,
     e em 1, 2, 3, 6 meses e 1 ano.
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
# "fora_de_todos": True mantém o índice fora da opção "Todos" da interface —
# usado para o IFIX, que é só de fundos imobiliários e não deve se misturar
# com as ações no ranking combinado.
INDICES = {
    "IBOV": {"nome": "Ibovespa",              "prefixo": "IBOVDia"},
    "IBXX": {"nome": "IBrX 100",              "prefixo": "IBXXDia"},
    "IDIV": {"nome": "Índice Dividendos",     "prefixo": "IDIVDia"},
    "SMLL": {"nome": "Small Caps",            "prefixo": "SMLLDia"},
    "IFIX": {"nome": "Fundos Imobiliários",   "prefixo": "IFIXDia",
             "fora_de_todos": True},
}

# Períodos de momentum. A função recebe a última data disponível e devolve a
# data-alvo lá atrás; comparamos o fechamento de hoje com o do último pregão
# ANTERIOR a essa data-alvo. Essa regra do "pregão anterior" é o que faz tudo
# funcionar sozinho em fim de semana e feriado.
#
# Três deles são ancorados no calendário, e não numa quantidade de dias:
#   "sem" — do fechamento da última sexta até hoje (a semana em que estamos).
#           Alvo = domingo desta semana, que cai no fechamento de sexta.
#   "mes" — do último pregão do mês passado até hoje (o mês em que estamos).
#           Alvo = último dia do mês anterior.
#   "1m"  — mesmo dia do mês passado até hoje. É o irmão de "2 meses" e
#           "3 meses". Aparece na tela como "30 dias", que é mais legível ao
#           lado de "Mês atual" — mas a conta é de mês, não de 30 dias corridos.
def _inicio_semana(d):
    """Domingo que antecede a semana corrente — cai no fechamento de sexta."""
    return d - timedelta(days=d.weekday() + 1)


def _fim_mes_passado(d):
    """Último dia do mês anterior — cai no último pregão daquele mês."""
    return d.replace(day=1) - timedelta(days=1)


PERIODOS = {
    "1d":  ("1 dia",     "Fechamento de hoje contra o do pregão anterior",
            lambda d: d - timedelta(days=1)),
    "sem": ("Semana",    "Do fechamento da última sexta até hoje — a semana corrente",
            _inicio_semana),
    "mes": ("Mês atual", "Do fechamento do último pregão do mês passado até hoje — o mês corrente",
            _fim_mes_passado),
    # Rótulo "30 dias" por ser mais legível ao lado de "Mês atual", mas a conta
    # é de mês de calendário: a chave "1m" e a descrição dizem o que ele mede
    # de fato. A janela real varia de 28 a 31 dias conforme o mês.
    "1m":  ("30 dias",   "Do mesmo dia do mês passado até hoje — de 28 a 31 dias, conforme o mês",
            lambda d: d - relativedelta(months=1)),
    "2m":  ("2 meses",   "Do mesmo dia de dois meses atrás até hoje",
            lambda d: d - relativedelta(months=2)),
    "3m":  ("3 meses",   "Do mesmo dia de três meses atrás até hoje",
            lambda d: d - relativedelta(months=3)),
    "6m":  ("6 meses",   "Do mesmo dia de seis meses atrás até hoje",
            lambda d: d - relativedelta(months=6)),
    "1a":  ("1 ano",     "Do mesmo dia do ano passado até hoje",
            lambda d: d - relativedelta(years=1)),
}

# A série de fechamentos de cada ação vai inteira para o dados.js, alinhada a
# um eixo de datas comum (campo "datas"). É isso que permite à interface
# calcular a variação de um intervalo de datas qualquer escolhido pelo usuário,
# além de desenhar o mini-gráfico (sparkline).

# Volume relativo (surto de negociação): compara a média dos últimos
# VOL_JANELA_RECENTE pregões com a média dos VOL_JANELA_BASE pregões anteriores.
VOL_JANELA_RECENTE = 5    # pregões "recentes"
VOL_JANELA_BASE = 60      # pregões de referência (o "normal" da ação)

# Quebra de série: variação de um pregão para o outro grande demais para ser
# mercado. Denuncia grupamento/desdobramento que o Yahoo não ajustou para trás,
# ou cotação corrompida. Exemplos reais encontrados na base:
#   NATU3  36,86 -> 10,19  e ficou nesse patamar (evento societário)
#   XPML11 14,19 -> 0,1376 -> 104,12 (três pregões de lixo + grupamento)
# Comparar preços dos dois lados de uma quebra não mede retorno nenhum: são
# unidades diferentes. Qualquer período que atravesse uma quebra é anulado.
# O limite é alto de propósito — a -55% de um pregão da RCSL4, que reverteu nos
# dias seguintes, é volatilidade de penny stock e continua valendo.
LIMITE_QUEBRA = 0.60


# --------------------------------------------------------------------------- #
# 1) Ler as carteiras da B3
# --------------------------------------------------------------------------- #

def data_da_carteira(caminho: str) -> datetime | None:
    """
    Data de referência da carteira, que é o que diz se ela é velha ou nova.

    Vem da 1ª linha do próprio CSV — a B3 carimba lá "IBOV - Carteira do Dia
    21/07/26". Se essa linha não estiver no formato esperado, tentamos a data no
    nome do arquivo ("IBOVDia_21-07-26.csv"). Devolve None se nenhuma das duas
    puder ser lida.
    """
    try:
        with open(caminho, encoding="latin-1") as f:
            cabecalho = f.readline()
    except OSError:
        cabecalho = ""

    # Ano com 2 dígitos: 26 -> 2026 (a regra do %y vai de 2000 a 2068).
    for texto in (cabecalho, os.path.basename(caminho)):
        m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{2}|\d{4})", texto)
        if not m:
            continue
        dia, mes, ano = m.groups()
        formato = "%d/%m/%Y" if len(ano) == 4 else "%d/%m/%y"
        try:
            return datetime.strptime(f"{dia}/{mes}/{ano}", formato)
        except ValueError:
            continue
    return None


def carteira_mais_recente(prefixo: str) -> tuple[str, datetime | None] | None:
    """
    Escolhe o CSV mais recente de um índice dentro de ./carteiras, devolvendo
    (caminho, data_de_referência).

    A ordenação é pela data que a B3 carimba no arquivo, e NÃO pela data de
    modificação: no GitHub Action o checkout grava todos os arquivos no mesmo
    instante, então o mtime não distingue nada e, com duas carteiras do mesmo
    índice na pasta, a antiga podia ser escolhida por sorteio — e o site sairia
    com a composição errada sem avisar ninguém. O mtime fica só como desempate
    para arquivos cuja data não dá para ler.
    """
    padrao = os.path.join(PASTA_CARTEIRAS, f"{prefixo}*.csv")
    arquivos = glob.glob(padrao)
    if not arquivos:
        return None
    candidatos = [(caminho, data_da_carteira(caminho)) for caminho in arquivos]
    return max(candidatos,
               key=lambda c: (c[1] or datetime.min, os.path.getmtime(c[0])))


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
        escolha = carteira_mais_recente(info["prefixo"])
        if not escolha:
            print(f"  ! Nenhum CSV encontrado para {cod} "
                  f"(esperado {info['prefixo']}*.csv em carteiras/) — pulando.")
            continue
        caminho, data = escolha
        acoes = ler_carteira(caminho)
        resultado[cod] = {"nome": info["nome"], "acoes": acoes,
                          "fora_de_todos": info.get("fora_de_todos", False),
                          "data_carteira": data.strftime("%d/%m/%Y") if data else None}
        rotulo = f"carteira de {data.strftime('%d/%m/%Y')}" if data else "data não identificada"
        print(f"  • {cod:5s} {info['nome']:20s} {len(acoes):3d} ações "
              f"({os.path.basename(caminho)} · {rotulo})")
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

def detectar_quebras(serie: pd.Series) -> list[pd.Timestamp]:
    """
    Datas em que a série dá um salto grande demais para ser mercado — ver
    LIMITE_QUEBRA. A data devolvida é a do pregão DEPOIS do salto.
    """
    s = serie.dropna()
    if len(s) < 2:
        return []
    variacao = s / s.shift(1) - 1
    return [d for d, v in variacao.items()
            if pd.notna(v) and abs(v) > LIMITE_QUEBRA]


def calcular_retornos(serie: pd.Series,
                      quebras: list) -> tuple[dict, dict, float | None]:
    """
    Para uma série de preços de UMA ação, devolve:
      - retornos: {periodo: variação_decimal ou None}
      - motivos:  {periodo: "sem-historico" | "quebra"} só para os que deram None
      - preco_atual: último fechamento
    """
    serie = serie.dropna()
    if serie.empty:
        return ({p: None for p in PERIODOS},
                {p: "sem-historico" for p in PERIODOS}, None)

    data_atual = serie.index[-1]
    preco_atual = float(serie.iloc[-1])

    retornos: dict[str, float | None] = {}
    motivos: dict[str, str] = {}
    for chave, (_rotulo, _desc, calc_data) in PERIODOS.items():
        alvo = pd.Timestamp(calc_data(data_atual))
        # Último pregão <= data-alvo (resolve feriado/fim de semana). Precisamos
        # da posição, e não só do preço, para saber a data-base do período.
        pos = serie.index.searchsorted(alvo, side="right") - 1
        if pos < 0:
            # A ação nem existia nessa data (IPO/listagem recente).
            retornos[chave] = None
            motivos[chave] = "sem-historico"
            continue

        data_base = serie.index[pos]
        preco_passado = float(serie.iloc[pos])

        # Uma quebra entre a data-base e hoje torna a comparação sem sentido.
        if any(data_base < q <= data_atual for q in quebras):
            retornos[chave] = None
            motivos[chave] = "quebra"
            continue

        if preco_passado == 0:
            retornos[chave] = None
            motivos[chave] = "sem-historico"
            continue

        retornos[chave] = round(preco_atual / preco_passado - 1, 6)

    return retornos, motivos, round(preco_atual, 2)


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
    com_quebra: list[str] = []
    for t in tickers_b3:
        col = f"{t}.SA"
        if col not in close.columns:
            sem_dados.append(t)
            por_ticker[t] = {"retornos": {p: None for p in PERIODOS},
                             "motivos": {p: "sem-historico" for p in PERIODOS},
                             "preco": None, "serie": [], "quebras": [],
                             "primeiro_pregao": None,
                             "rvol": None, "vol_rs": None}
            continue
        quebras = detectar_quebras(close[col])
        if quebras:
            com_quebra.append(f"{t} ({', '.join(q.strftime('%d/%m/%Y') for q in quebras)})")
        retornos, motivos, preco = calcular_retornos(close[col], quebras)
        rvol, vol_rs = (None, None)
        if col in volume.columns:
            rvol, vol_rs = calcular_volume(volume[col], close[col])
        if preco is None:
            sem_dados.append(t)
        # Série alinhada ao eixo comum: None onde a ação não tem fechamento
        # (ainda não existia, ou não negociou naquele pregão).
        #
        # 4 casas, não 2: esta série é a base do intervalo de datas calculado na
        # interface. Com 2 casas, um papel de centavos (R$ 0,26) carregava ~1%
        # de erro no denominador, e a coluna de intervalo discordava da coluna
        # de período fixo nas MESMAS duas datas — que o Python calcula com
        # precisão cheia.
        serie = [None if pd.isna(v) else round(float(v), 4) for v in close[col]]
        s_limpa = close[col].dropna()
        por_ticker[t] = {
            "retornos": retornos, "motivos": motivos, "preco": preco,
            "serie": serie,
            "quebras": [q.strftime("%Y-%m-%d") for q in quebras],
            "primeiro_pregao": s_limpa.index[0].strftime("%Y-%m-%d") if len(s_limpa) else None,
            "rvol": rvol, "vol_rs": vol_rs,
        }

    # Monta a estrutura final por índice.
    data_ref = None
    if not close.empty:
        data_ref = close.index[-1].strftime("%d/%m/%Y")

    # Cada ativo aparece UMA vez em "ativos"; os índices guardam só a lista de
    # tickers. Antes, uma ação presente em quatro índices tinha a série de
    # preços repetida quatro vezes no arquivo — quase metade do dados.js era
    # duplicata, comitada todo pregão pela Action.
    nomes: dict[str, str] = {}
    for idx in indices.values():
        for ticker, nome in idx["acoes"].items():
            nomes.setdefault(ticker, nome)

    ativos = {}
    for ticker in tickers_b3:
        d = por_ticker.get(ticker, {})
        ativos[ticker] = {
            "ticker": ticker,
            "nome": nomes.get(ticker, ticker),
            "preco": d.get("preco"),
            "retornos": d.get("retornos", {p: None for p in PERIODOS}),
            # Por que um período ficou sem retorno. Só entra o que deu None.
            "motivos": {k: v for k, v in (d.get("motivos") or {}).items() if v},
            "serie": d.get("serie", []),
            "quebras": d.get("quebras", []),
            "primeiro_pregao": d.get("primeiro_pregao"),
            "rvol": d.get("rvol"),
            "vol_rs": d.get("vol_rs"),
        }

    saida = {
        "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_pregao": data_ref,
        "periodos": {k: v[0] for k, v in PERIODOS.items()},
        # Explicação de cada período, para o title da coluna na interface —
        # "Semana", "Mês atual" e "1 mês" são fáceis de confundir entre si.
        "periodos_desc": {k: v[1] for k, v in PERIODOS.items()},
        # Eixo de datas comum a todas as séries (só dias de pregão).
        "datas": [d.strftime("%Y-%m-%d") for d in close.index],
        "ativos": ativos,
        "indices": {
            cod: {"nome": idx["nome"],
                  "tickers": list(idx["acoes"].keys()),
                  "fora_de_todos": idx.get("fora_de_todos", False),
                  # Data de referência do CSV da B3 que gerou esta lista — vai
                  # para a tela para dar de cara quando uma carteira ficou para
                  # trás de um rebalanceamento.
                  "data_carteira": idx.get("data_carteira")}
            for cod, idx in indices.items()
        },
    }

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
    if com_quebra:
        print(f"  Quebra de série em {len(com_quebra)} ativo(s) — os períodos "
              f"que atravessam a data ficam sem retorno:")
        for x in com_quebra:
            print(f"    · {x}")
    print(f"\n  Agora abra o arquivo index.html no navegador.")
    print("=" * 62)


if __name__ == "__main__":
    main()
