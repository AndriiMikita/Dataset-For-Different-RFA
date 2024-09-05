import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_PDF_FOLDER = os.path.join(BASE_DIR, "raw")

EDITED_PDF_FOLDER = os.path.join(BASE_DIR, "edited")

CSV_FOLDER = os.path.join(BASE_DIR, "output")

CSV_FILENAME = "document_changes.csv"

CSV_FILE_PATH = os.path.join(CSV_FOLDER, CSV_FILENAME)

FONT_PATH = os.path.join(BASE_DIR, "fonts/Helvetica-Bold.ttf")

os.makedirs(RAW_PDF_FOLDER, exist_ok=True)
os.makedirs(EDITED_PDF_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
