"""A API do recibo e da nota (`fiscal.py`): como a pediatra recebe (só ela muda), o documento de cada pagamento
(a pediatra e a recepção) e os CPFs que ele pede.

O documento de uma cobrança paga é o recibo do Receita Saúde (pessoa física) ou a nota fiscal (empresa). A recepção vê
os dados prontos para copiar, emite onde se emite e anexa o PDF aqui: ele vai para os arquivos da família, que vê no
app, e a cobrança sai da fila "a emitir".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import files, fiscal
from .api_staff import _get, _practice
from .context import Ctx, clinician, dep
from .db import insert, now_iso, one, transaction, update

router = APIRouter(prefix="/api/staff")


@router.get("/fiscal")
def fiscal_profile(ctx: Ctx = Depends(dep)):
    clinician(ctx)
    p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (ctx.practice_id,))
    return {"profile": fiscal.profile(p), "modes": fiscal.MODES, "regimes": fiscal.REGIMES, "city": fiscal.CITY,
            "portals": {k: fiscal.portal(k) for k in fiscal.PORTALS}}


class FiscalBody(BaseModel):
    mode: str | None = None
    tax_id: str | None = None
    legal_name: str | None = None
    municipal_registration: str | None = None
    regime: str | None = None
    iss_rate: float | None = None


@router.put("/fiscal")
def save_fiscal(body: FiscalBody, ctx: Ctx = Depends(dep)):
    """Só a pediatra diz como recebe. Ainda sem decidir, tudo fica em branco e a fila mostra o que falta."""
    clinician(ctx)
    values: dict = {"billing_mode": None, "tax_id": None, "legal_name": None, "municipal_registration": None,
                    "tax_regime": None, "iss_rate": None}
    if body.mode == "pf":
        values.update(billing_mode="pf", tax_id=fiscal.clean_cpf(body.tax_id, "da pediatra"),
                      legal_name=(body.legal_name or "").strip()[:120] or None)
    elif body.mode == "pj":
        if not fiscal.cnpj_ok(body.tax_id):
            raise HTTPException(400, "Confira o CNPJ da empresa: os números não fecham.")
        if not (body.legal_name or "").strip():
            raise HTTPException(400, "Escreva a razão social, como está no CNPJ.")
        if body.regime not in fiscal.REGIMES:
            raise HTTPException(400, "Escolha o regime da empresa: Simples Nacional ou Lucro Presumido.")
        if body.iss_rate is not None and not 0 <= body.iss_rate <= 5:
            raise HTTPException(400, "A alíquota do ISS vai de 0% a 5%.")
        values.update(billing_mode="pj", tax_id=fiscal.digits(body.tax_id), legal_name=body.legal_name.strip()[:120],
                      municipal_registration=fiscal.digits(body.municipal_registration) or None,
                      tax_regime=body.regime, iss_rate=body.iss_rate)
    elif body.mode:
        raise HTTPException(400, "Escolha pessoa física ou empresa.")
    update(ctx.pconn, "practices", ctx.practice_id, values)
    ctx.audit("fiscal_alterado", "practice", ctx.practice_id, detail=body.mode or "sem definir")
    return fiscal_profile(ctx)


def _paid_charge(conn, charge_id: int) -> dict:
    ch = _get(conn, "charges", charge_id, "Cobrança")
    if ch["status"] != "paga":
        raise HTTPException(409, "Esta cobrança ainda não foi paga: o recibo (ou a nota) vem depois do pagamento.")
    return ch


@router.get("/charges/{charge_id}/document")
def charge_document(charge_id: int, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    ch = _paid_charge(conn, charge_id)
    ctx.audit("ver_documento_fiscal", "charge", charge_id, conn=conn)
    return fiscal.document(conn, practice, ch)


@router.post("/charges/{charge_id}/document")
async def attach_document(charge_id: int, practice_id: int | None = None, upload: UploadFile = File(...),
                          ctx: Ctx = Depends(dep)):
    """O PDF do recibo (ou da nota) emitido lá fora: vai para os arquivos da família, e a cobrança sai da fila."""
    practice, conn = _practice(ctx, practice_id)
    ch = _paid_charge(conn, charge_id)
    content = await upload.read()
    stored = files.store(ctx.settings.data_dir, practice["id"], content, ctx.settings.max_upload_mb)
    kind = "recibo" if practice.get("billing_mode") == "pf" else "nota"
    title = f"{files.KINDS[kind]} · {ch['description']}"
    with transaction(conn):
        fid = insert(conn, "files", {
            "family_id": ch["family_id"], "patient_id": ch["patient_id"], "kind": kind, "title": title[:120],
            "original_name": upload.filename, **stored, "visibility": "admin", "uploaded_by": ctx.user["id"],
            "uploader_role": "pediatra" if practice["role"] == "clinician" else "atendente",
            "uploader_name": ctx.user["name"], "needs_review": 0, "created_at": now_iso()})
        update(conn, "charges", charge_id, {"invoice": "emitida", "document_file_id": fid})
    ctx.audit("documento_fiscal_anexado", "charge", charge_id, conn=conn)
    return {"file_id": fid, "kind": kind}


class CpfBody(BaseModel):
    cpf: str | None = None


@router.put("/guardians/{guardian_id}/cpf")
def guardian_cpf(guardian_id: int, body: CpfBody, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    """O CPF de quem paga: o recibo e a nota saem no nome dele."""
    practice, conn = _practice(ctx, practice_id)
    _get(conn, "guardians", guardian_id, "Responsável")
    update(conn, "guardians", guardian_id, {"cpf": fiscal.clean_cpf(body.cpf, "do responsável")})
    ctx.audit("cpf_responsavel", "guardian", guardian_id, conn=conn)
    return {"ok": True}


@router.put("/patients/{patient_id}/cpf")
def patient_cpf(patient_id: int, body: CpfBody, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    """O CPF da criança: o recibo do Receita Saúde pede o de quem foi atendido."""
    practice, conn = _practice(ctx, practice_id)
    _get(conn, "patients", patient_id, "Paciente")
    update(conn, "patients", patient_id, {"cpf": fiscal.clean_cpf(body.cpf, "da criança")})
    ctx.audit("cpf_crianca", "patient", patient_id, conn=conn)
    return {"ok": True}
