import io
import math
import tempfile
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk, ImageFont, ImageDraw
import os
import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class PDFEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Editor")
        self.pdf_document = None
        self.current_page = 0
        self.pdf_files = []
        self.current_file_index = 0
        self.mode = None  # 'text' для додавання тексту, 'image' для додавання зображення, 'edit' для редагування тексту
        self.text_items_by_page = {}  # Зберігає текстові елементи по сторінках
        self.current_text_item = None  # Текущий текстовий елемент для переміщення

        self.root.state('zoomed')  # Вікно на весь екран

        self.load_pdf_files()
        self.setup_ui()  # Створюємо елементи інтерфейсу, включаючи self.canvas
        self.open_next_pdf()  # Тепер викликаємо self.open_next_pdf()

    def load_pdf_files(self):
        folder_path = settings.RAW_PDF_FOLDER
        self.pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.pdf')]
        if not self.pdf_files:
            messagebox.showwarning("No PDFs", "No PDF files found in the specified folder.")
            self.root.quit()

    def setup_ui(self):
        # Створюємо головний фрейм для кнопок
        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.X)

        # Створюємо кнопки
        self.save_button = tk.Button(frame, text="Save PDF", command=self.save_pdf, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.previous_button = tk.Button(frame, text="Previous Page", command=self.previous_page, state=tk.DISABLED)
        self.previous_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.next_button = tk.Button(frame, text="Next Page", command=self.next_page, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.add_text_button = tk.Button(frame, text="Add Text", command=self.enable_text_mode, state=tk.DISABLED)
        self.add_text_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.add_image_button = tk.Button(frame, text="Add Image", command=self.enable_image_mode, state=tk.DISABLED)
        self.add_image_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.increase_font_button = tk.Button(frame, text="Increase Text Size", command=self.increase_font_size)
        self.increase_font_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.decrease_font_button = tk.Button(frame, text="Decrease Text Size", command=self.decrease_font_size)
        self.decrease_font_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.clear_text_button = tk.Button(frame, text="Clear All Text", command=self.clear_all_text)
        self.clear_text_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.duplicate_page_button = tk.Button(frame, text="Duplicate Page", command=self.duplicate_page, state=tk.DISABLED)
        self.duplicate_page_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Створюємо canvas для відображення PDF
        self.canvas = tk.Canvas(self.root, bg="gray")
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Додаємо прокрутку
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)

        # Додаємо лейбл для відображення номеру сторінки
        self.page_info_label = tk.Label(self.root, text="", font=("Helvetica", 14))
        self.page_info_label.pack(side=tk.BOTTOM, pady=5)

    def open_next_pdf(self):
        if self.current_file_index < len(self.pdf_files):
            file_path = self.pdf_files[self.current_file_index]
            self.current_file_index += 1
            self.open_pdf(file_path)
        else:
            messagebox.showinfo("End of Files", "No more PDF files to display.")
            self.root.quit()

    def open_pdf(self, file_path):
        self.pdf_document = fitz.open(file_path)
        self.pages_as_images = []  # Store pages as images

        # Extract each page as an image
        for i in range(len(self.pdf_document)):
            page = self.pdf_document[i]
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.pages_as_images.append(img)
        
        self.current_page = 0
        self.display_page()
        self.save_button.config(state=tk.NORMAL)
        self.previous_button.config(state=tk.NORMAL)
        self.next_button.config(state=tk.NORMAL)
        self.add_text_button.config(state=tk.NORMAL)
        self.add_image_button.config(state=tk.NORMAL)
        self.duplicate_page_button.config(state=tk.NORMAL)

    def display_page(self):
        # Очищення старого вмісту canvas
        self.canvas.delete("all")

        img = self.pages_as_images[self.current_page]

        # Масштабування зображення для підходу до canvas
        canvas_width = self.canvas.winfo_width()
        scale_ratio = canvas_width / img.width
        new_width = int(img.width * scale_ratio)
        new_height = int(img.height * scale_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        self.img_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self.img_tk, anchor=tk.NW)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))  # Оновлення області прокрутки

        # Перемальовування всіх текстових елементів та фону для поточної сторінки
        if self.current_page in self.text_items_by_page:
            for text_info in self.text_items_by_page[self.current_page]:
                # Перемальовування тексту
                self.add_text_with_background(text_info, redraw=True)

        self.page_info_label.config(text=f"Page {self.current_page + 1} of {len(self.pages_as_images)}")

        # Діагностичний вивід для перевірки значення current_text_item
        if self.current_text_item:
            print(f"Current text item: {self.current_text_item}")


    def on_resize(self, event):
        """Обробка зміни розміру вікна для перерисовки сторінки."""
        self.display_page()

    def on_canvas_click(self, event):
        if self.mode == "text":
            self.add_text_at_position(event.x, event.y)
        elif self.mode == "image":
            self.add_image_at_position(event.x, event.y)

    def on_canvas_drag(self, event):
        if self.current_text_item:
            # Отримуємо реальні координати з урахуванням прокрутки
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)

            # Оновлюємо позицію тексту і прямокутника
            self.canvas.coords(self.current_text_item["id"], x, y)
            bbox = self.canvas.bbox(self.current_text_item["id"])
            
            if self.current_text_item.get("rect_id"):
                self.canvas.coords(self.current_text_item["rect_id"], bbox)

            # Оновлюємо координати в об'єкті текстового елементу
            self.current_text_item["x"] = x
            self.current_text_item["y"] = y


    def increase_font_size(self):
        if self.current_text_item:
            self.current_text_item["font_size"] += 2  # Збільшуємо розмір шрифту на 2 пункти
            self.redraw_text_with_new_size()

    def decrease_font_size(self):
        if self.current_text_item and self.current_text_item["font_size"] > 2:
            self.current_text_item["font_size"] -= 2  # Зменшуємо розмір шрифту на 2 пункти
            self.redraw_text_with_new_size()

    def redraw_text_with_new_size(self):
        """Перемальовує текстовий елемент з новим розміром шрифту."""
        if self.current_text_item:
            # Видаляємо старий текст і фон
            self.canvas.delete(self.current_text_item["id"])
            self.canvas.delete(self.current_text_item.get("rect_id", None))

            # Перемальовуємо текст з новим розміром шрифту
            self.add_text_with_background(self.current_text_item)

    def clear_all_text(self):
        if self.current_page in self.text_items_by_page:
            for text_info in self.text_items_by_page[self.current_page]:
                self.canvas.delete(text_info["id"])
                self.canvas.delete(text_info.get("rect_id", None))
            self.text_items_by_page[self.current_page].clear()

    def on_canvas_right_click(self, event):
        closest_text = self.canvas.find_closest(event.x, event.y)
        if closest_text:
            text_info = next((item for item in self.text_items_by_page.get(self.current_page, []) if item["id"] == closest_text[0]), None)
            if text_info:
                self.current_text_item = text_info
                print(f"Selected text item: {self.current_text_item}")

    def add_text_with_background(self, text_info, redraw=False):
        """Додає текст з фоном на canvas."""
        if redraw:
            # Видалення старих елементів
            if text_info["id"]:
                self.canvas.delete(text_info["id"])
            if text_info.get("rect_id"):
                self.canvas.delete(text_info["rect_id"])
            
            # Додавання нового тексту
            text_id = self.canvas.create_text(
                text_info["x"],
                text_info["y"],
                text=text_info["text"],
                font=("ArialNarrow", text_info["font_size"]),
                anchor="nw",
                fill="black",
            )
        else:
            text_id = self.canvas.create_text(
                text_info["x"],
                text_info["y"],
                text=text_info["text"],
                font=("ArialNarrow", text_info["font_size"]),
                anchor="nw",
                fill="black",
            )
        
        # Створення фону для тексту
        bbox = self.canvas.bbox(text_id)
        rect_id = self.canvas.create_rectangle(bbox, fill="white", outline="")
        
        # Переміщення прямокутника під текст
        self.canvas.tag_lower(rect_id, text_id)  

        if not redraw:
            text_info["id"] = text_id
            text_info["rect_id"] = rect_id
            self.text_items_by_page.setdefault(self.current_page, []).append(text_info)

    def add_text_at_position(self, x, y):
        # Отримуємо відносні координати з урахуванням прокрутки
        canvas_x = self.canvas.canvasx(x)
        canvas_y = self.canvas.canvasy(y)

        # Відкриваємо діалог для введення тексту
        text = simpledialog.askstring("Add Text", "Enter the text:")
        if text:
            text_info = {
                "text": text,
                "x": canvas_x,
                "y": canvas_y,
                "font_size": 12,
                "id": None,  # Буде оновлено пізніше
                "rect_id": None  # Буде оновлено пізніше
            }
            self.add_text_with_background(text_info)
            self.current_text_item = text_info
            self.mode = "edit"

            # Оновлюємо область прокрутки, щоб включити новий текстовий елемент
            self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def on_mouse_wheel(self, event):
        """Обробляємо вертикальну прокрутку за допомогою коліщатка миші."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))  # Оновлюємо область прокрутки

    def enable_text_mode(self):
        self.mode = "text"

    def enable_image_mode(self):
        self.mode = "image"

    def next_page(self):
        if self.current_page < len(self.pages_as_images) - 1:
            self.current_page += 1
            self.display_page()

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def duplicate_page(self):
        # Зберігаємо поточну сторінку як новий зображенням
        new_page_image = self.pages_as_images[self.current_page].copy()
        self.pages_as_images.insert(self.current_page + 1, new_page_image)

        # Копіюємо текстові елементи поточної сторінки на нову сторінку
        if self.current_page in self.text_items_by_page:
            self.text_items_by_page[self.current_page + 1] = [
                {**item, "id": None, "rect_id": None} for item in self.text_items_by_page[self.current_page]
            ]

        # Переміщуємося на нову сторінку для редагування
        self.current_page += 1
        self.display_page()

    def canvas_to_image(self):
        """Перетворює canvas в зображення."""
        # Зберігаємо canvas як тимчасовий EPS файл
        temp_eps_file = "temp_canvas.eps"
        self.canvas.postscript(file=temp_eps_file)

        # Відкриваємо EPS файл і конвертуємо його в PNG
        with Image.open(temp_eps_file) as img:
            temp_png_file = "temp_canvas.png"
            img.save(temp_png_file, format="PNG")

        # Відкриваємо PNG файл як зображення
        with Image.open(temp_png_file) as img:
            # Видаляємо тимчасові файли після завершення
            try:
                os.remove(temp_eps_file)
                os.remove(temp_png_file)
            except PermissionError as e:
                print(f"Error removing file: {e}")

            return img
            
    def save_pdf(self):
        """"Збереження PDF-файлу з високою якістю зображення та тонким шрифтом."""
        if self.pages_as_images:
            folder_path = settings.EDITED_PDF_FOLDER
            original_file_name = os.path.basename(self.pdf_files[self.current_file_index - 1])
            new_file_name = f"{os.path.splitext(original_file_name)[0]}_edited.pdf"
            save_path = os.path.join(folder_path, new_file_name)

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            c = canvas.Canvas(save_path, pagesize=letter)

            for index, img in enumerate(self.pages_as_images):
                # Спочатку з'єднуємо текст з зображенням
                img_with_text = self.merge_texts_with_image(index)

                # Масштабування для PDF
                pdf_width, pdf_height = letter
                img_width, img_height = img_with_text.size
                scale = min(pdf_width / img_width, pdf_height / img_height)
                scaled_width = img_width * scale
                scaled_height = img_height * scale
                x_offset = (pdf_width - scaled_width) / 2
                y_offset = (pdf_height - scaled_height) / 2

                # Збереження зображення у тимчасовий файл з максимальною якістю
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                    img_with_text.save(temp_file.name, format="PNG", optimize=True)  # Оптимізоване PNG без втрати якості
                    temp_file_path = temp_file.name

                # Додаємо зображення до PDF
                c.drawImage(temp_file_path, x_offset, y_offset, width=scaled_width, height=scaled_height)
                c.showPage()

            c.save()
            messagebox.showinfo("PDF Saved", f"PDF saved to {save_path}")

    def merge_texts_with_image(self, page_index):
        """Об'єднує всі текстові елементи з зображенням сторінки з білим прямокутником позаду тексту."""
        img = self.pages_as_images[page_index]
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text)

        # Отримуємо масштабування з canvas
        canvas_width = self.canvas.winfo_width()
        scale_ratio = canvas_width / img.width

        if page_index in self.text_items_by_page:
            for text_info in self.text_items_by_page[page_index]:
                # Масштабуємо координати та розмір шрифту
                scaled_x = (text_info["x"]) / scale_ratio
                scaled_y = (text_info["y"]) / scale_ratio
                scaled_font_size = math.ceil(text_info["font_size"] / scale_ratio) + 2

                # Встановлюємо шрифт з масштабованим розміром
                font = ImageFont.truetype(settings.FONT_PATH, scaled_font_size)

                # Отримуємо розмір тексту для визначення меж прямокутника
                text_bbox = draw.textbbox((scaled_x, scaled_y), text_info["text"], font=font)

                # Малюємо білий прямокутник під текстом
                draw.rectangle(text_bbox, fill="blue")

                # Малюємо сам текст поверх прямокутника
                draw.text((scaled_x, scaled_y), text_info["text"], fill="black", font=font, stroke_width=1, stroke_fill="white")

        # Повертаємо зображення з накладеним текстом та білим фоном
        return img_with_text




if __name__ == "__main__":
    root = tk.Tk()
    app = PDFEditorApp(root)
    root.mainloop()
