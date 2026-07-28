import sys
import json
import os
import glob
import shutil
import subprocess
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


# Render scale for the PDF->PNG step: 2.0 ~= 144 DPI (matches pdf_to_png.py).
RENDER_ZOOM = 2.0

# Excel ExportAsFixedFormat type for PDF output (xlTypePDF = 0).
XL_TYPE_PDF = 0


# ---------------------------------------------------------------------------
# Shared: render a PDF to Slide###.png in output_path.
# ---------------------------------------------------------------------------
def render_pdf_to_pngs(pdf_file, output_path):
    matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
    doc = fitz.open(str(pdf_file))
    try:
        for page_num in range(doc.page_count):
            pix = doc.load_page(page_num).get_pixmap(matrix=matrix)
            dst = output_path / f"Slide{page_num + 1:03d}.png"
            pix.save(str(dst))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Primary path: LibreOffice headless (no printer / clipboard / desktop needed).
#
# Excel's own ExportAsFixedFormat / CopyPicture rendering fails on some servers
# (E_INVALIDARG / DISP_E_EXCEPTION) because Office COM needs an interactive
# desktop and a usable printer to lay out pages -- which a headless / service /
# disconnected-RDP session does not reliably provide. LibreOffice's --headless
# converter is built for exactly this and does not depend on any of that.
# ---------------------------------------------------------------------------
def find_soffice():
    """Locate the LibreOffice 'soffice' binary, or return None if not installed."""
    override = os.environ.get('LIBREOFFICE_BIN')
    if override and Path(override).exists():
        return override
    for name in ('soffice.exe', 'soffice.com', 'soffice'):
        found = shutil.which(name)
        if found:
            return found
    candidates = []
    for base in (os.environ.get('ProgramFiles', r'C:\Program Files'),
                 os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')):
        if base:
            candidates.append(Path(base) / 'LibreOffice' / 'program' / 'soffice.exe')
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return None


def convert_with_libreoffice(soffice, excel_file, output_path):
    """Convert via LibreOffice: workbook -> PDF -> Slide###.png. Returns png_count."""
    abs_excel = str(Path(excel_file).absolute())

    # Give LibreOffice a private profile dir so it never collides with a running
    # LibreOffice instance or a locked default profile (which would make it exit
    # without converting).
    profile_dir = output_path / "_lo_profile"
    profile_uri = "file:///" + str(profile_dir).replace("\\", "/")

    cmd = [
        soffice, '--headless', '--nologo', '--nofirststartwizard',
        '--norestore', '--invisible',
        f'-env:UserInstallation={profile_uri}',
        '--convert-to', 'pdf', '--outdir', str(output_path), abs_excel,
    ]
    sys.stderr.write("LibreOffice cmd: " + " ".join(cmd) + "\n")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        sys.stderr.write(f"LibreOffice rc={result.returncode}\n"
                         f"stdout: {result.stdout.strip()}\n"
                         f"stderr: {result.stderr.strip()}\n")
    finally:
        # The throwaway profile is large; remove it whether or not we succeeded.
        shutil.rmtree(profile_dir, ignore_errors=True)

    # LibreOffice writes "<stem>.pdf" into outdir.
    stem = Path(excel_file).stem
    pdf_out = output_path / f"{stem}.pdf"
    if not pdf_out.exists():
        # Fallback: pick up any PDF it produced (LO may sanitize the name).
        produced = [p for p in output_path.glob("*.pdf")]
        pdf_out = produced[0] if produced else None
    if not pdf_out or not Path(pdf_out).exists():
        raise RuntimeError("LibreOffice did not produce a PDF "
                           f"(rc={result.returncode}). stderr: {result.stderr.strip()}")

    render_pdf_to_pngs(pdf_out, output_path)
    try:
        os.remove(pdf_out)
    except Exception:
        pass

    return len(list(output_path.glob("Slide[0-9][0-9][0-9].png")))


# ---------------------------------------------------------------------------
# Fallback path: Excel COM (ExportAsFixedFormat -> PDF -> render). Used only
# when LibreOffice is not installed. Kept for deployments where Excel's export
# actually works.
# ---------------------------------------------------------------------------
def convert_with_excel_com(excel_file, output_dir, output_path):
    import win32com.client  # imported lazily so the LibreOffice path needs no pywin32

    workbook = None
    excel = None
    pdf_path = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 1  # open without Protected View (Mark-of-the-Web)

        abs_excel_file = str(Path(excel_file).absolute())
        workbook = excel.Workbooks.Open(abs_excel_file, False, True)
        if workbook is None:
            xlRepairFile = 1
            workbook = excel.Workbooks.Open(abs_excel_file, False, True, CorruptLoad=xlRepairFile)
        if workbook is None:
            raise RuntimeError("Excel could not open the workbook (returned None) even in "
                               "repair mode. Likely a password or a genuinely corrupt file.")

        sheet_count = workbook.Sheets.Count
        for sheet_num in range(1, sheet_count + 1):
            try:
                ps = workbook.Sheets(sheet_num).PageSetup
                ps.Zoom = False
                ps.FitToPagesWide = 1
                ps.FitToPagesTall = False
            except Exception as e:
                sys.stderr.write(f"PageSetup sheet {sheet_num} skipped: {e}\n")

        pdf_path = str(output_path / "_excel_export.pdf")
        workbook.ExportAsFixedFormat(XL_TYPE_PDF, pdf_path)

        try:
            workbook.Close(False)
        except Exception:
            pass
        workbook = None
        try:
            excel.Quit()
        except Exception:
            pass
        excel = None

        if not Path(pdf_path).exists():
            raise RuntimeError("Excel produced no PDF (nothing printable in the workbook).")

        render_pdf_to_pngs(pdf_path, output_path)
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        pdf_path = None

        return sheet_count, len(list(output_path.glob("Slide[0-9][0-9][0-9].png")))
    finally:
        try:
            if workbook:
                workbook.Close(False)
        except Exception:
            pass
        try:
            if excel:
                excel.Quit()
        except Exception:
            pass
        try:
            if pdf_path and Path(pdf_path).exists():
                os.remove(pdf_path)
        except Exception:
            pass


def convert_excel_to_png(excel_file, output_dir):
    """Convert an Excel workbook to Slide###.png images.

    Prefer LibreOffice headless (reliable on servers); fall back to Excel COM
    only if LibreOffice is not installed.
    """
    if not Path(excel_file).exists():
        print(json.dumps({
            "success": False,
            "excelFile": excel_file,
            "outputDir": output_dir,
            "error": f"Excel file not found: {excel_file}"
        }))
        sys.exit(1)

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir).resolve()

        soffice = find_soffice()
        last_error = None

        if soffice:
            try:
                png_count = convert_with_libreoffice(soffice, excel_file, output_path)
                if png_count > 0:
                    return {
                        "success": True,
                        "slideCount": png_count,
                        "sheetCount": png_count,
                        "pngCount": png_count,
                        "outputDir": output_dir,
                        "excelFile": excel_file,
                        "engine": "libreoffice"
                    }
                last_error = "LibreOffice produced no pages."
            except Exception as e:
                last_error = f"LibreOffice failed: {e}"
                sys.stderr.write(last_error + "\nFalling back to Excel COM...\n")
        else:
            sys.stderr.write("LibreOffice (soffice) not found; using Excel COM.\n")

        # Fallback: Excel COM.
        try:
            sheet_count, png_count = convert_with_excel_com(excel_file, output_dir, output_path)
            if png_count > 0:
                return {
                    "success": True,
                    "slideCount": png_count,
                    "sheetCount": sheet_count,
                    "pngCount": png_count,
                    "outputDir": output_dir,
                    "excelFile": excel_file,
                    "engine": "excel"
                }
            last_error = (last_error + " | " if last_error else "") + "Excel COM produced no pages."
        except Exception as e:
            excel_err = f"Excel COM failed: {e}"
            last_error = (last_error + " | " if last_error else "") + excel_err

        # Both engines failed.
        hint = ("Install LibreOffice on the server (https://www.libreoffice.org/download/) "
                "so .xlsx can be converted without Excel; Excel's own PDF export does not "
                "work in this headless session.")
        return {
            "success": False,
            "excelFile": excel_file,
            "outputDir": output_dir,
            "error": f"{last_error}. {hint}"
        }

    except Exception as e:
        return {
            "success": False,
            "excelFile": excel_file,
            "outputDir": output_dir,
            "error": str(e)
        }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(json.dumps({
            "success": False,
            "error": "Usage: python excel_to_png.py <excel_file> <output_dir>"
        }))
        sys.exit(1)

    excel_file = sys.argv[1]
    output_dir = sys.argv[2]

    result = convert_excel_to_png(excel_file, output_dir)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
