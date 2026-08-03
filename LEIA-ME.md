# Monitor de Momentum — B3 (VAROS)

Ferramenta para ver **quais ações de um índice mais subiram (ou caíram)** em
diferentes janelas de tempo: 1 dia, 7 dias, 15 dias, 30 dias, 2 meses, 3 meses,
6 meses e 1 ano — ou em **um intervalo de datas que você escolhe**. Os dados vêm
do **Yahoo Finance** (fechamento ajustado por proventos).

Índices cobertos: **IBOV** (Ibovespa), **IBXX** (IBrX 100),
**IDIV** (Dividendos), **SMLL** (Small Caps) e **IFIX** (Fundos Imobiliários).

> O **IFIX** só aparece quando você o seleciona no menu de índice. Ele fica de
> fora da opção **"Todos os índices de ações"** de propósito — FII e ação são
> universos diferentes e não faz sentido rankeá-los na mesma lista.

---

## Como funciona (a ideia central)

A ferramenta tem duas partes, de propósito:

```
   ┌──────────────┐   consulta o Yahoo,    ┌───────────┐   abre no      ┌──────────────┐
   │ atualizar.py │  calcula os retornos   │ dados.js  │  navegador     │  index.html  │
   │   (Python)   │ ─────────────────────► │ (gerado)  │ ─────────────► │  (interface) │
   └──────────────┘                        └───────────┘                └──────────────┘
        VOCÊ roda                                                        QUALQUER PESSOA abre
```

- **O Python faz o trabalho pesado.** O navegador não consegue chamar o Yahoo
  diretamente (bloqueio de segurança do browser, o tal do "CORS"). Então quem
  busca os preços e calcula o momentum é o Python.
- **O HTML é só a vitrine.** Ele lê o arquivo `dados.js` que o Python gerou. Não
  precisa de internet nem de Python para abrir — é só dar dois cliques.

Resultado: **só você precisa rodar o Python**. O resto do time apenas abre o
`index.html` (ou recebe a pasta pronta).

---

## Primeira vez (instalar)

Você só precisa fazer isso uma vez, no computador que vai **atualizar** os dados:

```bash
pip install -r requirements.txt
```

---

## Uso no dia a dia

1. **Atualizar os dados** (puxa as cotações mais recentes do Yahoo):

   ```bash
   python3 atualizar.py
   ```

   Leva ~1 minuto. Ao final ele gera/atualiza o `dados.js`.

2. **Abrir a ferramenta**: dê dois cliques no `index.html`. Escolha o índice, o
   período e veja o ranking. Dá para:
   - alternar entre **maiores altas** e **maiores baixas**;
   - clicar em qualquer coluna de período para reordenar por ela;
   - buscar por ticker ou empresa — e **vários de uma vez, separados por
     vírgula** (`VAMO3, KLBN11, PETR4`), que vira uma mini-carteira na tela;
   - clicar em **Datas…** para comparar duas datas quaisquer do último ano;
   - limitar a Top 10 / 20 / 50 ou ver todas.

---

## Atualizar a composição dos índices

Quando a B3 rebalancear um índice (muda a cada ~4 meses), baixe o CSV novo e
substitua o antigo:

1. Acesse o site da B3 → **Índices → Carteira do dia** → escolha o índice →
   **Download** do arquivo CSV.
2. Coloque o arquivo dentro da pasta **`carteiras/`** (pode manter o nome
   original, ex.: `IBOVDia_21-07-26.csv`). O script sempre usa o **mais recente**
   de cada índice automaticamente.
3. Rode `python3 atualizar.py` de novo.

Para adicionar um índice novo, basta o CSV correspondente estar em `carteiras/`
e registrar o prefixo dele no dicionário `INDICES` dentro de `atualizar.py`. Se
o índice não deve entrar no "Todos" (caso do IFIX), acrescente
`"fora_de_todos": True` no registro dele.

---

## Como colocar para o time inteiro usar

Do mais simples ao mais robusto:

