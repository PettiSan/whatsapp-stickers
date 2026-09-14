# whatsapp-stickers — CLAUDE.md

Pipeline dos pacotes de figurinha do WhatsApp (grupo GarrettMVP), publicados no getstickerpack.com.
Repo **pessoal** do Filipe: `PettiSan/whatsapp-stickers` no GitHub (MCP `mcp__github-personal__*`,
**não** o da Smartcob), clone em `C:\Projetos\whatsapp-stickers` (Windows nativo; o clone do WSL foi
abolido em 2026-09-13). Não tem CI nem Trello. O `README.md` é a referência humana; este arquivo é o
procedimento que **você** segue.

## Layout

```
whatsapp-stickers/
  CLAUDE.md, README.md          este procedimento / referência humana
  make_stickers.py              o pipeline
  requirements.txt, setup.cmd   ambiente: cria .venv/ (gitignored) e instala
  stickers.cmd                  wrapper: stickers.cmd <pacote> [opções]; <pacote> = nome da pasta em packs/
  defaults.json                 o que é igual em todo pacote (template do nome, descrição, keywords fixas)
  pack.template.json            esqueleto do pack.json: copiar pra pasta do pacote e preencher
  Stickers.md                   índice dos links publicados, por divisão da NFL. FONTE ÚNICA: o doc
                                do Google Drive foi abolido em 2026-09-13; um pacote só está pronto
                                quando o link está aqui e commitado
  packs/                        todos os pacotes moram aqui (desde 2026-09-13); pasta de pacote na
                                raiz do repo não existe mais
    <pacote>/                   uma pasta por pacote, ex.: packs/dallas-cowboys/
      *.jpg|*.jpeg|*.png|*.webp imagens brutas, qualquer tamanho, na raiz da pasta
      logo.*                    convenção: o logo do pacote (ícone + capa no site + figurinha)
      pack.json                 { "name", "keywords", "color" }: o que muda por pacote
      out/                      gerado (gitignored): stickers/, tray.png, preview.png, log.txt, report.json
```

## Comando

A sessão do Claude Desktop abre na pasta do clone, `C:\Projetos\whatsapp-stickers`. A tool Bash é
o Git Bash, e o `.cmd` roda por ele assim (o `//c` é o `/c` escapado do MSYS):

```
cmd //c "C:\Projetos\whatsapp-stickers\stickers.cmd <pacote>"
```

