"""Local server for the Excel-to-PDF upload page.

Run from this folder with: python app.py
Then browse to http://localhost:8000
"""

from cgi import FieldStorage, parse_header
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import tempfile

# On Windows, WeasyPrint needs Pango/GTK DLLs. The official MSYS2 install puts
# them here; set this before importing WeasyPrint so cffi can find them.
MSYS2_DLL_DIR = Path(r"C:\msys64\ucrt64\bin")
if os.name == "nt" and MSYS2_DLL_DIR.is_dir():
    os.environ.setdefault("WEASYPRINT_DLL_DIRECTORIES", str(MSYS2_DLL_DIR))

import pandas as pd
from weasyprint import HTML

BASE_DIR = Path(__file__).resolve().parent


def convert_excel_to_pdf(excel_path: Path, pdf_path: Path) -> None:
    """Create three-column member-detail cards from an uploaded Excel file."""
    df = pd.read_excel(excel_path).fillna("")

    # Keep PIN and mobile numbers free of Excel's common trailing '.0'.
    for column in ["PIN", "Mobile 1", "Mobile 2"]:
        if column in df.columns:
            df[column] = df[column].apply(
                lambda value: str(int(float(value)))
                if str(value).replace(".", "", 1).isdigit()
                else str(value)
            )

    def get_value(row, column: str) -> str:
        value = str(row[column]).strip() if column in df.columns else ""
        return "" if value.lower() == "nan" else value

    html_parts = ["""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
@page { size: A4 portrait; margin: 15mm 12mm; background-color: #ffffff; }
*, *::before, *::after { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; margin: 0; padding: 0; color: #000; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
tr { page-break-inside: avoid; }
td { border: 1px solid #000; padding: 12px 10px; vertical-align: top; width: 33.33%; overflow: hidden; }
.name { font-weight: bold; margin-bottom: 4px; font-size: 11pt; }
.details { margin: 2px 0; line-height: 1.3; }
.po-line { font-weight: bold; }
</style></head><body><table>"""]

    for index in range(0, len(df), 3):
        html_parts.append("<tr>")
        for offset in range(3):
            if index + offset >= len(df):
                html_parts.append("<td></td>")
                continue

            row = df.iloc[index + offset]
            title, name = get_value(row, "Title"), get_value(row, "Name")
            relation, rel_name = get_value(row, "Relation"), get_value(row, "Relative Name")
            house, address, village = (get_value(row, field) for field in ["House Name", "Address", "Village"])
            po, taluk, district = (get_value(row, field) for field in ["Post Office", "Taluk", "District"])
            pin, mobile1, mobile2 = (get_value(row, field) for field in ["PIN", "Mobile 1", "Mobile 2"])

            full_name = f"{title} {name}".strip()
            relation_text = f"{relation} {rel_name}".strip()
            address_line = ", ".join(part for part in ([f'\"{house}\"'] if house else []) + [address, village] if part)
            po_line = f"P.O. {po.upper()} - {pin}" if po and pin else (f"P.O. {po.upper()}" if po else (f"PIN - {pin}" if pin else ""))
            location_line = ", ".join(part for part in ([f"{taluk} Tq"] if taluk else []) + [district] if part)
            mobile_line = ", ".join(part for part in [mobile1, mobile2] if part)

            cell_parts = ["<td>"]
            for css_class, value in [
                ("name", full_name), ("details", relation_text), ("details", address_line),
                ("details po-line", po_line), ("details", location_line),
                ("details", f"M: {mobile_line}" if mobile_line else ""),
            ]:
                if value:
                    cell_parts.append(f'<div class="{css_class}">{escape(value)}</div>')
            cell_parts.append("</td>")
            html_parts.append("".join(cell_parts))
        html_parts.append("</tr>")

    html_parts.append("</table></body></html>")
    HTML(string="".join(html_parts), base_url=str(BASE_DIR)).write_pdf(pdf_path)


class ConverterHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/convert":
            self.send_error(404, "Endpoint not found")
            return

        content_type, _ = parse_header(self.headers.get("Content-Type", ""))
        if content_type != "multipart/form-data":
            self.send_error(400, "Expected a file upload")
            return

        form = FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers["Content-Type"]},
        )
        file_item = form["excel_file"] if "excel_file" in form else None
        if file_item is None or not getattr(file_item, "filename", None):
            self.send_error(400, "Please choose an Excel file")
            return

        extension = Path(file_item.filename).suffix.lower()
        if extension not in {".xlsx", ".xls", ".xlsm"}:
            self.send_error(400, "Only .xlsx, .xls, and .xlsm files are supported")
            return

        safe_name = Path(file_item.filename).name
        # Each request receives an isolated working directory. It is deleted in
        # all cases, including a failed conversion or a completed download.
        working_dir = Path(tempfile.mkdtemp(prefix="excel_pdf_", dir=BASE_DIR))
        response_started = False
        try:
            excel_path = working_dir / safe_name
            pdf_path = working_dir / f"{Path(safe_name).stem}.pdf"
            with excel_path.open("wb") as destination:
                shutil.copyfileobj(file_item.file, destination)

            convert_excel_to_pdf(excel_path, pdf_path)
            if not pdf_path.is_file():
                raise RuntimeError("Conversion did not create a PDF file")

            response_started = True
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{pdf_path.name}"')
            self.send_header("Content-Length", str(pdf_path.stat().st_size))
            self.end_headers()
            with pdf_path.open("rb") as pdf:
                shutil.copyfileobj(pdf, self.wfile)
        except Exception as error:
            # Do not attempt an HTTP error if the PDF response was already
            # started (for example, if the client disconnects mid-download).
            if not response_started:
                self.send_error(500, str(error))
        finally:
            shutil.rmtree(working_dir, ignore_errors=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("localhost", 8000), ConverterHandler)
    print("Open http://localhost:8000 in your browser. Press Ctrl+C to stop.")
    server.serve_forever()
