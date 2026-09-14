#!/usr/bin/env python3
"""
make_stickers.py: converte as imagens de uma pasta de pacote em figurinhas prontas
pra subir no getstickerpack.com (PNG 512x512, fundo transparente).

Uso:
    stickers.cmd <pacote> [opcoes]                   (wrapper que usa o venv certo)
    python make_stickers.py <pacote> [opcoes]

<pacote> e o nome da pasta do pacote dentro de packs/ (dallas-cowboys -> packs/dallas-cowboys), que e
onde todo pacote mora. Um caminho de pasta que exista tambem e aceito, pra rodar ad hoc fora do repo.

Entrada:  packs/<pacote>/*.jpg | *.jpeg | *.png | *.webp | *.avif  (so a raiz; subpastas sao ignoradas)
          packs/<pacote>/logo.*                     convencao: vira o icone do pacote (tray) e a capa no site
Saida:    packs/<pacote>/out/stickers/NN-<nome>.png 512x512 RGBA: selecionar tudo aqui no Batch upload
          packs/<pacote>/out/tray.png               96x96, icone do pacote
          packs/<pacote>/out/preview.png            folha de contato original | resultado, pra conferir
          packs/<pacote>/out/log.txt                o que foi feito em cada imagem (mesmo texto do terminal)
          packs/<pacote>/out/report.json            tudo que o upload precisa: dados do site (defaults.json +
                                                    pack.json), caminho de cada figurinha, capa, icone, avisos
          packs/<pacote>/out/webp/NN-<nome>.webp    so com --webp: formato nativo do WhatsApp, <= 100 KB

Codigo de saida: 0 = tudo certo; 3 = gerou tudo, mas ha AVISOS no fim do log (foto pra trocar,
pack.json incompleto, logo faltando...); 2 = nao rodou (pasta/imagens nao encontradas).

O que acontece com cada foto (PNG que ja e transparente pula tudo isso e so e enquadrado):
  0. se o pack.json tem "photos": {"<arquivo>": {"crop": [x1, y1, x2, y2]}}, a foto e cortada nesse
     retangulo (fracao de 0 a 1) antes de tudo, e a busca por legenda e pulada: o recorte e escolha
     humana, tipo "so o rosto". E a unica coisa que se declara por foto.
  1. legenda/overlay de texto no topo ou na base e cortada fora da foto (RapidOCR acha o texto)
  2. fundo removido (rembg, birefnet)
  3. se a foto tem mais de uma pessoa, so a(s) principal(is) fica(m) (YOLO segmenta cada pessoa;
     quem tem menos da metade da area da maior e descartado). O que a pessoa principal segura vai
     junto: o corte tira os pixels de quem foi descartado, nao tudo que estiver fora da silhueta,
     entao bola, trofeu e capacete na mao sobrevivem. Bola solta no ar entra pela classe
     "sports ball" do COCO, que o mesmo YOLO ja detecta.
  4. recorte, enquadramento em 512x512 com margem

Regras que o script garante (spec oficial: github.com/WhatsApp/stickers, Android/README.md):
  - 512x512 px exatos, fundo transparente
  - tray 96x96 PNG <= 50 KB
  - com --webp, cada figurinha <= 100 KB
  - 3 a 30 figurinhas por pacote (avisa, nao bloqueia)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# o sigmoid do birefnet estoura o exp em pixel extremo; e inofensivo e polui a saida
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"rembg\..*")

STICKER = 512
TRAY = 96
WEBP_MAX = 100 * 1024
TRAY_MAX = 50 * 1024
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}  # avif: nativo no Pillow >= 11.3, sem plugin
# medido em 2026-09-13 nas imagens de teste (CPU): isnet-general-use ~1.3 s/img mas deixa gente
# de fundo e overlay; birefnet-general-lite ~7 s/img e limpa a multidao; birefnet-general ~13 s/img,
# ganho marginal sobre o lite
DEFAULT_MODEL = "birefnet-general-lite"
MODELS_DIR = Path.home() / ".rembg"  # o rembg ja guarda os dele aqui; o YOLO vai junto
YOLO_WEIGHTS = "yolo11m-seg.pt"       # ~43 MB, baixa do github.com/ultralytics/assets no primeiro uso
SCRIPT_DIR = Path(__file__).resolve().parent  # onde mora o defaults.json
PACKS_DIR = SCRIPT_DIR / "packs"              # onde mora todo pacote (raiz do repo e so codigo e config)
MIN_SOURCE_PX = 300                   # lado maior abaixo disso: a figurinha de 512 sai borrada
LANCZOS = Image.Resampling.LANCZOS

# --- texto: o que conta como legenda/overlay (e nao numero de camisa, sigla de logo etc.)
TEXT_MIN_SCORE = 0.8
TEXT_WIDE = 0.30       # uma palavra so conta se ocupar >= 30% da largura da foto
TOP_ZONE = 0.30        # legenda no topo: caixa inteira acima de 30% da altura
BOTTOM_ZONE = 0.60     # legenda na base: caixa inteira abaixo de 60% da altura
CROP_PAD = 0.02        # folga alem da caixa, fracao da altura
MIN_KEEP_HEIGHT = 0.45  # se sobrar menos que isso da foto, nao corta
PERSON_MIN_KEEP = 0.60  # corte na base pode tirar no maximo 40% da altura da pessoa principal
TEXT_NOT_CROPPED = {"texto no meio, nao cortado", "texto sobre a pessoa, nao cortado",
                    "texto demais, corte descartado"}  # viram aviso "sugiro trocar a foto"

# --- pessoas: quem fica quando ha mais de uma
PERSON_MIN_AREA = 0.05  # pessoa principal menor que 5% da foto: o sujeito nao e gente, nao mexe
PERSON_KEEP_RATIO = 0.5  # fica quem tem >= 50% da area da maior
PERSON_DILATE = 0.03    # folga em volta da mascara de quem sai, fracao do maior lado

# --- objetos: o que a pessoa principal segura nao pode ser comido junto com o figurante
BALL_CLASS = 32         # "sports ball" no COCO, ja treinado no yolo11m-seg: nao precisa treinar nada
# 0.5 e alto de proposito, e nao adianta baixar. Medido no pacote seattle-seahawks em 2026-09-14: o
# COCO foi treinado em bola redonda e le mal a oval. Bola de verdade na mao sai com 0.73 e 0.96, mas
# bola solta no ar sai com 0.113 (kupp-2), no meio do ruido: o logo da Pepsi no painel de fundo do
# sam-7 da 0.107 e um ombro do mayers-1 da 0.113 enquanto a bola real dele nao e detectada. Sinal e
# ruido se cruzam, entao limiar nenhum separa os dois, e bola falsa pintada e pior que bola perdida.
# Bola na mao nao depende disto: quem garante ela e a regra de conectividade do keep_main_people.
BALL_MIN_CONF = 0.5
OBJECT_NOTE_MIN = 0.01  # so anota "objeto junto" se ele passar de 1% da area do sujeito
# "keep" que volta enchendo mais que isto da caixa quer dizer que o rembg nao achou borda nenhuma ali
# e devolveu o retangulo inteiro. Medido: bola nitida do kupp-2 da 0.41, bola borrada do mayers-1 da 0.75.
KEEP_FALLBACK = 0.65


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "sticker"


def transparent_ratio(img: Image.Image) -> float:
    """Fracao de pixels totalmente transparentes. Zero se a imagem nao tem alpha."""
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if not has_alpha:
        return 0.0
    alpha = img.convert("RGBA").getchannel("A")
    return alpha.histogram()[0] / (alpha.width * alpha.height)


# ---------------------------------------------------------------------------
# modelos, carregados sob demanda (cada um leva segundos pra subir)

class Models:
    def __init__(self, rembg_model: str) -> None:
        self.rembg_model = rembg_model
        self._rembg = self._yolo = self._ocr = None

    def remove_bg(self, img: Image.Image) -> Image.Image:
        if self._rembg is None:
            from rembg import new_session, remove
            self._rembg = (new_session(self.rembg_model), remove)
        session, remove = self._rembg
        return remove(img, session=session)

    def captions(self, rgb: Image.Image) -> list[tuple[float, float, float, float]]:
        """Caixas (x1, y1, x2, y2) de texto que parece legenda/overlay, nao numero de camisa."""
        if self._ocr is None:
            from rapidocr import RapidOCR
            self._ocr = RapidOCR(params={"Global.log_level": "warning"})
        result = self._ocr(np.array(rgb), use_cls=False)
        boxes = []
        if result.boxes is None:
            return boxes
        for box, txt, score in zip(result.boxes, result.txts, result.scores):
            if score < TEXT_MIN_SCORE or not re.search(r"[^\W\d_]", txt):  # sem letra = numero/simbolo
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            if len(txt.split()) >= 2 or (x2 - x1) >= TEXT_WIDE * rgb.width:
                boxes.append((x1, y1, x2, y2))
        return boxes


# ---------------------------------------------------------------------------
# pessoas (YOLO) rodam num processo separado: medido em 2026-09-13, depois de uma inferencia do
# torch no mesmo processo o rembg (onnxruntime) cai de ~6 s pra ~12 s por imagem, e nao volta.

def people_prepass(sources: list[Path]) -> tuple[dict[int, list[np.ndarray]], dict[int, list[np.ndarray]]]:
    """Por imagem (indice em `sources`): mascaras das pessoas, da maior pra menor, e das bolas."""
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "people.npz"
        subprocess.run([sys.executable, __file__, "--_people-worker", str(cache), *map(str, sources)], check=True)
        with np.load(cache) as z:
            people = {int(k): list(z[k]) for k in z.files if not k.endswith("b")}
            balls = {int(k[:-1]): list(z[k]) for k in z.files if k.endswith("b")}
            return people, balls


def people_worker(cache: str, files: list[str]) -> int:
    import os
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")  # senao ele instala pacote sozinho ao tropecar
    from ultralytics import YOLO
    MODELS_DIR.mkdir(exist_ok=True)
    yolo = YOLO(str(MODELS_DIR / YOLO_WEIGHTS))
    found = {}
    for i, f in enumerate(files):
        try:
            rgb = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
            result = yolo.predict(rgb, classes=[0, BALL_CLASS], conf=0.3, verbose=False, retina_masks=True)[0]
        except Exception:  # imagem ilegivel: o processo principal reporta, aqui so segue
            found[str(i)] = found[f"{i}b"] = np.zeros((0, 1, 1), bool)
            continue
        people, balls = [], []
        if result.masks is not None:
            for data, cls, conf in zip(result.masks.data, result.boxes.cls, result.boxes.conf):
                mask = data.cpu().numpy() > 0.5
                if int(cls) == 0:
                    people.append(mask)
                elif float(conf) >= BALL_MIN_CONF:
                    balls.append(mask)
        people.sort(key=lambda m: int(m.sum()), reverse=True)
        empty = np.zeros((0, rgb.height, rgb.width), bool)
        found[str(i)] = np.array(people, dtype=bool) if people else empty
        found[f"{i}b"] = np.array(balls, dtype=bool) if balls else empty
    np.savez_compressed(cache, **found)
    return 0


# ---------------------------------------------------------------------------
# passos

def text_crop(size: tuple[int, int], boxes: list[tuple[float, float, float, float]],
              person: np.ndarray | None) -> tuple[tuple[int, int, int, int] | None, str]:
    """Faixa da foto que sobra depois de tirar legenda do topo e da base. Nunca corta pelo meio."""
    w, h = size
    top, bottom, middle = 0.0, float(h), 0
    for _, y1, _, y2 in boxes:
        if y2 <= TOP_ZONE * h:
            top = max(top, y2 + CROP_PAD * h)
        elif y1 >= BOTTOM_ZONE * h:
            bottom = min(bottom, y1 - CROP_PAD * h)
        else:
            middle += 1
    if top == 0 and bottom == h:
        return None, "texto no meio, nao cortado" if middle else ""

    if person is not None:
        rows = np.where(person.any(axis=1))[0]
        py1, py2 = int(rows[0]), int(rows[-1])
        if top > py1:  # corte de cima passaria pela pessoa (cabeca): nao corta em cima
            top = 0.0
        if bottom < py1 + PERSON_MIN_KEEP * (py2 - py1):  # tiraria mais de 40% da pessoa
            bottom = float(h)
    top_i, bottom_i = int(top), int(bottom)
    if top_i == 0 and bottom_i == h:
        return None, "texto sobre a pessoa, nao cortado"
    if bottom_i - top_i < MIN_KEEP_HEIGHT * h:
        return None, "texto demais, corte descartado"
    parts = []
    if top_i:
        parts.append(f"topo {top_i / h:.0%}")
    if bottom_i < h:
        parts.append(f"base {1 - bottom_i / h:.0%}")
    return (0, top_i, w, bottom_i), "texto cortado: " + ", ".join(parts)


def keep_main_people(alpha: Image.Image, masks: list[np.ndarray],
                     balls: list[np.ndarray]) -> tuple[Image.Image, str]:
    """Tira as pessoas secundarias sem comer o que a principal segura.

    Recortar na silhueta da pessoa apaga bola e trofeu junto, porque o YOLO segmenta o corpo e nao
    o objeto na mao. Entao aqui se corta o contrario: tira os pixels de quem foi descartado e mantem
    o que continuar grudado no sujeito. O microfone do figurante nao sobra flutuando porque a
    subtracao vem antes da busca por regiao conectada, e o que sobra solto nao encosta em ninguem.
    """
    import cv2
    areas = [int(m.sum()) for m in masks]
    biggest = max(areas)
    if biggest < PERSON_MIN_AREA * masks[0].size:
        return alpha, ""
    kept = [m for m, a in zip(masks, areas) if a >= PERSON_KEEP_RATIO * biggest]
    dropped = [m for m, a in zip(masks, areas) if a < PERSON_KEEP_RATIO * biggest]
    if not dropped:
        return alpha, f"pessoas: {len(masks)}, todas mantidas"

    arr = np.asarray(alpha)
    seed = np.logical_or.reduce(kept + balls)
    cut = np.logical_or.reduce(dropped).astype(np.uint8)
    k = max(3, int(PERSON_DILATE * max(cut.shape)) | 1)
    cut = cv2.dilate(cut, np.ones((k, k), np.uint8)).astype(bool) & ~seed

    fg = (arr > 0) & ~cut
    count, labels = cv2.connectedComponents(fg.astype(np.uint8), connectivity=8)
    lut = np.zeros(count, bool)
    lut[np.unique(labels[seed & fg])] = True
    lut[0] = False  # rotulo 0 e o fundo
    final = lut[labels]

    note = f"pessoas: {len(masks)} -> {len(kept)}"
    if int((final & ~seed).sum()) > OBJECT_NOTE_MIN * int(seed.sum()):
        note += ", objeto junto"
    return Image.fromarray(np.where(final, arr, 0).astype(np.uint8)), note


def clean_alpha(img: Image.Image, threshold: int = 8) -> Image.Image:
    """Zera alpha residual (ruido quase invisivel que o rembg deixa em volta)."""
    img.putalpha(img.getchannel("A").point(lambda v: 0 if v < threshold else v))
    return img


def trim(img: Image.Image) -> Image.Image:
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


def scale_to_fit(img: Image.Image, box: int) -> Image.Image:
    scale = box / max(img.size)
    size = tuple(max(1, round(d * scale)) for d in img.size)
    return img.resize(size, LANCZOS)


def add_outline(img: Image.Image, px: int) -> Image.Image:
    """Contorno branco de `px` pixels em volta da silhueta (o visual classico de figurinha)."""
    img = ImageOps.expand(img, border=px, fill=(0, 0, 0, 0))
    dilated = img.getchannel("A").filter(ImageFilter.MaxFilter(2 * px + 1))
    outline = Image.new("RGBA", img.size, (255, 255, 255, 255))
    outline.putalpha(dilated)
    return Image.alpha_composite(outline, img)


def center_on_canvas(img: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, dest=((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def save_webp_under(img: Image.Image, path: Path, limit: int) -> tuple[int, int]:
    """Salva WebP baixando a qualidade ate caber em `limit` bytes. Retorna (qualidade, bytes)."""
    data = b""
    quality = 95
    for quality in (95, 90, 85, 80, 75, 70, 60, 50, 40, 30):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        data = buf.getvalue()
        if len(data) <= limit:
            break
    path.write_bytes(data)
    return quality, len(data)


def checkerboard(size: int, cell: int = 16) -> Image.Image:
    board = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(204, 204, 204, 255))
    return board


def write_preview(pairs: list[tuple[str, Image.Image, Image.Image]], path: Path,
                  thumb: int = 256, cols: int = 2) -> None:
    """Folha de contato: original | resultado sobre xadrez, pra julgar o recorte de uma vez."""
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:  # Pillow antigo, sem fonte escalavel
        font = ImageFont.load_default()
    label_h, pad = 22, 12
    cell_w, cell_h = thumb * 2 + pad, thumb + label_h
    rows = -(-len(pairs) // cols)
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (cell_h + pad) + pad), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for idx, (name, before, after) in enumerate(pairs):
        cx = pad + (idx % cols) * (cell_w + pad)
        cy = pad + (idx // cols) * (cell_h + pad)
        draw.text((cx, cy + 4), name, fill=(40, 40, 40), font=font)
        white = Image.new("RGBA", before.size, (255, 255, 255, 255))
        b = ImageOps.contain(Image.alpha_composite(white, before).convert("RGB"), (thumb, thumb))
        sheet.paste(b, (cx + (thumb - b.width) // 2, cy + label_h + (thumb - b.height) // 2))
        board = checkerboard(thumb)
        board.alpha_composite(after.resize((thumb, thumb), LANCZOS))
        sheet.paste(board.convert("RGB"), (cx + thumb + pad, cy + label_h))
    sheet.save(path, "PNG", optimize=True)


def kb(n: int) -> str:
    return f"{n / 1024:.0f} KB"


def resolve_pack(arg: str) -> Path | None:
    """Padrao: <pacote> e o nome da pasta em packs/. Caminho de pasta que exista tambem serve (ad hoc)."""
    by_name = PACKS_DIR / arg
    if by_name.is_dir():
        return by_name
    as_path = Path(arg)
    if as_path.is_dir():
        return as_path
    return None


def load_metadata(pack: Path, warn) -> tuple[dict, dict]:
    """Junta defaults.json (ao lado do script) com pack.json no que o site pede, mais o bloco "photos"."""
    defaults_path = SCRIPT_DIR / "defaults.json"
    defaults: dict = {}
    if defaults_path.is_file():
        defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    else:
        warn(f"{defaults_path.name} nao encontrado ao lado do script: sem template de nome e descricao")

    meta_path = pack / "pack.json"
    meta: dict = {}
    if not meta_path.is_file():
        warn("pack.json nao encontrado na pasta do pacote: faltam name, keywords e color pro site")
    else:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            warn(f"pack.json invalido ({e}): faltam name, keywords e color pro site")

    name = meta.get("name")
    if not name:
        warn('pack.json sem "name": e o que entra no lugar de {name} no nome do pacote')
    elif "<" in name:
        warn(f'pack.json com "name" ainda do template ({name}); preencha')
    keywords = list(defaults.get("keywords_always", [])) + [k for k in meta.get("keywords", []) if k]
    if not meta.get("keywords"):
        warn('pack.json sem "keywords": o site aceita ate 20, alem das fixas do defaults.json')
    elif any("<" in k for k in keywords):
        warn('pack.json com "keywords" ainda do template; preencha')
    if len(keywords) > 20:
        warn(f"{len(keywords)} keywords; o site aceita no maximo 20")
    color = meta.get("color")
    if not (isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color)):
        warn('pack.json sem "color" valida (#RRGGBB): e a cor da pagina do pacote no site')
    site = {
        "name": defaults.get("name_template", "{name}").format(name=name or "???"),
        "description": defaults.get("description", ""),
        "keywords": keywords,
        "color": color,
    }
    photos = meta.get("photos") or {}
    if not isinstance(photos, dict):
        warn('pack.json com "photos" que nao e objeto; ignorado')
        photos = {}
    return site, photos


def crop_to_pixels(frac, size: tuple[int, int], warn, name: str) -> tuple[int, int, int, int] | None:
    """Retangulo [x1, y1, x2, y2] em fracao de 0 a 1 -> pixels. None (com aviso) se vier torto."""
    try:
        x1, y1, x2, y2 = (float(v) for v in frac)
    except (TypeError, ValueError):
        warn(f'{name}: "crop" precisa de 4 numeros [x1, y1, x2, y2] em fracao da imagem; ignorado')
        return None
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        warn(f'{name}: "crop" fora de 0..1 ou com os cantos invertidos; ignorado')
        return None
    w, h = size
    return round(x1 * w), round(y1 * h), round(x2 * w), round(y2 * h)


def crop_list(regions, size: tuple[int, int], warn, name: str,
              campo: str) -> list[tuple[int, int, int, int]]:
    if not regions:
        return []
    if not isinstance(regions, list) or not all(isinstance(r, (list, tuple)) for r in regions):
        warn(f'{name}: "{campo}" precisa ser uma lista de retangulos; ignorado')
        return []
    return [b for b in (crop_to_pixels(r, size, warn, f"{name} ({campo})") for r in regions) if b]


def shift_box(box, crop):
    """Leva um retangulo pro sistema de coordenadas de um recorte. None se ficou todo de fora."""
    x1, y1 = max(box[0] - crop[0], 0), max(box[1] - crop[1], 0)
    x2, y2 = min(box[2] - crop[0], crop[2] - crop[0]), min(box[3] - crop[1], crop[3] - crop[1])
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


# ---------------------------------------------------------------------------

def process_photo(img: Image.Image, models: Models, people: list[np.ndarray],
                  balls: list[np.ndarray], keeps: list, drops: list, keep_text: bool,
                  keep_all: bool) -> tuple[Image.Image, list[str]]:
    """Foto comum (sem transparencia): corta legenda, tira o fundo, isola a(s) pessoa(s) principal(is)."""
    notes = []
    rgb = img.convert("RGB")

    if not keep_text:
        main = max(people, key=lambda m: int(m.sum())) if people else None
        crop, note = text_crop(rgb.size, models.captions(rgb), main)
        if note:
            notes.append(note)
        if crop:
            img = img.crop(crop)
            people = [m[crop[1]:crop[3], crop[0]:crop[2]] for m in people]
            balls = [m[crop[1]:crop[3], crop[0]:crop[2]] for m in balls]
            keeps = [b for b in (shift_box(b, crop) for b in keeps) if b]
            drops = [b for b in (shift_box(b, crop) for b in drops) if b]

    source = img  # com fundo ainda: e dele que sai o recorte das regioes de "keep"
    img = models.remove_bg(img)

    if balls:  # bola solta no ar o rembg as vezes le como fundo; a mascara do YOLO garante ela
        alpha = np.asarray(img.getchannel("A")).copy()
        alpha[np.logical_or.reduce(balls)] = 255
        img.putalpha(Image.fromarray(alpha))
        notes.append(f"bola: {len(balls)}")

    forced = np.zeros((img.height, img.width), bool)
    for region in keeps:  # rembg de novo, so no retangulo: ali o objeto e que e o saliente
        patch = models.remove_bg(source.crop(region)).getchannel("A")
        recorte = np.asarray(patch) > 0
        if recorte.mean() > KEEP_FALLBACK:
            # o rembg nao achou borda nenhuma ali dentro (objeto pequeno, borrado, da cor do fundo).
            # "keep" e o usuario afirmando que tem algo ali, entao vale a caixa, so arredondada.
            oval = Image.new("L", patch.size, 0)
            ImageDraw.Draw(oval).ellipse((0, 0, patch.width - 1, patch.height - 1), fill=255)
            recorte = np.asarray(oval) > 0
            notes.append("keep sem borda, usei a caixa")
        forced[region[1]:region[3], region[0]:region[2]] |= recorte
    if keeps:
        # a cor tem que voltar da foto original junto com o alpha: onde o rembg decidiu que era fundo
        # ele zera o RGB, entao so mexer no alpha revelaria um borrao preto no lugar do objeto.
        base = np.array(img)
        base[forced, :3] = np.asarray(source.convert("RGB"))[forced]
        base[forced, 3] = 255
        img = Image.fromarray(base, "RGBA")
        notes.append(f"keep do pack.json: {len(keeps)}")

    if not keep_all and len(people) >= 2:
        alpha, note = keep_main_people(img.getchannel("A"), people, balls + ([forced] if keeps else []))
        if note:
            notes.append(note)
        img.putalpha(alpha)

    if drops:
        alpha = np.asarray(img.getchannel("A")).copy()
        for x1, y1, x2, y2 in drops:
            alpha[y1:y2, x1:x2] = 0
        img.putalpha(Image.fromarray(alpha))
        notes.append(f"drop do pack.json: {len(drops)}")
    return img, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack", help="nome do pacote, pasta em packs/ (as imagens ficam na raiz dela); "
                                 "caminho de pasta existente tambem serve")
    ap.add_argument("--out", type=Path, default=None, help="pasta de saida (default: packs/<pacote>/out)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"modelo do rembg (default: {DEFAULT_MODEL}; alternativas: isnet-general-use (rapido), birefnet-general (pesado))")
    ap.add_argument("--margin", type=int, default=16,
                    help="margem transparente em px em volta da figurinha (default: 16)")
    ap.add_argument("--outline", type=int, default=0,
                    help="contorno branco em px (default: 0 = sem contorno; a spec do WhatsApp sugere 8)")
    ap.add_argument("--keep-text", action="store_true", help="nao corta legenda/overlay de texto")
    ap.add_argument("--keep-all", action="store_true", help="nao descarta pessoas secundarias")
    ap.add_argument("--webp", action="store_true", help="tambem gera out/webp/ com WebP <= 100 KB")
    ap.add_argument("--force-bg", action="store_true",
                    help="trata PNG transparente como foto comum (passa por todos os passos)")
    ap.add_argument("--tray", default="logo",
                    help="trecho do nome do arquivo que vira o icone do pacote (default: 'logo'; senao, o primeiro)")
    args = ap.parse_args()

    pack = resolve_pack(args.pack)
    if pack is None:
        print(f"pacote nao encontrado: nem {PACKS_DIR / args.pack} nem a pasta {args.pack}", file=sys.stderr)
        return 2

    sources = sorted(p for p in pack.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    if not sources:
        print(f"nenhuma imagem ({', '.join(sorted(EXTS))}) na raiz de {pack}", file=sys.stderr)
        return 2

    inner = STICKER - 2 * args.margin - 2 * args.outline
    if inner < 64:
        print("margem + contorno grandes demais pra caber em 512 px", file=sys.stderr)
        return 2

    out = args.out or pack / "out"
    stickers_dir = out / "stickers"
    stickers_dir.mkdir(parents=True, exist_ok=True)
    webp_dir = out / "webp"
    if args.webp:
        webp_dir.mkdir(exist_ok=True)

    lines: list[str] = []
    problems: list[str] = []

    def log(msg: str = "") -> None:  # terminal + out/log.txt, pra ficar junto do preview
        print(msg)
        lines.append(msg)

    def warn(msg: str) -> None:  # vai pra secao AVISOS no fim do log e pro report.json
        problems.append(msg)

    site, photos = load_metadata(pack, warn)
    unknown = sorted(set(photos) - {p.stem for p in sources})
    if unknown:
        warn(f'pack.json com "photos" pra arquivo que nao existe: {", ".join(unknown)}')
    logo = next((p for p in sources if args.tray and args.tray.lower() in p.stem.lower()), None)
    if logo is None:
        warn(f"nenhum arquivo com '{args.tray}' no nome: icone e capa do site vao precisar de escolha "
             f"manual (usei {sources[0].name} como icone)")
    models = Models(args.model)
    if args.keep_text and args.keep_all:
        people_by_index, balls_by_index = {}, {}
    else:
        people_by_index, balls_by_index = people_prepass(sources)
    first_sticker = tray_source = None
    pairs = []
    stickers: list[dict] = []
    log(f"{len(sources)} imagens em {pack}  ->  {out}")
    if PACKS_DIR not in pack.resolve().parents:
        log(f"(pasta fora de packs/: ok pra teste ad hoc, mas pacote do repo mora em {PACKS_DIR / pack.name})")
    log()

    for i, src in enumerate(sources, start=1):
        try:
            original = ImageOps.exif_transpose(Image.open(src)).convert("RGBA")
            people = people_by_index.get(i - 1, [])
            balls = balls_by_index.get(i - 1, [])

            entry = photos.get(src.stem)
            entry = entry if isinstance(entry, dict) else {}
            wanted = entry.get("crop")
            keeps = crop_list(entry.get("keep"), original.size, warn, src.name, "keep")
            drops = crop_list(entry.get("drop"), original.size, warn, src.name, "drop")
            box = crop_to_pixels(wanted, original.size, warn, src.name) if wanted else None
            pre = []
            if box:
                original = original.crop(box)
                people = [m for m in (p[box[1]:box[3], box[0]:box[2]] for p in people) if m.any()]
                balls = [m for m in (b[box[1]:box[3], box[0]:box[2]] for b in balls) if m.any()]
                keeps = [b for b in (shift_box(b, box) for b in keeps) if b]
                drops = [b for b in (shift_box(b, box) for b in drops) if b]
                pre.append(f"crop do pack.json -> {original.width}x{original.height}")

            if max(original.size) < MIN_SOURCE_PX:
                warn(f"{src.name}: {original.width}x{original.height}, vai ficar borrada em 512; "
                     "sugiro uma versao maior")

            if args.force_bg or transparent_ratio(original) < 0.02:
                img, notes = process_photo(original, models, people, balls, keeps, drops,
                                           args.keep_text or box is not None, args.keep_all)
            else:
                img, notes = original, ["ja transparente, so enquadrado"]
            notes = pre + notes

            img = scale_to_fit(trim(clean_alpha(img)), inner)
            if args.outline:
                img = add_outline(img, args.outline)
            sticker = center_on_canvas(img, STICKER)

            name = f"{i:02d}-{slugify(src.stem)}"
            png_path = stickers_dir / f"{name}.png"
            sticker.save(png_path, "PNG", optimize=True)
        except Exception as e:  # uma foto ruim nao derruba o pacote
            log(f"{src.name}  ERRO: {e}")
            warn(f"{src.name}: erro ao processar ({e}); ficou fora do pacote")
            continue

        line = f"{name}.png  {kb(png_path.stat().st_size):>7}  " + "; ".join(notes)
        for note in notes:
            if note in TEXT_NOT_CROPPED:
                warn(f"{src.name}: {note}; sugiro trocar a foto")

        if args.webp:
            quality, size = save_webp_under(sticker, webp_dir / f"{name}.webp", WEBP_MAX)
            line += f"  | webp q{quality} {kb(size)}" + ("" if size <= WEBP_MAX else "  ACIMA DE 100 KB")

        first_sticker = first_sticker or sticker
        if src == logo:
            tray_source = sticker
        stickers.append({"file": str(png_path.resolve()), "source": src.name, "notes": notes,
                         "is_logo": src == logo})
        pairs.append((src.name, original, sticker))
        log(line)

    if not stickers:
        log("\nnenhuma imagem processada")
        return 2
    if not 3 <= len(stickers) <= 30:
        warn(f"{len(stickers)} figurinhas; o WhatsApp exige entre 3 e 30 por pacote")
    tray = center_on_canvas(scale_to_fit(tray_source or first_sticker, TRAY), TRAY)
    tray_path = out / "tray.png"
    tray.save(tray_path, "PNG", optimize=True)
    size = tray_path.stat().st_size
    log(f"\ntray.png  {TRAY}x{TRAY}  {kb(size)}" + ("" if size <= TRAY_MAX else "  ACIMA DE 50 KB"))

    write_preview(pairs, out / "preview.png")
    log("preview.png  original | resultado, confira antes de subir")

    if problems:
        log(f"\nAVISOS ({len(problems)}):")
        for p in problems:
            log(f"  - {p}")
    else:
        log("\nsem avisos")

    icon = next((s["file"] for s in stickers if s["is_logo"]), None)
    report = {
        "pack": str(pack.resolve()),
        "site": site,
        "cover": str(logo.resolve()) if logo else None,   # capa da pagina: o logo como veio
        "icon": icon,                                     # icone do pacote: o logo ja recortado em 512
        "tray": str(tray_path.resolve()),
        "stickers": stickers,
        "warnings": problems,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 3 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--_people-worker":
        sys.exit(people_worker(sys.argv[2], sys.argv[3:]))
    sys.exit(main())
