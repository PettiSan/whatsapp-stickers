# whatsapp-stickers

Pipeline dos pacotes de figurinha do WhatsApp (grupo GarrettMVP), publicados no getstickerpack.com:
uma pasta de imagens brutas entra, figurinhas 512x512 com fundo transparente saem, prontas pro
Batch upload do site. `Stickers.md` é o índice dos links publicados, versionado aqui e fonte única.
`CLAUDE.md` é o procedimento que o Claude segue quando a sessão abre nesta pasta.

Clone em `C:\Projetos\whatsapp-stickers`, Windows nativo (o clone do WSL foi abolido em 2026-09-13).

## Setup (uma vez)

```
setup.cmd         # cria .venv/ com o py launcher (Python 3.14) e instala rembg, ultralytics, rapidocr
```

Uns minutos e ~2 GB de pacotes (o torch CPU sozinho é ~1 GB). Os modelos (~250 MB) baixam sozinhos
no primeiro uso pra `%USERPROFILE%\.rembg\`. Tudo isso é local e gitignored: o repo em si tem ~400 KB.

## Amanhã: criar um pacote novo, do zero

1. **Imagens.** Criar `packs/<nome-do-pacote>/` (ex.: `packs/dallas-cowboys/`; todo pacote mora
   dentro de `packs/`, nunca na raiz do repo) e jogar as imagens brutas na raiz dela. Aceita `jpg`,
   `jpeg`, `png`, `webp` e `avif`, em qualquer tamanho (abaixo de 300 px o script avisa que vai ficar
   borrada). Não precisa tirar fundo, redimensionar nem renomear, nem converter o `avif` que o Google
   Imagens serve hoje.
   Uma delas tem que se chamar `logo.png` (ou `logo.jpg`...): é o ícone e a capa do pacote.
   Entre 3 e 30 imagens.
2. **Dados do site.** Copiar `pack.template.json` da raiz pra dentro da pasta como `pack.json` e
   preencher os três campos:

   ```json
   { "name": "Dallas Cowboys", "keywords": ["cowboys", "dak prescott", "jerry jones"], "color": "#041E42" }
   ```

   O nome final vira `GarrettMVP - Dallas Cowboys 2026`, a descrição e o `#NFL` vêm de
   `defaults.json`. Se pular este passo, o Claude pergunta os três valores antes de rodar; se
   sobrar placeholder do template, o script avisa.
3. **Abrir o Claude Code Desktop na pasta do clone**, `C:\Projetos\whatsapp-stickers`, com a sessão
   direto na pasta, **sem worktree**: num worktree (`.claude\worktrees\...`) a pasta nova do pacote
   e o `.venv` não aparecem, e o Claude pede pra reabrir. O `CLAUDE.md` carrega sozinho. Primeira
   mensagem: `processa dallas-cowboys`. Ele roda o script, manda o `preview.png` e lista os avisos
   (foto pra trocar, dado faltando). Você aprova ou troca fotos e pede de novo.
4. **Upload.** Na mesma sessão, com o preview aprovado, dizer `sobe o dallas-cowboys`. O Claude usa
   o Chrome real (extensão Claude in Chrome, painel aberto e logado na mesma conta do app), preenche
   o form com o `report.json`, sobe os PNGs pelo Batch upload e **para antes do Publish**, mostrando
   o print. Você confere e diz `publica`. A receita do form está no `CLAUDE.md` (mapeada em
   2026-09-13). O site **não salva rascunho**: tudo que está no form some se a aba for fechada ou
   recarregada antes do Publish, então preenchimento e publicação são na mesma aba. Sem o Claude, o
   mesmo form à mão: dados do `out/report.json`, ícone com o `NN-logo.png` (512) de `out/stickers/`,
   capa com o `logo.*` bruto, Batch upload com tudo de `out/stickers/`.
5. **Link e commit.** O site revisa antes de liberar a URL. Quando ela aparecer no dashboard, dizer
   `registra o link do dallas-cowboys`: o Claude coloca no `Stickers.md` e commita a pasta do pacote
   (imagens brutas + `pack.json`) junto com o índice. `Stickers.md` é a fonte única dos links (o doc
   do Google Drive foi abolido em 2026-09-13): o pacote só está pronto com esse commit pushado.

