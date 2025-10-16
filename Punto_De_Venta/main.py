# -*- coding: utf-8 -*-
import sqlite3
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
from functools import partial
import datetime

# --- LIBRERÍAS EXTERNAS (MANEJO DE ERRORES) ---
try:
    from escpos.printer import Usb
except ImportError:
    # Si python-escpos no está instalado, se crea una clase 'falsa' para evitar que el programa se cierre.
    class Usb:
        def __init__(self, *args, **kwargs):
            print("ADVERTENCIA: Librería 'python-escpos' no encontrada. La impresión física está desactivada.")
        def text(self, *args, **kwargs): pass
        def cut(self, *args, **kwargs): pass

try:
    from PIL import Image
except ImportError:
    Image = None  # Permite que el programa corra sin Pillow, pero sin imprimir logos

# --- CONFIGURACIÓN GLOBAL ---
DB_FILE = "pos_database.db"
INFO_NEGOCIO = {
    "nombre": "El Aguachile Mariscos",
    "direccion": "Av. Principal #123, Col. Centro, Veracruz, Ver.",
    "telefono": "229-123-4567",
    "mensaje_final": "¡Gracias por su preferencia!"
}
# IDs de la impresora térmica (Vendor y Product ID)
ID_VENDOR = 0x1ba0
ID_PRODUCT = 0x2204

# --- FUNCIONES AUXILIARES ---
def conectar_db():
    """Establece conexión con la base de datos SQLite."""
    return sqlite3.connect(DB_FILE)

def imprimir_ticket_fisico(texto_del_ticket, con_logo=True):
    """
    Envía el texto y, opcionalmente, la imagen del logo a la impresora.
    Ahora procesa la imagen internamente para máxima compatibilidad.
    """
    p = None
    try:
        p = Usb(ID_VENDOR, ID_PRODUCT, profile="TM-T88V")

        if con_logo:
            if not Image:
                print("ADVERTENCIA: Pillow no está instalado (`pip install Pillow`), no se puede imprimir el logo.")
            else:
                try:
                    logo_path = "logoo.png"
                    img = Image.open(logo_path)
                    img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
                    p.set(align='center')
                    p.image(img)
                    p.text("\n")

                except FileNotFoundError:
                    print(f"ERROR: No se encontró el archivo del logo en la ruta: {logo_path}")
                except Exception as e:
                    print(f"ERROR: No se pudo procesar o imprimir el logo. Detalle: {e}")

        p.set(align='left')
        p.text(texto_del_ticket)
        p.cut()

        print("Ticket enviado a la impresora.")
        return True

    except Exception as e:
        messagebox.showerror("Error de Impresión", f"No se pudo conectar con la impresora física:\n{e}")
        return False

    finally:
        if p:
            p.close()
            print("Conexión con la impresora cerrada.")

def formatear_cuenta_cliente(orden):
    """Genera el texto para una pre-cuenta."""
    texto = f"{INFO_NEGOCIO['nombre']}\n"
    texto += "=" * 30 + f"\nMesa: {orden['mesa']}\nFecha: {datetime.datetime.now().strftime('%d/%m/%Y %I:%M %p')}\n"
    texto += "-" * 30 + "\nCant  Descripción        P.U.   Total\n" + "-" * 30 + "\n"

    for item in orden['ticket'].values():
        total_linea = item['cantidad'] * item['precio']
        nombre_corto = (item['nombre'][:18] + '..') if len(item['nombre']) > 20 else item['nombre']
        texto += f"{item['cantidad']:<4} {nombre_corto:<20} {item['precio']:>6.2f} {total_linea:>7.2f}\n"

    texto += "-" * 30 + f"\nTOTAL: {orden['total']:>23.2f}\n"
    return texto

def formatear_recibo_final(id_venta):
    """Genera el texto para el ticket de venta final desde la base de datos."""
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id_mesa, total, metodo_pago, descuento, paga_con, fecha_hora FROM Ventas WHERE id = ?", (id_venta,))
    venta = cursor.fetchone()
    if not venta: return "ERROR: Venta no encontrada"

    id_mesa, total, metodo_pago, descuento, paga_con, fecha_hora = venta
    cursor.execute("SELECT dv.cantidad, dv.precio_unitario, p.nombre FROM Detalle_Venta dv JOIN Productos p ON dv.id_producto = p.id WHERE dv.id_venta = ?", (id_venta,))
    detalles = cursor.fetchall()
    conn.close()

    fecha_str = datetime.datetime.fromisoformat(fecha_hora).strftime("%d/%m/%Y %I:%M %p")

    texto = f"{INFO_NEGOCIO['nombre']}\n{INFO_NEGOCIO['direccion']}\nTel: {INFO_NEGOCIO['telefono']}\n"
    texto += "=" * 30 + f"\nTicket: {id_venta:05d}   Mesa: {id_mesa}\nFecha: {fecha_str}\n"
    texto += "-" * 30 + "\nCant  Descripción        P.U.   Total\n" + "-" * 30 + "\n"

    subtotal = 0
    for cant, pu, nombre in detalles:
        total_linea = cant * pu
        subtotal += total_linea
        nombre_corto = (nombre[:18] + '..') if len(nombre) > 20 else nombre
        texto += f"{cant:<4} {nombre_corto:<20} {pu:>6.2f} {total_linea:>7.2f}\n"

    texto += "-" * 30 + f"\nSUBTOTAL: {subtotal:>20.2f}\n"
    if descuento > 0:
        texto += f"DESCUENTO: {descuento:>19.2f}\n"
    texto += f"TOTAL: {total:>23.2f}\n"
    texto += "=" * 30 + f"\nForma de Pago: {metodo_pago}\n"

    if metodo_pago == "Efectivo":
        cambio = paga_con - total
        texto += f"Pagado: ${paga_con:.2f}\nCambio: ${cambio:.2f}\n"

    texto += f"\n{INFO_NEGOCIO['mensaje_final']}\n"
    return texto

