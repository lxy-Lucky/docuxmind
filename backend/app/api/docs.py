from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.db.session import db

router = APIRouter(tags=["docs"])


@router.get("/folders/{fid}/docs")
def list_docs(fid: str):
    with db() as c:
        rows = c.execute(
            """SELECT id, folder_id, name, type, size_bytes, status, error_reason,
                      segment_count, language, created_at
                 FROM docs
                WHERE folder_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC""",
            (fid,),
        ).fetchall()
        return [dict(r) for r in rows]


@router.delete("/docs/{did}")
def delete_doc(did: str):
    with db() as c:
        cur = c.execute(
            "UPDATE docs SET deleted_at = datetime('now') WHERE id = ? AND deleted_at IS NULL",
            (did,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "doc not found")
        # FTS rows can be removed eagerly: they're cheap to rebuild and useless for a deleted doc
        c.execute("DELETE FROM fts_segments WHERE doc_id = ?", (did,))
    return {"ok": True}


@router.post("/docs/{did}/reindex")
def reindex_doc(did: str, bg: BackgroundTasks):
    from app.ingest.pipeline import run_ingest

    with db() as c:
        row = c.execute(
            "SELECT id FROM docs WHERE id = ? AND deleted_at IS NULL", (did,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "doc not found")
        c.execute(
            "UPDATE docs SET status = 'pending', error_reason = NULL WHERE id = ?",
            (did,),
        )
    bg.add_task(run_ingest, did)
    return {"ok": True}
