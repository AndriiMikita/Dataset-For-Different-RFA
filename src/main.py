import csv
import json
import math
import tempfile
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter.colorchooser import askcolor
import fitz  # PyMuPDF
from PIL import Image, ImageTk, ImageFont, ImageDraw
import os
import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_PDF_FOLDER = os.path.join(BASE_DIR, "raw")

EDITED_PDF_FOLDER = os.path.join(BASE_DIR, "edited")

CSV_FOLDER = os.path.join(BASE_DIR, "output")

CSV_FILENAME = "document_changes.csv"

CSV_FILE_PATH = os.path.join(CSV_FOLDER, CSV_FILENAME)

FONT_PATH = os.path.join(BASE_DIR, "fonts/Helvetica-Bold.ttf")



class PDFEditorApp:
    def __init__(self, root):
        os.makedirs(RAW_PDF_FOLDER, exist_ok=True)
        os.makedirs(EDITED_PDF_FOLDER, exist_ok=True)
        os.makedirs(CSV_FOLDER, exist_ok=True)
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
        folder_path = RAW_PDF_FOLDER
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

        self.increase_font_button = tk.Button(frame, text="Increase Text Size", command=self.increase_font_size)
        self.increase_font_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.decrease_font_button = tk.Button(frame, text="Decrease Text Size", command=self.decrease_font_size)
        self.decrease_font_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.clear_text_button = tk.Button(frame, text="Clear All Text", command=self.clear_all_text)
        self.clear_text_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.duplicate_page_button = tk.Button(frame, text="Duplicate Pages", command=self.duplicate_pages, state=tk.DISABLED)
        self.duplicate_page_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.edit_text_button = tk.Button(frame, text="Edit Text", command=self.edit_selected_text, state=tk.DISABLED)
        self.edit_text_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.delete_text_button = tk.Button(frame, text="Delete Text", command=self.delete_selected_text, state=tk.DISABLED)
        self.delete_text_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.setup_color_button = tk.Button(frame, text="Setup Color", command=self.enable_pipette_mode, state=tk.NORMAL)
        self.setup_color_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.finish_pdf_button = tk.Button(frame, text="Finish PDF", command=self.open_next_pdf, state=tk.NORMAL)
        self.finish_pdf_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.skip_pdf_button = tk.Button(frame, text="Skip PDF", command=self.skip_pdf, state=tk.NORMAL)
        self.skip_pdf_button.pack(side=tk.LEFT, padx=5, pady=5)

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

    def skip_pdf(self):
        """Пропускає поточний PDF і позначає його як 'skipped' у local_records.csv"""
        if self.current_file_index < len(self.pdf_files):
            # Оновлюємо статус у local_records.csv
            self.local_records(status='skipped')

            # Відкриваємо наступний PDF
            self.open_next_pdf(status='skipped')
        else:
            messagebox.showinfo("End of Files", "No more PDF files to skip.")
            self.root.quit()

    def open_next_pdf(self, status='processed'):
        """Відкриває наступний PDF після останнього записаного і очищає текстові елементи."""
        # Якщо це перший PDF, зчитуємо, який був оброблений останнім
        if self.current_file_index == 0:
            self.current_file_index = self.find_last_processed_pdf()
        elif status != 'skipped':
            self.save_pdf(file_status='processed')

        # Очищаємо всі текстові елементи
        self.clear_text_items()

        if self.current_file_index < len(self.pdf_files):
            file_path = self.pdf_files[self.current_file_index]
            self.current_file_index += 1
            self.open_pdf(file_path)
        else:
            messagebox.showinfo("End of Files", "No more PDF files to display.")
            self.root.quit()

    def clear_text_items(self):
        """Видаляє всі текстові елементи з canvas та очищає список text_items_by_page."""
        for page, text_items in self.text_items_by_page.items():
            for text_info in text_items:
                if text_info["id"] is not None:
                    self.canvas.delete(text_info["id"])
                if text_info.get("rect_id") is not None:
                    self.canvas.delete(text_info["rect_id"])
        self.text_items_by_page.clear()
    
    def find_last_processed_pdf(self):
        """Знаходить останній оброблений PDF в local_records.csv і повертає його індекс"""
        record_file = 'local_records.csv'

        # Перевіряємо, чи існує файл з записами
        if not os.path.exists(record_file):
            return 0  # Якщо файл не існує, починаємо з першого PDF

        last_processed_pdf = None

        # Читаємо файл записів
        with open(record_file, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            if reader:
                for record in reader:
                    if record:
                        pdf_id, status = record
                        if status == 'processed' or status == 'skipped':
                            last_processed_pdf = pdf_id
                            
        if last_processed_pdf:
            # Знаходимо індекс PDF у списку файлів
            for index, file_path in enumerate(self.pdf_files):
                if os.path.basename(file_path) == last_processed_pdf:
                    return index + 1  # Повертаємо наступний індекс після обробленого

        return 0  # Якщо нічого не знайдено, починаємо з першого PDF

    def local_records(self, status):
        """Оновлює або додає записи до local_records.csv для поточного PDF"""
        record_file = os.path.join(BASE_DIR, 'local_records.csv')
        records = []

        # Отримуємо назву поточного PDF файлу
        pdf_id = os.path.basename(self.pdf_files[self.current_file_index - 1])  # Останній відкритий файл

        # Якщо файл існує, читаємо його
        if os.path.exists(record_file):
            with open(record_file, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                records = list(reader)

        # Оновлюємо або додаємо запис для поточного PDF
        pdf_found = False
        for record in records:
            if record[0] == pdf_id:
                record[1] = status  # Оновлюємо статус
                pdf_found = True
                break

        if not pdf_found:
            # Якщо PDF ще не записаний, додаємо новий запис
            records.append([pdf_id, status])

        # Записуємо оновлені дані назад у CSV
        with open(record_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(records)

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
        self.duplicate_page_button.config(state=tk.NORMAL)
        
    def enable_pipette_mode(self):
        """Enables pipette mode to choose background and text colors from the document."""
        messagebox.showinfo("Pipette Mode", "Click on the document to pick a background color.")
        self.canvas.bind("<Button-1>", self.pick_color)  # Бінд для вибору кольору
        self.picking_background = True  # Спочатку вибираємо колір фону


    def pick_color(self, event):
        """Pick a color from the document image at the clicked position."""
        # Отримуємо координати кліку
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Масштабуємо координати для відповідності розміру зображення
        img_x = int(canvas_x / self.scale_ratio)
        img_y = int(canvas_y / self.scale_ratio)

        # Отримуємо зображення сторінки
        img = self.pages_as_images[self.current_page]
        
        # Перевіряємо, що координати в межах зображення
        if 0 <= img_x < img.width and 0 <= img_y < img.height:
            # Отримуємо колір пікселя
            pixel_color = img.getpixel((img_x, img_y))
            hex_color = '#%02x%02x%02x' % pixel_color  # Перетворюємо RGB в HEX

            if self.picking_background:
                # Якщо це колір фону
                self.text_background_color = hex_color
                messagebox.showinfo("Pipette Mode", f"Background color set to {hex_color}. Now pick a text color.")
                self.picking_background = False  # Тепер будемо вибирати колір тексту
            else:
                # Якщо це колір тексту
                self.text_color = hex_color
                messagebox.showinfo("Pipette Mode", f"Text color set to {hex_color}.")
                self.canvas.unbind("<Button-1>")  # Вимикаємо режим піпетки
                self.canvas.bind("<Button-1>", self.on_canvas_click)

    def display_page(self):
        # Очищення старого вмісту canvas
        self.canvas.delete("all")

        img = self.pages_as_images[self.current_page]

        # Масштабування зображення для підходу до canvas
        canvas_width = self.canvas.winfo_width()
        self.scale_ratio = canvas_width / img.width  # Зберігаємо коефіцієнт масштабування
        new_width = int(img.width * self.scale_ratio)
        new_height = int(img.height * self.scale_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        self.img_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self.img_tk, anchor=tk.NW)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

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
        if self.current_text_item and not self.current_text_item.get("readonly", False):
            # Отримуємо реальні координати з урахуванням прокрутки
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)

            # Оновлюємо координати об'єкта текстового елементу
            self.current_text_item["x"] = x
            self.current_text_item["y"] = y

            # Використовуємо попередні кольори для перемальовування
            text_color = self.current_text_item.get("text_color", "black")
            text_background_color = self.current_text_item.get("text_background_color", "white")

            # Видаляємо попередні елементи
            if self.current_text_item.get("id"):
                self.canvas.delete(self.current_text_item["id"])
            if self.current_text_item.get("rect_id"):
                self.canvas.delete(self.current_text_item["rect_id"])

            # Перемальовуємо текст
            text_id = self.canvas.create_text(
                x,
                y,
                text=self.current_text_item["text"],
                font=("ArialNarrow", self.current_text_item["font_size"]),
                anchor="nw",
                fill=text_color,
            )

            # Перемальовуємо фон для тексту
            bbox = self.canvas.bbox(text_id)
            rect_id = self.canvas.create_rectangle(bbox, fill=text_background_color, outline="")

            # Переміщуємо прямокутник під текст
            self.canvas.tag_lower(rect_id, text_id)

            # Оновлюємо ID тексту та фону у self.current_text_item
            self.current_text_item["id"] = text_id
            self.current_text_item["rect_id"] = rect_id

    def increase_font_size(self):
        if self.current_text_item and not self.current_text_item.get("readonly", False):
            self.current_text_item["font_size"] += 2  # Збільшуємо розмір шрифту на 2 пункти
            self.redraw_text_with_new_size()

    def decrease_font_size(self):
        if self.current_text_item and self.current_text_item["font_size"] > 2 and not self.current_text_item.get("readonly", False):
            self.current_text_item["font_size"] -= 2  # Зменшуємо розмір шрифту на 2 пункти
            self.redraw_text_with_new_size()

    def redraw_text_with_new_size(self):
        """Перемальовує текстовий елемент з новим розміром шрифту."""
        if self.current_text_item and not self.current_text_item.get("readonly", False):
            # Видаляємо старий текст і фон
            self.canvas.delete(self.current_text_item["id"])
            self.canvas.delete(self.current_text_item.get("rect_id", None))

            # Перемальовуємо текст з новим розміром шрифту
            self.add_text_with_background(self.current_text_item)

    def clear_all_text(self):
        if self.current_page in self.text_items_by_page and (not self.text_items_by_page.get(self.current_page, []) or not self.text_items_by_page.get(self.current_page, [])[0].get("readonly", False)):
            for text_info in self.text_items_by_page[self.current_page]:
                self.canvas.delete(text_info["id"])
                self.canvas.delete(text_info.get("rect_id", None))
            self.text_items_by_page[self.current_page].clear()

    def on_canvas_right_click(self, event):
        # Отримуємо координати кліка
        click_x = self.canvas.canvasx(event.x)
        click_y = self.canvas.canvasy(event.y)

        # Знаходимо найближчий текстовий елемент вручну
        closest_item = min(
            self.text_items_by_page.get(self.current_page, []),
            key=lambda item: (abs(item["x"] - click_x) + abs(item["y"] - click_y)),
            default=None
        )

        if closest_item:
            self.current_text_item = closest_item
            self.edit_text_button.config(state=tk.NORMAL)  # Активуємо кнопку "Edit Text"
            self.delete_text_button.config(state=tk.NORMAL)
            print(f"Selected text item: {self.current_text_item}")

    def add_text_with_background(self, text_info, redraw=False):
        """Adds text with background on the canvas using the selected colors."""
        # Використовуємо обрані кольори
        text_color = text_info.get("text_color", getattr(self, 'text_color', 'black'))
        text_background_color = text_info.get("text_background_color", getattr(self, 'text_background_color', 'white'))
        
        # Якщо редагуємо (redraw), видаляємо попередні елементи
        if redraw:
            if text_info["id"] is not None:
                self.canvas.delete(text_info["id"])
            if text_info.get("rect_id") is not None:
                self.canvas.delete(text_info["rect_id"])
        
        # Створюємо текстовий елемент
        text_id = self.canvas.create_text(
            text_info["x"],
            text_info["y"],
            text=text_info["text"],
            font=("ArialNarrow", text_info["font_size"]),
            anchor="nw",
            fill=text_color,
        )

        # Створюємо фон для тексту
        bbox = self.canvas.bbox(text_id)
        rect_id = self.canvas.create_rectangle(bbox, fill=text_background_color, outline="")

        # Переміщуємо фон під текст
        self.canvas.tag_lower(rect_id, text_id)

        # Перевіряємо, чи елемент вже існує, щоб уникнути дублювання
        if not redraw:
            existing_text_items = self.text_items_by_page.get(self.current_page, [])
            for item in existing_text_items:
                if (item["x"], item["y"], item["text"]) == (text_info["x"], text_info["y"], text_info["text"]):
                    print("This text item already exists and will not be added again.")
                    return
                
            if "text_color" not in text_info:
                text_info["text_color"] = text_color
            if "text_background_color" not in text_info:
                text_info["text_background_color"] = text_background_color

            # Додаємо новий елемент у список текстових елементів сторінки
            text_info["id"] = text_id
            text_info["rect_id"] = rect_id
            self.text_items_by_page.setdefault(self.current_page, []).append(text_info)

    def add_text_at_position(self, x, y, text=None):
        """Додає текст на обрану позицію, якщо сторінка не є дубльованою."""
        # Перевірка, чи сторінка не є дубльованою
        if not self.text_items_by_page.get(self.current_page, []) or not self.text_items_by_page.get(self.current_page, [])[0].get("readonly", False):
            canvas_x = self.canvas.canvasx(x)
            canvas_y = self.canvas.canvasy(y)
            
            # Відкриваємо діалог для введення тексту, якщо текст не передано як параметр
            if not text:
                text = simpledialog.askstring("Add Text", "Enter the text:")
            if text:
                # Перевірка на наявність існуючих текстових елементів на поточній сторінці
                for existing_text_info in self.text_items_by_page.get(self.current_page, []):
                    if (existing_text_info["x"], existing_text_info["y"], existing_text_info["text"]) == (canvas_x, canvas_y, text):
                        # Текст з такими ж координатами і вмістом вже існує, не додаємо його повторно
                        print("Text already exists at this position.")
                        return

                # Створення нового тексту
                text_info = {
                    "text": text,
                    "x": canvas_x,
                    "y": canvas_y,
                    "font_size": 12,
                    "id": None,
                    "rect_id": None
                }
                self.add_text_with_background(text_info)
                self.current_text_item = text_info
                self.mode = "edit"
            
    def edit_selected_text(self):
        """Редагує вибраний текстовий елемент."""
        if self.current_text_item:
            # Відкриваємо діалог для введення нового тексту
            new_text = simpledialog.askstring("Edit Text", "Enter new text:", initialvalue=self.current_text_item["text"])
            if new_text:
                # Оновлюємо текст
                self.current_text_item["text"] = new_text

                # Видаляємо старий текст з canvas
                if self.current_text_item["id"]:
                    self.canvas.delete(self.current_text_item["id"])

                # Додаємо оновлений текст з фоном
                self.add_text_with_background(self.current_text_item, redraw=True)

                # Оновлюємо область прокрутки
                self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
                
    def delete_selected_text(self):
            """Видаляє вибраний текстовий елемент після підтвердження."""
            if self.current_text_item:
                response = messagebox.askquestion("Delete Text", "Are you sure you want to delete this text?")
                if response == 'yes':
                    # Видаляємо текст з canvas
                    if self.current_text_item["id"]:
                        self.canvas.delete(self.current_text_item["id"])
                        
                    if self.current_text_item["rect_id"]:
                        self.canvas.delete(self.current_text_item["rect_id"])
                        
                    self.text_items_by_page[self.current_page].remove(self.current_text_item)

                    # Очищаємо вибраний текстовий елемент
                    self.current_text_item = None

                    # Оновлюємо область прокрутки
                    self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
                    self.edit_text_button.config(state=tk.DISABLED)
                    self.delete_text_button.config(state=tk.DISABLED)

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
            
    def shift_text(self, start, end):
        temp = {}
        
        for page, data in self.text_items_by_page.items():
            if page >= end:
                temp[page + end - start + 1] = data
            else:
                temp[page] = data
                
        self.text_items_by_page = temp.copy()

    def duplicate_pages(self):
        # Запитуємо у користувача діапазон сторінок
        range_str = simpledialog.askstring("Duplicate Pages", "Enter the range of pages to duplicate (e.g., 1-3):")
        
        if not range_str:
            return  # Якщо нічого не введено, виходимо з функції

        try:
            start, end = map(int, range_str.split('-'))
            if start < 1 or end > len(self.pages_as_images) or start > end:
                messagebox.showerror("Invalid Range", "The range you entered is invalid.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid range in the format 'start-end'.")
            return

        # Індекс початку вставки дубльованих сторінок (після кінця діапазону)
        insert_index = end
        print(*self.text_items_by_page)
        self.shift_text(start, end)
        print(*self.text_items_by_page)

        # Створюємо тимчасовий список для дубльованих сторінок
        duplicated_pages = []
        duplicated_text_items = []

        # Дублюємо кожну сторінку і текст у вказаному діапазоні
        for page_num in range(start - 1, end):
            # Копіюємо сторінку
            new_page_image = self.pages_as_images[page_num].copy()
            duplicated_pages.append(new_page_image)

            # Копіюємо текстові елементи
            if page_num in self.text_items_by_page:
                new_text_items = []
                for item in self.text_items_by_page[page_num]:
                    new_item = item.copy()

                    # Додаємо прапор "readonly", щоб заборонити редагування
                    new_item["readonly"] = True

                    new_text_items.append(new_item)
                
                duplicated_text_items.append(new_text_items)
            else:
                duplicated_text_items.append([])  # Якщо текстових елементів немає, додаємо порожній список

        # Вставляємо дубльовані сторінки і текст одразу після кінця діапазону
        self.pages_as_images[insert_index:insert_index] = duplicated_pages

        # Вставляємо дубльовані текстові елементи
        for i, text_items in enumerate(duplicated_text_items):
            # Перевіряємо, чи існує сторінка для текстових елементів
            if insert_index + i in self.text_items_by_page:
                # Якщо сторінка вже містить текстові елементи, додаємо нові до існуючих
                self.text_items_by_page[insert_index + i].extend(text_items)
            else:
                # Якщо це нова сторінка, просто додаємо текстові елементи
                self.text_items_by_page[insert_index + i] = text_items

        # Переходимо на останню дубльовану сторінку для перегляду
        self.current_page = insert_index + len(duplicated_pages) - 1  # Остання сторінка після дублювання
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
            
    def save_pdf(self, file_status='saved'):
        """Збереження PDF-файлу з високою якістю зображення та тонким шрифтом."""
        self.local_records(file_status)
        if self.pages_as_images:
            folder_path = EDITED_PDF_FOLDER
            original_file_name = os.path.basename(self.pdf_files[self.current_file_index - 1])
            new_file_name = f"{os.path.splitext(original_file_name)[0]}_edited.pdf"
            save_path = os.path.join(folder_path, new_file_name)

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            # Створення або оновлення records.json
            records_path = os.path.join(BASE_DIR, 'records.json')

            # Перевіряємо, чи існує файл, і чи він не порожній
            if os.path.exists(records_path):
                try:
                    with open(records_path, 'r', encoding='utf-8') as json_file:
                        file_data = json.load(json_file)
                except json.JSONDecodeError:
                    file_data = {}
            else:
                file_data = {}

            # Створюємо новий запис для поточного файлу
            file_id = os.path.splitext(original_file_name)[0]
            file_data[file_id] = {
                'original_pages': {},
                'duplicated_pages': {}
            }

              # Множина для відстеження унікальних id

            # Заповнюємо інформацію про сторінки
            for page_index, text_items in self.text_items_by_page.items():
                # Номер сторінки
                seen_ids = set()
                real_page_number = page_index + 1
                page_range_key = f'{real_page_number}'
                print(*text_items)
                # Очищаємо текстові елементи від id, readonly та rect_id і перевіряємо на дублювання id
                cleaned_text_items = []
                for item in text_items:
                    # Перевіряємо, чи id унікальне
                    if item.get('id') not in seen_ids:
                        seen_ids.add(item.get('id'))  # Додаємо id до множини

                        # Очищаємо item від 'id', 'readonly', і 'rect_id'
                        cleaned_item = {k: v for k, v in item.items() if k not in ['id', 'readonly', 'rect_id']}
                        cleaned_text_items.append(cleaned_item)
                        
                print(*text_items)
                print(f"Cleaned: {cleaned_text_items}")

                # Ділимо на оригінальні та дубльовані сторінки
                if any('readonly' not in item for item in text_items):  # Дубльовані сторінки (з readonly)
                    file_data[file_id]['original_pages'][page_range_key] = {
                        'added': cleaned_text_items
                    }
                else:  # Оригінальні сторінки (без readonly)
                    file_data[file_id]['duplicated_pages'][page_range_key] = {
                        'edited': cleaned_text_items
                    }


            # Зберігаємо JSON дані у файл
            with open(records_path, 'w', encoding='utf-8') as json_file:
                json.dump(file_data, json_file, ensure_ascii=False, indent=4)

            # Збереження PDF-файлу
            c = canvas.Canvas(save_path, pagesize=letter)

            for index, img in enumerate(self.pages_as_images):
                img_with_text = self.merge_texts_with_image(index)

                pdf_width, pdf_height = letter
                img_width, img_height = img_with_text.size
                scale = min(pdf_width / img_width, pdf_height / img_height)
                scaled_width = img_width * scale
                scaled_height = img_height * scale
                x_offset = (pdf_width - scaled_width) / 2
                y_offset = (pdf_height - scaled_height) / 2

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                    img_with_text.save(temp_file.name, format="PNG", optimize=True)
                    temp_file_path = temp_file.name

                c.drawImage(temp_file_path, x_offset, y_offset, width=scaled_width, height=scaled_height)
                c.showPage()

            c.save()
            messagebox.showinfo("PDF Saved", f"PDF saved to {save_path}")

    def merge_texts_with_image(self, page_index):
        """Об'єднує всі текстові елементи з зображенням сторінки з обраними кольорами фону та тексту."""
        img = self.pages_as_images[page_index]
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text)

        canvas_width = self.canvas.winfo_width()
        scale_ratio = canvas_width / img.width
        padding = 1

        if page_index in self.text_items_by_page:
            for text_info in self.text_items_by_page[page_index]:
                scaled_x = (text_info["x"]) / scale_ratio
                scaled_y = (text_info["y"]) / scale_ratio + 1
                scaled_font_size = math.ceil(text_info["font_size"] / scale_ratio) + 2

                font = ImageFont.truetype(FONT_PATH, scaled_font_size)

                # Отримуємо розмір тексту для прямокутника
                text_bbox = draw.textbbox((scaled_x, scaled_y), text_info["text"], font=font)
                text_bbox_with_padding = (
                    text_bbox[0] - padding,
                    text_bbox[1] - padding,
                    text_bbox[2] + padding,
                    text_bbox[3] + padding
                )

                # Використовуємо вибрані кольори
                text_color = text_info.get("text_color", getattr(self, 'text_color', 'black'))
                text_background_color = text_info.get("text_background_color", getattr(self, 'text_background_color', 'white'))

                draw.rectangle(text_bbox_with_padding, fill=text_background_color)
                draw.text((scaled_x, scaled_y), text_info["text"], fill=text_color, font=font)

        return img_with_text


if __name__ == "__main__":
    
    root = tk.Tk()
    app = PDFEditorApp(root)
    root.mainloop()