No PowerShell ou no cmd é `stickers.cmd <pacote>` direto. `<pacote>` é o **nome** da pasta em
`packs/`: `processa dallas-cowboys` vira `stickers.cmd dallas-cowboys`, e o script resolve pra
`packs/dallas-cowboys` sozinho (caminho de pasta existente também é aceito, pra teste ad hoc; nome
que não existe em `packs/` dá exit 2). Se `.venv/` não existir: `setup.cmd` (uns minutos, ~2 GB;
usa o `py` launcher, Python 3.14). Modelos baixam sozinhos no primeiro uso pra
`%USERPROFILE%\.rembg\` (~250 MB).

~8 s por imagem no CPU; 30 imagens ≈ 4 min: rodar com `run_in_background` e ler `out/log.txt` no
fim. Código de saída: `0` limpo, `3` gerou tudo mas há AVISOS, `2` não rodou. Exit 3 **não é
falha**: é a lista de coisas que o usuário precisa decidir.

Se a sessão abriu num **worktree** (cwd em `.claude\worktrees\<id>`, branch `claude/...`): o
`.venv/` não está lá (gitignored) e pasta de pacote nova criada no clone também não (não
commitada). Dizer isso na primeira resposta e pedir pra reabrir a sessão direto no clone, sem
worktree; não copiar pasta de pacote pra dentro do worktree. Se mesmo assim precisar rodar o script
ali (pacote já commitado), ligar o venv por junction em vez de rodar outro `setup.cmd`:
`New-Item -ItemType Junction -Path <worktree>\.venv -Target C:\Projetos\whatsapp-stickers\.venv`
(PowerShell; a junction é gitignored como o `.venv/`).

## Procedimento: "novo pacote" / "processa <pasta>" / "roda o <pacote>"

1. Ler `packs/<pacote>/pack.json`. Se não existir, copiar `pack.template.json` pra lá e **perguntar**
   `name`, `keywords` e `color` antes de rodar (não inventar; a cor é a cor oficial do time ou a
   que o usuário disser). O script avisa se sobrou placeholder do template. Pasta de pacote que
   apareceu na raiz do repo (criada à mão no lugar errado): mover pra `packs/` antes de rodar, com
   `git mv` se já estiver versionada.

   ```json
   { "name": "Dallas Cowboys", "keywords": ["cowboys", "dak prescott"], "color": "#041E42" }
   ```

2. Conferir que existe `logo.*` na pasta. Se não, avisar antes de rodar (o site pede ícone e capa).
3. Rodar o comando. Não passar flag nenhuma por conta própria: os defaults são as decisões do
   usuário (sem contorno, cortar legenda, descartar figurante, `birefnet-general-lite`).
4. Ler `out/log.txt` e `out/report.json`. Mandar `out/preview.png` pro usuário com `SendUserFile`
   (`C:\Projetos\whatsapp-stickers\packs\<pacote>\out\preview.png`).
5. Reportar **neste formato**, nada além:
   - `AVISOS` do log, um por linha, cada um com a ação sugerida (trocar a foto X, completar
     `pack.json`, adicionar `logo.*`...). Se `sem avisos`, dizer só isso.
   - Linhas do log com `texto cortado` e `pessoas: N -> M`, pra ele saber o que foi mexido.
6. Parar e esperar. O usuário olha o preview e aprova, troca fotos ou pede rodar de novo. Só depois
   de aprovado vem o upload.

## Procedimento: upload no getstickerpack.com

Ferramenta: **Claude in Chrome** (`mcp__claude-in-chrome__*`), no Chrome real do usuário, já logado
no site. É a única que sobe arquivo num input de upload; o browser embutido do Desktop não serve.
Se a extensão não estiver conectada (`list_connected_browsers` vazio), pedir pro usuário abrir o
painel do Claude no Chrome e conferir a conta; não existe alternativa por aqui.

Pré-condição: as tools `mcp__claude-in-chrome__*` só existem em sessão do Desktop aberta numa pasta
do Windows (a do clone serve; verificado em 2026-09-13). Primeira ação: `ToolSearch` por
`claude-in-chrome`. Se não acha, o upload não é desta sessão: dizer isso ao usuário na primeira
resposta, sem tentar reconectar a extensão.

Fonte dos dados: `out/report.json` do pacote. Ele já traz `site.name`, `site.description`,
`site.keywords` (fixas + do pack.json), `site.color`, `cover` (logo bruto), `icon` (logo já recortado
em 512), `stickers[].file` (os PNGs em ordem). Os caminhos são absolutos do Windows e vão direto pro
`file_upload`.

Regras que não mudam:
- **Nunca** clicar em *Publish stickerpack* / *Publish changes* sem um "publica" explícito do usuário
  na conversa. Mapear, preencher, subir arquivos e mostrar print: sim. Publicar: só com ordem.
- **Nunca** digitar senha em lugar nenhum, mesmo que o usuário ofereça. Login é ele quem faz.
- Reaproveitar rascunho vazio que já exista na conta antes de criar outro.
- Depois de publicado, o site passa por revisão antes de liberar o link; o link só vai pro
  `Stickers.md` quando existir de verdade (o próprio dashboard mostra a URL `getstickerpack.com/stickers/<slug>`).

### Como o site funciona (lido em `js/edit-sticker-pack.js`, 2026-09-13, rascunho `139267`)

- **Nada é salvo antes do Publish.** Título, descrição, keywords, cor e redes só atualizam um objeto
  em memória (`stickerPackUpdate.metadata`). Ícone, capa e figurinhas sobem pro S3 na hora do
  `change` de cada input (`POST .../tray-icon`, `.../cover-image`, `.../upload-sticker`), mas a
  associação ao pacote também fica só em memória: o `POST .../publish-stickerpack` manda o objeto
  inteiro. Consequência: tudo numa aba só, sem recarregar, navegar ou fechar (o site avisa "leave
  without publishing?"). O "rascunho" da conta é só um id; reaberto, o form está zerado.
- Não existe botão *Save*. O único botão é *Publish stickerpack* (`#saveStickersBtn`), que exige
  ≥ 3 figurinhas ("The stickers field must be at least 3.") e abre o modal `#confirm-publication`
  (termos + "you own or have explicit written permission") com *Cancel* / *Confirm & publish*
  (`#confirm-terms-conditions`). Depois faz polling em `.../status` a cada 10 s; `processed` mostra
  "Review in progress", e a resposta traz `public_url`. Essa parte está lida no código, não vista.
- Grade de **30 slots** (`.stickerSpace[data-index=1..30]`), cada um com seu `input file`. O *Batch
  upload* (`#multiStickersInput`, `multiple`) distribui os arquivos, na ordem, nos primeiros N slots
  vazios (`[data-empty=true]`) e avisa se sobrar ("sticker pack full"). Lixeira do slot apaga.
- Ícone (`#trayIconInput`): o site guarda **como está** (o 512 ficou 512x512 no S3) e exibe a 189 px
  no círculo; o 96x96 do WhatsApp ele gera no processamento. Subir o `icon` do `report.json`, nunca
  o `tray.png`.
- Capa (`#coverFile`): vai o `cover` (o logo) e ponto. O site converte pra 1024x450 com corte
  central e o logo sai cortado; decisão do usuário em 2026-09-13, não sinalizar nem sugerir outra
  imagem.
