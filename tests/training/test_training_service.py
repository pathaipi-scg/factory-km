import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.training_service import (
    CONVERTERS,
    TrainingError,
    TrainingService,
    UploadedFile,
)


FORMAT_MATRIX = {
    ".ppt": "ppt_to_png.py",
    ".pptx": "ppt_to_png.py",
    ".xls": "excel_to_png.py",
    ".xlsx": "excel_to_png.py",
    ".doc": "docx_to_png.py",
    ".docx": "docx_to_png.py",
    ".pdf": "pdf_to_png.py",
}


class FakeVisionClient:
    def analyze_slide(self, image_path: Path) -> str:
        return f"analysis for {image_path.name}"

    def summarize(self, analysis: str) -> str:
        return "# Summary\nEngineering summary"


class FailingSummaryClient(FakeVisionClient):
    def summarize(self, analysis: str) -> str:
        raise TrainingError("summary failed")


class ConcurrentVisionClient(FakeVisionClient):
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.lock = threading.Lock()

    def analyze_slide(self, image_path: Path) -> str:
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            time.sleep(0.05)
            return f"analysis for {image_path.name}"
        finally:
            with self.lock:
                self.active -= 1


class TrainingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def successful_converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
        count = 2 if source.suffix.lower() == ".pptx" else 3
        for index in range(1, count + 1):
            (assets / f"Slide{index:03d}.png").write_bytes(b"png")
        return {"success": True, "slideCount": count, "pngCount": count}

    def service(self) -> TrainingService:
        return TrainingService(
            vault_root=self.root,
            converter_runner=self.successful_converter,
            vision_client=FakeVisionClient(),  # type: ignore[arg-type]
        )

    def test_pptx_upload_generates_assets_and_nonzero_metadata(self) -> None:
        created = self.service().upload(
            [UploadedFile("manual.pptx", b"pptx")], "Packing/Packer"
        )

        self.assertEqual(len(created), 1)
        markdown = created[0].markdown_path.read_text(encoding="utf-8")
        self.assertIn("Processing_Status : Converted", markdown)
        self.assertIn("Slide_Count : 2", markdown)
        self.assertIn("PNG_Count : 2", markdown)
        self.assertEqual(len(list(created[0].asset_path.glob("Slide*.png"))), 2)

    def test_xlsx_upload_preserves_rendered_page_count(self) -> None:
        created = self.service().upload(
            [UploadedFile("troubleshooting.xlsx", b"xlsx")], "Packing/Packer"
        )

        markdown = created[0].markdown_path.read_text(encoding="utf-8")
        self.assertIn("Slide_Count : 3", markdown)
        self.assertIn("![[%s/Slide003.png]]" % created[0].km_id, markdown)
        self.assertEqual(len(list(created[0].asset_path.glob("Slide*.png"))), 3)

    def test_all_supported_formats_dispatch_and_complete_shared_pipeline(self) -> None:
        self.assertEqual(CONVERTERS, FORMAT_MATRIX)
        for extension, expected_script in FORMAT_MATRIX.items():
            with self.subTest(extension=extension):
                calls: list[str] = []

                def converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
                    calls.append(script.name)
                    for index in range(1, 3):
                        (assets / f"Slide{index:03d}.png").write_bytes(b"png")
                    return {"success": True, "slideCount": 2, "pngCount": 2}

                with tempfile.TemporaryDirectory() as directory:
                    service = TrainingService(
                        vault_root=Path(directory),
                        converter_runner=converter,
                        vision_client=FakeVisionClient(),  # type: ignore[arg-type]
                    )
                    record = service.upload(
                        [UploadedFile(f"source{extension}", b"source")],
                        "Packing/Packer",
                    )[0]
                    upload_markdown = record.markdown_path.read_text(encoding="utf-8")
                    assets = sorted(path.name for path in record.asset_path.iterdir())

                    result = service.train_one(record.km_id)
                    detail = record.markdown_path.read_text(encoding="utf-8")
                    summary = record.markdown_path.with_name(
                        f"{record.km_id}_summary.md"
                    )

                    self.assertEqual(calls, [expected_script])
                    self.assertIn("Slide_Count : 2", upload_markdown)
                    self.assertEqual(assets, ["Slide001.png", "Slide002.png"])
                    self.assertGreater(result["slideCount"], 0)
                    self.assertTrue(result["success"])
                    self.assertIn("Training_Status : Trained", detail)
                    self.assertIn("Training_Slides : 2", detail)
                    self.assertTrue(summary.exists())
                    self.assertIn(
                        "Engineering summary", summary.read_text(encoding="utf-8")
                    )

    def test_zero_page_conversion_is_failure(self) -> None:
        service = TrainingService(
            vault_root=self.root,
            converter_runner=lambda *_: {"success": True, "slideCount": 0},
        )

        with self.assertRaisesRegex(TrainingError, "zero or mismatched pages"):
            service.upload([UploadedFile("empty.pptx", b"pptx")], "Packing/Packer")
        markdown = next(self.root.rglob("KM_*.md")).read_text(encoding="utf-8")
        self.assertIn("Processing_Status : ConversionFailed", markdown)
        self.assertIn("Slide_Count : 0", markdown)

    def test_unsupported_upload_is_not_reported_as_success(self) -> None:
        with self.assertRaisesRegex(TrainingError, "Unsupported file type"):
            self.service().upload(
                [UploadedFile("notes.txt", b"text")], "Packing/Packer"
            )
        markdown = next(self.root.rglob("KM_*.md")).read_text(encoding="utf-8")
        self.assertIn("Processing_Status : ConversionFailed", markdown)

    def test_converter_exception_marks_conversion_failed(self) -> None:
        def failing_converter(*_args):
            raise RuntimeError("Office automation unavailable")

        service = TrainingService(
            vault_root=self.root,
            converter_runner=failing_converter,
        )
        with patch("backend.services.training_service.time.sleep"):
            with self.assertRaisesRegex(TrainingError, "Office automation unavailable"):
                service.upload(
                    [UploadedFile("manual.doc", b"doc")], "Packing/Packer"
                )
        markdown = next(self.root.rglob("KM_*.md")).read_text(encoding="utf-8")
        self.assertIn("Processing_Status : ConversionFailed", markdown)
        self.assertIn("Slide_Count : 0", markdown)

    def test_not_trained_lists_created_detail_only(self) -> None:
        record = self.service().upload(
            [UploadedFile("manual.pptx", b"pptx")], "Packing/Packer"
        )[0]
        record.markdown_path.with_name(f"{record.km_id}_summary.md").write_text(
            record.markdown_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

        pending = self.service().list_not_trained()

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kmId"], record.km_id)
        self.assertEqual(pending[0]["slideCount"], 2)

    def test_training_writes_detail_summary_and_trained_status(self) -> None:
        service = self.service()
        record = service.upload(
            [UploadedFile("manual.pptx", b"pptx")], "Packing/Packer"
        )[0]

        result = service.train_one(record.km_id)

        detail = record.markdown_path.read_text(encoding="utf-8")
        summary = record.markdown_path.with_name(f"{record.km_id}_summary.md")
        self.assertTrue(result["success"])
        self.assertEqual(result["slideCount"], 2)
        self.assertIn("Training_Status : Trained", detail)
        self.assertIn("Training_Slides : 2", detail)
        self.assertIn("## Slide 1", detail)
        self.assertTrue(summary.exists())
        self.assertIn("Engineering summary", summary.read_text(encoding="utf-8"))

    def test_completed_markdown_is_the_extraction_hook_with_source_sha(self) -> None:
        service = self.service()
        record = service.upload([UploadedFile("quotation.pdf", b"quotation-source")], "Purchasing/Quotes")[0]
        with self.assertRaisesRegex(TrainingError, "not successfully trained"):
            service.read_trained_input(record.km_id)
        service.train_one(record.km_id)
        source = service.read_trained_input(record.km_id)
        self.assertEqual(source.source_document_id, record.km_id)
        self.assertEqual(source.source_file, "quotation.pdf")
        self.assertEqual(len(source.source_content_sha256), 64)
        self.assertIn("Training_Status : Trained", source.detail_markdown)
        self.assertIn("Engineering summary", source.summary_markdown)
        self.assertEqual(service.list_trained()[0]["kmId"], record.km_id)

    def test_training_without_assets_is_not_success(self) -> None:
        service = self.service()
        record = service.upload(
            [UploadedFile("manual.pptx", b"pptx")], "Packing/Packer"
        )[0]
        for slide in record.asset_path.glob("Slide*.png"):
            slide.unlink()

        with self.assertRaisesRegex(TrainingError, "No Slide PNG"):
            service.train_one(record.km_id)
        detail = record.markdown_path.read_text(encoding="utf-8")
        self.assertIn("Training_Status : TrainingError", detail)
        self.assertNotIn("Training_Status : Trained", detail)

    def test_summary_failure_never_marks_partial_detail_trained(self) -> None:
        service = TrainingService(
            vault_root=self.root,
            converter_runner=self.successful_converter,
            vision_client=FailingSummaryClient(),  # type: ignore[arg-type]
        )
        record = service.upload(
            [UploadedFile("manual.pdf", b"pdf")], "Packing/Packer"
        )[0]

        with self.assertRaisesRegex(TrainingError, "summary failed"):
            service.train_one(record.km_id)

        detail = record.markdown_path.read_text(encoding="utf-8")
        summary = record.markdown_path.with_name(f"{record.km_id}_summary.md")
        self.assertIn("Training_Status : TrainingError", detail)
        self.assertNotIn("Training_Status : Trained", detail)
        self.assertFalse(summary.exists())

    def test_vision_uses_five_slide_batches_and_preserves_order(self) -> None:
        client = ConcurrentVisionClient()

        def six_page_converter(script: Path, source: Path, assets: Path) -> dict[str, object]:
            for index in range(1, 7):
                (assets / f"Slide{index:03d}.png").write_bytes(b"png")
            return {"success": True, "slideCount": 6, "pngCount": 6}

        service = TrainingService(
            vault_root=self.root,
            converter_runner=six_page_converter,
            vision_client=client,  # type: ignore[arg-type]
        )
        record = service.upload(
            [UploadedFile("manual.pdf", b"pdf")], "Packing/Packer"
        )[0]

        service.train_one(record.km_id)

        detail = record.markdown_path.read_text(encoding="utf-8")
        self.assertEqual(client.maximum_active, 5)
        positions = [detail.index(f"analysis for Slide{index:03d}.png") for index in range(1, 7)]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