Sem o Claude: os passos 1 e 2 iguais, depois `stickers.cmd dallas-cowboys` e olhar `out/preview.png`
e `out/log.txt`. O argumento é o nome da pasta em `packs/`; o script resolve o `packs/` sozinho.

## O que o script gera

`stickers.cmd dallas-cowboys` escreve em `packs/dallas-cowboys/out/` (gitignored):

| Arquivo | O que é |
|---|---|
| `stickers/01-<nome>.png … NN-<nome>.png` | 512x512, fundo transparente: selecionar tudo aqui no **Batch upload** |
| `tray.png` | 96x96, ícone do pacote na spec do WhatsApp; **não sobe pro site**, que quer o 512 (`icon` do `report.json`) e gera o 96 sozinho |
| `preview.png` | folha de contato original \| resultado, pra conferir antes de subir |
| `log.txt` | o que foi feito em cada imagem (o mesmo que sai no terminal), com a seção `AVISOS` no fim |
| `report.json` | tudo que o upload precisa: dados do site já montados, caminho de cada figurinha, capa, ícone, avisos |
| `webp/` | só com `--webp`: WebP ≤ 100 KB, formato nativo do WhatsApp |

Código de saída: `0` sem avisos, `3` gerou tudo mas há avisos (foto pra trocar, `pack.json`
incompleto, `logo.*` faltando, imagem ilegível), `2` não rodou.

Imagem que saiu ruim: trocar a foto de origem (é mais barato que qualquer flag), ou rodar de novo
com `--model birefnet-general` (mais pesado).

## O que acontece com cada foto

PNG que já vem com fundo transparente (logo baixado do Google) pula tudo isso e só é enquadrado.

0. **Recorte manual**, se o `pack.json` pedir aquele arquivo no bloco `photos` (ver abaixo). Foto com
   recorte manual pula o passo 1, porque o enquadramento já foi escolhido a mão.
1. **Legenda/overlay de texto** no topo ou na base é cortada fora da foto (RapidOCR acha o texto).
   Só conta como legenda texto com letras e ≥ 2 palavras, ou uma palavra ocupando ≥ 30% da largura:
   número de camisa, sigla de logo e marca d'água pequena não disparam corte. Corte em cima nunca
   passa pela pessoa; corte embaixo tira no máximo 40% da altura dela. Texto no meio da foto não é
   cortado (a linha de log avisa: aí é trocar a foto).
2. **Fundo removido** (rembg, `birefnet-general-lite`).
3. **Mais de uma pessoa na foto:** o YOLO segmenta cada uma; fica quem tem ≥ 50% da área da maior,
   o resto é apagado. Duas pessoas de tamanho parecido ficam as duas (celebração entre jogadores).
   Se a maior pessoa tem < 5% da foto, o sujeito não é gente e nada é mexido.

   **O que o sujeito segura vai junto** (bola, troféu, capacete, microfone). Isso não é detecção de
   objeto: o corte apaga os pixels de **quem foi descartado** e mantém o que continuar grudado no
   sujeito, em vez de recortar na silhueta dele. A diferença importa quando o figurante encosta no
   sujeito, tipo repórter ao lado do jogador: ela sai, o troféu na mão dele fica. Antes de
   2026-09-14 o corte era na silhueta, e comia todo objeto na mão.

   **Bola solta no ar** (passe, chute, bola ainda não agarrada) não está grudada em ninguém, então
   dependeria de detecção: classe `sports ball` do COCO, que o mesmo YOLO já traz. Só que o COCO foi
   treinado em bola redonda e lê mal a oval. Medido no pacote do Seattle em 2026-09-14: bola na mão
   sai com 0.73 e 0.96, mas bola no ar sai com 0.113, empatada com o ruído (o logo da Pepsi num
   painel de fundo deu 0.107). Como sinal e ruído se cruzam, o limiar fica em 0.5 e **a bola solta no
   ar se perde mesmo**. É a única lacuna conhecida, e a saída seria treinar um detector, que só vale
   se isso aparecer em muitos pacotes.
4. Recorte, enquadramento em 512x512 com margem.

A linha de log de cada imagem diz o que foi feito (`texto cortado: base 25%`, `pessoas: 10 -> 1`,
`objeto junto`, `bola: 1`, `crop do pack.json`).

## Ajuste manual de uma foto

