import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from backend.routers.upload import (
    create_extraction_draft,
    get_training_gateway_role,
    not_trained,
    train_km,
    upload_km,
)
from backend.services.engineering_extraction_service import EngineeringExtractionService
from backend.services.training_service import TrainingService
from tests.test_engineering_extraction import FakeOpcClient, FakeProvider, quotation_payload


class FakeVisionClient:
    def analyze_slide(self, image_path: Path) -> str:
        return f"analysis {image_path.name}"

    def summarize(self, analysis: str) -> str:
        return "summary"


def converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
    (assets / "Slide001.png").write_bytes(b"png")
    return {"success": True, "slideCount": 1, "pngCount": 1}


def zero_converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
    return {"success": True, "slideCount": 0}


def slow_converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
    time.sleep(0.25)
    (assets / "Slide001.png").write_bytes(b"png")
    return {"success": True, "slideCount": 1, "pngCount": 1}


class FakeRequest:
    def __init__(
        self, service: TrainingService, *, body: bytes = b"", content_type: str = "",
        payload=None, client_host: str = "127.0.0.1", gateway_role: str = "factory", extraction_service=None,
    ):
        self.app = SimpleNamespace(state=SimpleNamespace(training_service=service, engineering_extraction_service=extraction_service))
        self.client = SimpleNamespace(host=client_host)
        self.headers = {
            "content-type": content_type,
            "x-factory-km-gateway": "node",
            "x-factory-km-role": gateway_role,
        }
        self._body = body
        self._payload = payload

    async def body(self) -> bytes:
        return self._body

    async def json(self):
        return self._payload


async def response_records(response) -> list[dict[str, object]]:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return [json.loads(line) for line in "".join(chunks).splitlines()]


def multipart(filename: str) -> tuple[str, bytes]:
    boundary = "FactoryKmBoundary"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"targetPath\"\r\n\r\n"
        f"Packing/Packer\r\n--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"data\"; filename=\"{filename}\"\r\n"
        "Content-Type: application/octet-stream\r\n\r\noffice\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return f"multipart/form-data; boundary={boundary}", body


class TrainingEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = TrainingService(
            vault_root=Path(self.temporary.name),
            converter_runner=converter,
            vision_client=FakeVisionClient(),  # type: ignore[arg-type]
        )
        self.role = "factory"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def upload(self, filename: str = "manual.pptx") -> dict[str, object]:
        content_type, body = multipart(filename)
        response = asyncio.run(upload_km(
            FakeRequest(self.service, body=body, content_type=content_type),  # type: ignore[arg-type]
            self.role,
        ))
        records = asyncio.run(response_records(response))
        self.assertTrue(records[-1]["success"])
        self.assertEqual((records[-2]["done"], records[-2]["total"]), (1, 1))
        return records[-1]

    def test_upload_and_not_trained_contract(self) -> None:
        final = self.upload("book.xlsx")
        response = not_trained(FakeRequest(self.service))  # type: ignore[arg-type]
        pending = json.loads(response.body)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kmId"], final["kms"][0]["kmId"])
        self.assertEqual(pending[0]["slideCount"], 1)

    def test_post_training_extraction_endpoint_returns_draft_only(self) -> None:
        final = self.upload("quotation.pdf"); km_id = final["kms"][0]["kmId"]
        train = asyncio.run(train_km(FakeRequest(self.service, payload={"kmIds": [km_id]}), self.role))  # type: ignore[arg-type]
        self.assertTrue(asyncio.run(response_records(train))[-1]["success"])
        extraction = EngineeringExtractionService(FakeProvider(quotation_payload()), FakeOpcClient())
        response = asyncio.run(create_extraction_draft(FakeRequest(self.service, payload={"kmId": km_id}, extraction_service=extraction), self.role))  # type: ignore[arg-type]
        body = json.loads(response.body)
        self.assertTrue(body["success"]); self.assertEqual(body["draft"]["state"], "extracted")
        self.assertIsNone(body["draft"]["quotation"]["issuer_supplier"]["provisional_candidate_id"])

    def test_train_reports_one_of_one_only_on_success(self) -> None:
        uploaded = self.upload()
        km_id = uploaded["kms"][0]["kmId"]
        response = asyncio.run(train_km(
            FakeRequest(self.service, payload={"kmIds": [km_id]}),  # type: ignore[arg-type]
            self.role,
        ))
        records = asyncio.run(response_records(response))
        self.assertEqual((records[-2]["done"], records[-2]["total"]), (1, 1))
        self.assertEqual(records[-1]["updated"], 1)
        self.assertTrue(records[-1]["success"])

    def test_train_zero_of_one_is_failure(self) -> None:
        uploaded = self.upload()
        km_id = uploaded["kms"][0]["kmId"]
        for slide in Path(self.temporary.name).rglob("Slide*.png"):
            slide.unlink()
        response = asyncio.run(train_km(
            FakeRequest(self.service, payload={"kmIds": [km_id]}),  # type: ignore[arg-type]
            self.role,
        ))
        final = asyncio.run(response_records(response))[-1]
        self.assertFalse(final["success"])
        self.assertEqual(final["updated"], 0)
        self.assertIn("No Slide PNG", final["error"])

    def test_upload_zero_of_one_is_failure_with_reason(self) -> None:
        self.service.converter_runner = zero_converter
        content_type, body = multipart("empty.pptx")
        response = asyncio.run(upload_km(
            FakeRequest(self.service, body=body, content_type=content_type),  # type: ignore[arg-type]
            self.role,
        ))
        final = asyncio.run(response_records(response))[-1]
        self.assertFalse(final["success"])
        self.assertEqual(final["count"], 0)
        self.assertIn("zero or mismatched pages", final["error"])

    def test_upload_stream_starts_before_conversion_finishes(self) -> None:
        self.service.converter_runner = slow_converter
        content_type, body = multipart("slow.pptx")

        async def scenario():
            response = await upload_km(
                FakeRequest(self.service, body=body, content_type=content_type),  # type: ignore[arg-type]
                self.role,
            )
            iterator = response.body_iterator
            started = time.monotonic()
            first = await anext(iterator)
            first_elapsed = time.monotonic() - started
            remaining = []
            async for chunk in iterator:
                remaining.append(chunk)
            return first, first_elapsed, remaining

        first, elapsed, remaining = asyncio.run(scenario())
        self.assertLess(elapsed, 0.1)
        self.assertEqual(json.loads(first)["done"], 0)
        self.assertTrue(json.loads(remaining[-1])["success"])

    def test_viewer_cannot_upload_or_train(self) -> None:
        viewer = "viewer"
        content_type, body = multipart("manual.pptx")
        upload = asyncio.run(upload_km(
            FakeRequest(self.service, body=body, content_type=content_type), viewer  # type: ignore[arg-type]
        ))
        train = asyncio.run(train_km(
            FakeRequest(self.service, payload={"kmIds": ["KM_20260101_000000"]}), viewer  # type: ignore[arg-type]
        ))
        self.assertEqual(upload.status_code, 403)
        self.assertEqual(train.status_code, 403)

    def test_training_gateway_accepts_only_loopback_node_identity(self) -> None:
        accepted = asyncio.run(get_training_gateway_role(FakeRequest(self.service)))  # type: ignore[arg-type]
        self.assertEqual(accepted, "factory")

        for request in (
            FakeRequest(self.service, client_host="10.0.0.8"),
            FakeRequest(self.service, gateway_role=""),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(get_training_gateway_role(request))  # type: ignore[arg-type]
            self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
