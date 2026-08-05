# Monitor de Momentum — B3 (VAROS)

Ferramenta para ver **quais ações de um índice mais subiram (ou caíram)** em
diferentes janelas de tempo — ou em **um intervalo de datas que você escolhe**.
Os dados vêm do **Yahoo Finance** (fechamento ajustado por proventos).

| Período | O que mede |
|---------|------------|
| 1 dia | fechamento de hoje contra o do pregão anterior |
| **Semana** | do fechamento da **última sexta** até hoje — a semana em que estamos |
| **Mês atual** | do fechamento do **último pregão do mês passado** até hoje — o mês em que estamos |
| **30 dias** | do **mesmo dia do mês passado** até hoje — a janela real vai de 28 a 31 dias, conforme o mês |
| 2, 3, 6 meses e 1 ano | do mesmo dia daquele mês/ano até hoje |

"Semana" e "Mês atual" são ancorados no calendário: no primeiro pregão do mês,
os dois mostram o mesmo número, e numa segunda-feira "Semana" coincide com
"1 dia". Não é erro — é o que essas janelas significam.

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
   - limitar a Top 10 / 20 / 50 ou ver todas;
   - cortar o que negocia pouco em **Liquidez mínima** (R$ 1 mi, 5 mi ou 20 mi
     por dia). Sem esse corte, o topo do SMLL costuma ser tomado por papel de
     R$ 200 mil/dia: o retorno é real, mas não é um ativo em que dê para entrar
     e sair. O resumo diz quantos ficaram de fora.

   **No celular** a tabela vira uma lista de cartões: cada ativo mostra ticker,
   preço, o mini-gráfico e todos os períodos em blocos com rótulo, sem precisar
   rolar de lado. A faixa de períodos rola horizontalmente com o dedo.

---

## Atualizar a composição dos índices

Quando a B3 rebalancear um índice (muda a cada ~4 meses), baixe o CSV novo e
substitua o antigo:

1. Acesse o site da B3 → **Índices → Carteira do dia** → escolha o índice →
   **Download** do arquivo CSV.
2. Coloque o arquivo dentro da pasta **`carteiras/`** (pode manter o nome
   original, ex.: `IBOVDia_21-07-26.csv`). O script sempre usa o **mais recente**
   de cada índice automaticamente — e "mais recente" é pela data que a B3
   carimba na 1ª linha do CSV (`IBOV - Carteira do Dia 21/07/26`), não pela data
   de modificação do arquivo. Pode renomear à vontade; não mexa nessa 1ª linha.
3. Rode `python3 atualizar.py` de novo.

> A data da carteira em uso aparece no fim da linha de resumo do site
> ("carteira da B3 de 21/07/2026"). É o jeito de perceber que um índice ficou
> para trás de um rebalanceamento.
>
> Por que não pela data de modificação: quem publica o site é a GitHub Action, e
> o `checkout` grava todos os arquivos no mesmo instante. Com duas carteiras do
> mesmo índice na pasta, o critério de modificação virava sorteio — e o site
> podia sair com a composição antiga sem avisar ninguém.

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

3. **Atualização automática** — é o que está no ar hoje. A GitHub Action
   `.github/workflows/atualizar.yml` roda todo dia útil às 19h30 (horário de
   Brasília), busca as cotações, monta o site e publica no GitHub Pages.
   Ninguém precisa rodar nada.

Para momentum de 1 dia a 1 ano, **atualizar uma vez por dia é mais que
suficiente** — por isso não vale a pena montar um servidor rodando o tempo todo.

### Como a publicação funciona

O `dados.js` **não é versionado**. Quem o gera é a Action, na hora de publicar:
ela roda o `atualizar.py`, junta o resultado com o `index.html` e o `assets/`
numa pasta temporária, e manda essa pasta para o Pages.

```
   main  ─────►  [Action: roda o atualizar.py e monta o site]  ─────►  site no ar
   (só código)          (os dados existem só aqui)
```

