# whatsapp-stickers

Pipeline dos pacotes de figurinha do WhatsApp (grupo GarrettMVP), publicados no getstickerpack.com:
uma pasta de imagens brutas entra, figurinhas 512x512 com fundo transparente saem, prontas pro
Batch upload do site. `Stickers.md` é o índice dos links publicados, versionado aqui e fonte única.
`CLAUDE.md` é o procedimento que o Claude segue quando a sessão abre nesta pasta.

Clone em `~/projects/whatsapp-stickers` no WSL (Ubuntu 24.04). Roda em Linux e em Windows.

## Setup (uma vez)

```
./setup.sh        # Linux/WSL: cria .venv/ e instala (torch CPU, rembg, ultralytics, rapidocr)
setup.cmd         # Windows: idem, com o py launcher
```

Uns minutos e ~1 GB de pacotes. Os modelos (~250 MB) baixam sozinhos no primeiro uso pra `~/.rembg/`.

## Amanhã: criar um pacote novo, do zero

1. **Imagens.** Criar `packs/<nome-do-pacote>/` (ex.: `packs/dallas-cowboys/`; todo pacote mora
   dentro de `packs/`, nunca na raiz do repo) e jogar as imagens brutas na raiz dela. Aceita `jpg`,
   `jpeg`, `png`, `webp`, em qualquer tamanho (abaixo de 300 px o script avisa que vai ficar
   borrada). Não precisa tirar fundo, redimensionar nem renomear.
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
3. **Abrir o Claude Code Desktop numa pasta do Windows** (ex.: `C:\Users\filip\OneDrive\Documentos\Stickers`,
   fica nas pastas recentes), **não** na pasta do repo: pasta `\\wsl.localhost\...` o Desktop roda
   dentro do WSL, e essa sessão não enxerga a extensão do Chrome que o passo 4 precisa (detalhe no
   `CLAUDE.md`). Como o cwd não é o repo, a primeira mensagem aponta o procedimento:
   `leia \\wsl.localhost\Ubuntu-24.04\home\pettisan\projects\whatsapp-stickers\CLAUDE.md e processa dallas-cowboys`.
   Ele roda o script (dentro do WSL), manda o `preview.png` e lista os avisos (foto pra trocar, dado
   faltando). Você aprova ou troca fotos e pede de novo.
4. **Upload.** Na mesma sessão, com o preview aprovado, dizer `sobe o dallas-cowboys`. O Claude usa
   o Chrome real (extensão Claude in Chrome, painel aberto e logado na mesma conta do app), preenche
   o form com o `report.json`, sobe os PNGs pelo Batch upload e **para antes do Publish**, mostrando
   o print. Você confere e diz `publica`. Enquanto a receita do form não estiver mapeada (ver
   `CLAUDE.md`), este passo é manual: Batch upload com tudo que está em `out/stickers/`, ícone e
   capa com o logo, dados do `out/report.json`.
5. **Link e commit.** O site revisa antes de liberar a URL. Quando ela aparecer no dashboard, dizer
   `registra o link do dallas-cowboys`: o Claude coloca no `Stickers.md` e commita a pasta do pacote
   (imagens brutas + `pack.json`) junto com o índice. `Stickers.md` é a fonte única dos links (o doc
   do Google Drive foi abolido em 2026-09-13): o pacote só está pronto com esse commit pushado.

Sem o Claude: os passos 1 e 2 iguais, depois `./stickers.sh dallas-cowboys` (WSL) ou
`stickers.cmd dallas-cowboys` (Windows) e olhar `out/preview.png` e `out/log.txt`. O argumento é o
nome da pasta em `packs/`; o script resolve o `packs/` sozinho.

## O que o script gera

`./stickers.sh dallas-cowboys` escreve em `packs/dallas-cowboys/out/` (gitignored):

| Arquivo | O que é |
|---|---|
| `stickers/01-<nome>.png … NN-<nome>.png` | 512x512, fundo transparente: selecionar tudo aqui no **Batch upload** |
| `tray.png` | 96x96, ícone do pacote na spec do WhatsApp |
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

1. **Legenda/overlay de texto** no topo ou na base é cortada fora da foto (RapidOCR acha o texto).
   Só conta como legenda texto com letras e ≥ 2 palavras, ou uma palavra ocupando ≥ 30% da largura:
   número de camisa, sigla de logo e marca d'água pequena não disparam corte. Corte em cima nunca
   passa pela pessoa; corte embaixo tira no máximo 40% da altura dela. Texto no meio da foto não é
   cortado (a linha de log avisa: aí é trocar a foto).
2. **Fundo removido** (rembg, `birefnet-general-lite`).
3. **Mais de uma pessoa na foto:** o YOLO segmenta cada uma; fica quem tem ≥ 50% da área da maior,
   o resto é apagado. Duas pessoas de tamanho parecido ficam as duas (celebração entre jogadores).
   Se a maior pessoa tem < 5% da foto, o sujeito não é gente e nada é mexido.
4. Recorte, enquadramento em 512x512 com margem.

A linha de log de cada imagem diz o que foi feito (`texto cortado: base 25%`, `pessoas: 10 -> 1`).

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

- `.venv/` na raiz do repo (gitignored), criado por `setup.sh`/`setup.cmd`. Versões usadas:
  Python 3.12 (WSL) / 3.14 (Windows); rembg 2.0.84, onnxruntime 1.30 CPU, Pillow 12.3,
  ultralytics 8.4 + torch 2.14 CPU, rapidocr 3.9.
- No Linux o torch precisa vir do índice CPU (`download.pytorch.org/whl/cpu`), senão o pip puxa o
  build com CUDA (~3 GB). O `setup.sh` faz isso antes do `requirements.txt`.
- Modelos em `~/.rembg/` (baixados no primeiro uso: `models/` do rembg, birefnet-lite ~200 MB,
  isnet 170 MB e birefnet-general ~900 MB só se usar `--model`; `yolo11m-seg.pt` 43 MB). Os do
  RapidOCR vêm dentro do pacote pip.

## Spec do WhatsApp

Fonte: `github.com/WhatsApp/stickers`, `Android/README.md`. 512x512 px, WebP, estática ≤ 100 KB,
animada ≤ 500 KB, tray 96x96 PNG ≤ 50 KB, 3 a 30 figurinhas por pacote, contorno branco de 8 px
recomendado. O getstickerpack.com aceita PNG e faz a conversão pra WebP do lado dele.