1. **Compartilhar a pasta** (mais simples): rode o `atualizar.py`, compacte a
   pasta e mande. Cada um abre o `index.html`. Ponto fraco: os dados congelam na
   data em que você rodou.

2. **Hospedar num link fixo** (recomendado): jogue a pasta num servidor interno,
   Google Drive/SharePoint com link, ou **GitHub Pages** (grátis). O time acessa
   por uma URL e sempre vê a mesma versão. Se hospedar num servidor de verdade, o
   `index.html` também consegue ler o `dados.json` via `fetch`.

3. **Atualização automática**: agende o `atualizar.py` para rodar sozinho todo
   dia após o fechamento (via `cron` no Mac/Linux, Agendador de Tarefas no
   Windows, ou uma GitHub Action). Aí ninguém precisa mais rodar nada — o link
   fica sempre atualizado.

Para momentum de 7 dias a 1 ano, **atualizar uma vez por dia é mais que
suficiente** — por isso não vale a pena montar um servidor rodando o tempo todo.

---

## Arquivos

| Arquivo            | O que é                                                        |
|--------------------|----------------------------------------------------------------|
| `atualizar.py`     | Script que busca os dados e calcula o momentum (você roda).     |
| `index.html`       | A interface. Abra no navegador.                                 |
| `dados.js`         | Dados gerados pelo `atualizar.py` (lido pelo `index.html`). Carrega a série de fechamentos de cada ativo, que é o que permite o intervalo de datas. ~900 KB, ~270 KB comprimido no ar. |
| `dados.json`       | Mesmos dados em JSON, para quem for hospedar num servidor.       |
| `carteiras/`       | CSVs de composição dos índices baixados da B3.                  |
| `assets/`          | Fonte Instrument Sans embutida (identidade visual VAROS). **Mantenha junto.** |
| `requirements.txt` | Bibliotecas Python necessárias.                                 |

> **Identidade visual:** segue o guia da VAROS — fundo `#131313`/preto, paleta
> verde-turquesa, textos `#E2E5EB`/`#C6CAD2` e fonte **Instrument Sans** (já
> embutida em `assets/`, funciona offline). Quedas usam vermelho como sinal
> funcional (a paleta de séries da marca não tem cor de baixa).

---

## Observações

- **Duas análises (seletor "Análise"):**
  - **Momentum** — a tabela limpa de retornos por período (1 dia a 1 ano).
  - **Volume** — visão dedicada, ordenada pelo **volume relativo**: o quanto a
    ação está sendo negociada acima do normal dela mesma (média dos últimos 5
    pregões ÷ média dos ~60 anteriores). `1,0×` = normal; `2,5×` = negociando
    2,5 vezes o usual. Traz também o volume financeiro (R$/dia) e a variação do
    período escolhido como contexto. Serve para **confirmar o momentum**: alta
    com volume alto é sinal forte; alta com volume fraco, desconfie. Clique em
    "Vol. relativo" ou "Var." para ordenar por cada uma.
- Os retornos usam **fechamento ajustado** (proventos e desdobramentos já
  embutidos), que é a forma correta de medir momentum de retorno total.
- Cada período compara o **último pregão** com o pregão **mais próximo** da
  data-alvo (resolve feriados e fins de semana automaticamente). "1 dia" é a
  variação do último pregão contra o anterior — numa segunda, contra a sexta.
- **Intervalo de datas ("Datas…")**: compara duas datas quaisquer dentro do
  histórico disponível (cerca de 1 ano). Cada ponta usa o fechamento do pregão
  mais próximo **para trás**, então escolher um sábado vale a sexta. Datas fora
  do histórico são puxadas para o limite, e datas invertidas são trocadas — nos
  dois casos o próprio campo mostra a correção.
- Ações com IPO recente aparecem com "—" nos períodos que ainda não existiam.
- Buscar **vários tickers separados por vírgula** mostra todos os que casarem,
  ignorando o limite de Top N — a ideia é ver a lista inteira que você pediu.
- É uma ferramenta de **acompanhamento**, não recomendação de investimento.
