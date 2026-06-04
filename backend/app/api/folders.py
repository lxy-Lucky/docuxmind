import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.session import db

router = APIRouter(tags=["folders"])

ALLOWED_COLORS = {"amber", "green", "blue", "purple", "red"}


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str = "amber"


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = None


def _new_id() -> str:
    return "f_" + uuid.uuid4().hex[:10]


@router.get("/folders")
def list_folders():
    with db() as c:
        rows = c.execute(
            """
            SELECT f.id, f.name, f.color, f.position, f.created_at,
                   (SELECT COUNT(*) FROM docs d
                      WHERE d.folder_id = f.id AND d.deleted_at IS NULL) AS doc_count,
                   (SELECT COALESCE(SUM(segment_count), 0) FROM docs d
                      WHERE d.folder_id = f.id AND d.deleted_at IS NULL) AS segment_count
              FROM folders f
             WHERE f.deleted_at IS NULL
             ORDER BY f.position ASC, f.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/folders")
def create_folder(payload: FolderCreate):
    if payload.color not in ALLOWED_COLORS:
        raise HTTPException(422, "invalid color")
    fid = _new_id()
    name = payload.name.strip()
    with db() as c:
        c.execute(
            """INSERT INTO folders(id, name, color, position)
               VALUES (?, ?, ?, (SELECT COALESCE(MIN(position), 0) - 1 FROM folders))""",
            (fid, name, payload.color),
        )
    return {
        "id": fid,
        "name": name,
        "color": payload.color,
        "doc_count": 0,
        "segment_count": 0,
    }


@router.patch("/folders/{fid}")
def update_folder(fid: str, payload: FolderUpdate):
    sets: list[str] = []
    args: list[str] = []
    if payload.name is not None:
        sets.append("name = ?")
        args.append(payload.name.strip())
    if payload.color is not None:
        if payload.color not in ALLOWED_COLORS:
            raise HTTPException(422, "invalid color")
        sets.append("color = ?")
        args.append(payload.color)
    if not sets:
        return {"ok": True}
    args.append(fid)
    with db() as c:
        cur = c.execute(
            f"UPDATE folders SET {', '.join(sets)} WHERE id = ? AND deleted_at IS NULL",
            args,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "folder not found")
    return {"ok": True}


@router.delete("/folders/{fid}")
def delete_folder(fid: str):
    """Soft-delete; cascades to docs via 24h retention rule (handled out-of-band)."""
    with db() as c:
        cur = c.execute(
            "UPDATE folders SET deleted_at = datetime('now') WHERE id = ? AND deleted_at IS NULL",
            (fid,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "folder not found")
        # cascade soft-delete on docs so UI counts stay correct
        c.execute(
            "UPDATE docs SET deleted_at = datetime('now') WHERE folder_id = ? AND deleted_at IS NULL",
            (fid,),
        )
    return {"ok": True}
