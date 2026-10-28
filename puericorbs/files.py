"""Os arquivos que pediatra, recepção e família trocam: guardar, decidir quem vê e servir.

O arquivo fica em `data/practices/p<id>/files/`, com um nome aleatório (o nome original só vai para o banco). O tipo
é decidido pelos primeiros bytes, não pelo que o navegador declara. Foto do celular perde o EXIF (com a localização) e
a HEIC do iPhone vira JPEG.
"""

from __future__ import annotations

import io
import re
import secrets
from pathlib import Path

from fastapi import HTTPException

from .db import practice_dir

KINDS = {
    "exame": "Exame", "foto": "Foto", "video": "Vídeo", "receita": "Receita", "atestado": "Atestado",
    "pedido": "Pedido de exame", "resumo": "Resumo da consulta", "nota": "Nota fiscal", "recibo": "Recibo",
    "comprovante": "Comprovante", "caderneta": "Caderneta de vacinação", "documento": "Documento",
}
# o que a família manda e o pediatra precisa ver
REVIEW = {"exame", "foto", "video", "caderneta"}
# o que a recepção também vê (dinheiro e papelada)
ADMIN = {"nota", "recibo", "comprovante", "documento"}
FILTERS = {
    "exames": {"exame", "pedido"},
    "receitas": {"receita", "atestado"},
    "notas": {"nota", "recibo", "comprovante"},
    "fotos": {"foto", "video", "caderneta"},
}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf",
       "video/mp4": ".mp4", "video/quicktime": ".mov"}
NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|pdf|mp4|mov)$")


def sniff(head: bytes) -> str | None:
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"%PDF":
        return "application/pdf"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"):
            return "image/heic"
        if brand == b"qt  ":
            return "video/quicktime"
        return "video/mp4"
    return None


def _clean_image(content: bytes, mime: str) -> tuple[bytes, str]:
    from PIL import Image, ImageOps
    if mime == "image/heic":
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError as exc:  # pragma: no cover - a dependência está no pyproject
            raise HTTPException(415, "Não deu para ler a foto HEIC. Mande em JPEG.") from exc
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        raise HTTPException(415, "Não deu para abrir a imagem. Tente outra foto.") from exc
    out = io.BytesIO()
    if mime in ("image/heic", "image/jpeg"):
        img.convert("RGB").save(out, "JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    fmt = "PNG" if mime == "image/png" else "WEBP"
    img.save(out, fmt)
    return out.getvalue(), mime


def store(data_dir: Path, practice_id: int, content: bytes, max_mb: int) -> dict:
    if not content:
        raise HTTPException(400, "O arquivo veio vazio.")
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"O arquivo passa de {max_mb} MB. Mande um menor (no vídeo, só o trecho que importa).")
    mime = sniff(content[:16])
    if not mime:
        raise HTTPException(415, "Esse tipo de arquivo não é aceito. Mande foto, PDF ou vídeo.")
    if mime.startswith("image/"):
        content, mime = _clean_image(content, mime)
    name = secrets.token_hex(16) + EXT[mime]
    folder = practice_dir(data_dir, practice_id) / "files"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(content)
    return {"stored_name": name, "mime": mime, "size": len(content)}


def path_of(data_dir: Path, practice_id: int, stored_name: str) -> Path:
    if not NAME.match(stored_name):
        raise HTTPException(404, "Arquivo não encontrado.")
    return practice_dir(data_dir, practice_id) / "files" / stored_name


def visibility_for(kind: str, uploader_role: str) -> str:
    if kind in ADMIN:
        return "admin"
    return "family"


def can_see(row: dict, role: str, family_ids: set[int]) -> bool:
    if role == "clinician":
        return True
    if role == "receptionist":
        return row["visibility"] == "admin"
    if role == "guardian":
        return row["family_id"] in family_ids and row["visibility"] in ("family", "admin")
    return False
