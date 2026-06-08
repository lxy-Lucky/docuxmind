"""Ingest pipeline: parse → outline → FTS5 index. Synchronous; runs in BackgroundTasks."""
import json
import traceback

from app.core.logging import get_logger
from app.db.session import db
from app.ingest.parsers import code as code_parser
from app.ingest.parsers import md as md_parser
from app.ingest.parsers import txt as txt_parser
from app.ingest.parsers import xlsx as xlsx_parser

log = get_logger("ingest")

PARSERS = {
    "txt": txt_parser.parse,
    "md": md_parser.parse,
    "xlsx": xlsx_parser.parse,
    "code": code_parser.parse,
    # pdf/docx/csv come in Sprint 3
}


def run_ingest(doc_id: str) -> None:
    with db() as c:
        row = c.execute(
            "SELECT id, folder_id, type, storage_path, name FROM docs WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if not row:
            log.warning("ingest.missing_doc", doc_id=doc_id)
            return
        c.execute(
            "UPDATE docs SET status = 'indexing', error_reason = NULL WHERE id = ?",
            (doc_id,),
        )

    folder_id = row["folder_id"]
    typ = row["type"]
    path = row["storage_path"]

    try:
        parser = PARSERS.get(typ)
        if not parser:
            raise ValueError(f"no parser for type: {typ}")

        outline, segments = parser(path)

        with db() as c:
            c.execute("DELETE FROM fts_segments WHERE doc_id = ?", (doc_id,))
            for seg in segments:
                c.execute(
                    "INSERT INTO fts_segments(doc_id, folder_id, locator, content) VALUES (?, ?, ?, ?)",
                    (doc_id, folder_id, seg["locator"], seg["content"]),
                )
            c.execute(
                "UPDATE docs SET status = 'ok', outline_json = ?, segment_count = ? WHERE id = ?",
                (
                    json.dumps(outline, ensure_ascii=False),
                    len(segments),
                    doc_id,
                ),
            )
        log.info("ingest.ok", doc_id=doc_id, segments=len(segments))
    except Exception as e:
        log.error(
            "ingest.error",
            doc_id=doc_id,
            error=str(e),
            tb=traceback.format_exc(),
        )
        with db() as c:
            c.execute(
                "UPDATE docs SET status = 'error', error_reason = ? WHERE id = ?",
                (str(e)[:500], doc_id),
            )
