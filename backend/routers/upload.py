from __future__ import annotations

import asyncio
from collections.abc import Iterator
from email.parser import BytesParser
from email.policy import default
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.services.training_service import TrainingError, TrainingService, UploadedFile


router = APIRouter()


def get_training_service(request: Request) -> TrainingService:
    """Return an app-injected service in tests or the production service."""
    configured = getattr(request.app.state, "training_service", None)
    return configured if isinstance(configured, TrainingService) else TrainingService()


async def get_training_gateway_role(request: Request) -> str:
    """Accept identity only from the loopback Node frontend/auth gateway."""
    client_host = request.client.host if request.client else ""
    gateway = request.headers.get("x-factory-km-gateway", "")
    role = request.headers.get("x-factory-km-role", "")
    if client_host not in {"127.0.0.1", "::1"} or gateway != "node" or not role:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Training API requires the Node gateway.")
    return role


def _write_allowed(role: str) -> JSONResponse | None:
    if role == "viewer":
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Viewer mode cannot modify Factory-KM."},
        )
    return None


def _parse_multipart(content_type: str, body: bytes) -> tuple[str, list[UploadedFile]]:
    """Parse the browser FormData payload without adding python-multipart."""
    if "multipart/form-data" not in content_type.lower() or "boundary=" not in content_type:
        raise TrainingError("Missing boundary in content-type")
    envelope = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    message = BytesParser(policy=default).parsebytes(envelope)
    target_path = ""
    files: list[UploadedFile] = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if name == "targetPath" and filename is None:
            target_path = payload.decode(part.get_content_charset() or "utf-8").strip()
        elif filename:
            files.append(UploadedFile(filename=filename, content=payload))
    return target_path, files


def _ndjson(records: list[dict[str, object]]) -> Iterator[bytes]:
    for record in records:
        yield (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


def _ndjson_record(record: dict[str, object]) -> bytes:
    return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


@router.post("/km/upload", response_model=None)
async def upload_km(
    request: Request,
    gateway_role: str = Depends(get_training_gateway_role),
) -> JSONResponse | StreamingResponse:
    """Upload each source as one KM package and convert its pages sequentially."""
    denied = _write_allowed(gateway_role)
    if denied:
        return denied
    try:
        target_path, files = _parse_multipart(
            request.headers.get("content-type", ""), await request.body()
        )
        service = get_training_service(request)
    except TrainingError as error:
        return StreamingResponse(
            _ndjson([{"type": "done", "success": False, "count": 0, "error": str(error)}]),
            media_type="application/x-ndjson",
        )
    except OSError:
        return StreamingResponse(
            _ndjson([{
                "type": "done", "success": False, "count": 0,
                "error": "Unable to write the Factory-KM package.",
            }]),
            media_type="application/x-ndjson",
        )

    async def stream_upload():
        total = len(files)
        yield _ndjson_record({"type": "progress", "done": 0, "total": total})
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress(done: int, progress_total: int, source_file: str) -> None:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("progress", {
                    "type": "progress", "done": done, "total": progress_total,
                    "current": source_file,
                }),
            )

        def run_upload() -> None:
            try:
                created = service.upload(files, target_path, progress)
                loop.call_soon_threadsafe(queue.put_nowait, ("result", created))
            except Exception as error:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", error))

        worker = asyncio.create_task(asyncio.to_thread(run_upload))
        while True:
            kind, value = await queue.get()
            if kind == "progress":
                yield _ndjson_record(value)  # type: ignore[arg-type]
                continue
            if kind == "result":
                created = value
                yield _ndjson_record({
                    "type": "done", "success": len(created) > 0,
                    "targetPath": target_path.replace("\\", "/").strip("/"),
                    "count": len(created),
                    "kms": [
                        {"kmId": item.km_id, "sourceFile": item.source_file}
                        for item in created
                    ],
                })
            else:
                safe_error = value if isinstance(value, TrainingError) else TrainingError(type(value).__name__)
                yield _ndjson_record({
                    "type": "done", "success": False, "count": 0,
                    "error": str(safe_error),
                })
            await worker
            break

    return StreamingResponse(stream_upload(), media_type="application/x-ndjson")


@router.get("/km/not-trained")
def not_trained(request: Request) -> JSONResponse:
    """List detail Markdown packages awaiting successful vision training."""
    try:
        return JSONResponse(content=get_training_service(request).list_not_trained())
    except TrainingError as error:
        return JSONResponse(status_code=503, content={"success": False, "error": str(error)})


@router.post("/km/train", response_model=None)
async def train_km(
    request: Request,
    gateway_role: str = Depends(get_training_gateway_role),
) -> JSONResponse | StreamingResponse:
    """Analyze SlideNNN.png assets and write detail and summary Markdown."""
    denied = _write_allowed(gateway_role)
    if denied:
        return denied
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid JSON body"})
    km_ids = payload.get("kmIds") if isinstance(payload, dict) else None
    km_ids = [item for item in km_ids if isinstance(item, str) and item] if isinstance(km_ids, list) else []
    if not km_ids:
        return JSONResponse(status_code=400, content={"success": False, "error": "Missing kmIds"})
    service = get_training_service(request)
    total_slides = 0
    for km_id in km_ids:
        try:
            total_slides += service.slide_count(km_id)
        except (TrainingError, OSError):
            pass

    async def stream_training():
        yield _ndjson_record({"type": "progress", "done": 0, "total": total_slides})
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        done = 0

        def progress(source_file: str) -> None:
            nonlocal done
            done += 1
            loop.call_soon_threadsafe(queue.put_nowait, ("progress", {
                "type": "progress", "done": done, "total": total_slides,
                "current": source_file,
            }))

        def run_training() -> None:
            try:
                results: list[dict[str, object]] = []
                errors: list[str] = []
                for km_id in km_ids:
                    try:
                        results.append(service.train_one(km_id, progress))
                    except TrainingError as error:
                        errors.append(str(error))
                        results.append({
                            "kmId": km_id, "updated": False, "success": False,
                            "error": str(error),
                        })
                loop.call_soon_threadsafe(queue.put_nowait, ("result", (results, errors)))
            except Exception as error:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", error))

        worker = asyncio.create_task(asyncio.to_thread(run_training))
        while True:
            kind, value = await queue.get()
            if kind == "progress":
                yield _ndjson_record(value)  # type: ignore[arg-type]
                continue
            if kind == "error":
                safe_error = value if isinstance(value, TrainingError) else TrainingError(type(value).__name__)
                yield _ndjson_record({
                    "type": "done", "success": False, "updated": 0,
                    "results": [], "error": str(safe_error),
                })
                await worker
                break
            results, errors = value  # type: ignore[misc]
            updated = sum(1 for result in results if result.get("success") is True)
            success = updated == len(km_ids) and updated > 0 and total_slides > 0
            yield _ndjson_record({
                "type": "done", "success": success, "updated": updated,
                "results": results,
                **({"error": "; ".join(errors)} if errors else {}),
            })
            await worker
            break

    return StreamingResponse(stream_training(), media_type="application/x-ndjson")
