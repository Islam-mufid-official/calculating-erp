import os
import csv
import psycopg2
import hashlib
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DB_URL = "postgresql://postgres.dnlvokrxpdmmnzjrndjx:Bekuz20031028%40%40@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class DatabaseManager:
    def __init__(self,check_tables: bool = False):
        if check_tables:
            self.init_tables()

    def connect(self):
        return psycopg2.connect(DB_URL)

    def init_tables(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    stock INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    total_spent DOUBLE PRECISION DEFAULT 0.0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY,
                    customer_id INTEGER REFERENCES customers(id),
                    product_id INTEGER REFERENCES products(id),
                    quantity INTEGER NOT NULL,
                    total_price DOUBLE PRECISION NOT NULL,
                    sale_date TEXT NOT NULL
                )
            """)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                ("admin", hash_password("admin123"), "admin")
            )
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                ("kassir", hash_password("kassir123"), "kassir")
            )
            conn.commit()

    def verify_user(self, username: str, password: str):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM users WHERE username = %s AND password_hash = %s",
                (username, hash_password(password))
            )
            row = cursor.fetchone()
            if row is not None:
                (user_role,) = row
                return str(user_role).strip().lower()
            return None

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            self.db = DatabaseManager(check_tables=True)
        except Exception as e:
            messagebox.showerror("Ulanish xatosi", f"Bazaga ulanib bo'lmadi:\n{e}")
            self.destroy()
            return

        self.title("Calculating — Bulutli Tizimga Kirish")
        self.geometry("400x360")
        self.resizable(False, False)

        frame = ctk.CTkFrame(self)
        frame.pack(pady=30, padx=30, fill="both", expand=True)

        ctk.CTkLabel(frame, text="☁️ BULUTLI TIZIM", font=("Arial", 20, "bold")).pack(pady=20)

        self.username_entry = ctk.CTkEntry(frame, placeholder_text="Login (admin / kassir)", width=250, height=40)
        self.username_entry.pack(pady=10)

        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Parol", show="*", width=250, height=40)
        self.password_entry.pack(pady=10)
        self.password_entry.bind("<Return>", lambda event: self.check_login())

        login_btn = ctk.CTkButton(frame, text="Kirish", width=250, height=40, command=self.check_login)
        login_btn.pack(pady=20)

    def check_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        role = self.db.verify_user(username, password)
        if role:
            self.withdraw()
            self.after(150, lambda: self._open_main_app(role, username))
        else:
            messagebox.showerror("Xatolik", "Login yoki parol noto'g'ri!")

    def _open_main_app(self, role: str, username: str):
        app = ERPApp(user_role=role, username=username)
        app.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), self.destroy()))
        app.mainloop()


class ERPApp(ctk.CTk):
    def fast_initial_load(self):
        with self.db.connect() as conn:
            cursor = conn.cursor()

            # 1. Mijozlarni bitta so'rovda yuklash
            cursor.execute("SELECT id, full_name, phone, total_spent FROM customers ORDER BY id")
            customers = cursor.fetchall()
            for row in self.cust_tree.get_children():
                self.cust_tree.delete(row)
            self.customer_map = {}
            for cid, full_name, phone, total_spent in customers:
                self.cust_tree.insert("", "end", values=(cid, full_name, phone, f"{total_spent:,.0f}"))
                self.customer_map[f"{full_name} ({phone})"] = cid

            cust_list = list(self.customer_map.keys()) or ["Avval mijoz qo'shing"]
            self.sale_cust_combo.configure(values=cust_list)
            self.sale_cust_combo.set(next(iter(cust_list)))

            # 2. Mahsulotlarni bitta so'rovda yuklash
            cursor.execute("SELECT id, name, category, price, stock FROM products ORDER BY id")
            products = cursor.fetchall()
            self.product_map = {}
            if self.user_role == "admin":
                for row in self.prod_tree.get_children():
                    self.prod_tree.delete(row)

            for pid, name, category, price, stock in products:
                self.product_map[f"{name} — {price:,.0f} so'm (Zaxira: {stock})"] = (pid, name, price, stock)
                if self.user_role == "admin":
                    self.prod_tree.insert("", "end", values=(pid, name, category, f"{price:,.0f}", stock))

            prod_list = list(self.product_map.keys()) or ["Avval mahsulot qo'shing"]
            self.sale_prod_combo.configure(values=prod_list)
            self.sale_prod_combo.set(next(iter(prod_list)))

            # 3. Admin bo'lsa statistika va xodimlarni ham shu ulanishda olish
            if self.user_role == "admin":
                cursor.execute("SELECT SUM(total_price), COUNT(id) FROM sales")
                revenue, count = cursor.fetchone()
                revenue = revenue or 0.0
                self.analytics_label.configure(
                    text=f"☁️ BULUTLI SAVDO STATISTIKASI\n\nJami amalga oshirilgan savdolar: {count} ta\nUmumiy tushum: {revenue:,.0f} so'm"
                )

                for row in self.user_tree.get_children():
                    self.user_tree.delete(row)
                cursor.execute("SELECT id, username, role FROM users ORDER BY id")
                for uid, uname, urole in cursor.fetchall():
                    self.user_tree.insert("", "end", values=(uid, uname, urole))


    def __init__(self, user_role: str, username: str):
        super().__init__()
        self.db = DatabaseManager()
        self.user_role = user_role
        self.username = username

        self.customer_map = {}
        self.product_map = {}

        self.title(f"Calculating (Cloud) — {username.upper()} ({self.user_role.upper()} PANELI)")
        self.geometry("1000x640")

        self.tabview = ctk.CTkTabview(self, width=960, height=600)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tab_sales = self.tabview.add("🛒 Sotuv Oynasi")
        self.tab_customers = self.tabview.add("👥 Mijozlar")
        self.setup_sales_tab()
        self.setup_customers_tab()

        if self.user_role == "admin":
            self.tab_products = self.tabview.add("📦 Ombor")
            self.tab_analytics = self.tabview.add("📊 Analitika va Hisobot")
            self.tab_users = self.tabview.add("🔑 Xodimlar")
            self.setup_products_tab()
            self.setup_analytics_tab()
            self.setup_users_tab()

        self.fast_initial_load()

    def setup_sales_tab(self):
        sale_frame = ctk.CTkFrame(self.tab_sales)
        sale_frame.pack(pady=30, padx=120, fill="both", expand=True)

        ctk.CTkLabel(sale_frame, text="Yangi Sotuvni Rasmiylashtirish", font=("Arial", 20, "bold")).pack(pady=15)

        ctk.CTkLabel(sale_frame, text="Mijozni tanlang:", font=("Arial", 13)).pack(pady=(5, 2))
        self.sale_cust_combo = ctk.CTkComboBox(sale_frame, values=["Mijoz mavjud emas"], width=360, height=38)
        self.sale_cust_combo.pack(pady=5)

        ctk.CTkLabel(sale_frame, text="Mahsulotni tanlang:", font=("Arial", 13)).pack(pady=(10, 2))
        self.sale_prod_combo = ctk.CTkComboBox(
            sale_frame, values=["Mahsulot mavjud emas"], width=360, height=38,
            command=lambda _: self.calculate_preview()
        )
        self.sale_prod_combo.pack(pady=5)

        ctk.CTkLabel(sale_frame, text="Sotilayotgan miqdor (dona):", font=("Arial", 13)).pack(pady=(10, 2))
        self.sale_qty = ctk.CTkEntry(sale_frame, placeholder_text="Masalan: 2", width=360, height=38)
        self.sale_qty.pack(pady=5)
        self.sale_qty.bind("<KeyRelease>", lambda _: self.calculate_preview())

        self.preview_label = ctk.CTkLabel(sale_frame, text="Jami summa: 0 so'm", font=("Arial", 16, "bold"), text_color="#4ADE80")
        self.preview_label.pack(pady=15)

        sell_btn = ctk.CTkButton(
            sale_frame, text="✅ Sotuvni Tasdiqlash va Chek Chiqarish", width=360, height=45,
            fg_color="green", hover_color="darkgreen", command=self.process_sale
        )
        sell_btn.pack(pady=10)

        sync_btn = ctk.CTkButton(
            sale_frame, text="🔄 Bazadan ma'lumotlarni yangilash", width=360, height=35,
            fg_color="#3B82F6", command=self.refresh_dropdowns
        )
        sync_btn.pack(pady=5)

    def refresh_dropdowns(self):
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, full_name, phone FROM customers ORDER BY id")
            customers = cursor.fetchall()
            self.customer_map = {f"{name} ({phone})": cid for cid, name, phone in customers}
            cust_list = list(self.customer_map.keys()) or ["Avval mijoz qo'shing"]
            self.sale_cust_combo.configure(values=cust_list)
            self.sale_cust_combo.set(next(iter(cust_list)))

            cursor.execute("SELECT id, name, price, stock FROM products ORDER BY id")
            products = cursor.fetchall()
            self.product_map = {f"{name} — {price:,.0f} so'm (Zaxira: {stock})": (pid, name, price, stock) for pid, name, price, stock in products}
            prod_list = list(self.product_map.keys()) or ["Avval mahsulot qo'shing"]
            self.sale_prod_combo.configure(values=prod_list)
            self.sale_prod_combo.set(next(iter(prod_list)))

    def calculate_preview(self):
        prod_key = self.sale_prod_combo.get()
        if prod_key in self.product_map:
            _, _, price, _ = self.product_map[prod_key]
            try:
                qty = int(self.sale_qty.get())
                if qty > 0:
                    self.preview_label.configure(text=f"Jami summa: {price * qty:,.0f} so'm")
                    return
            except ValueError:
                pass
        self.preview_label.configure(text="Jami summa: 0 so'm")

    def generate_receipt(self, sale_id: int, cust_name: str, prod_name: str, qty: int, price: float, total: float, date_str: str):
        os.makedirs("cheklar", exist_ok=True)
        receipt_text = (
            "====================================\n"
            "         CALCULATING SAVDO          \n"
            "====================================\n"
            f"Chek №: #{sale_id}\n"
            f"Sana:   {date_str}\n"
            f"Kassir: {self.username}\n"
            f"Mijoz:  {cust_name}\n"
            "------------------------------------\n"
            f"Mahsulot: {prod_name}\n"
            f"Narxi:    {price:,.0f} so'm\n"
            f"Soni:     {qty} dona\n"
            "------------------------------------\n"
            f"JAMI TO'LOV: {total:,.0f} so'm\n"
            "====================================\n"
            "     Xaridingiz uchun rahmat!       \n"
        )
        file_path = os.path.join("cheklar", f"chek_{sale_id}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(receipt_text)
        return receipt_text, file_path

    def process_sale(self):
        cust_key = self.sale_cust_combo.get()
        prod_key = self.sale_prod_combo.get()

        if cust_key not in self.customer_map or prod_key not in self.product_map:
            messagebox.showerror("Xato", "Iltimos, ro'yxatdan to'g'ri mijoz va mahsulotni tanlang!")
            return

        try:
            qty = int(self.sale_qty.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Xato", "Miqdorni musbat butun sonda kiriting!")
            return

        c_id = self.customer_map[cust_key]
        p_id, prod_name, price, _ = self.product_map[prod_key]
        total_price = price * qty
        sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stock FROM products WHERE id = %s", (p_id,))
            (current_stock,) = cursor.fetchone()
            if current_stock < qty:
                messagebox.showwarning("Zaxira yetarli emas", f"Omborda faqat {current_stock} dona '{prod_name}' qolgan.")
                self.refresh_dropdowns()
                return

            cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, p_id))
            cursor.execute("UPDATE customers SET total_spent = total_spent + %s WHERE id = %s", (total_price, c_id))
            cursor.execute(
                "INSERT INTO sales (customer_id, product_id, quantity, total_price, sale_date) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (c_id, p_id, qty, total_price, sale_date)
            )
            (sale_id,) = cursor.fetchone()
            conn.commit()

        receipt_text, file_path = self.generate_receipt(sale_id, cust_key, prod_name, qty, price, total_price, sale_date)

        self.sale_qty.delete(0, "end")
        self.preview_label.configure(text="Jami summa: 0 so'm")
        self.refresh_dropdowns()
        self.load_customers()
        if self.user_role == "admin":
            self.load_products()
            self.update_analytics()

        messagebox.showinfo("Chek tayyor!", f"Chek '{file_path}' fayliga saqlandi.\n\n{receipt_text}")

    def setup_customers_tab(self):
        form_frame = ctk.CTkFrame(self.tab_customers)
        form_frame.pack(pady=10, padx=10, fill="x")

        self.cust_name = ctk.CTkEntry(form_frame, placeholder_text="Mijoz F.I.Sh.", width=280)
        self.cust_name.pack(side="left", padx=10, pady=10)

        self.cust_phone = ctk.CTkEntry(form_frame, placeholder_text="Telefon (+998...)", width=220)
        self.cust_phone.pack(side="left", padx=10, pady=10)

        add_cust_btn = ctk.CTkButton(form_frame, text="➕ Mijoz qo'shish", command=self.add_customer)
        add_cust_btn.pack(side="left", padx=10, pady=10)

        columns = ("id", "full_name", "phone", "total_spent")
        self.cust_tree = ttk.Treeview(self.tab_customers, columns=columns, show="headings", height=15)
        self.cust_tree.heading("id", text="ID")
        self.cust_tree.heading("full_name", text="F.I.Sh.")
        self.cust_tree.heading("phone", text="Telefon raqami")
        self.cust_tree.heading("total_spent", text="Jami xaridi (so'm)")

        self.cust_tree.column("id", width=50, anchor="center")
        self.cust_tree.column("full_name", width=300)
        self.cust_tree.column("phone", width=200)
        self.cust_tree.column("total_spent", width=180, anchor="e")
        self.cust_tree.pack(pady=10, padx=10, fill="both", expand=True)

        self.load_customers()

    def add_customer(self):
        name = self.cust_name.get().strip()
        phone = self.cust_phone.get().strip()
        if not name or not phone:
            messagebox.showwarning("Diqqat", "Ism va telefon raqamni kiriting!")
            return

        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO customers (full_name, phone) VALUES (%s, %s)", (name, phone))
                conn.commit()
            self.cust_name.delete(0, "end")
            self.cust_phone.delete(0, "end")
            self.load_customers()
            self.refresh_dropdowns()
            messagebox.showinfo("OK", f"Mijoz '{name}' qo'shildi!")
        except psycopg2.IntegrityError:
            messagebox.showerror("Xato", "Bu telefon raqam allaqachon ro'yxatdan o'tgan!")

    def load_customers(self):
        for row in self.cust_tree.get_children():
            self.cust_tree.delete(row)

        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, full_name, phone, total_spent FROM customers ORDER BY id")
            for cid, full_name, phone, total_spent in cursor.fetchall():
                self.cust_tree.insert("", "end", values=(cid, full_name, phone, f"{total_spent:,.0f}"))

    def setup_products_tab(self):
        form_frame = ctk.CTkFrame(self.tab_products)
        form_frame.pack(pady=10, padx=10, fill="x")

        self.prod_name = ctk.CTkEntry(form_frame, placeholder_text="Mahsulot nomi", width=220)
        self.prod_name.pack(side="left", padx=5, pady=10)

        self.prod_cat = ctk.CTkEntry(form_frame, placeholder_text="Kategoriya", width=160)
        self.prod_cat.pack(side="left", padx=5, pady=10)

        self.prod_price = ctk.CTkEntry(form_frame, placeholder_text="Narxi (so'm)", width=140)
        self.prod_price.pack(side="left", padx=5, pady=10)

        self.prod_stock = ctk.CTkEntry(form_frame, placeholder_text="Soni", width=100)
        self.prod_stock.pack(side="left", padx=5, pady=10)

        add_btn = ctk.CTkButton(form_frame, text="➕ Qo'shish", command=self.add_product)
        add_btn.pack(side="left", padx=10, pady=10)

        columns = ("id", "name", "category", "price", "stock")
        self.prod_tree = ttk.Treeview(self.tab_products, columns=columns, show="headings", height=15)
        self.prod_tree.heading("id", text="ID")
        self.prod_tree.heading("name", text="Mahsulot nomi")
        self.prod_tree.heading("category", text="Kategoriya")
        self.prod_tree.heading("price", text="Narxi (so'm)")
        self.prod_tree.heading("stock", text="Zaxira (dona)")

        self.prod_tree.column("id", width=50, anchor="center")
        self.prod_tree.column("name", width=260)
        self.prod_tree.column("category", width=180)
        self.prod_tree.column("price", width=150, anchor="e")
        self.prod_tree.column("stock", width=120, anchor="center")
        self.prod_tree.pack(pady=10, padx=10, fill="both", expand=True)

        self.load_products()

    def add_product(self):
        name = self.prod_name.get().strip()
        cat = self.prod_cat.get().strip()
        try:
            price = float(self.prod_price.get())
            stock = int(self.prod_stock.get())
            if not name or not cat:
                messagebox.showwarning("Diqqat", "Barcha maydonlarni to'ldiring!")
                return

            with self.db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO products (name, category, price, stock) VALUES (%s, %s, %s, %s)",
                    (name, cat, price, stock)
                )
                conn.commit()

            self.prod_name.delete(0, "end")
            self.prod_cat.delete(0, "end")
            self.prod_price.delete(0, "end")
            self.prod_stock.delete(0, "end")
            self.load_products()
            self.refresh_dropdowns()
            messagebox.showinfo("Muvaffaqiyatli", f"'{name}' omborga qo'shildi!")
        except psycopg2.IntegrityError:
            messagebox.showerror("Xato", "Bunday nomli mahsulot bazada mavjud!")
        except ValueError:
            messagebox.showerror("Xato", "Narx va soni raqamlarda kiritilishi shart!")

    def load_products(self):
        for row in self.prod_tree.get_children():
            self.prod_tree.delete(row)

        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, category, price, stock FROM products ORDER BY id")
            for pid, name, category, price, stock in cursor.fetchall():
                self.prod_tree.insert("", "end", values=(pid, name, category, f"{price:,.0f}", stock))

    def setup_analytics_tab(self):
        self.analytics_label = ctk.CTkLabel(self.tab_analytics, text="", font=("Arial", 18))
        self.analytics_label.pack(pady=40)

        btn_frame = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        btn_frame.pack(pady=10)

        refresh_btn = ctk.CTkButton(btn_frame, text="🔄 Statistikani yangilash", width=220, height=40, command=self.update_analytics)
        refresh_btn.pack(side="left", padx=10)

        export_btn = ctk.CTkButton(
            btn_frame, text="📥 Excel (CSV) hisobot yuklash", width=240, height=40,
            fg_color="#2563EB", command=self.export_csv_report
        )
        export_btn.pack(side="left", padx=10)

        self.update_analytics()

    def update_analytics(self):
        self.load_products()
        self.load_customers()
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_price), COUNT(id) FROM sales")
            revenue, count = cursor.fetchone()
            revenue = revenue or 0.0

        text = f"☁️ BULUTLI SAVDO STATISTIKASI\n\nJami amalga oshirilgan savdolar: {count} ta\nUmumiy tushum: {revenue:,.0f} so'm"
        self.analytics_label.configure(text=text)

    def export_csv_report(self):
        filename = f"savdo_hisoboti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, c.full_name, p.name, s.quantity, s.total_price, s.sale_date
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                JOIN products p ON s.product_id = p.id
                ORDER BY s.id
            """)
            rows = cursor.fetchall()

        with open(filename, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Sotuv ID", "Mijoz", "Mahsulot", "Soni", "Jami Summa (so'm)", "Sana"])
            writer.writerows(rows)

        messagebox.showinfo("Hisobot tayyor", f"Barcha savdolar '{filename}' fayliga saqlandi!")

    def setup_users_tab(self):
        form_frame = ctk.CTkFrame(self.tab_users)
        form_frame.pack(pady=10, padx=10, fill="x")

        self.new_user_login = ctk.CTkEntry(form_frame, placeholder_text="Yangi login", width=180)
        self.new_user_login.pack(side="left", padx=8, pady=10)

        self.new_user_pass = ctk.CTkEntry(form_frame, placeholder_text="Yangi parol", width=180)
        self.new_user_pass.pack(side="left", padx=8, pady=10)

        self.new_user_role = ctk.CTkComboBox(form_frame, values=["kassir", "admin"], width=140)
        self.new_user_role.pack(side="left", padx=8, pady=10)

        add_user_btn = ctk.CTkButton(form_frame, text="➕ Xodim qo'shish", command=self.add_user)
        add_user_btn.pack(side="left", padx=8, pady=10)

        del_user_btn = ctk.CTkButton(form_frame, text="🗑 Tanlanganni o'chirish", fg_color="#DC2626", hover_color="#991B1B", command=self.delete_user)
        del_user_btn.pack(side="left", padx=8, pady=10)

        columns = ("id", "username", "role")
        self.user_tree = ttk.Treeview(self.tab_users, columns=columns, show="headings", height=12)
        self.user_tree.heading("id", text="ID")
        self.user_tree.heading("username", text="Login")
        self.user_tree.heading("role", text="Lavozimi (Rol)")

        self.user_tree.column("id", width=60, anchor="center")
        self.user_tree.column("username", width=250)
        self.user_tree.column("role", width=180, anchor="center")
        self.user_tree.pack(pady=10, padx=10, fill="both", expand=True)

        self.load_users()

    def add_user(self):
        uname = self.new_user_login.get().strip()
        upass = self.new_user_pass.get().strip()
        urole = self.new_user_role.get()

        if not uname or not upass:
            messagebox.showwarning("Diqqat", "Login va parolni kiriting!")
            return

        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (uname, hash_password(upass), urole)
                )
                conn.commit()
            self.new_user_login.delete(0, "end")
            self.new_user_pass.delete(0, "end")
            self.load_users()
            messagebox.showinfo("OK", f"Yangi xodim '{uname}' ({urole}) qo'shildi!")
        except psycopg2.IntegrityError:
            messagebox.showerror("Xato", "Bunday login bazada mavjud!")

    def delete_user(self):
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showwarning("Diqqat", "O'chirish uchun jadvaldan xodimni tanlang!")
            return

        first_item = next(iter(selected))
        user_id, uname, _ = self.user_tree.item(first_item).get("values")

        if uname == self.username:
            messagebox.showerror("Xato", "O'zingizning faol akkauntingizni o'chira olmaysiz!")
            return

        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

        self.load_users()
        messagebox.showinfo("O'chirildi", f"Xodim '{uname}' tizimdan o'chirildi.")

    def load_users(self):
        for row in self.user_tree.get_children():
            self.user_tree.delete(row)

        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role FROM users ORDER BY id")
            for uid, uname, urole in cursor.fetchall():
                self.user_tree.insert("", "end", values=(uid, uname, urole))


if __name__ == "__main__":
    login_app = LoginWindow()
    login_app.mainloop()
