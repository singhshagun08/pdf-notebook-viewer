from flask import Flask, render_template, request, redirect, url_for, abort
import os
import shutil
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
BOOK_FOLDER = os.path.join(BASE_DIR, "static", "books")
TEMP_FOLDER = os.path.join(BASE_DIR, "static", "temp")

ALLOWED_EXTENSIONS = {"pdf"}

POPPLER_PATH = os.environ.get("POPPLER_PATH")


def ensure_folders():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(BOOK_FOLDER, exist_ok=True)
    os.makedirs(TEMP_FOLDER, exist_ok=True)


ensure_folders()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_books():
    if not os.path.exists(BOOK_FOLDER):
        return []

    books = []
    for item in os.listdir(BOOK_FOLDER):
        item_path = os.path.join(BOOK_FOLDER, item)
        if os.path.isdir(item_path):
            books.append(item)

    return sorted(books, key=str.lower)


def get_book_pages(bookname):
    book_path = os.path.join(BOOK_FOLDER, bookname)
    if not os.path.exists(book_path):
        return []

    pages = [
        f for f in os.listdir(book_path)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    def numeric_sort(filename):
        name = os.path.splitext(filename)[0]
        return int(name) if name.isdigit() else 999999

    return sorted(pages, key=numeric_sort)


def convert_pdf_to_images(pdf_path, output_folder):
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    convert_kwargs = {}
    if POPPLER_PATH:
        convert_kwargs["poppler_path"] = POPPLER_PATH

    try:
        images = convert_from_path(pdf_path, **convert_kwargs)
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF: {e}")

    for i, img in enumerate(images):
        img.save(os.path.join(output_folder, f"{i}.jpg"), "JPEG")


@app.route("/")
def home():
    books = get_books()
    return render_template("firstpge.html", books=books)


@app.route("/try")
def try_page():
    books = get_books()
    return render_template(
        "secondpge.html",
        books=books,
        preview_pdf=None,
        preview_name=None,
        error=None
    )


@app.route("/preview-pdf", methods=["POST"])
def preview_pdf():
    books = get_books()

    if "pdf" not in request.files:
        return render_template(
            "secondpge.html",
            books=books,
            preview_pdf=None,
            preview_name=None,
            error="No PDF file was selected."
        )

    pdf = request.files["pdf"]

    if pdf.filename == "":
        return render_template(
            "secondpge.html",
            books=books,
            preview_pdf=None,
            preview_name=None,
            error="Please choose a PDF file."
        )

    if not allowed_file(pdf.filename):
        return render_template(
            "secondpge.html",
            books=books,
            preview_pdf=None,
            preview_name=None,
            error="Only PDF files are allowed."
        )

    filename = secure_filename(pdf.filename)
    temp_pdf_path = os.path.join(TEMP_FOLDER, filename)
    pdf.save(temp_pdf_path)

    preview_name = os.path.splitext(filename)[0]

    return render_template(
        "secondpge.html",
        books=books,
        preview_pdf=filename,
        preview_name=preview_name,
        error=None
    )


@app.route("/convert-preview", methods=["POST"])
def convert_preview():
    pdf_name = request.form.get("pdf_name", "").strip()
    if not pdf_name:
        return redirect(url_for("try_page"))

    temp_pdf_path = os.path.join(TEMP_FOLDER, pdf_name)
    if not os.path.exists(temp_pdf_path):
        return redirect(url_for("try_page"))

    filename = secure_filename(pdf_name)
    book_name = os.path.splitext(filename)[0]

    final_pdf_path = os.path.join(UPLOAD_FOLDER, f"{book_name}.pdf")
    shutil.copy(temp_pdf_path, final_pdf_path)

    book_folder = os.path.join(BOOK_FOLDER, book_name)

    try:
        convert_pdf_to_images(final_pdf_path, book_folder)
    except RuntimeError as e:
        books = get_books()
        return render_template(
            "secondpge.html",
            books=books,
            preview_pdf=pdf_name,
            preview_name=book_name,
            error=str(e)
        )

    return redirect(url_for("book", bookname=book_name))


@app.route("/reconvert/<bookname>", methods=["POST"])
def reconvert_book(bookname):
    bookname = secure_filename(bookname)
    pdf_file = os.path.join(UPLOAD_FOLDER, f"{bookname}.pdf")

    if not os.path.exists(pdf_file):
        abort(404, description="Original PDF not found.")

    book_folder = os.path.join(BOOK_FOLDER, bookname)

    try:
        convert_pdf_to_images(pdf_file, book_folder)
    except RuntimeError as e:
        abort(500, description=str(e))

    return redirect(url_for("book", bookname=bookname))


@app.route("/book/<bookname>")
def book(bookname):
    bookname = secure_filename(bookname)
    book_path = os.path.join(BOOK_FOLDER, bookname)

    if not os.path.exists(book_path):
        abort(404, description="Book not found.")

    pages = get_book_pages(bookname)
    if not pages:
        abort(404, description="No pages found for this book.")

    return render_template("book.html", bookname=bookname, pages=pages)


@app.route("/delete/<bookname>", methods=["POST"])
def delete(bookname):
    bookname = secure_filename(bookname)

    book_folder = os.path.join(BOOK_FOLDER, bookname)
    pdf_file = os.path.join(UPLOAD_FOLDER, f"{bookname}.pdf")

    if os.path.exists(book_folder):
        shutil.rmtree(book_folder)

    if os.path.exists(pdf_file):
        os.remove(pdf_file)

    return redirect(url_for("try_page"))


@app.route("/edit/<bookname>")
def edit(bookname):
    bookname = secure_filename(bookname)
    return f"<h1>Edit page for {bookname}</h1><p>Editor coming soon.</p>"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")