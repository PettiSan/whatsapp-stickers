# whatsapp-stickers — CLAUDE.md

Pipeline dos pacotes de figurinha do WhatsApp (grupo GarrettMVP), publicados no getstickerpack.com.
Repo **pessoal** do Filipe: `PettiSan/whatsapp-stickers` no GitHub (MCP `mcp__github-personal__*`,
**não** o da Smartcob), clone em `/home/pettisan/projects/whatsapp-stickers` no WSL. Não tem CI nem
Trello. O `README.md` é a referência humana; este arquivo é o procedimento que **você** segue.

## Layout

```
whatsapp-stickers/
  CLAUDE.md, README.md          este procedimento / referência humana
  make_stickers.py              o pipeline
  requirements.txt, setup.sh, setup.cmd   ambiente: cria .venv/ (gitignored) e instala
  stickers.sh, stickers.cmd     wrappers: ./stickers.sh <pacote> [opções]; <pacote> = nome da pasta em packs/
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

Do Claude Desktop (Windows), o script roda **dentro do WSL**:

```
MSYS_NO_PATHCONV=1 wsl --cd /home/pettisan/projects/whatsapp-stickers ./stickers.sh <pacote>
```

De um shell WSL (inclui sessão do Desktop cujo runtime é o WSL: shell zsh, caminhos Linux):
`./stickers.sh <pacote>`. `<pacote>` é o **nome** da pasta em `packs/`: `processa dallas-cowboys` vira
`./stickers.sh dallas-cowboys`, e o script resolve pra `packs/dallas-cowboys` sozinho (caminho de
pasta existente também é aceito, pra teste ad hoc; nome que não existe em `packs/` dá exit 2). Se
`.venv/` não existir: `./setup.sh` (uns minutos, baixa torch CPU). Modelos baixam sozinhos no
primeiro uso pra `~/.rembg/` (~250 MB).

~8 s por imagem no CPU; 30 imagens ≈ 4 min. Código de saída: `0` limpo, `3` gerou tudo mas há
AVISOS, `2` não rodou. Exit 3 **não é falha**: é a lista de coisas que o usuário precisa decidir.

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
   (caminho Windows: `\\wsl.localhost\Ubuntu-24.04\home\pettisan\projects\whatsapp-stickers\packs\<pacote>\out\preview.png`).
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

Pré-condição antes de qualquer coisa (verificado em 2026-09-13): as tools `mcp__claude-in-chrome__*`
só existem em sessão do Desktop rodando no **Windows**, que é a sessão aberta numa **pasta do
Windows** (`C:\...`, ex.: `C:\Users\filip\OneDrive\Documentos\Stickers`; shell Git Bash, a que usa
`MSYS_NO_PATHCONV=1 wsl ...`). Pasta `\\wsl.localhost\...` (inclusive a deste repo) o Desktop roda
**dentro do WSL** (modo remoto: shell zsh, caminhos Linux), e nessa sessão as tools não existem nem
pra carregar via `ToolSearch`: a ponte da extensão é o native messaging host registrado no Chrome do
Windows (`HKCU\Software\Google\Chrome\NativeMessagingHosts\com.anthropic.claude_browser_extension`),
e o CLI que roda dentro do WSL não chega nele. Se `ToolSearch` não acha `claude-in-chrome`, o upload
não é desta sessão: dizer isso ao usuário na primeira resposta, sem tentar reconectar a extensão.
A sessão Windows não carrega este arquivo sozinha (o cwd não é o repo): o usuário aponta pra ele na
primeira mensagem, e daí tudo (processar, subir, git) roda de lá via `wsl ...`.

Fonte dos dados: `out/report.json` do pacote. Ele já traz `site.name`, `site.description`,
`site.keywords` (fixas + do pack.json), `site.color`, `cover` (logo bruto), `icon` (logo já recortado
em 512), `stickers[].file` (os PNGs em ordem). Os caminhos lá são Linux (`/home/pettisan/...`); pro
`file_upload` da extensão converter pra `\\wsl.localhost\Ubuntu-24.04\home\pettisan\...`.

Regras que não mudam:
- **Nunca** clicar em *Publish stickerpack* / *Publish changes* sem um "publica" explícito do usuário
  na conversa. Mapear, preencher, subir arquivos e mostrar print: sim. Publicar: só com ordem.
- **Nunca** digitar senha em lugar nenhum, mesmo que o usuário ofereça. Login é ele quem faz.
- Reaproveitar rascunho vazio que já exista na conta antes de criar outro.
- Depois de publicado, o site passa por revisão antes de liberar o link; o link só vai pro
  `Stickers.md` quando existir de verdade (o próprio dashboard mostra a URL `getstickerpack.com/stickers/<slug>`).

Receita do formulário (campos, ordem, o que o batch upload aceita): **PENDENTE**, será mapeada na
primeira subida com o `packs/pack-1-teste` e registrada aqui. Até lá, quem sobe é o usuário, com os
arquivos de `out/stickers/` e os dados do `report.json`.

## Procedimento: registrar o link (fecha o pacote)

Depois de publicado: adicionar a linha no `Stickers.md`, na divisão certa, no formato que já está lá
(`* ### [Nome do Time](https://getstickerpack.com/stickers/<slug>)`; jogador vira sub-item `* ####`
embaixo do time). Time que já tem entrada sem link: colocar o link na entrada existente. Em seguida
commitar `Stickers.md` junto com `packs/<pacote>/` (imagens brutas + `pack.json`), mensagem
`Add <nome> pack`. O pacote só conta como pronto com esse commit feito e pushado.

## Git

- Estado sempre com `MSYS_NO_PATHCONV=1 wsl git -C /home/pettisan/projects/whatsapp-stickers status`
  (git do WSL; nunca o do Windows neste clone). Em sessão com runtime WSL, o mesmo sem o prefixo:
  `git -C /home/pettisan/projects/whatsapp-stickers status`.
- Repo pessoal, solo: commit direto na `main`, um commit por pacote ou por mudança no pipeline.
- Mostrar o diff e esperar aprovação antes de commitar; mensagem em inglês; sem `Co-Authored-By`.
- Push por SSH (`git push origin main`), sem token.
- `out/` de pacote publicado é gitignored mas é o único backup local do que está no site: não apagar.

## Não fazer

- Não "melhorar" o `make_stickers.py` sem pedido: o YOLO em subprocesso e os defaults são decisões
  medidas (ver README). Não trocar modelo, não ligar contorno, não mexer nos limiares de texto/pessoa.
- Não criar pasta, `pack.json` ou entrada no `Stickers.md` pra pacote que o usuário não pediu.
- Não criar pasta de pacote fora de `packs/`: a raiz do repo é só código, config e índice.
- Não usar o MCP do GitHub da Smartcob aqui.