- Keywords: widget `use-bootstrap-tag` em cima do `#keywords`, max 20, **tudo vira minúscula**
  (`#NFL` → `#nfl`). Vírgula fecha a tag. O modelo só é atualizado no `blur` do input visível do
  widget, e lê **antes** de o widget comitar o termo pendente: termo sem vírgula no fim se perde do
  modelo mesmo aparecendo como tag. Remover tag pelo × também não atualiza o modelo.

### Passos (tools `mcp__claude-in-chrome__*`; refs vêm de `find`/`read_page` e mudam a cada carga)

1. `tabs_context_mcp` + `navigate` pra `https://getstickerpack.com/dashboard`. Rascunho vazio
   (`[untitled]`, *Resume draft*): abrir `dashboard/sticker-packs/<id>`. Senão, *Create new sticker
   pack*.
2. Texto por `form_input` (dispara `change`, o modelo pega): `#title` ← `site.name`; `#about` ←
   `site.description` (max 300); `#backgroundColor` ← `site.color` (default `#25d366`). Redes
   (`#facebookUrl`, `#instagramUrl`, `#twitterUrl`, `#tiktokUrl`): vazias.
3. Keywords: `form_input` não serve. `left_click` no input visível do widget (o `find` acha por
   "input dentro do widget de keywords"; **nunca** por coordenada sem screenshot fresco, e nunca
   `type` com o foco fora de um input: espaço vira page-down), `type` com **vírgula depois de cada
   termo, inclusive o último** (`#nfl, curti, paulo antunes,`), depois `key Tab`. Depois de
   qualquer mexida (× em tag, termo a mais), clicar no input e `Tab` de novo. Conferir com
   `javascript_tool`: `stickerPackUpdate.metadata.keywords`.
4. Ícone: `file_upload` no input `#trayIconInput` (ref pelo `find`: "file input do pack icon") com
   `icon`. Capa: `file_upload` em `#coverFile` com `cover`.
5. Figurinhas: `file_upload` em `#multiStickersInput` com todos os `stickers[].file` **numa chamada
   só, na ordem** (limite da tool: 10 MB por chamada; 30 PNGs de ~200 KB cabem). Esperar ~1 s por
   arquivo. Trocar uma: `file_upload` no input do slot (`.stickerSpace[data-index=N] input`).
6. Conferir por `javascript_tool`: `getCurrentStickersCount()`, `stickerPackUpdate.metadata`
   (`title`, `keywords`, `trayIcon` e `coverImage` preenchidos), e `read_network_requests` com
   todos os `POST` em 200. Screenshot da grade pro usuário e **parar**, com a aba aberta.
7. Só com o "publica": `left_click` em `#saveStickersBtn`, depois em `#confirm-terms-conditions` no
   modal. Esperar o `.../status` virar `processed`; a URL aparece no dashboard e vai pro
   `Stickers.md`.

Mapeado em 2026-09-13 com o `packs/pack-1-teste`: título, descrição, 4 keywords, cor, ícone 512,
capa e 8 figurinhas na ordem, todos os `POST` em 200, parado antes do Publish.

## Procedimento: registrar o link (fecha o pacote)

Depois de publicado: adicionar a linha no `Stickers.md`, na divisão certa, no formato que já está lá
(`* ### [Nome do Time](https://getstickerpack.com/stickers/<slug>)`; jogador vira sub-item `* ####`
embaixo do time). Time que já tem entrada sem link: colocar o link na entrada existente. Em seguida
commitar `Stickers.md` junto com `packs/<pacote>/` (imagens brutas + `pack.json`), mensagem
`Add <nome> pack`. O pacote só conta como pronto com esse commit feito e pushado.

## Git

- Git nativo do Windows, no clone. Estado com `git status` na pasta da sessão. Line endings são do
  `.gitattributes` (LF no repo e no checkout, `.cmd` em CRLF): não mexer em `core.autocrlf`.
- Repo pessoal, solo: commit direto na `main`, um commit por pacote ou por mudança no pipeline. Em
  worktree do Desktop o commit cai na branch `claude/...`: depois de aprovado, `git push origin
  HEAD:main` (fast-forward) e `git -C C:\Projetos\whatsapp-stickers pull --ff-only` pra alinhar o
  clone.
- Mostrar o diff e esperar aprovação antes de commitar; mensagem em inglês; sem `Co-Authored-By`.
- Push por SSH (`git push origin main`), sem token.
- `out/` de pacote publicado é gitignored mas é o único backup local do que está no site: não apagar.

## Não fazer

- Não "melhorar" o `make_stickers.py` sem pedido: o YOLO em subprocesso e os defaults são decisões
  medidas (ver README). Não trocar modelo, não ligar contorno, não mexer nos limiares de texto/pessoa.
- Não criar pasta, `pack.json` ou entrada no `Stickers.md` pra pacote que o usuário não pediu.
- Não criar pasta de pacote fora de `packs/`: a raiz do repo é só código, config e índice.
- Não usar o MCP do GitHub da Smartcob aqui.