Antes, a Action commitava o `dados.js` no repositório todo pregão. Funcionava,
mas qualquer branch aberta há mais de um dia colidia com esses commits e dava
conflito na hora de mergear. Tirando os dados do controle de versão, o problema
some pela raiz. O preço é não ter mais o histórico do que o site mostrou em cada
dia — o que aqui não faz falta, porque a ferramenta é de acompanhamento, não de
registro.

> Se o Pages precisar ser reconfigurado algum dia: **Settings → Pages → Source
> = GitHub Actions** (e não "Deploy from a branch").

### Quando o Yahoo falha

Sob throttling, o Yahoo responde normalmente mas com **só uma parte dos
tickers** — não dá erro, só vem menos dado. Publicar isso seria pior do que não
publicar: o site trocaria uma versão boa por uma tabela cheia de "—" com cara de
legítima. Então o `atualizar.py`:

1. **repete o download** até 3 vezes, pedindo na segunda volta apenas os tickers
   que não vieram (e não a lista inteira de novo);
2. se ainda assim mais de **10%** ficarem sem cotação, **aborta antes de gravar
   qualquer arquivo**. A Action falha, o deploy não acontece e o site do dia
   anterior continua no ar. Quem roda na mão também não perde o `dados.js` que
   já tinha.

O limite não é zero porque sempre há papel recém-listado ou suspenso que a fonte
não devolve — esses aparecem como aviso no fim da execução, sem derrubar nada.
Os três números vivem no topo do `atualizar.py` (`TENTATIVAS_DOWNLOAD`,
`ESPERA_ENTRE_TENTATIVAS`, `LIMITE_SEM_COTACAO`).

### O que a Action confere

Antes de publicar, ela roda o **`testes.py`** — se a lógica de datas ou a
detecção de quebra estiver quebrada, não faz sentido gastar um minuto no Yahoo
nem colocar número errado no ar.

Depois de publicar, ela confere **o site que ficou no ar**, e não só o que saiu
daqui, pedindo dois arquivos:

| Arquivo | Esperado | O que um resultado diferente significa |
|---|---|---|
| `/dados.js` | 200 | 404 = o site está no ar sem dados |
| `/atualizar.py` | 404 | 200 = o Pages voltou a publicar a **branch** em vez do pacote da Action |

A segunda linha é a mais útil, e nasceu de um problema real: em 05/08/2026 todos
os passos terminaram em verde e o site subiu mostrando "não encontrei o arquivo
de dados", porque o Pages estava publicando o conteúdo do repositório — onde o
`dados.js` não existe de propósito. Como o `atualizar.py` nunca entra no pacote
publicado, vê-lo respondendo no site denuncia a origem errada na hora. O
conserto está na caixa acima: **Settings → Pages → Source = GitHub Actions**.

## Rodar os testes

```bash
python3 testes.py
```

Levam cerca de um segundo e não vão à rede — o Yahoo é substituído por uma
função falsa. Cobrem as âncoras de calendário ("Semana", "Mês atual"), a regra
do "último pregão até a data-alvo" (feriado, fim de semana, IPO recente), a
detecção de quebra de série (o caso XPML11 é pego; a queda de 55% da RCSL4 não
é), a escolha da carteira da B3 e o comportamento diante de resposta parcial do
Yahoo.

São as partes que já foram corrigidas mais de uma vez e que quebram **em
silêncio**: o site continua abrindo, só com número errado.

---

## Arquivos

