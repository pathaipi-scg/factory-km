import sys
import os
import json
import time
from pathlib import Path
import win32com.client

# Reuse the PDF rendering pipeline (Word has no native page-to-PNG export, so
# we convert DOCX -> PDF via Word COM, then render the PDF pages to images).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_to_png import convert_pdf_to_png

# Word COM constants
WD_EXPORT_FORMAT_PDF = 17       # wdExportFormatPDF
WD_DO_NOT_SAVE_CHANGES = 0      # wdDoNotSaveChanges


def _retry(fn, attempts=8, delay=0.5):
    """Retry a COM call that may transiently fail while Word is busy
    (RPC_E_CALL_REJECTED: "Call was rejected by callee")."""
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def _quit_word(word):
    """Quit Word without saving, tolerating COM quirks during cleanup."""
    if not word:
        return
    try:
        word.Quit(WD_DO_NOT_SAVE_CHANGES)
    except Exception:
        try:
            word.Quit()
        except Exception:
            pass


def convert_docx_to_png(docx_file, output_dir):
    """Convert a Word document to Slide###.png images (via an intermediate PDF)."""
    if not Path(docx_file).exists():
        print(json.dumps({
            "success": False,
            "docxFile": docx_file,
            "outputDir": output_dir,
            "error": f"DOCX file not found: {docx_file}"
        }))
        sys.exit(1)

    word = None
    pdf_path = Path(output_dir) / "_docx_source.pdf"
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        abs_docx = str(Path(docx_file).absolute())
        # EnsureDispatch (early binding) so Word methods like ExportAsFixedFormat
        # and Close resolve reliably; plain Dispatch leaves Word late-bound and
        # those methods fail to resolve ("Open.ExportAsFixedFormat").
        word = win32com.client.gencache.EnsureDispatch("Word.Application")
        _retry(lambda: setattr(word, "Visible", False))
        word.DisplayAlerts = False
        time.sleep(0.3)  # give Word a moment to finish starting up

        # Open read-only and export the whole document to a single PDF.
        # Wrapped in retries: a freshly launched Word can reject calls while busy.
        document = _retry(lambda: word.Documents.Open(abs_docx, ReadOnly=True))
        _retry(lambda: document.ExportAsFixedFormat(str(pdf_path), WD_EXPORT_FORMAT_PDF))
        document.Saved = True   # avoid a save prompt on quit

        # Quit Word (closes the document too); Document.Close can fail to
        # resolve under dynamic dispatch, so we rely on Application.Quit.
        _quit_word(word)
        word = None

        if not pdf_path.exists():
            return {
                "success": False,
                "docxFile": docx_file,
                "outputDir": output_dir,
                "error": "Word did not produce an intermediate PDF"
            }

        # Render the produced PDF into Slide###.png pages
        result = convert_pdf_to_png(str(pdf_path), output_dir)
        result["docxFile"] = docx_file
        result.pop("pdfFile", None)
        return result

    except Exception as e:
        return {
            "success": False,
            "docxFile": docx_file,
            "outputDir": output_dir,
            "error": str(e)
        }

    finally:
        _quit_word(word)
        # Remove the intermediate PDF so it is not mistaken for a KM asset
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(json.dumps({
            "success": False,
            "error": "Usage: python docx_to_png.py <docx_file> <output_dir>"
        }))
        sys.exit(1)

    docx_file = sys.argv[1]
    output_dir = sys.argv[2]

    result = convert_docx_to_png(docx_file, output_dir)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)