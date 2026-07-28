import sys
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    # Emit a parseable result instead of dying with a bare traceback, so the
    # server reports a clear reason (empty stdout -> meaningless ConversionFailed
    # otherwise). Fix on the server with:  python -m pip install PyMuPDF
    print(json.dumps({
        "success": False,
        "error": "PyMuPDF (fitz) is not installed for this Python. "
                 "Run: python -m pip install PyMuPDF"
    }))
    sys.exit(1)

# Render scale: 2.0 ~= 144 DPI, a good balance of sharpness vs file size.
RENDER_ZOOM = 2.0


def convert_pdf_to_png(pdf_file, output_dir):
    """Render each PDF page to a Slide###.png image."""
    if not Path(pdf_file).exists():
        print(json.dumps({
            "success": False,
            "pdfFile": pdf_file,
            "outputDir": output_dir,
            "error": f"PDF file not found: {pdf_file}"
        }))
        sys.exit(1)

    doc = None
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir)

        doc = fitz.open(pdf_file)
        page_count = doc.page_count

        matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=matrix)
            dst = output_path / f"Slide{page_num + 1:03d}.png"
            pix.save(str(dst))

        png_files = list(sorted(output_path.glob("Slide[0-9][0-9][0-9].png")))
        png_count = len(png_files)

        if png_count != page_count:
            return {
                "success": False,
                "slideCount": page_count,
                "pngCount": png_count,
                "pdfFile": pdf_file,
                "outputDir": output_dir,
                "error": f"PNG count ({png_count}) does not match page count ({page_count})"
            }

        return {
            "success": True,
            "slideCount": page_count,
            "outputDir": output_dir,
            "pdfFile": pdf_file
        }

    except Exception as e:
        return {
            "success": False,
            "pdfFile": pdf_file,
            "outputDir": output_dir,
            "error": str(e)
        }

    finally:
        if doc:
            doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(json.dumps({
            "success": False,
            "error": "Usage: python pdf_to_png.py <pdf_file> <output_dir>"
        }))
        sys.exit(1)

    pdf_file = sys.argv[1]
    output_dir = sys.argv[2]

    result = convert_pdf_to_png(pdf_file, output_dir)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)