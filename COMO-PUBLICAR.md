# Como deixar o monitor online, grátis e 24/7

A ferramenta já está pronta para isso. Vamos usar **GitHub Pages** (hospeda o
site de graça, no ar 24/7) + **GitHub Actions** (roda o `atualizar.py` sozinho
todo dia, sem depender do seu computador). Custo: **zero**.

Você não precisa saber programar — o passo a passo é de clicar.

---

## Visão geral

```
   GitHub Actions (robô na nuvem)          GitHub Pages (hospedagem)
   ┌────────────────────────────┐          ┌────────────────────────┐
   │ Todo dia útil, 19:30 (BRA): │  gera    │  Seu site no ar 24/7:  │
   │ roda atualizar.py e         │ ───────► │  ...github.io/...      │
   │ publica o dados.js novo     │  dados   │  (time acessa por link)│
   └────────────────────────────┘          └────────────────────────┘
```

Os arquivos de configuração já foram criados para você:
`.github/workflows/atualizar.yml` (o robô), `.nojekyll` e `.gitignore`.

---

## Passo 1 — Criar uma conta no GitHub (grátis)

1. Acesse **github.com** e clique em **Sign up**.
2. Crie a conta (e-mail, senha, usuário). É grátis.

## Passo 2 — Instalar o GitHub Desktop

É o jeito mais fácil de enviar a pasta (sem terminal).

1. Acesse **desktop.github.com** → **Download**.
2. Instale e faça login com a conta do Passo 1.

## Passo 3 — Enviar a pasta do projeto

1. No GitHub Desktop: menu **File → Add Local Repository…**
2. Escolha a pasta **"Monitor de momentum"**.
3. Se aparecer um aviso "this directory is not a Git repository", clique em
   **"create a repository"** (ou "Create a Repository") e confirme em
   **Create Repository**.
4. Clique no botão azul **Publish repository** (canto superior direito).
   - Nome: `monitor-momentum` (ou o que preferir).
   - **Deixe MARCADO "Keep this code private"** se quiser o código escondido —
     o site funciona igual. (Público também funciona; tanto faz.)
   - Clique **Publish repository**.

Pronto, todos os arquivos subiram para o GitHub.

## Passo 4 — Ligar o site (GitHub Pages)

1. No navegador, abra **github.com** → seu repositório `monitor-momentum`.
2. Clique na aba **Settings** (engrenagem, no topo).
3. No menu da esquerda, clique em **Pages**.
4. Em **Build and deployment → Source**, escolha **Deploy from a branch**.
5. Em **Branch**, selecione **main** e a pasta **/ (root)** → clique **Save**.
6. Espere ~1 minuto e atualize a página. No topo vai aparecer:
   **"Your site is live at https://SEU-USUARIO.github.io/monitor-momentum/"**

Esse é o link do seu monitor. Já está no ar. 🎉

## Passo 5 — Ligar a atualização automática (GitHub Actions)

1. Ainda no repositório, clique na aba **Actions** (no topo).
2. Se aparecer um aviso, clique em
   **"I understand my workflows, go ahead and enable them"**.
3. Na lista à esquerda, clique em **"Atualizar dados do monitor"**.
4. Clique em **Run workflow → Run workflow** (para rodar a primeira vez agora).
5. Em 1–2 minutos ele consulta o Yahoo, gera os dados novos e o site se atualiza.

A partir daí, ele roda **sozinho todo dia útil às 19:30 (horário de Brasília)**.
Você não precisa fazer mais nada.

## Passo 6 — Compartilhar

Mande o link do Passo 4 para o time. Qualquer pessoa abre no navegador,
sem instalar nada, e sempre vê os dados atualizados.

---

## Perguntas comuns

**Quanto custa?** Nada. GitHub Pages é grátis e o robô roda ~1 minuto por dia,
muito dentro da cota gratuita.

**Preciso deixar meu computador ligado?** Não. Quem roda o `atualizar.py` é o
servidor do GitHub.

**Como mudar o horário da atualização?** Edite a linha `cron` no arquivo
`.github/workflows/atualizar.yml`. O horário é em **UTC** (Brasília = UTC − 3).
Ex.: `30 22 * * 1-5` = 22:30 UTC = **19:30 em Brasília**, de segunda a sexta.
Para 20:00 de Brasília, use `0 23 * * 1-5`.

**A B3 rebalanceou um índice — como atualizar a carteira?** Baixe o CSV novo da
B3, substitua o arquivo dentro de `carteiras/`, e no GitHub Desktop clique em
**Commit to main** e depois **Push origin**. O próximo update já usa a carteira nova.

**E se um dia a atualização falhar?** Raramente o Yahoo limita acesso de
servidores. Se acontecer, o run do dia seguinte normaliza — ou rode manual pelo
botão **Run workflow** (Passo 5). O site nunca sai do ar; no pior caso mostra os
últimos dados que deram certo.

**Posso rodar manualmente quando quiser?** Sim: aba **Actions** → "Atualizar
dados do monitor" → **Run workflow**.

---

## Alternativa sem GitHub (alto nível)

Se preferir não usar GitHub, dá para hospedar a pasta em serviços como Netlify
ou Cloudflare Pages (arrastar e soltar). Mas aí a **atualização automática** fica
por sua conta (rodar o `atualizar.py` no seu Mac e reenviar). Por isso o GitHub
é a melhor opção: resolve hospedagem **e** atualização no mesmo lugar, de graça.
