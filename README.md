# Excel to PDF page

1. Install dependencies: `python -m pip install -r requirements.txt`.
2. In this folder, run `python app.py`.
3. Open `http://localhost:8000` in a browser and upload an Excel file.

## Windows: install WeasyPrint system libraries

WeasyPrint also needs the Pango/GTK native libraries on Windows. If you see an
error mentioning `libgobject-2.0-0`, install [MSYS2](https://www.msys2.org/),
open its **MSYS2 UCRT64** terminal, and run:

```powershell
pacman -S mingw-w64-ucrt-x86_64-pango
```

Close that terminal and restart `python app.py`. The application automatically
uses the usual MSYS2 DLL directory, `C:\msys64\ucrt64\bin`. If MSYS2 was
installed elsewhere, set this environment variable before starting the server:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'D:\your-msys2-folder\ucrt64\bin'
python app.py
```

The conversion creates three member cards per PDF row using the column names in
the supplied conversion code. `index.html` can be opened directly to view the
page, but submitting needs the Python server because a browser cannot run a
Python script from a local HTML file.

Uploaded Excel files and generated PDFs are kept only in a unique temporary
folder while that request is processed. They are deleted immediately after the
download finishes (or if the conversion fails).
