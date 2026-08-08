# Member Doc Converter

This project converts uploaded Excel files into a downloadable PDF containing three member cards per row.

## Project structure

member_doc_converter/
├── templates/
│   └── index.html
├── app.py
├── requirements.txt
├── render-build.sh
├── README.md
├── test.py
├── uploads/
└── output/

## Local setup

1. Install dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. Run the FastAPI server:

   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

3. Open `http://localhost:8000` in your browser.

## Render deployment

1. Add this repository to Render as a Python Web Service.
2. Set the build command to:

   ```bash
   sh render-build.sh
   ```

3. Set the start command to:

   ```bash
   uvicorn app:app --host 0.0.0.0 --port $PORT
   ```

4. If using WeasyPrint on Render, you may need a custom Docker image or a service
   with the required native dependencies (`cairo`, `pango`, `gdk-pixbuf`).

## Windows notes

WeasyPrint requires native Pango/GTK libraries on Windows. Install MSYS2 and the
required packages if you see an error about `libgobject-2.0-0`.

```powershell
pacman -S mingw-w64-ucrt-x86_64-pango
```

Then restart the app with:

```powershell
python app.py
```

## How it works

- `app.py` serves the upload page from `templates/index.html`.
- Uploaded Excel files are converted to a temporary PDF and returned directly.
- The app supports `.xlsx`, `.xls`, and `.xlsm` files.