| Arquivo            | O que é                                                        |
|--------------------|----------------------------------------------------------------|
| `atualizar.py`     | Script que busca os dados e calcula o momentum (você roda).     |
| `index.html`       | A interface. Abra no navegador.                                 |
| `dados.js`         | Dados gerados pelo `atualizar.py` (lido pelo `index.html`). Carrega a série de fechamentos de cada ativo, que é o que permite o intervalo de datas. ~630 KB, ~220 KB comprimido no ar. **Não vai para o git** — veja "Como a publicação funciona". |
| `dados.json`       | Mesmos dados em JSON, para quem for hospedar num servidor. Também fora do git. |
| `carteiras/`       | CSVs de composição dos índices baixados da B3.                  |
| `assets/`          | Fonte Instrument Sans embutida (identidade visual VAROS). **Mantenha junto.** |
| `testes.py`        | Testes do `atualizar.py` (`python3 testes.py`, ~1s, sem internet). A Action roda antes de publicar. |
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
- **Liquidez mínima:** corta pelo **volume financeiro médio dos últimos 5
  pregões** — o mesmo número que a aba Volume mostra em "Volume (R$/dia)". Duas
  regras que valem saber:
  - quem está **sem esse dado** também sai quando há um corte ativo. Sem o
    número não dá para afirmar que o ativo passa, e deixá-lo entrar seria fingir
    que passou;
  - a **busca ignora o filtro**. Quem digita um ticker está pedindo aquele
    ativo; escondê-lo por ser ilíquido só produziria um "Nada encontrado" sem
    explicação. Para conferir a liquidez de um papel específico, a aba Volume
    mostra o R$/dia dele.
- Os retornos usam **fechamento ajustado** (proventos e desdobramentos já
  embutidos), que é a forma correta de medir momentum de retorno total.
- Cada período compara o **último pregão** com o pregão **mais próximo** da
  data-alvo (resolve feriados e fins de semana automaticamente). É por isso que
  "1 dia" numa segunda compara com a sexta, e que "Semana" e "Mês atual" caem no
  último pregão útil da semana/mês anterior mesmo quando a virada foi num
  feriado. Passe o mouse no botão ou no cabeçalho da coluna para ver o que cada
  período mede.
- **Intervalo de datas ("Datas…")**: compara duas datas quaisquer dentro do
  histórico disponível (cerca de 1 ano). Cada ponta usa o fechamento do pregão
  mais próximo **para trás**, então escolher um sábado vale a sexta. Datas fora
  do histórico são puxadas para o limite, e datas invertidas são trocadas — nos
  dois casos o próprio campo mostra a correção.
- Ações com IPO recente aparecem com "—" nos períodos que ainda não existiam.
- **Quando não dá para calcular, a ferramenta não inventa número.** Duas
  situações produzem célula sem valor, e as duas dizem o motivo (passe o mouse,
  e olhe o aviso acima da tabela):
  - **`—` sem histórico**: o ativo não tinha cotação em toda a janela pedida. O
    aviso informa a partir de que pregão ele existe.
  - **`⚠` quebra de série**: a cotação deu um salto grande demais para ser
    mercado (acima de 60% em um pregão) — grupamento ou desdobramento que o
    Yahoo não ajustou para trás, ou dado corrompido. Comparar preços dos dois
    lados dessa data não mede retorno nenhum, porque não são a mesma unidade.
    Todo período que atravessa a quebra fica sem valor, e o mini-gráfico só
    desenha o trecho posterior a ela.

    > Caso real: em 14/01/2026 o XPML11 saiu de R$ 14,19 para R$ 0,1376, ficou
    > três pregões assim e reapareceu em R$ 104,12. Sem esse tratamento, a
    > coluna de 1 ano exibia **+731%**, comparando cotações incomparáveis.
- **Formato do `dados.js`**: cada ativo aparece uma única vez em `ativos`, e os
  índices guardam só a lista de tickers. Uma ação que está em quatro índices não
  repete a série de preços quatro vezes no arquivo.
- Buscar **vários tickers separados por vírgula** mostra todos os que casarem,
  ignorando o limite de Top N — a ideia é ver a lista inteira que você pediu.
- É uma ferramenta de **acompanhamento**, não recomendação de investimento.
