---
description: Processa um pacote de figurinhas e reporta o resultado pra conferencia
argument-hint: <pacote> [observacoes soltas do run]
---

Processa o pacote `$1`, que e o nome de uma pasta em `packs/`.

Observacoes deste run, se houver: $2

## O que fazer

1. **`pack.json`.** Ler `packs/$1/pack.json`. Se nao existir, **propor** os campos derivados do time,
   neste formato, e esperar a resposta antes de rodar:

   ```
   Sugestoes pack.json:
   name: "<Time>"
   color: "<#RRGGBB da cor oficial>"
   keywords: <time>, <cidade>, <jogadores que aparecem nas fotos>
   ```

   O `#NFL` entra sozinho pelo `defaults.json`, nao repetir na sugestao.

2. **Logo.** Conferir que existe `logo.*` na pasta. Se nao, avisar antes de rodar.

3. **Rodar.** `stickers.cmd $1`, sem inventar flag: os defaults sao decisoes medidas. Demora uns
   8 s por imagem, entao rodar em background e ler `out/log.txt` no fim. Saida `3` nao e falha, e a
   lista de coisas pra voce decidir.

4. **Reportar**, so isto:
   - os `AVISOS` do log, um por linha, cada um com a acao sugerida;
   - as linhas com `texto cortado`, `pessoas: N -> M`, `objeto junto`, `bola:` e `crop do pack.json`,
     que e o que mostra o que o script mexeu;
   - mandar `out/preview.png` com `SendUserFile`.

5. **Parar e esperar.** O upload so acontece depois que ele aprovar o preview.

## Pedido por foto

Se ele pedir tratamento especial de uma foto, isso **nao** se resolve na conversa nem na prosa: grava
em `packs/$1/pack.json`, no bloco `photos`. Assim o mesmo comando da o mesmo resultado daqui a seis
meses. Todo retangulo e `[x1, y1, x2, y2]` em fracao de 0 a 1 da imagem original.

```json
"photos": {
  "mike-3": { "crop": [0.42, 0.23, 0.74, 0.50] },
  "kupp-2": { "keep": [[0.30, 0.08, 0.45, 0.19]] },
  "mike-2": { "drop": [[0.0, 0.58, 0.33, 1.0]] }
}
```

- "foca so no rosto", "expressao facial" -> `crop`, fechando **no rosto e mais nada** (referencia: a
  figurinha do Dak). "Corta da cintura pra baixo" tambem e `crop`.
- "faltou a bola", "sumiu o objeto" -> `keep` em volta do que sumiu.
- "sobrou sujeira", "tem uma sombra perdida" -> `drop` em cima da sujeira.

Para achar o retangulo, recortar num arquivo de teste no scratchpad e **olhar** antes de gravar, em vez
de chutar coordenada. Desenhar uma grade de coordenadas sobre a foto ampliada ajuda a ler a fracao.

**Nao** declarar por foto "mantem a bola" nem "mantem o trofeu": isso ja e comportamento padrao do
script desde que o recorte passou a tirar os pixels de quem foi descartado em vez de recortar na
silhueta do sujeito. Se mesmo assim algum objeto sair cortado, isso e bug do script, nao pedido de
usuario, e a correcao e no `make_stickers.py`.
