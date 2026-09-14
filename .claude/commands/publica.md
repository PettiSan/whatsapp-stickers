---
description: Sobe um pacote ja aprovado no getstickerpack.com e para antes de publicar
argument-hint: <pacote> [observacoes/pedidos]
---

Sobe o pacote `$1` no getstickerpack.com.

Observacoes/pedidos deste upload, se houver: $2

## Antes de comecar, checar duas coisas

1. **Modelo.** Isto tem que rodar em **Sonnet**, nao em Opus: e execucao de uma receita ja mapeada,
   e Opus dirigindo browser e token caro a toa. Se a sessao nao for Sonnet, dizer isso ao usuario e
   pedir `/model claude-sonnet-5` antes de seguir. Nao fazer o upload por subagente.
2. **Arquivos e extensao.** O upload le `packs/$1/out/report.json`, que e gitignored. Se nao existir,
   rodar `stickers.cmd $1` uma vez (uns 4 min) e so entao seguir. Depois, `ToolSearch` por
   `claude-in-chrome`; se as tools nao aparecerem, o upload nao e desta sessao, e a causa e a sessao
   ter sido aberta fora de uma pasta do Windows. Dizer isso e parar, sem tentar reconectar a extensao.

## Regras que nao mudam

- **Nunca** clicar em *Publish stickerpack* nem em *Confirm & publish* sem um "publica" explicito do
  usuario nesta conversa. Mapear, preencher, subir arquivo e mostrar print: pode. Publicar: so com
  ordem dita.
- **Nunca** digitar senha em lugar nenhum, mesmo que o usuario ofereca. Login e ele quem faz.
- Reaproveitar rascunho vazio que ja exista na conta antes de criar outro.
- Tudo numa aba so, sem recarregar nem navegar: nada e salvo no site antes do Publish.

## Passos

Fonte dos dados e sempre o `out/report.json`: ele ja traz `site.name`, `site.description`,
`site.keywords`, `site.color`, `cover`, `icon` e `stickers[].file` na ordem, com caminho absoluto.

1. Dashboard, e abrir o rascunho vazio se houver, senao *Create new sticker pack*.
2. Texto por `form_input`: `#title`, `#about`, `#backgroundColor`. Redes sociais ficam vazias.
3. Keywords: clicar no input do widget, digitar com **virgula depois de cada termo, inclusive o
   ultimo**, e `Tab`. Conferir com `javascript_tool` que `stickerPackUpdate.metadata.keywords` bateu.
4. Icone em `#trayIconInput` com `icon` (o 512 recortado, nunca o `tray.png`). Capa em `#coverFile`
   com `cover`.
5. Figurinhas: `file_upload` em `#multiStickersInput` com todos os `stickers[].file` numa chamada so,
   na ordem.
6. Conferir `getCurrentStickersCount()`, o `stickerPackUpdate.metadata` e os POST em 200. Mandar
   print da grade e **parar**, com a aba aberta.
7. So depois do "publica": `#saveStickersBtn`, depois `#confirm-terms-conditions`. Esperar o status
   virar `processed` e pegar a URL.
8. Com a URL na mao, adicionar a linha no `Stickers.md` na divisao certa e commitar.

O detalhe de como o site se comporta por dentro (o que persiste, o que nao persiste, limites da grade
de 30 slots, comportamento do widget de keywords) esta no `CLAUDE.md`, secao "upload no
getstickerpack.com". Ler de la em vez de descobrir na tentativa.
