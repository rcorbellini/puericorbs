"""Como o consultório aparece fora da página: o nome do app no celular (o manifesto e as metatags do iPhone) e a prévia
do link compartilhado (as metatags og: e a imagem do cartão).

Cada consultório aparece com o nome que a pediatra deu a ele em Consultório; só o endereço da plataforma se chama
Puericorbs. Tudo sai do servidor, porque quem lê o link (WhatsApp, iMessage, Telegram) não roda o JavaScript.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WEB = Path(__file__).parent / "web"
FONT = WEB / "fonts" / "figtree-latin.woff2"
PLATFORM = "Puericorbs"
PLATFORM_TEXT = "O consultório pediátrico pequeno inteiro num lugar: agenda, cuidado da criança, dinheiro e família."
ACCENTS = {"agua": "#08746b", "azul": "#1f5fbf", "coral": "#b8452a", "lavanda": "#5b47c4"}
BG, TEXT, MUTED = "#f5f7fb", "#1c2b3a", "#5a6b7d"
VEIL = ("#a9d8ff", "#aeeedb", "#ffd2bf", "#dccfff", "#ffeaa8")  # --veil-1 a --veil-5 do glass.css (tema claro)
SHORT = 12  # o que cabe embaixo do ícone, na tela do celular
CARD = (1200, 630)
CARD_LAYOUT = 1  # suba quando o desenho do cartão mudar: o endereço da imagem muda junto


def short_name(name: str) -> str:
    """O nome embaixo do ícone: o do consultório; se não couber, sem o "Dra."; depois, o primeiro e o último nome; por
    fim, "Dra. Primeiro" ou só o primeiro."""
    name = " ".join(name.split())
    if len(name) <= SHORT:
        return name
    prefix = re.match(r"^(dra?\.?)\s+", name, flags=re.I)
    plain = name[prefix.end():] if prefix else name
    if len(plain) <= SHORT:
        return plain
    words = plain.split()
    pair = f"{words[0]} {words[-1]}"
    if len(words) > 1 and len(pair) <= SHORT:
        return pair
    if prefix and len(f"{prefix.group(1)} {words[0]}") <= SHORT:
        return f"{prefix.group(1)} {words[0]}"
    return words[0] if len(words[0]) <= SHORT else words[0][:SHORT - 1] + "…"


def _clip(text: str, size: int) -> str:
    if len(text) <= size:
        return text
    return text[:size].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def identity(practice: dict | None) -> dict:
    """O nome, o nome curto, a linha de baixo (especialidade e registro), o texto da prévia e a cor de quem este endereço
    abre. Sem consultório, é a plataforma."""
    if not practice:
        return {"name": PLATFORM, "short": PLATFORM, "title": "", "line": "", "text": PLATFORM_TEXT,
                "accent": ACCENTS["agua"]}
    name = " ".join(practice["name"].split())
    title = practice.get("title") or "Pediatra"
    bio = " ".join((practice.get("bio") or "").split())
    text = _clip(bio, 200) if bio else \
        f"{title}. Agende a consulta e acompanhe a criança: vacinas, crescimento e o que vem pela frente."
    return {"name": name, "short": short_name(name), "title": title,
            "line": " · ".join(x for x in (title, practice.get("registry")) if x),
            "text": text, "accent": ACCENTS.get(practice.get("accent") or "", ACCENTS["agua"])}


def card_version(ident: dict, host: str) -> str:
    """Muda quando o cartão muda (o nome, a linha, a cor, o endereço): o WhatsApp guarda a imagem pelo endereço dela."""
    key = repr((ident["name"], ident["line"], ident["accent"], host, CARD_LAYOUT))
    return hashlib.sha256(key.encode()).hexdigest()[:10]


def head(ident: dict, origin: str, host: str) -> str:
    """O <title> e as metatags do nome e da prévia, que entram no lugar do <title> do index.html."""
    def e(value: str) -> str:
        return escape(value, quote=True)

    og_title = f"{ident['name']} · {ident['title']}" if ident["title"] else ident["name"]
    image = f"{origin}/og.png?v={card_version(ident, host)}"
    return "\n  ".join([
        f"<title>{e(ident['name'])}</title>",
        f'<meta name="description" content="{e(ident["text"])}">',
        f'<meta name="application-name" content="{e(ident["short"])}">',
        f'<meta name="apple-mobile-web-app-title" content="{e(ident["short"])}">',
        '<meta name="mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-capable" content="yes">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="pt_BR">',
        f'<meta property="og:site_name" content="{e(ident["name"])}">',
        f'<meta property="og:title" content="{e(og_title)}">',
        f'<meta property="og:description" content="{e(ident["text"])}">',
        f'<meta property="og:url" content="{e(origin)}/">',
        f'<meta property="og:image" content="{e(image)}">',
        '<meta property="og:image:type" content="image/png">',
        f'<meta property="og:image:width" content="{CARD[0]}">',
        f'<meta property="og:image:height" content="{CARD[1]}">',
        f'<meta property="og:image:alt" content="{e(og_title)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def manifest(ident: dict) -> dict:
    """O manifesto do PWA: o nome com que o app fica instalado no celular."""
    icons = "/static/icons/icon-192.png", "/static/icons/icon-512.png"
    return {
        "id": "/", "name": ident["name"], "short_name": ident["short"], "description": ident["text"],
        "start_url": "/", "scope": "/", "display": "standalone", "background_color": BG, "theme_color": BG,
        "lang": "pt-BR",
        "icons": [{"src": icons[0], "sizes": "192x192", "type": "image/png"},
                  {"src": icons[1], "sizes": "512x512", "type": "image/png"},
                  {"src": icons[1], "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }


# ---- o cartão (1200 × 630): o fundo da página, a bolha com a cor do consultório e o nome no meio ----------------------
# O WhatsApp, quando mostra pequeno, recorta o quadrado do meio: por isso tudo fica centralizado.

def _rgb(hexa: str) -> tuple[int, int, int]:
    return int(hexa[1:3], 16), int(hexa[3:5], 16), int(hexa[5:7], 16)


def _mix(a: tuple, b: tuple, t: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _veil(w: int, h: int) -> Image.Image:
    """O véu colorido do fundo (o .veil do glass.css): só degradê, então é calculado pequeno e ampliado."""
    sw, sh = 120, 63
    spots = [((0.04, 0.0), (0.62, 0.48), VEIL[0]), ((1.0, 0.04), (0.48, 0.40), VEIL[2]),
             ((0.98, 1.0), (0.62, 0.50), VEIL[1]), ((0.0, 0.98), (0.46, 0.44), VEIL[3])]
    bg = _rgb(BG)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    for y in range(sh):
        for x in range(sw):
            u, v = (x + .5) / sw, (y + .5) / sh
            color, alpha = (0.0, 0.0, 0.0), 0.0
            for (cx, cy), (rx, ry), hexa in reversed(spots):  # o primeiro do CSS fica por cima
                a = max(0.0, 1 - math.hypot((u - cx) / rx, (v - cy) / ry) / .72)
                color = tuple(c * a + k * (1 - a) for c, k in zip(_rgb(hexa), color))
                alpha = a + alpha * (1 - a)
            alpha *= .62
            px[x, y] = tuple(round(c * .62 + b * (1 - alpha)) for c, b in zip(color, bg))
    return img.resize((w, h), Image.BICUBIC)


def _bubble(size: int, accent: str | None) -> Image.Image:
    """A bolha do logo (o .logo do glass.css): o degradê girando, o brilho e, no logo, o ponto com a cor do consultório."""
    n = 128
    stops = [_rgb(VEIL[i]) for i in (0, 3, 2, 4, 1, 0)]
    base = Image.new("RGB", (n, n))
    px = base.load()
    for y in range(n):
        for x in range(n):
            u, v = (x + .5) / n, (y + .5) / n
            turn = ((math.degrees(math.atan2(u - .5, .5 - v)) - 210) % 360) / 360 * 5  # o CSS gira a partir do alto
            i = min(int(turn), 4)
            c = _mix(stops[i], stops[i + 1], turn - i)
            r = math.hypot(u - .5, v - .5)
            c = _mix(c, (255, 255, 255), .38 if r <= .275 else max(0.0, .38 * (1 - (r - .275) / .225)))
            r = math.hypot(u - .32, v - .26)
            c = _mix(c, (255, 255, 255), .98 if r <= .10 else max(0.0, .98 * (1 - (r - .10) / .20)))
            px[x, y] = c
    img = base.resize((size, size), Image.BICUBIC).convert("RGBA")
    big = size * 4  # as bordas desenhadas grandes e reduzidas saem lisas
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    img.putalpha(mask.resize((size, size), Image.LANCZOS))
    over = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    rim = max(4, big // 70)
    d.ellipse((0, 0, big - 1, big - 1), outline=(255, 255, 255, 200), width=rim)
    if accent:
        c, r, ring = .70 * big, .15 * big, .035 * big
        d.ellipse((c - r - ring, c - r - ring, c + r + ring, c + r + ring), fill=(255, 255, 255, 220))
        d.ellipse((c - r, c - r, c + r, c + r), fill=(*_rgb(accent), 255))
    img.alpha_composite(over.resize((size, size), Image.LANCZOS))
    return img


def _font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT), size)
    font.set_variation_by_axes([weight])
    return font


def _fit(text: str, weight: int, size: int, smallest: int, width: int) -> tuple[ImageFont.FreeTypeFont, str]:
    """A maior letra (até `size`) em que o texto cabe na largura; se nem na menor couber, corta com reticências."""
    while True:
        font = _font(size, weight)
        if font.getlength(text) <= width or size <= smallest:
            break
        size -= 2
    if font.getlength(text) > width:
        while text and font.getlength(text + "…") > width:
            text = text[:-1]
        text = text.rstrip() + "…"
    return font, text


def _name_lines(name: str, width: int = 1060) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """O nome grande numa linha; se não couber, em duas, quebrado onde as duas ficam mais parecidas; nem assim, cortado."""
    for size in range(78, 57, -2):
        font = _font(size, 800)
        if font.getlength(name) <= width:
            return [name], font
    words = name.split()
    for size in range(64, 45, -2):
        font = _font(size, 800)
        splits = [[" ".join(words[:i]), " ".join(words[i:])] for i in range(1, len(words))]
        fits = [pair for pair in splits if max(font.getlength(x) for x in pair) <= width]
        fits = [pair for pair in fits if not re.search(r"\bdra?\.$", pair[0], re.I)] or fits  # "Dra." fica com o nome
        if fits:
            return min(fits, key=lambda pair: max(font.getlength(x) for x in pair)), font
    font, text = _fit(name, 800, 46, 46, width)
    return [text], font


@lru_cache(maxsize=64)
def card_png(name: str, line: str, accent: str, host: str) -> bytes:
    w, h = CARD
    img = _veil(w, h).convert("RGBA")
    # duas bolhas soltas, como as que flutuam na página, fora do quadrado do meio
    for size, (x, y), alpha in ((300, (1000, -80), .5), (180, (30, 490), .45)):
        b = _bubble(size, None)
        b.putalpha(b.getchannel("A").point(lambda a: round(a * alpha)))
        img.alpha_composite(b, (x, y))
    lines, big = _name_lines(name)
    two = len(lines) > 1
    logo = 150 if two else 188
    lx, ly = (w - logo) // 2, 46 if two else 64
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((lx + 10, ly + 22, lx + logo - 10, ly + logo + 14), fill=(30, 60, 100, 60))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(_bubble(logo, accent), (lx, ly))
    d = ImageDraw.Draw(img)
    for i, text in enumerate(lines):
        d.text((w / 2, (284 if two else 338) + i * 68), text, font=big, fill=TEXT, anchor="mm")
    if line:
        font, text = _fit(line, 600, 34, 24, 1000)
        d.text((w / 2, 424 if two else 414), text, font=font, fill=MUTED, anchor="mm")
    if host:
        font, text = _fit(host, 700, 30, 22, 900)
        pw = font.getlength(text) + 64
        box = ((w - pw) / 2, 486, (w + pw) / 2, 546)
        pill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle(box, radius=30, fill=(255, 255, 255, 190), outline=(255, 255, 255, 240), width=2)
        img.alpha_composite(pill)
        ImageDraw.Draw(img).text((w / 2, 516), text, font=font, fill=accent, anchor="mm")
    out = BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