# --- CLASES DE LA APLICACIÓN ---

class VentanaCambio(tk.Toplevel):
    """Ventana emergente que muestra el cambio a devolver."""
    def __init__(self, parent, cambio):
        super().__init__(parent)
        self.title("Cambio")
        self.geometry("350x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="CAMBIO A DEVOLVER:", font=("Arial", 16)).pack(pady=(20, 10))
        tk.Label(self, text=f"${cambio:.2f}", font=("Arial", 32, "bold"), fg="green").pack(pady=10)

        btn_ok = tk.Button(self, text="Aceptar (Enter)", font=("Arial", 14), command=self.destroy)
        btn_ok.pack(pady=20, ipady=5, ipadx=10)

        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        btn_ok.focus_set()
        self.wait_window()

class VistaMesas(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        frame_titulo = tk.Frame(self)
        frame_titulo.pack(pady=20, fill='x')

        tk.Label(frame_titulo, text="Seleccione una Mesa", font=("Arial", 26, "bold")).pack(side='left', padx=20, expand=True)

        frame_botones_accion = tk.Frame(frame_titulo)
        frame_botones_accion.pack(side='right', padx=20)
        tk.Button(frame_botones_accion, text="⚙️ Gestionar Menú", font=("Arial", 14), command=lambda: controller.mostrar_vista(VistaGestion)).pack(pady=5)
        tk.Button(frame_botones_accion, text="📊 Corte de Caja", font=("Arial", 14), command=lambda: controller.mostrar_vista(VistaReporte)).pack(pady=5)

        contenedor_botones = tk.Frame(self)
        contenedor_botones.pack(pady=20, expand=True)

        self.botones = {}
        for i in range(1, 14):
            btn = tk.Button(contenedor_botones, text=str(i), font=("Arial", 22, "bold"), width=4, height=2, command=partial(controller.seleccionar_mesa, i))
            btn.grid(row=(i - 1) // 5, column=(i - 1) % 5, padx=15, pady=15)
            self.botones[i] = btn

        tk.Button(self, text="Salir de la Aplicación", font=("Arial", 12, "bold"), bg="salmon", command=self.controller.quit).pack(pady=20, side="bottom")
        self.actualizar_colores()

    def actualizar_colores(self):
        for num, estado in self.controller.estado_mesas.items():
            color = "#90EE90" if estado == "libre" else "#F08080"
            self.botones[num].config(bg=color, activebackground=color)

    def cargar_datos(self):
        self.actualizar_colores()

class VistaPedido(tk.Frame):
    # En la clase VistaPedido, reemplaza el método __init__ completo

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.current_products = []

        # --- Columna de Categorías con Scroll ---
        col_categorias_main = tk.Frame(self, width=200, bg='lightgrey')
        col_categorias_main.pack(side="left", fill="y", padx=5)
        col_categorias_main.pack_propagate(False)

        tk.Label(col_categorias_main, text="Categorías", font=("Arial", 18, "bold"), bg='lightgrey').pack(pady=10)

        canvas_cat = tk.Canvas(col_categorias_main, bg='lightgrey', highlightthickness=0)
        scrollbar_cat = ttk.Scrollbar(col_categorias_main, orient="vertical", command=canvas_cat.yview)
        canvas_cat.configure(yscrollcommand=scrollbar_cat.set)

        scrollbar_cat.pack(side="right", fill="y")
        canvas_cat.pack(side="left", fill="both", expand=True)

        self.frame_interior_categorias = tk.Frame(canvas_cat, bg='lightgrey')
        canvas_cat.create_window((0, 0), window=self.frame_interior_categorias, anchor="nw")

        self.frame_interior_categorias.bind("<Configure>", lambda e: canvas_cat.configure(scrollregion=canvas_cat.bbox("all")))

        # --- Columna Derecha (Ticket y Productos) ---
        col_derecha = tk.Frame(self, bg='white')
        col_derecha.pack(side="left", fill="both", expand=True)

        col_derecha.grid_rowconfigure(0, weight=3) # Proporción para el ticket
        col_derecha.grid_rowconfigure(1, weight=7) # Proporción para los productos
        col_derecha.grid_columnconfigure(0, weight=1)

        frame_superior = tk.Frame(col_derecha, bg='lightblue')
        frame_superior.grid(row=0, column=0, sticky="nsew")

        self.frame_productos = tk.Frame(col_derecha, bg='white', padx=10)
        self.frame_productos.grid(row=1, column=0, sticky="nsew")

        # --- Contenido del Ticket ---
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=35, font=('Arial', 11))
        style.map("Custom.Treeview", background=[('selected', '#347083')])

        self.label_titulo_ticket = tk.Label(frame_superior, font=("Arial", 18, "bold"), bg='lightblue')
        self.label_titulo_ticket.pack(pady=5)

        frame_ticket_bottom = tk.Frame(frame_superior, bg='lightblue')
        frame_ticket_bottom.pack(side="bottom", fill="x", pady=5)

        self.label_total = tk.Label(frame_ticket_bottom, font=("Arial", 24, "bold"), bg='lightblue')
        self.label_total.pack()

        frame_acciones = tk.Frame(frame_ticket_bottom, bg='lightblue')
        frame_acciones.pack(pady=5, fill='x')
        tk.Button(frame_acciones, text="< Volver a Mesas", font=("Arial", 12), bg='khaki', command=self.volver_a_mesas).pack(side='left', expand=True, padx=2)
        tk.Button(frame_acciones, text="Imprimir Cuenta", font=("Arial", 12), bg='orange', command=self.imprimir_pre_cuenta).pack(side='left', expand=True, padx=2)
        tk.Button(frame_acciones, text="PAGAR", font=("Arial", 14, "bold"), bg="lightgreen", command=self.ir_a_pagar).pack(side='right', expand=True, padx=2)

        cols = ("Cant", "Producto", "P.U.", "Total")
        self.ticket_tree = ttk.Treeview(frame_superior, columns=cols, show="headings", style="Custom.Treeview")
        self.ticket_tree.tag_configure('oddrow', background='white'); self.ticket_tree.tag_configure('evenrow', background='#E8F0F2')
        for col in cols: self.ticket_tree.heading(col, text=col)
        self.ticket_tree.column("Cant", width=50, anchor="center"); self.ticket_tree.column("Producto", width=190)
        self.ticket_tree.column("P.U.", width=80, anchor="e"); self.ticket_tree.column("Total", width=80, anchor="e")
        self.ticket_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Contenido de Productos ---
        tk.Label(self.frame_productos, text="Productos", font=("Arial", 20, "bold"), bg='white').pack(pady=5)
        canvas_prod = tk.Canvas(self.frame_productos, bg='white', highlightthickness=0)
        canvas_prod.pack(side="left", fill="both", expand=True)
        scrollbar_prod = ttk.Scrollbar(self.frame_productos, orient="vertical", command=canvas_prod.yview)
        scrollbar_prod.pack(side="right", fill="y")
        self.grid_productos = tk.Frame(canvas_prod, bg='white')
        canvas_prod.create_window((0, 0), window=self.grid_productos, anchor="nw")
        canvas_prod.configure(yscrollcommand=scrollbar_prod.set)

        # --- LÓGICA DE SCROLL CORREGIDA ---
        def _on_mousewheel(event):
            # Encuentra el widget que está directamente bajo el cursor del mouse
            target_widget = event.widget.winfo_containing(event.x_root, event.y_root)
            if target_widget is None: return

            # Recorre los "padres" del widget para ver si pertenece a la columna de categorías
            parent = target_widget
            while parent:
                if parent == col_categorias_main:
                    canvas_cat.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return # Si lo encontramos, hacemos scroll y terminamos
                if parent == self: break # Si llegamos al final, paramos
                parent = parent.master

            # Si el cursor no estaba sobre la columna de categorías, hacemos scroll en la de productos
            canvas_prod.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Vinculamos la función a toda la ventana para que siempre esté "escuchando"
        self.bind_all("<MouseWheel>", _on_mousewheel)

        # --- Resto de los Binds ---
        self.grid_productos.bind("<Configure>", lambda e: canvas_prod.configure(scrollregion=canvas_prod.bbox("all")))
        self.ticket_tree.bind("<Double-1>", self.on_double_click_item)
        self.ticket_tree.bind("<plus>", self.aumentar_cantidad); self.ticket_tree.bind("<KP_Add>", self.aumentar_cantidad)
        self.ticket_tree.bind("<minus>", self.disminuir_cantidad); self.ticket_tree.bind("<KP_Subtract>", self.disminuir_cantidad)
        self.frame_productos.bind("<Configure>", self.redraw_product_grid)

    # --- INICIO DE MÉTODOS CORREGIDOS ---
    def on_double_click_item(self, event):
        region = self.ticket_tree.identify("region", event.x, event.y)
        if region != "cell": return
        column_id = self.ticket_tree.identify_column(event.x)
        column_index = int(column_id.replace('#', '')) - 1
        item_id = self.ticket_tree.focus()
        if not item_id or column_index not in [1, 2]: return
        self.create_cell_editor(item_id, column_index)

    def create_cell_editor(self, item_id, column_index):
        column_id_str = f"#{column_index + 1}"
        x, y, width, height = self.ticket_tree.bbox(item_id, column_id_str)
        value = self.ticket_tree.item(item_id, "values")[column_index]
        entry = ttk.Entry(self.ticket_tree, font=('Arial', 11))
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus_force()
        entry.bind("<Return>", lambda e, i=item_id, c=column_index: self.save_edit(e.widget, i, c))
        entry.bind("<FocusOut>", lambda e, i=item_id, c=column_index: self.save_edit(e.widget, i, c))

    def save_edit(self, entry, item_id, column_index):
        new_value = entry.get()
        entry.destroy()
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not orden or item_id not in orden['ticket']: return

        ticket_item = orden['ticket'][item_id]
        if column_index == 1:
            ticket_item['nombre'] = new_value
        elif column_index == 2:
            try:
                new_price = float(new_value)
                if new_price < 0: raise ValueError
                ticket_item['precio'] = new_price
            except ValueError:
                messagebox.showerror("Error", "Precio inválido.")
                return
        self.actualizar_ticket_display()

    def aumentar_cantidad(self, event):
        seleccion = self.ticket_tree.selection()
        if not seleccion: return
        item_id = seleccion[0]
        orden = self.controller.ordenes_abiertas[self.controller.mesa_activa]
        if item_id in orden['ticket']:
            orden['ticket'][item_id]['cantidad'] += 1
            self.actualizar_ticket_display()

    def disminuir_cantidad(self, event):
        seleccion = self.ticket_tree.selection()
        if not seleccion: return
        item_id = seleccion[0]
        orden = self.controller.ordenes_abiertas[self.controller.mesa_activa]
        if item_id in orden['ticket']:
            orden['ticket'][item_id]['cantidad'] -= 1
            if orden['ticket'][item_id]['cantidad'] <= 0:
                del orden['ticket'][item_id]
            self.actualizar_ticket_display()

    def volver_a_mesas(self):
        self.controller.unbind("<space>")
        self.controller.mostrar_vista(VistaMesas)

    def ir_a_pagar(self):
        self.controller.unbind("<space>")
        self.controller.mostrar_vista(VistaPago)

    def imprimir_pre_cuenta(self):
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not orden or not orden['ticket']:
            messagebox.showwarning("Vacío", "No hay productos en el ticket.")
            return
        contenido = formatear_cuenta_cliente(orden)
        imprimir_ticket_fisico(contenido, con_logo=True)

    def cargar_datos(self):
        self.controller.bind("<space>", lambda e: self.ir_a_pagar())
        mesa = self.controller.mesa_activa
        self.label_titulo_ticket.config(text=f"Ticket Mesa {mesa}")
        self.cargar_categorias()
        self.actualizar_ticket_display()
        self.redraw_product_grid()

    def cargar_categorias(self):
        for widget in self.frame_interior_categorias.winfo_children():
            widget.destroy()
        
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM Categorias ORDER BY nombre")

        for id_cat, nombre in cursor.fetchall():
            tk.Button(self.frame_interior_categorias, text=nombre, font=("Arial", 12), wraplength=180, justify="center", command=partial(self.cargar_productos, id_cat)).pack(pady=5, padx=5, fill="x", ipady=8)
        
        conn.close()

    def cargar_productos(self, id_categoria):
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, precio, precio_variable FROM Productos WHERE id_categoria = ? ORDER BY nombre", (id_categoria,))
        self.current_products = cursor.fetchall()
        conn.close()
        self.redraw_product_grid()

    def redraw_product_grid(self, event=None):
        for widget in self.grid_productos.winfo_children():
            widget.destroy()

        container_width = self.frame_productos.winfo_width()
        button_width = 200
        num_cols = max(1, container_width // button_width)

        for i, (id_prod, nombre, precio, es_variable) in enumerate(self.current_products):
            info = {'id': id_prod, 'nombre': nombre, 'precio': precio, 'es_variable': es_variable}
            texto_boton = f"{nombre}\n${precio:.2f}"
            btn = tk.Button(self.grid_productos, text=texto_boton, font=("Arial", 11), width=20, height=5, wraplength=150, command=partial(self.agregar_a_ticket, info))
            btn.grid(row=i // num_cols, column=i % num_cols, padx=5, pady=5)

    def agregar_a_ticket(self, prod):
        ticket = self.controller.ordenes_abiertas[self.controller.mesa_activa]['ticket']
        prod_id = str(prod['id'])
        p_final = prod['precio']

        if prod['es_variable']:
            dialog = simpledialog.askfloat("Precio Variable", f"Introduzca el precio para:\n{prod['nombre']}", parent=self)
            if dialog is None: return
            p_final = dialog
            prod_id = f"var_{prod['id']}_{datetime.datetime.now().timestamp()}"

        if prod_id in ticket:
            ticket[prod_id]['cantidad'] += 1
        else:
            ticket[prod_id] = {'nombre': prod['nombre'], 'precio': p_final, 'cantidad': 1}
        self.actualizar_ticket_display()

    def actualizar_ticket_display(self):
        last_selection = self.ticket_tree.selection()
        for i in self.ticket_tree.get_children():
            self.ticket_tree.delete(i)

        if not self.controller.mesa_activa: return

        orden = self.controller.ordenes_abiertas[self.controller.mesa_activa]
        ticket = orden['ticket']
        total = sum(item['cantidad'] * item['precio'] for item in ticket.values())
        orden['total'] = total

        for i, (p_id, item) in enumerate(ticket.items()):
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            self.ticket_tree.insert("", "end", iid=p_id, values=(item['cantidad'], item['nombre'], f"{item['precio']:.2f}", f"{item['cantidad']*item['precio']:.2f}"), tags=(tag,))

        if last_selection and self.ticket_tree.exists(last_selection[0]):
            self.ticket_tree.selection_set(last_selection[0])
            self.ticket_tree.focus(last_selection[0])

        self.label_total.config(text=f"TOTAL: ${total:.2f}")

    # --- FIN DE MÉTODOS CORREGIDOS ---

class VistaPago(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="grey90")
        self.controller = controller

        self.metodo_pago = tk.StringVar(value="Efectivo")
        self.descuento_var = tk.StringVar(value="0")
        self.paga_con_var = tk.StringVar(value="")
        self.total_final_var = tk.StringVar()
        self.cambio_var = tk.StringVar()

        self.descuento_var.trace_add("write", self.actualizar_calculos)
        self.paga_con_var.trace_add("write", self.actualizar_calculos)

        contenedor = tk.Frame(self, bg="grey90")
        contenedor.pack(expand=True)

        tk.Label(contenedor, text="Finalizar Venta", font=("Arial", 22, "bold"), bg="grey90").grid(row=0, column=0, columnspan=2, pady=20)
        tk.Label(contenedor, text="Total Original:", font=("Arial", 14), bg="grey90").grid(row=1, column=0, sticky="e", padx=10)
        self.label_total_original = tk.Label(contenedor, text="$0.00", font=("Arial", 14, "bold"), bg="grey90")
        self.label_total_original.grid(row=1, column=1, sticky="w")

        frame_pago = tk.Frame(contenedor, bg="grey90")
        frame_pago.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Radiobutton(frame_pago, text="Efectivo", variable=self.metodo_pago, value="Efectivo", command=self.toggle_paga_con, font=("Arial", 12), bg="grey90").pack(side="left", padx=10)
        tk.Radiobutton(frame_pago, text="Tarjeta", variable=self.metodo_pago, value="Tarjeta", command=self.toggle_paga_con, font=("Arial", 12), bg="grey90").pack(side="left", padx=10)

        tk.Label(contenedor, text="Descuento ($):", font=("Arial", 12), bg="grey90").grid(row=3, column=0, sticky="e", padx=10, pady=5)
        self.entry_descuento = tk.Entry(contenedor, textvariable=self.descuento_var, font=("Arial", 12), width=10)
        self.entry_descuento.grid(row=3, column=1, sticky="w")

        tk.Label(contenedor, text="Paga con ($):", font=("Arial", 12), bg="grey90").grid(row=4, column=0, sticky="e", padx=10, pady=5)
        self.entry_paga_con = tk.Entry(contenedor, textvariable=self.paga_con_var, font=("Arial", 12), width=10)
        self.entry_paga_con.grid(row=4, column=1, sticky="w")

        tk.Label(contenedor, text="Total Final:", font=("Arial", 16, "bold"), bg="grey90").grid(row=5, column=0, sticky="e", padx=10, pady=(20, 0))
        tk.Label(contenedor, textvariable=self.total_final_var, font=("Arial", 16, "bold"), fg="blue", bg="grey90").grid(row=5, column=1, sticky="w")

        tk.Label(contenedor, text="Cambio:", font=("Arial", 16, "bold"), bg="grey90").grid(row=6, column=0, sticky="e", padx=10, pady=5)
        tk.Label(contenedor, textvariable=self.cambio_var, font=("Arial", 16, "bold"), fg="green", bg="grey90").grid(row=6, column=1, sticky="w")

        frame_botones = tk.Frame(contenedor, bg="grey90")
        frame_botones.grid(row=7, column=0, columnspan=2, pady=30)
        tk.Button(frame_botones, text="< Volver al Pedido", font=("Arial", 12), bg='khaki', command=lambda: self.controller.mostrar_vista(VistaPedido)).pack(side="left", padx=10)
        tk.Button(frame_botones, text="Finalizar Venta (Enter)", font=("Arial", 14, "bold"), bg="lightgreen", command=self.finalizar_venta).pack(side="left", padx=10, ipady=5)

    def cargar_datos(self):
        self.controller.bind("<Return>", lambda e: self.finalizar_venta())
        self.orden_original = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not self.orden_original: return
        total = self.orden_original.get('total', 0.0)
        self.label_total_original.config(text=f"${total:.2f}")
        self.paga_con_var.set("")
        self.actualizar_calculos()
        self.entry_paga_con.focus_set()
        self.entry_paga_con.icursor(tk.END)

    def toggle_paga_con(self):
        state = "normal" if self.metodo_pago.get() == "Efectivo" else "disabled"
        self.entry_paga_con.config(state=state)
        self.actualizar_calculos()

    def actualizar_calculos(self, *args):
        try:
            total_original = self.orden_original.get('total', 0.0)
            descuento = float(self.descuento_var.get() or 0)
            paga_con = float(self.paga_con_var.get() or 0)
        except (ValueError, TypeError):
            return
        total_final = total_original - descuento
        cambio = paga_con - total_final if self.metodo_pago.get() == "Efectivo" else 0.0
        self.total_final_var.set(f"${total_final:.2f}")
        self.cambio_var.set(f"${cambio:.2f}")

    def finalizar_venta(self):
        paga_con = float(self.paga_con_var.get() or 0)
        total_final = float(self.total_final_var.get().replace('$', ''))

        if self.metodo_pago.get() == "Efectivo" and paga_con < total_final:
            messagebox.showerror("Error", "La cantidad pagada es menor al total.")
            return

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Ventas (id_mesa, total, metodo_pago, descuento, paga_con, fecha_hora) VALUES (?, ?, ?, ?, ?, ?)",
            (self.controller.mesa_activa, total_final, self.metodo_pago.get(), float(self.descuento_var.get() or 0), paga_con, datetime.datetime.now())
        )
        id_venta = cursor.lastrowid

        for prod_id, item in self.orden_original['ticket'].items():
            real_prod_id_str = str(prod_id).split('_')[0]
            if not real_prod_id_str.isdigit():
                real_prod_id_str = str(prod_id).split('_')[1]
            real_prod_id = int(real_prod_id_str)
            cursor.execute(
                "INSERT INTO Detalle_Venta (id_venta, id_producto, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                (id_venta, real_prod_id, item['cantidad'], item['precio'])
            )

        conn.commit()
        conn.close()
        messagebox.showinfo("Éxito", "Venta guardada.")

        cambio = paga_con - total_final
        if self.metodo_pago.get() == "Efectivo" and cambio > 0:
            VentanaCambio(self.controller, cambio)

        contenido_ticket = formatear_recibo_final(id_venta)
        imprimir_ticket_fisico(contenido_ticket, con_logo=True)
        self.controller.finalizar_y_liberar_mesa()

class VistaGestion(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        tk.Button(self, text="< Volver a Mesas", command=lambda: controller.mostrar_vista(VistaMesas)).pack(anchor="ne", padx=10, pady=10)

        notebook = ttk.Notebook(self)
        notebook.pack(pady=10, padx=10, expand=True, fill="both")

        frame_productos = ttk.Frame(notebook)
        notebook.add(frame_productos, text='Productos')
        frame_categorias = ttk.Frame(notebook)
        notebook.add(frame_categorias, text='Categorías')

        self.crear_widgets_categorias(frame_categorias)
        self.crear_widgets_productos(frame_productos)

    def cargar_datos(self):
        self.cargar_categorias()
        self.cargar_productos()
        self.cargar_categorias_en_combobox()

    def crear_widgets_categorias(self, tab):
        tk.Label(tab, text="Gestionar Categorías", font=("Arial", 16)).pack(pady=10)
        main_frame = tk.Frame(tab)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        col_izquierda = tk.Frame(main_frame)
        col_izquierda.pack(side="left", fill="y", padx=10)
        col_derecha = tk.Frame(main_frame)
        col_derecha.pack(side="left", fill="both", expand=True, padx=10)

        frame_entrada = tk.Frame(col_izquierda)
        frame_entrada.pack(pady=10)
        tk.Label(frame_entrada, text="Nueva Categoría:").pack()
        self.entry_categoria = tk.Entry(frame_entrada, width=30)
        self.entry_categoria.pack()
        tk.Button(frame_entrada, text="Añadir", command=self.anadir_categoria).pack(pady=5)

        self.lista_categorias = tk.Listbox(col_izquierda, width=35, height=15, exportselection=False)
        self.lista_categorias.pack(pady=10)
        self.lista_categorias.bind("<<ListboxSelect>>", self.mostrar_productos_de_categoria)

        tk.Button(col_izquierda, text="Eliminar Seleccionada", command=self.eliminar_categoria).pack(pady=5)

        tk.Label(col_derecha, text="Productos en Categoría", font=("Arial", 14)).pack(pady=10)
        self.lista_productos_cat = tk.Listbox(col_derecha, height=18)
        self.lista_productos_cat.pack(fill="both", expand=True)

    def crear_widgets_productos(self, tab):
        tk.Label(tab, text="Gestionar Productos", font=("Arial", 16)).pack(pady=10)
        frame_principal = tk.Frame(tab)
        frame_principal.pack(fill="both", expand=True, padx=10)

        frame_entrada = tk.Frame(frame_principal)
        frame_entrada.pack(pady=10, fill="x", padx=20)

        tk.Label(frame_entrada, text="Nombre:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_prod_nombre = tk.Entry(frame_entrada, width=40)
        self.entry_prod_nombre.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(frame_entrada, text="Precio:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_prod_precio = tk.Entry(frame_entrada, width=20)
        self.entry_prod_precio.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        tk.Label(frame_entrada, text="Categoría:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.combo_prod_categoria = ttk.Combobox(frame_entrada, state="readonly", width=37)
        self.combo_prod_categoria.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.precio_variable_var = tk.BooleanVar()
        tk.Checkbutton(frame_entrada, text="Asignar precio al vender", variable=self.precio_variable_var).grid(row=3, column=1, sticky="w", padx=5, pady=5)

        tk.Button(frame_entrada, text="Añadir Producto", command=self.anadir_producto).grid(row=4, column=0, columnspan=2, pady=10)

        self.tree_productos = ttk.Treeview(frame_principal, columns=("ID", "Nombre", "Precio", "Categoría", "Variable"), show="headings")
        self.tree_productos.heading("ID", text="ID")
        self.tree_productos.heading("Nombre", text="Nombre")
        self.tree_productos.heading("Precio", text="Precio")
        self.tree_productos.heading("Categoría", text="Categoría")
        self.tree_productos.heading("Variable", text="Precio Variable")
        self.tree_productos.column("ID", width=40)
        self.tree_productos.column("Variable", width=100, anchor="center")
        self.tree_productos.pack(pady=10, padx=20, fill="both", expand=True)

        tk.Button(frame_principal, text="Eliminar Seleccionado", command=self.eliminar_producto).pack(pady=5)

    def cargar_categorias(self):
        self.lista_categorias.delete(0, tk.END)
        self.lista_productos_cat.delete(0, tk.END)
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM Categorias ORDER BY nombre")
        for row in cursor.fetchall():
            self.lista_categorias.insert(tk.END, row[0])
        conn.close()

    def cargar_productos(self):
        for i in self.tree_productos.get_children():
            self.tree_productos.delete(i)
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT p.id, p.nombre, p.precio, c.nombre, p.precio_variable FROM Productos p JOIN Categorias c ON p.id_categoria = c.id ORDER BY p.id")
        for row in cursor.fetchall():
            id_prod, nombre, precio, cat, es_var = row
            variable_texto = "Sí" if es_var else "No"
            self.tree_productos.insert("", "end", values=(id_prod, nombre, f"${precio:.2f}", cat, variable_texto))
        conn.close()

    def cargar_categorias_en_combobox(self):
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM Categorias ORDER BY nombre")
        self.combo_prod_categoria['values'] = [row[0] for row in cursor.fetchall()]
        conn.close()

    def anadir_producto(self):
        nombre = self.entry_prod_nombre.get().strip()
        precio_str = self.entry_prod_precio.get().strip()
        categoria = self.combo_prod_categoria.get()
        es_variable = self.precio_variable_var.get()

        if not all([nombre, precio_str, categoria]):
            messagebox.showwarning("Campos incomplecos", "Todos los campos son obligatorios.")
            return

        try:
            precio = float(precio_str)
        except ValueError:
            messagebox.showerror("Error de formato", "El precio debe ser un número.")
            return

        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Categorias WHERE nombre = ?", (categoria,))
            id_categoria = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Productos (nombre, precio, id_categoria, precio_variable) VALUES (?, ?, ?, ?)", (nombre, precio, id_categoria, es_variable))
            conn.commit()
            conn.close()
            self.entry_prod_nombre.delete(0, tk.END)
            self.entry_prod_precio.delete(0, tk.END)
            self.precio_variable_var.set(False)
            self.cargar_productos()
            messagebox.showinfo("Éxito", f"Producto '{nombre}' añadido.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"El producto '{nombre}' ya existe.")

    def eliminar_producto(self):
        if not self.tree_productos.selection():
            messagebox.showwarning("Sin selección", "Selecciona un producto de la lista para eliminar.")
            return
        item_seleccionado = self.tree_productos.item(self.tree_productos.selection()[0])
        prod_id, prod_nombre = item_seleccionado['values'][0], item_seleccionado['values'][1]
        if messagebox.askyesno("Confirmar", f"¿Seguro que quieres eliminar el producto '{prod_nombre}'?"):
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Productos WHERE id = ?", (prod_id,))
            conn.commit()
            conn.close()
            self.cargar_productos()
            messagebox.showinfo("Éxito", "Producto eliminado.")

    def mostrar_productos_de_categoria(self, event=None):
        if not self.lista_categorias.curselection():
            self.lista_productos_cat.delete(0, tk.END)
            return
        nombre_cat = self.lista_categorias.get(self.lista_categorias.curselection())
        self.lista_productos_cat.delete(0, tk.END)
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT p.nombre, p.precio FROM Productos p JOIN Categorias c ON p.id_categoria = c.id WHERE c.nombre = ? ORDER BY p.nombre", (nombre_cat,))
        for n, p in cursor.fetchall():
            self.lista_productos_cat.insert(tk.END, f"{n} - ${p:.2f}")
        conn.close()

    def anadir_categoria(self):
        nombre = self.entry_categoria.get().strip()
        if nombre:
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Categorias (nombre) VALUES (?)", (nombre,))
                conn.commit()
                conn.close()
                self.entry_categoria.delete(0, tk.END)
                self.cargar_datos()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Esa categoría ya existe.")
        else:
            messagebox.showwarning("Inválido", "El nombre no puede estar vacío.")

    def eliminar_categoria(self):
        if not self.lista_categorias.curselection():
            messagebox.showwarning("Sin selección", "Selecciona una categoría para eliminar.")
            return
        nombre_cat = self.lista_categorias.get(self.lista_categorias.curselection())
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{nombre_cat}'? Se eliminarán TODOS los productos de esta categoría."):
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Productos WHERE id_categoria = (SELECT id FROM Categorias WHERE nombre = ?)", (nombre_cat,))
            cursor.execute("DELETE FROM Categorias WHERE nombre = ?", (nombre_cat,))
            conn.commit()
            conn.close()
            self.cargar_datos()

class VistaReporte(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.reporte_seleccionado_texto = ""

        frame_superior = tk.Frame(self)
        frame_superior.pack(pady=10, padx=20, fill='x')
        tk.Label(frame_superior, text="Corte de Caja", font=("Arial", 24, "bold")).pack(side='left', expand=True)
        tk.Button(frame_superior, text="< Volver a Mesas", command=lambda: controller.mostrar_vista(VistaMesas)).pack(side='right')

        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        frame_historial = tk.Frame(paned_window, width=250)
        tk.Label(frame_historial, text="Historial de Cortes", font=("Arial", 14, "bold")).pack(pady=5)
        self.lista_historial = tk.Listbox(frame_historial, font=("Arial", 12), exportselection=False)
        self.lista_historial.pack(fill=tk.BOTH, expand=True, pady=5)
        self.lista_historial.bind("<<ListboxSelect>>", self.mostrar_reporte_historico)
        tk.Button(frame_historial, text="Ver Reporte del Día", command=self.cargar_datos).pack(fill='x', ipady=5)
        paned_window.add(frame_historial, width=250)
        paned_window.paneconfigure(frame_historial, minsize=200)

        frame_detalle = tk.Frame(paned_window)
        self.reporte_widget = tk.Text(frame_detalle, font=("Courier", 12), wrap="word", state="disabled")
        self.reporte_widget.pack(expand=True, fill="both")

        frame_botones = tk.Frame(frame_detalle)
        frame_botones.pack(pady=10, fill='x')
        self.btn_cerrar_caja = tk.Button(frame_botones, text="Cerrar Caja de Hoy", font=("Arial", 14, "bold"), bg="lightblue", command=self.cerrar_caja_hoy)
        self.btn_cerrar_caja.pack(side="left", expand=True, padx=10, ipady=5)
        self.btn_reimprimir = tk.Button(frame_botones, text="Re-imprimir Reporte", font=("Arial", 14), command=self.reimprimir_reporte, state="disabled")
        self.btn_reimprimir.pack(side="right", expand=True, padx=10, ipady=5)
        paned_window.add(frame_detalle)

    def cargar_datos(self):
        self.lista_historial.selection_clear(0, tk.END)
        self.cargar_historial_cortes()
        self.mostrar_reporte_actual()

    def cargar_historial_cortes(self):
        self.lista_historial.delete(0, tk.END)
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT corte_id FROM Ventas WHERE corte_id IS NOT NULL ORDER BY corte_id DESC")
        for row in cursor.fetchall():
            self.lista_historial.insert(tk.END, row[0])
        conn.close()

    def generar_reporte_texto(self, fecha_str):
        conn = conectar_db()
        cursor = conn.cursor()

        if fecha_str == datetime.date.today().strftime('%Y-%m-%d'):
            cursor.execute("""
                SELECT COUNT(*), SUM(total),
                       SUM(CASE WHEN metodo_pago = 'Efectivo' THEN total ELSE 0 END),
                       SUM(CASE WHEN metodo_pago = 'Tarjeta' THEN total ELSE 0 END)
                FROM Ventas WHERE DATE(fecha_hora) = ? AND corte_id IS NULL
            """, (fecha_str,))
            titulo = f"REPORTE DEL DÍA - {datetime.datetime.now().strftime('%d/%m/%Y')} (ACTUAL)"
        else:
            cursor.execute("""
                SELECT COUNT(*), SUM(total),
                       SUM(CASE WHEN metodo_pago = 'Efectivo' THEN total ELSE 0 END),
                       SUM(CASE WHEN metodo_pago = 'Tarjeta' THEN total ELSE 0 END)
                FROM Ventas WHERE corte_id = ?
            """, (fecha_str,))
            titulo = f"REPORTE HISTÓRICO - {datetime.datetime.strptime(fecha_str, '%Y-%m-%d').strftime('%d/%m/%Y')}"

        resultado = cursor.fetchone()
        conn.close()

        num_ventas, total_dia, total_efectivo, total_tarjeta = (resultado or (0, 0, 0, 0))
        num_ventas = num_ventas or 0
        total_dia = total_dia or 0
        total_efectivo = total_efectivo or 0
        total_tarjeta = total_tarjeta or 0

        texto = f"{titulo}\n{'='*45}\n\n"
        texto += f"Total de Ventas (Tickets): {num_ventas}\n\n"
        texto += f"Ingresos en Efectivo: ${total_efectivo:10.2f}\n"
        texto += f"Ingresos con Tarjeta: ${total_tarjeta:10.2f}\n"
        texto += "-" * 45 + "\n"
        texto += f"VENTA TOTAL DEL DÍA:  ${total_dia:10.2f}\n"
        texto += f"EFECTIVO EN CAJA:      ${total_efectivo:10.2f}\n"
        texto += "=" * 45 + "\n"

        return texto

    def mostrar_reporte_actual(self):
        fecha_hoy = datetime.date.today().strftime('%Y-%m-%d')
        self.reporte_seleccionado_texto = self.generar_reporte_texto(fecha_hoy)
        self.actualizar_widget_texto(self.reporte_seleccionado_texto)
        self.btn_cerrar_caja.config(state="normal")
        self.btn_reimprimir.config(state="disabled")

    def mostrar_reporte_historico(self, event=None):
        if not self.lista_historial.curselection():
            return
        fecha_seleccionada = self.lista_historial.get(self.lista_historial.curselection())
        self.reporte_seleccionado_texto = self.generar_reporte_texto(fecha_seleccionada)
        self.actualizar_widget_texto(self.reporte_seleccionado_texto)
        self.btn_cerrar_caja.config(state="disabled")
        self.btn_reimprimir.config(state="normal")

    def actualizar_widget_texto(self, contenido):
        self.reporte_widget.config(state="normal")
        self.reporte_widget.delete("1.0", tk.END)
        self.reporte_widget.insert("1.0", contenido)
        self.reporte_widget.config(state="disabled")

    def cerrar_caja_hoy(self):
        fecha_hoy = datetime.date.today()
        fecha_hoy_str = fecha_hoy.strftime('%Y-%m-%d')
        reporte_a_cerrar = self.generar_reporte_texto(fecha_hoy_str)

        if "VENTA TOTAL DEL DÍA:  $        0.00" in reporte_a_cerrar:
            messagebox.showinfo("Caja Vacía", "No hay ventas para cerrar el día de hoy.")
            return

        confirmar = messagebox.askyesno("Confirmar Cierre",
                                      "Se imprimirá el reporte final y se marcarán las ventas de hoy como 'cerradas'.\n"
                                      "Esta acción no se puede deshacer.\n\n"
                                      "¿Desea continuar?")

        if confirmar:
            imprimir_ticket_fisico(reporte_a_cerrar, con_logo=True)
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE Ventas SET corte_id = ? WHERE DATE(fecha_hora) = ? AND corte_id IS NULL",
                           (fecha_hoy_str, fecha_hoy))
            conn.commit()
            conn.close()
            messagebox.showinfo("Cierre Exitoso", f"Corte del día {fecha_hoy_str} finalizado.")
            self.cargar_datos()

    def reimprimir_reporte(self):
        if self.reporte_seleccionado_texto:
            imprimir_ticket_fisico(self.reporte_seleccionado_texto, con_logo=True)
        else:
            messagebox.showwarning("Sin Selección", "No hay un reporte seleccionado para imprimir.")

# --- CLASE PRINCIPAL Y EJECUCIÓN ---

class App(tk.Tk):
    """Clase principal que controla toda la aplicación y sus vistas."""
    def __init__(self):
        super().__init__()
        self.title("Mariscos POS")
        self.state("zoomed")

        self.estado_mesas = {i: "libre" for i in range(1, 14)}
        self.ordenes_abiertas = {}
        self.mesa_activa = None

        self.bind("<Escape>", self.volver_a_mesas_global)

        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.vistas = {}
        for F in (VistaMesas, VistaPedido, VistaPago, VistaGestion, VistaReporte):
            frame = F(container, self)
            self.vistas[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.vista_actual = None
        self.mostrar_vista(VistaMesas)

    def mostrar_vista(self, clase_vista):
        self.vista_actual = clase_vista
        frame = self.vistas[clase_vista]
        if hasattr(frame, 'cargar_datos'):
            frame.cargar_datos()
        frame.tkraise()

    def volver_a_mesas_global(self, event=None):
        if self.vista_actual != VistaMesas:
            self.unbind("<space>")
            self.unbind("<Return>")
            self.mostrar_vista(VistaMesas)

    def seleccionar_mesa(self, numero_mesa):
        self.mesa_activa = numero_mesa
        if numero_mesa not in self.ordenes_abiertas:
            self.ordenes_abiertas[numero_mesa] = {'mesa': numero_mesa, 'ticket': {}, 'total': 0.0}
            self.estado_mesas[numero_mesa] = "ocupada"
            self.vistas[VistaMesas].actualizar_colores()
        self.mostrar_vista(VistaPedido)

    def finalizar_y_liberar_mesa(self):
        self.unbind("<Return>")
        numero_mesa = self.mesa_activa
        if numero_mesa in self.ordenes_abiertas:
            del self.ordenes_abiertas[numero_mesa]
        self.estado_mesas[numero_mesa] = "libre"
        self.vistas[VistaMesas].actualizar_colores()
        self.mesa_activa = None
        self.mostrar_vista(VistaMesas)

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        messagebox.showerror("Error de Base de Datos", f"No se encontró el archivo '{DB_FILE}'.\nPor favor, ejecuta primero el script 'crear_db.py' para generar la base de datos con el menú.")
    else:
        app = App()
        app.mainloop()