O que é gosto, e não percepção, vai no `pack.json`, no bloco `photos`. A chave é o nome do arquivo sem
extensão, e todo retângulo é `[x1, y1, x2, y2]` em **fração de 0 a 1 da imagem original**:

```json
"photos": {
  "mike-3":   { "crop": [0.42, 0.23, 0.74, 0.50] },
  "kupp-2":   { "keep": [[0.30, 0.08, 0.45, 0.19]] },
  "mike-2":   { "drop": [[0.0, 0.58, 0.33, 1.0]] }
}
```

| Chave | O que faz | Quando usar |
|---|---|---|
| `crop` | corta a foto nesse retângulo antes de tudo, e pula a busca por legenda | "quero só o rosto", "corta da cintura pra baixo" |
| `keep` | roda o rembg **de novo só dentro do retângulo** e força o que sair de lá pro resultado | o pipeline perdeu algo: bola solta no ar, objeto que o rembg leu como fundo |
| `drop` | apaga o retângulo no fim | sobrou sujeira: pedaço de gente que o YOLO não detectou, então não havia máscara pra subtrair |

`keep` funciona porque, num retângulo apertado em volta do objeto, ele é que é o saliente, então o
mesmo modelo que errou na foto inteira acerta ali dentro. É a saída para o caso da bola solta no ar,
que a detecção não cobre.

Ficando no `pack.json` e não num pedido escrito no chat, o mesmo comando dá o mesmo resultado daqui a
seis meses. Recorte fechado num rosto sobe pouco pixel pra 512 e sai mais mole, o que é esperado.

## Opções do script

| Opção | Efeito |
|---|---|
| `--outline 8` | contorno branco de 8 px (default 0: decidido em 2026-09-13, sem contorno) |
| `--margin 16` | margem transparente em volta (default 16) |
| `--model X` | `birefnet-general-lite` (default), `isnet-general-use` (5x mais rápido, pior com gente no fundo), `birefnet-general` (2x mais lento que o lite, ganho marginal) |
| `--keep-text` | não corta legenda/overlay |
| `--keep-all` | não descarta pessoas secundárias |
| `--force-bg` | trata PNG transparente como foto comum (passa por todos os passos) |
| `--tray josh` | escolhe qual imagem vira o ícone (trecho do nome; default `logo`, senão a primeira) |
| `--webp` | também gera `out/webp/` |
| `--out pasta` | saída em outro lugar (default `packs/<pacote>/out`) |

Medido em 2026-09-13 nas 8 imagens de teste (CPU, Windows): `isnet-general-use` ~1,3 s/imagem,
`birefnet-general-lite` ~7 s/imagem, `birefnet-general` ~13 s/imagem. YOLO e OCR somam ~0,5 s por
imagem. Pacote de 30 no default: uns 4 min, sem precisar ficar olhando.

O YOLO roda num processo separado de propósito: depois de uma inferência do torch no mesmo
processo, o rembg (onnxruntime) cai de ~6 s pra ~12 s por imagem e não volta. Medido, causa não
investigada; isolar resolveu.

## Ambiente

- `.venv/` na raiz do repo (gitignored), criado por `setup.cmd` com o `py` launcher. Versões usadas:
  Python 3.14; rembg 2.0.84, onnxruntime 1.30 CPU, Pillow 12.3, ultralytics 8.4 + torch 2.14 CPU,
  rapidocr 3.9.
- O torch entra transitivo pelo `ultralytics`, e no Windows o wheel default do PyPI é o CPU: por isso
  o `setup.cmd` não instala torch à parte. Se um dia vier build com CUDA (~3 GB), instalar o CPU
  antes, do índice `download.pytorch.org/whl/cpu`.
- Modelos em `%USERPROFILE%\.rembg\` (baixados no primeiro uso: `models/` do rembg, birefnet-lite ~200 MB,
  isnet 170 MB e birefnet-general ~900 MB só se usar `--model`; `yolo11m-seg.pt` 43 MB). Os do
  RapidOCR vêm dentro do pacote pip.

## Spec do WhatsApp

Fonte: `github.com/WhatsApp/stickers`, `Android/README.md`. 512x512 px, WebP, estática ≤ 100 KB,
animada ≤ 500 KB, tray 96x96 PNG ≤ 50 KB, 3 a 30 figurinhas por pacote, contorno branco de 8 px
recomendado. O getstickerpack.com aceita PNG e faz a conversão pra WebP do lado dele.
