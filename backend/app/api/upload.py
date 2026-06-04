import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.errors import is_safe_filename
from app.db.session import db
from app.ingest.pipeline import run_ingest

router = APIRouter(tags=["upload"])

ALLOWED_EXT = {"pdf", "docx", "doc", "md", "txt", "csv", "xlsx", "xls", "xlsm", "json"}
TYPE_MAP = {
    "pdf": "pdf",
    "docx": "docx",
    "doc": "docx",
    "md": "md",
    "txt": "txt",
    "csv": "csv",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "xlsm": "xlsx",
    "json": "txt",
}


@router.post("/folders/{fid}/upload")
async def upload_to_folder(
    fid: str, bg: BackgroundTasks, file: UploadFile = File(...)
):
    # 1. validate folder
    with db() as c:
        row = c.execute(
            "SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL", (fid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "folder not found")

    raw_name = file.filename or "unnamed"
    if not is_safe_filename(raw_name):
        raise HTTPException(422, "invalid filename")
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, f"unsupported file type: .{ext}")

    # 2. stream-read with size cap
    max_bytes = settings.max_upload_mb * 1024 * 1024
    parts: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                413, f"file exceeds {settings.max_upload_mb}MB limit"
            )
        parts.append(chunk)
    data = b"".join(parts)
    sha = hashlib.sha256(data).hexdigest()

    # 3. dedup by (folder, content hash)
    with db() as c:
        existing = c.execute(
            "SELECT id, name FROM docs WHERE folder_id = ? AND sha256 = ? AND deleted_at IS NULL",
            (fid, sha),
        ).fetchone()
        if existing:
            return {
                "id": existing["id"],
                "duplicated": True,
                "name": existing["name"],
            }

    # 4. write to disk under data/uploads/{folder}/
    folder_dir = settings.uploads_dir / fid
    folder_dir.mkdir(parents=True, exist_ok=True)
    storage_path = folder_dir / f"{sha[:16]}_{raw_name}"
    storage_path.write_bytes(data)

    # 5. insert metadata row
    did = "d_" + uuid.uuid4().hex[:12]
    typ = TYPE_MAP.get(ext, "txt")
    with db() as c:
        c.execute(
            """INSERT INTO docs(id, folder_id, name, type, size_bytes, sha256, storage_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (did, fid, raw_name, typ, total, sha, str(storage_path)),
        )

    # 6. fire-and-forget ingest
    bg.add_task(run_ingest, did)

    return {
        "id": did,
        "duplicated": False,
        "name": raw_name,
        "type": typ,
        "size_bytes": total,
        "status": "pending",
    }
