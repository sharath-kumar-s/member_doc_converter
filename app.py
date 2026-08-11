"""FastAPI application for converting Excel uploads to member PDF cards."""

import io
import os
from html import escape
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from weasyprint import HTML

# On Windows, WeasyPrint needs Pango/GTK DLLs. The MSYS2 install puts them here.
MSYS2_DLL_DIR = Path(r"C:\msys64\ucrt64\bin")
if os.name == "nt" and MSYS2_DLL_DIR.is_dir():
    os.environ.setdefault("WEASYPRINT_DLL_DIRECTORIES", str(MSYS2_DLL_DIR))

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Member Doc Converter")


def convert_excel_to_pdf(df: pd.DataFrame) -> bytes:
    """Create three-column member-detail cards from an uploaded Excel file."""
    df = df.fillna("")

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
            address_line = ", ".join(
                part for part in ([f'\"{house}\"'] if house else []) + [address, village] if part
            )
            po_line = (
                f"P.O. {po.upper()} - {pin}"
                if po and pin
                else (f"P.O. {po.upper()}" if po else (f"PIN - {pin}" if pin else ""))
            )
            location_line = ", ".join(part for part in ([f"{taluk} Tq"] if taluk else []) + [district] if part)
            mobile_line = ", ".join(part for part in [mobile1, mobile2] if part)

            cell_parts = ["<td>"]
            for css_class, value in [
                ("name", full_name),
                ("details", relation_text),
                ("details", address_line),
                ("details po-line", po_line),
                ("details", location_line),
                ("details", f"M: {mobile_line}" if mobile_line else ""),
            ]:
                if value:
                    cell_parts.append(f'<div class="{css_class}">{escape(value)}</div>')
            cell_parts.append("</td>")
            html_parts.append("".join(cell_parts))
        html_parts.append("</tr>")

    html_parts.append("</table></body></html>")
    try:
        return HTML(string="".join(html_parts), base_url=str(BASE_DIR)).write_pdf()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF conversion failed: {exc}")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(BASE_DIR / "templates" / "index.html", media_type="text/html")


@app.post("/convert")
async def convert(excel_file: UploadFile = File(...)) -> Response:
    if not excel_file.filename:
        raise HTTPException(status_code=400, detail="Please upload an Excel file")

    extension = Path(excel_file.filename).suffix.lower()
    if extension not in {".xlsx", ".xls", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .xlsm files are supported")

    content = await excel_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Please upload a non-empty Excel file")

    try:
        df = pd.read_excel(io.BytesIO(content)).fillna("")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid Excel file")

    pdf_bytes = convert_excel_to_pdf(df)
    filename = f"{Path(excel_file.filename).stem}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
