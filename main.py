# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
from functools import partial
import datetime
import configparser

def resource_path(relative_path):
    """ Obtiene la ruta absoluta a un recurso, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_persistent_path(filename):
    """ Obtiene la ruta a un archivo en una carpeta de datos persistente. """
    # Para Windows, usamos la carpeta AppData/Roaming
    app_data_path = os.path.join(os.getenv('APPDATA'), 'PuntoDeVentaAguachile')

    # Nos aseguramos de que la carpeta exista
    os.makedirs(app_data_path, exist_ok=True)

    return os.path.join(app_data_path, filename)

# --- LIBRERÍAS EXTERNAS (MANEJO DE ERRORES) ---
try:
    from escpos.printer import Usb
except ImportError:
    class Usb:
        def __init__(self, *args, **kwargs): print("ADVERTENCIA: Librería 'python-escpos' no encontrada.")
        def text(self, *args, **kwargs): pass
        def cut(self, *args, **kwargs): pass
        def image(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def close(self, *args, **kwargs): pass

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None
    print("ADVERTENCIA: Librería 'Pillow' no encontrada. Las imágenes no se cargarán.")


# --- SECCIÓN DE TEMA Y ESTILO ---
class Theme:
    COLOR_FONDO_PRINCIPAL = "#F0F0F0"
    COLOR_FONDO_SECUNDARIO = "#FFFFFF"
    COLOR_FONDO_CABECERA = "#2C3E50"
    COLOR_TEXTO_CABECERA = "#ECF0F1"
    COLOR_TEXTO_PRINCIPAL = "#34495E"
    COLOR_TEXTO_TOTAL = "#2980B9"
    COLOR_MESA_LIBRE = "#2ECC71"
    COLOR_MESA_OCUPADA = "#E74C3C"
    COLOR_ACCENT_SUCCESS = "#27AE60"
    COLOR_ACCENT_WARNING = "#F39C12"
    COLOR_ACCENT_PRIMARY = "#3498DB"
    COLOR_ACCENT_BACK = "#F1C40F"
    
    FONT_TITULO_GRANDE = ("Helvetica", 28, "bold")
    FONT_TITULO = ("Helvetica", 20, "bold")
    FONT_SUBTITULO = ("Helvetica", 16, "bold")
    FONT_BOTON = ("Helvetica", 12, "bold")
    FONT_NORMAL = ("Helvetica", 11)
    FONT_TOTAL = ("Helvetica", 26, "bold")
    FONT_TICKET = ('Consolas', 11)

config = configparser.ConfigParser()
CONFIG_FILE_PATH = resource_path('config.ini') # El config SÍ va dentro del .exe
config.read(CONFIG_FILE_PATH)

# --- CORRECCIÓN CRÍTICA PARA LA BASE DE DATOS ---
# Determina si el programa se está ejecutando como un script o como un .exe compilado
if getattr(sys, 'frozen', False):
    # Si es un .exe, la base de datos estará junto al ejecutable
    application_path = os.path.dirname(sys.executable)
else:
    # Si es un script, estará en el directorio actual
    application_path = os.path.dirname(os.path.abspath(__file__))

# La ruta de la base de datos ahora es siempre externa al .exe
DB_FILE = os.path.join(application_path, config.get('Database', 'file', fallback='pos_database.db'))

# Los otros assets (imágenes, etc.) sí se buscan dentro del .exe
ASSETS_PATH = resource_path("assets")
# --- FIN DE LA CORRECCIÓN ---

ASSETS_PATH = resource_path("assets")

INFO_NEGOCIO = {
    "nombre": config.get('Business', 'name', fallback='Mi Negocio'),
    "direccion": config.get('Business', 'address', fallback='Dirección no configurada'),
    "telefono": config.get('Business', 'phone', fallback='Teléfono no configurado'),
    "mensaje_final": config.get('Business', 'footer_message', fallback='¡Gracias por su visita!')
}

try:
    ID_VENDOR = int(config.get('Printer', 'vendor_id', fallback='0x0'), 16)
    ID_PRODUCT = int(config.get('Printer', 'product_id', fallback='0x0'), 16)
except (ValueError, configparser.NoSectionError, configparser.NoOptionError):
    ID_VENDOR = 0x0
    ID_PRODUCT = 0x0

# --- FUNCIONES AUXILIARES ---
def conectar_db():
    return sqlite3.connect(DB_FILE)

def imprimir_ticket_fisico(texto_del_ticket, con_logo=True):
    p = None
    try:
        if ID_VENDOR == 0x0 or ID_PRODUCT == 0x0:
            raise ValueError("ID de Vendedor o Producto no configurados en config.ini")
        p = Usb(ID_VENDOR, ID_PRODUCT, profile="TM-T88V")
        if con_logo:
            if not Image:
                print("ADVERTENCIA: Pillow no está instalado, no se puede imprimir el logo.")
            else:
                try:
                    logo_path = resource_path(config.get('Files', 'logo', fallback='logoo.png'))
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
        mensaje = f"La operación se completó, pero no se pudo imprimir el ticket.\n\nVerifique la conexión de la impresora y la configuración en 'config.ini'.\n\nError: {e}"
        messagebox.showwarning("Advertencia de Impresión", mensaje)
        print(f"Error de impresión manejado: {e}")
        return False
    finally:
        if p:
            p.close()
            print("Conexión con la impresora cerrada.")

def formatear_cuenta_cliente(orden):
    texto = f"{INFO_NEGOCIO['nombre']}\n"
    identificador_mesa = f"Mesa: {orden['mesa']}" if str(orden['mesa']).isdigit() else orden['mesa']
    texto += "=" * 30 + f"\n{identificador_mesa}\nFecha: {datetime.datetime.now().strftime('%d/%m/%Y %I:%M %p')}\n"
    texto += "-" * 30 + "\nCant  Descripción        P.U.   Total\n" + "-" * 30 + "\n"
    for item in orden['ticket'].values():
        total_linea = item['cantidad'] * item['precio']
        nombre_corto = (item['nombre'][:18] + '..') if len(item['nombre']) > 20 else item['nombre']
        texto += f"{item['cantidad']:<4} {nombre_corto:<20} {item['precio']:>6.2f} {total_linea:>7.2f}\n"
    texto += "-" * 30 + f"\nTOTAL: {orden['total']:>23.2f}\n"
    return texto

def formatear_recibo_final(id_venta):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_mesa, total, metodo_pago, descuento, paga_con, fecha_hora FROM Ventas WHERE id = ?", (id_venta,))
    venta = cursor.fetchone()
    if not venta: return "ERROR: Venta no encontrada"
    id_mesa_o_texto, total, metodo_pago, descuento, paga_con, fecha_hora = venta
    cursor.execute("SELECT dv.cantidad, dv.precio_unitario, p.nombre FROM Detalle_Venta dv JOIN Productos p ON dv.id_producto = p.id WHERE dv.id_venta = ?", (id_venta,))
    detalles = cursor.fetchall()
    conn.close()
    fecha_str = datetime.datetime.fromisoformat(fecha_hora).strftime("%d/%m/%Y %I:%M %p")
    identificador_mesa = f"Mesa: {id_mesa_o_texto}" if str(id_mesa_o_texto).isdigit() else id_mesa_o_texto
    texto = f"{INFO_NEGOCIO['nombre']}\n{INFO_NEGOCIO['direccion']}\nTel: {INFO_NEGOCIO['telefono']}\n"
    texto += "=" * 30 + f"\nTicket: {id_venta:05d}   {identificador_mesa}\nFecha: {fecha_str}\n"
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
    def __init__(self, parent, cambio):
        super().__init__(parent)
        self.title("Cambio")
        self.config(bg=Theme.COLOR_FONDO_SECUNDARIO)
        self.geometry("350x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        tk.Label(self, text="CAMBIO A DEVOLVER:", font=("Arial", 16), bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(pady=(20, 10))
        tk.Label(self, text=f"${cambio:.2f}", font=("Arial", 32, "bold"), fg=Theme.COLOR_ACCENT_SUCCESS, bg=Theme.COLOR_FONDO_SECUNDARIO).pack(pady=10)
        btn_ok = tk.Button(self, text="Aceptar (Enter)", font=("Arial", 14), command=self.destroy, bg=Theme.COLOR_ACCENT_PRIMARY, fg=Theme.COLOR_TEXTO_CABECERA, relief="flat")
        btn_ok.pack(pady=20, ipady=5, ipadx=10)
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        btn_ok.focus_set()
        self.wait_window()

class TransferDialog(simpledialog.Dialog):
    def __init__(self, parent, mesas_libres, mesa_actual):
        self.mesas_libres = mesas_libres
        self.mesa_actual = mesa_actual
        self.result = None
        super().__init__(parent, title="Transferir Mesa")

    def body(self, master):
        self.resizable(False, False)
        tk.Label(master, text=f"Transferir orden de '{self.mesa_actual}' a:", font=Theme.FONT_NORMAL).pack(pady=10, padx=10)
        self.combo_mesas = ttk.Combobox(master, values=self.mesas_libres, state="readonly", font=Theme.FONT_NORMAL)
        self.combo_mesas.pack(pady=5, padx=10, fill='x')
        if self.mesas_libres:
            self.combo_mesas.current(0)
        return self.combo_mesas

    def apply(self):
        self.result = self.combo_mesas.get()

class ReporteProductosDialog(tk.Toplevel):
    def __init__(self, parent, titulo, contenido):
        super().__init__(parent)
        self.title(titulo)
        self.geometry("500x600")
        self.config(bg=Theme.COLOR_FONDO_SECUNDARIO)
        self.transient(parent)
        self.grab_set()

        text_widget = tk.Text(self, font=Theme.FONT_TICKET, wrap="word", state="normal", bg=Theme.COLOR_FONDO_SECUNDARIO, relief="flat", bd=0)
        text_widget.pack(expand=True, fill="both", padx=15, pady=15)
        text_widget.insert("1.0", contenido)
        text_widget.config(state="disabled")

        frame_botones = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL, pady=10)
        frame_botones.pack(pady=10, fill='x')
        tk.Button(frame_botones, text="Cerrar", font=Theme.FONT_BOTON, relief="flat", command=self.destroy).pack(side='right', padx=10, ipady=5)
        tk.Button(frame_botones, text="Imprimir Reporte", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_PRIMARY, fg="white", relief="flat", command=lambda: imprimir_ticket_fisico(contenido, con_logo=True)).pack(side='right', padx=10, ipady=5)
        
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")


class VistaMesas(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.COLOR_FONDO_PRINCIPAL)
        self.controller = controller
        
        self.img_mesa_libre = self.cargar_imagen_mesa("table_free.png")
        self.img_mesa_ocupada = self.cargar_imagen_mesa("table_occupied.png")

        frame_titulo = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
        frame_titulo.pack(pady=20, fill='x')
        tk.Label(frame_titulo, text="Seleccione una Mesa", font=Theme.FONT_TITULO_GRANDE, bg=Theme.COLOR_FONDO_PRINCIPAL, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(side='left', padx=20, expand=True)

        frame_botones_accion = tk.Frame(frame_titulo, bg=Theme.COLOR_FONDO_PRINCIPAL)
        frame_botones_accion.pack(side='right', padx=20)
        tk.Button(frame_botones_accion, text="⚙️ Gestionar Menú", font=Theme.FONT_BOTON, command=lambda: controller.mostrar_vista(VistaGestion)).pack(pady=5, ipady=5)
        tk.Button(frame_botones_accion, text="📊 Corte de Caja", font=Theme.FONT_BOTON, command=lambda: controller.mostrar_vista(VistaReporte)).pack(pady=5, ipady=5)
        
        main_content_frame = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
        main_content_frame.pack(pady=20, expand=True, fill='both')

        contenedor_botones = tk.Frame(main_content_frame, bg=Theme.COLOR_FONDO_PRINCIPAL)
        contenedor_botones.place(relx=0.5, rely=0.5, anchor="center")

        self.botones = {}
        for i in range(1, 15):
            frame_mesa = tk.Frame(contenedor_botones, bg=Theme.COLOR_FONDO_PRINCIPAL)
            frame_mesa.grid(row=(i - 1) // 7, column=(i - 1) % 7, padx=15, pady=15)

            if i == 14:
                texto_display = "Para llevar"
                valor_orden = "Para llevar"
            else:
                texto_display = f"Mesa {i}"
                valor_orden = str(i)

            lbl = tk.Label(frame_mesa, image=self.img_mesa_libre, cursor="hand2", bg=Theme.COLOR_FONDO_PRINCIPAL)
            lbl.bind("<Button-1>", partial(self.seleccionar_mesa_click, i, valor_orden))
            lbl.pack()
            
            tk.Label(frame_mesa, text=texto_display, font=("Helvetica", 14, "bold"), bg=Theme.COLOR_FONDO_PRINCIPAL, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack()
            self.botones[i] = lbl

        tk.Button(self, text="Salir de la Aplicación", font=Theme.FONT_BOTON, bg=Theme.COLOR_MESA_OCUPADA, fg=Theme.COLOR_TEXTO_CABECERA, relief="flat", command=self.controller.quit).pack(pady=20, side="bottom", ipady=8, ipadx=10)
        self.actualizar_colores()

    def seleccionar_mesa_click(self, numero_boton, valor_orden, event):
        self.controller.seleccionar_mesa(numero_boton, valor_orden)

    def cargar_imagen_mesa(self, nombre_archivo):
        if not ImageTk: return None
        try:
            path = resource_path(os.path.join("assets", "images", nombre_archivo))
            img = Image.open(path).resize((150, 150), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error cargando imagen de mesa '{nombre_archivo}': {e}")
            messagebox.showerror("Error de Imagen", f"No se pudo cargar la imagen '{nombre_archivo}'.\n\nAsegúrate de que el archivo existe en la carpeta 'assets/images'.")
            return None

    def actualizar_colores(self):
        if not self.img_mesa_libre or not self.img_mesa_ocupada: return
        
        for num, estado in self.controller.estado_mesas.items():
            imagen = self.img_mesa_libre if estado == "libre" else self.img_mesa_ocupada
            if num in self.botones and self.botones[num].cget("image") != str(imagen):
                self.botones[num].config(image=imagen)

    def cargar_datos(self):
        self.actualizar_colores()

class VistaPedido(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.COLOR_FONDO_PRINCIPAL)
        self.controller = controller
        self.current_products = []

        # Columna de Categorías con Scroll
        col_categorias_main = tk.Frame(self, width=200, bg=Theme.COLOR_FONDO_SECUNDARIO)
        col_categorias_main.pack(side="left", fill="y", padx=(5,0), pady=5)
        col_categorias_main.pack_propagate(False)
        tk.Label(col_categorias_main, text="Categorías", font=Theme.FONT_TITULO, bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(pady=10)
        canvas_cat = tk.Canvas(col_categorias_main, bg=Theme.COLOR_FONDO_SECUNDARIO, highlightthickness=0)
        scrollbar_cat = ttk.Scrollbar(col_categorias_main, orient="vertical", command=canvas_cat.yview)
        canvas_cat.configure(yscrollcommand=scrollbar_cat.set)
        scrollbar_cat.pack(side="right", fill="y")
        canvas_cat.pack(side="left", fill="both", expand=True)
        self.frame_interior_categorias = tk.Frame(canvas_cat, bg=Theme.COLOR_FONDO_SECUNDARIO)
        canvas_cat.create_window((0, 0), window=self.frame_interior_categorias, anchor="nw")
        self.frame_interior_categorias.bind("<Configure>", lambda e: canvas_cat.configure(scrollregion=canvas_cat.bbox("all")))
        
        col_derecha = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
        col_derecha.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        col_derecha.grid_rowconfigure(0, weight=4)
        col_derecha.grid_rowconfigure(1, weight=6)
        col_derecha.grid_columnconfigure(0, weight=1)
        
        frame_superior = tk.Frame(col_derecha, bg=Theme.COLOR_FONDO_CABECERA)
        frame_superior.grid(row=0, column=0, sticky="nsew")
        
        self.frame_productos = tk.Frame(col_derecha, bg=Theme.COLOR_FONDO_SECUNDARIO)
        self.frame_productos.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=35, font=Theme.FONT_NORMAL, background=Theme.COLOR_FONDO_SECUNDARIO, foreground=Theme.COLOR_TEXTO_PRINCIPAL, fieldbackground=Theme.COLOR_FONDO_SECUNDARIO)
        style.map("Custom.Treeview", background=[('selected', Theme.COLOR_ACCENT_PRIMARY)])
        style.configure("Custom.Treeview.Heading", font=Theme.FONT_BOTON, background="#EAECEE", foreground=Theme.COLOR_TEXTO_PRINCIPAL)
        
        self.label_titulo_ticket = tk.Label(frame_superior, font=Theme.FONT_TITULO, bg=Theme.COLOR_FONDO_CABECERA, fg=Theme.COLOR_TEXTO_CABECERA)
        self.label_titulo_ticket.pack(pady=10)
        
        frame_ticket = tk.Frame(frame_superior, bg=Theme.COLOR_FONDO_SECUNDARIO)
        frame_ticket.pack(fill="both", expand=True, padx=5)
        
        cols = ("Cant", "Producto", "P.U.", "Total")
        self.ticket_tree = ttk.Treeview(frame_ticket, columns=cols, show="headings", style="Custom.Treeview")
        self.ticket_tree.tag_configure('oddrow', background='#FDFEFE')
        self.ticket_tree.tag_configure('evenrow', background='#F4F6F7')
        for col in cols: self.ticket_tree.heading(col, text=col)
        self.ticket_tree.column("Cant", width=50, anchor="center")
        self.ticket_tree.column("Producto", width=250)
        self.ticket_tree.column("P.U.", width=80, anchor="e")
        self.ticket_tree.column("Total", width=90, anchor="e")
        self.ticket_tree.pack(fill="both", expand=True)
        
        frame_ticket_bottom = tk.Frame(frame_superior, bg=Theme.COLOR_FONDO_CABECERA)
        frame_ticket_bottom.pack(side="bottom", fill="x", pady=5)
        
        self.label_total = tk.Label(frame_ticket_bottom, font=Theme.FONT_TOTAL, bg=Theme.COLOR_FONDO_CABECERA, fg=Theme.COLOR_TEXTO_CABECERA)
        self.label_total.pack(side="left", padx=20)
        
        frame_acciones = tk.Frame(frame_ticket_bottom, bg=Theme.COLOR_FONDO_CABECERA)
        frame_acciones.pack(side="right", pady=5, padx=10)
        tk.Button(frame_acciones, text="< Volver", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_BACK, fg="#000000", relief="flat", command=self.volver_a_mesas).pack(side='left', padx=5, ipady=8)
        tk.Button(frame_acciones, text="Transferir Mesa", font=Theme.FONT_BOTON, bg='#ffc107', command=self.transferir_mesa).pack(side='left', padx=5, ipady=8)
        tk.Button(frame_acciones, text="Imprimir Cuenta", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_WARNING, fg=Theme.COLOR_TEXTO_CABECERA, relief="flat", command=self.imprimir_pre_cuenta).pack(side='left', padx=5, ipady=8)
        tk.Button(frame_acciones, text="🗑️ Cerrar Mesa", font=Theme.FONT_BOTON, bg=Theme.COLOR_MESA_OCUPADA, fg=Theme.COLOR_TEXTO_CABECERA, relief="flat", command=self.cerrar_mesa_vacia).pack(side='left', padx=5, ipady=8)
        tk.Button(frame_acciones, text="PAGAR", font=("Helvetica", 14, "bold"), bg=Theme.COLOR_ACCENT_SUCCESS, fg=Theme.COLOR_TEXTO_CABECERA, relief="flat", command=self.ir_a_pagar).pack(side='right', padx=5, ipady=8)

        # --- BARRA DE BÚSQUEDA ---
        frame_busqueda = tk.Frame(self.frame_productos, bg=Theme.COLOR_FONDO_SECUNDARIO)
        frame_busqueda.pack(fill='x', pady=(10,5), padx=10)
        tk.Label(frame_busqueda, text="Buscar:", font=Theme.FONT_BOTON, bg=Theme.COLOR_FONDO_SECUNDARIO).pack(side='left', padx=(0,5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filtrar_productos)
        search_entry = tk.Entry(frame_busqueda, textvariable=self.search_var, font=Theme.FONT_NORMAL, relief="solid", bd=1)
        search_entry.pack(fill='x', expand=True, ipady=4)
        
        canvas_prod = tk.Canvas(self.frame_productos, bg=Theme.COLOR_FONDO_SECUNDARIO, highlightthickness=0)
        canvas_prod.pack(side="left", fill="both", expand=True, padx=10, pady=(0,10))
        
        scrollbar_prod = ttk.Scrollbar(self.frame_productos, orient="vertical", command=canvas_prod.yview)
        scrollbar_prod.pack(side="right", fill="y", pady=(0,10), padx=(0,10))
        
        self.grid_productos = tk.Frame(canvas_prod, bg=Theme.COLOR_FONDO_SECUNDARIO)
        canvas_prod.create_window((0, 0), window=self.grid_productos, anchor="nw")
        canvas_prod.configure(yscrollcommand=scrollbar_prod.set)
        
        self.bind_all("<MouseWheel>", lambda e, c=canvas_cat, p=canvas_prod: self._on_mousewheel(e, c, p))
        self.grid_productos.bind("<Configure>", lambda e: canvas_prod.configure(scrollregion=canvas_prod.bbox("all")))
        self.ticket_tree.bind("<Double-1>", self.on_double_click_item)
        self.ticket_tree.bind("<plus>", self.aumentar_cantidad); self.ticket_tree.bind("<KP_Add>", self.aumentar_cantidad)
        self.ticket_tree.bind("<minus>", self.disminuir_cantidad); self.ticket_tree.bind("<KP_Subtract>", self.disminuir_cantidad)
        self.frame_productos.bind("<Configure>", self.redraw_product_grid)

    def cerrar_mesa_vacia(self):
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if orden and not orden['ticket']:
            self.controller.liberar_mesa_vacia()
        else:
            messagebox.showwarning("Mesa Ocupada", "No se puede cerrar una mesa que ya tiene productos registrados.\nElimine todos los productos del ticket primero.")

    def _on_mousewheel(self, event, canvas_cat, canvas_prod):
        if event.widget.winfo_ismapped() and "TCombobox" not in str(event.widget.winfo_class()):
            widget_bajo_cursor = self.winfo_containing(event.x_root, event.y_root)
            if widget_bajo_cursor:
                parent = widget_bajo_cursor
                while parent:
                    if parent == canvas_cat.master:
                        canvas_cat.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        return
                    if parent == canvas_prod.master:
                        canvas_prod.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        return
                    parent = parent.master

    def on_double_click_item(self, event):
        region = self.ticket_tree.identify("region", event.x, event.y)
        if region != "cell": return
        column_id = self.ticket_tree.identify_column(event.x)
        column_index = int(column_id.replace('#', '')) - 1
        item_id = self.ticket_tree.focus()
        if not item_id or column_index not in [1, 2]: # Solo editable Nombre y P.U.
            return
        self.create_cell_editor(item_id, column_index)

# En la clase VistaPedido, reemplaza este método

    def create_cell_editor(self, item_id, column_index):
        # Desactiva el atajo de la barra espaciadora para poder escribir en el campo
        self.controller.unbind("<space>")
        self.controller.unbind("p")

        column_id_str = f"#{column_index + 1}"
        x, y, width, height = self.ticket_tree.bbox(item_id, column_id_str)
        value = self.ticket_tree.item(item_id, "values")[column_index]
        
        entry = ttk.Entry(self.ticket_tree, font=Theme.FONT_NORMAL)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus_force()
        entry.bind("<Return>", lambda e, i=item_id, c=column_index: self.save_edit(e.widget, i, c))
        entry.bind("<FocusOut>", lambda e, i=item_id, c=column_index: self.save_edit(e.widget, i, c))

# En la clase VistaPedido, reemplaza también este método

    def save_edit(self, entry, item_id, column_index):
        new_value = entry.get()
        entry.destroy()
        
        # Vuelve a activar el atajo de la barra espaciadora
        self.controller.bind("<space>", lambda e: self.ir_a_pagar())
        print("Atajo <space> reactivado.")

        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not orden or item_id not in orden['ticket']: return
        
        ticket_item = orden['ticket'][item_id]
        if column_index == 1: # Nombre
            ticket_item['nombre'] = new_value
        elif column_index == 2: # Precio Unitario
            try:
                new_price = float(new_value)
                if new_price < 0: raise ValueError
                ticket_item['precio'] = new_price
            except ValueError:
                messagebox.showerror("Error", "Precio inválido. Debe ser un número positivo.")
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
            if orden['ticket'][item_id]['cantidad'] == 1:
                if not messagebox.askyesno("Confirmar", "¿Seguro que quieres eliminar este producto del ticket?"):
                    return
            
            orden['ticket'][item_id]['cantidad'] -= 1
            
            if orden['ticket'][item_id]['cantidad'] <= 0:
                del orden['ticket'][item_id]
            self.actualizar_ticket_display()
    
    def volver_a_mesas(self):
        self.controller.unbind("<space>")
        self.controller.unbind("p")
        self.controller.mostrar_vista(VistaMesas)

    def ir_a_pagar(self):
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not orden or not orden['ticket']:
            messagebox.showwarning("Vacío", "No hay productos en el ticket para pagar.")
            return
        self.controller.unbind("<space>")
        self.controller.unbind("p")
        self.controller.mostrar_vista(VistaPago)
    
    def transferir_mesa(self):
        mesas_libres = [str(m) for m, estado in self.controller.estado_mesas.items() if estado == 'libre' and str(m).isdigit()]
        if not mesas_libres:
            messagebox.showinfo("Transferir", "No hay mesas libres para transferir la cuenta.")
            return

        dialog = TransferDialog(self, mesas_libres, self.controller.ordenes_abiertas[self.controller.mesa_activa]['mesa'])
        if dialog.result is not None:
            self.controller.transferir_orden(self.controller.mesa_activa, int(dialog.result))

    def imprimir_pre_cuenta(self):
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not orden or not orden['ticket']:
            messagebox.showwarning("Vacío", "No hay productos en el ticket.")
            return
        contenido = formatear_cuenta_cliente(orden)
        imprimir_ticket_fisico(contenido, con_logo=True)

    def cargar_datos(self):
        self.controller.bind("<space>", lambda e: self.ir_a_pagar())
        self.controller.bind("p", lambda e: self.imprimir_pre_cuenta())
        orden = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if orden:
            texto_mesa = orden.get('mesa')
            if texto_mesa == "Para llevar":
                self.label_titulo_ticket.config(text="Ticket Para Llevar")
            else:
                self.label_titulo_ticket.config(text=f"Ticket Mesa {texto_mesa}")
        
        self.cargar_categorias()
        self.actualizar_ticket_display()
        self.search_var.set("")
        self.id_categoria_actual = None
        self.filtrar_productos()

    def cargar_categorias(self):
        for widget in self.frame_interior_categorias.winfo_children():
            widget.destroy()
        
        tk.Button(self.frame_interior_categorias, text="Todos", font=Theme.FONT_NORMAL, wraplength=160, justify="center", command=lambda: self.cargar_productos(None), relief="flat", bg="#D5DBDB", fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(pady=3, padx=10, fill="x", ipady=8)

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM Categorias ORDER BY nombre")
        for id_cat, nombre in cursor.fetchall():
            tk.Button(self.frame_interior_categorias, text=nombre, font=Theme.FONT_NORMAL, wraplength=160, justify="center", command=partial(self.cargar_productos, id_cat), relief="flat", bg="#ECF0F1", fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(pady=3, padx=10, fill="x", ipady=8)
        conn.close()

    def filtrar_productos(self, *args):
        termino_busqueda = self.search_var.get().lower()
        id_categoria_actual = getattr(self, 'id_categoria_actual', None)

        conn = conectar_db()
        cursor = conn.cursor()
        
        if id_categoria_actual:
            query = "SELECT id, nombre, precio, precio_variable FROM Productos WHERE id_categoria = ? AND lower(nombre) LIKE ? ORDER BY nombre"
            params = (id_categoria_actual, f'%{termino_busqueda}%')
        else:
            query = "SELECT id, nombre, precio, precio_variable FROM Productos WHERE lower(nombre) LIKE ? ORDER BY nombre"
            params = (f'%{termino_busqueda}%',)
        
        cursor.execute(query, params)
        self.current_products = cursor.fetchall()
        conn.close()
        self.redraw_product_grid()

    def cargar_productos(self, id_categoria):
        self.id_categoria_actual = id_categoria
        self.filtrar_productos()

    def redraw_product_grid(self, event=None):
        for widget in self.grid_productos.winfo_children():
            widget.destroy()
        
        container_width = self.frame_productos.winfo_width()
        button_width = 200
        num_cols = max(1, container_width // button_width)
        
        for i, (id_prod, nombre, precio, es_variable) in enumerate(self.current_products):
            info = {'id': id_prod, 'nombre': nombre, 'precio': precio, 'es_variable': es_variable}
            texto_boton = f"{nombre}\n${precio:.2f}"
            if es_variable:
                texto_boton = f"{nombre}\n(Precio Variable)"
            
            btn = tk.Button(self.grid_productos, text=texto_boton, font=Theme.FONT_NORMAL, 
                            width=20, height=5, wraplength=150, 
                            command=partial(self.agregar_a_ticket, info),
                            bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL,
                            relief="solid", bd=1)
            btn.grid(row=i // num_cols, column=i % num_cols, padx=5, pady=5)

    def agregar_a_ticket(self, prod):
        ticket = self.controller.ordenes_abiertas[self.controller.mesa_activa]['ticket']
        prod_id = str(prod['id'])
        p_final = prod['precio']
        
        if prod['es_variable']:
            dialog = simpledialog.askfloat("Precio Variable", f"Introduzca el precio para:\n{prod['nombre']}", parent=self)
            if dialog is None or dialog < 0: return
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

class VistaPago(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.COLOR_FONDO_PRINCIPAL)
        self.controller = controller
        
        def validate_numeric(text):
            if not text: # permite que el campo esté vacío
                return True
            try:
                # Intenta convertir el texto a un número flotante.
                # Si funciona, es un número válido (ej: "150" o "150.5")
                float(text)
                return True
            except ValueError:
                # Si falla, significa que hay letras o símbolos.
                return False
            
        vcmd = (self.register(validate_numeric), '%P')
        self.metodo_pago = tk.StringVar(value="Efectivo")
        self.descuento_var = tk.StringVar(value="0")
        self.paga_con_var = tk.StringVar(value="")
        self.total_final_var = tk.StringVar()
        self.cambio_var = tk.StringVar()
        self.descuento_var.trace_add("write", self.actualizar_calculos)
        self.paga_con_var.trace_add("write", self.actualizar_calculos)
        
        contenedor = tk.Frame(self, bg=Theme.COLOR_FONDO_SECUNDARIO, bd=1, relief="solid")
        contenedor.pack(expand=True)
        
        tk.Label(contenedor, text="Finalizar Venta", font=Theme.FONT_TITULO, bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL).grid(row=0, column=0, columnspan=2, pady=20, padx=50)
        tk.Label(contenedor, text="Total Original:", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=1, column=0, sticky="e", padx=10)
        self.label_total_original = tk.Label(contenedor, text="$0.00", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL)
        self.label_total_original.grid(row=1, column=1, sticky="w")
        
        frame_pago = tk.Frame(contenedor, bg=Theme.COLOR_FONDO_SECUNDARIO)
        frame_pago.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Radiobutton(frame_pago, text="Efectivo", variable=self.metodo_pago, value="Efectivo", command=self.toggle_paga_con, font=Theme.FONT_BOTON, bg=Theme.COLOR_FONDO_SECUNDARIO).pack(side="left", padx=10)
        tk.Radiobutton(frame_pago, text="Tarjeta", variable=self.metodo_pago, value="Tarjeta", command=self.toggle_paga_con, font=Theme.FONT_BOTON, bg=Theme.COLOR_FONDO_SECUNDARIO).pack(side="left", padx=10)
        
        tk.Label(contenedor, text="Descuento ($):", font=Theme.FONT_NORMAL, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=3, column=0, sticky="e", padx=10, pady=5)
        self.entry_descuento = tk.Entry(contenedor, textvariable=self.descuento_var, font=Theme.FONT_NORMAL, width=12)
        self.entry_descuento.grid(row=3, column=1, sticky="w")
        
        tk.Label(contenedor, text="Paga con ($):", font=Theme.FONT_NORMAL, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=4, column=0, sticky="e", padx=10, pady=5)
        self.entry_paga_con = tk.Entry(contenedor, textvariable=self.paga_con_var, font=Theme.FONT_NORMAL, width=12,
                                       validate='key', validatecommand=vcmd)
        self.entry_paga_con.grid(row=4, column=1, sticky="w")
        
        tk.Label(contenedor, text="Total Final:", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=5, column=0, sticky="e", padx=10, pady=(20, 0))
        tk.Label(contenedor, textvariable=self.total_final_var, font=Theme.FONT_SUBTITULO, fg=Theme.COLOR_ACCENT_PRIMARY, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=5, column=1, sticky="w")
        
        tk.Label(contenedor, text="Cambio:", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=6, column=0, sticky="e", padx=10, pady=5)
        tk.Label(contenedor, textvariable=self.cambio_var, font=Theme.FONT_SUBTITULO, fg=Theme.COLOR_ACCENT_SUCCESS, bg=Theme.COLOR_FONDO_SECUNDARIO).grid(row=6, column=1, sticky="w")
        
        frame_botones = tk.Frame(contenedor, bg=Theme.COLOR_FONDO_SECUNDARIO)
        frame_botones.grid(row=7, column=0, columnspan=2, pady=30)
        tk.Button(frame_botones, text="< Volver al Pedido", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_BACK, command=lambda: self.controller.mostrar_vista(VistaPedido), relief="flat").pack(side="left", padx=10, ipady=8)
        tk.Button(frame_botones, text="Finalizar Venta", font=("Helvetica", 14, "bold"), bg=Theme.COLOR_ACCENT_SUCCESS, fg=Theme.COLOR_TEXTO_CABECERA, command=self.finalizar_venta, relief="flat").pack(side="left", padx=10, ipady=8)
 
    def cargar_datos(self):
        self.controller.bind("<Return>", lambda e: self.finalizar_venta())
        self.orden_original = self.controller.ordenes_abiertas.get(self.controller.mesa_activa)
        if not self.orden_original: return
        total = self.orden_original.get('total', 0.0)
        self.label_total_original.config(text=f"${total:.2f}")
        self.descuento_var.set("0")
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
            paga_con = float(self.paga_con_var.get() or 0) if self.metodo_pago.get() == "Efectivo" else 0
        except (ValueError, TypeError):
            self.total_final_var.set("$----")
            self.cambio_var.set("$----")
            return
        
        if descuento > total_original:
            descuento = total_original

        total_final = total_original - descuento
        cambio = paga_con - total_final if self.metodo_pago.get() == "Efectivo" else 0.0
        
        self.total_final_var.set(f"${total_final:.2f}")
        self.cambio_var.set(f"${cambio:.2f}" if cambio >= 0 else "-")

# main.py -> Dentro de la clase VistaPago

# main.py -> Dentro de la clase VistaPago

    def finalizar_venta(self):
        try:
            total_final = float(self.total_final_var.get().replace('$', ''))
            paga_con_str = self.paga_con_var.get()
            
            if not paga_con_str.replace('.', '', 1).isdigit() and self.metodo_pago.get() == "Efectivo":
                messagebox.showerror("Error", "El monto 'Paga con' no es válido.")
                return

            paga_con = float(paga_con_str or 0)

            if self.metodo_pago.get() == "Efectivo" and paga_con < total_final:
                messagebox.showerror("Error", "La cantidad pagada es menor al total.")
                return
            
            valor_mesa = self.orden_original['mesa']
            descuento_final = float(self.descuento_var.get() or 0)

            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Ventas (id_mesa, total, metodo_pago, descuento, paga_con, fecha_hora) VALUES (?, ?, ?, ?, ?, ?)",
                (valor_mesa, total_final, self.metodo_pago.get(), descuento_final, paga_con, datetime.datetime.now())
            )
            id_venta = cursor.lastrowid
            
            for prod_id, item in self.orden_original['ticket'].items():
                real_prod_id = -1
                if 'var_' in str(prod_id):
                    real_prod_id = int(str(prod_id).split('_')[1])
                else:
                    real_prod_id = int(prod_id)
                
                cursor.execute(
                    "INSERT INTO Detalle_Venta (id_venta, id_producto, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                    (id_venta, real_prod_id, item['cantidad'], item['precio'])
                )
            conn.commit()
            conn.close()

            
            
            cambio = paga_con - total_final
            if self.metodo_pago.get() == "Efectivo" and cambio > 0:
                VentanaCambio(self.controller, cambio)
            
            contenido_ticket = formatear_recibo_final(id_venta)
            imprimir_ticket_fisico(contenido_ticket, con_logo=True)
            
        except Exception as e:
            messagebox.showerror("Error Inesperado", f"Ocurrió un error al finalizar la venta: {e}")
        finally:
            self.controller.finalizar_y_liberar_mesa()
            

class VistaGestion(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.COLOR_FONDO_PRINCIPAL)
        self.controller = controller
        
        top_bar = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
        top_bar.pack(fill='x', padx=10, pady=10)
        
        tk.Label(top_bar, text="Gestión de Menú", font=Theme.FONT_TITULO_GRANDE, bg=Theme.COLOR_FONDO_PRINCIPAL).pack(side='left', expand=True)
        tk.Button(top_bar, text="< Volver a Mesas", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_BACK, command=lambda: controller.mostrar_vista(VistaMesas)).pack(side='right')
        
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
        tk.Label(tab, text="Gestionar Categorías", font=Theme.FONT_TITULO).pack(pady=10)
        main_frame = tk.Frame(tab)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        col_izquierda = tk.Frame(main_frame)
        col_izquierda.pack(side="left", fill="y", padx=10)
        
        col_derecha = tk.Frame(main_frame)
        col_derecha.pack(side="left", fill="both", expand=True, padx=10)
        
        frame_entrada = tk.Frame(col_izquierda)
        frame_entrada.pack(pady=10)
        tk.Label(frame_entrada, text="Nombre de Categoría:", font=Theme.FONT_NORMAL).pack()
        self.entry_categoria = tk.Entry(frame_entrada, width=30, font=Theme.FONT_NORMAL)
        self.entry_categoria.pack()
        tk.Button(frame_entrada, text="Añadir", command=self.anadir_categoria, font=Theme.FONT_BOTON).pack(pady=5)
        
        self.lista_categorias = tk.Listbox(col_izquierda, width=35, height=15, exportselection=False, font=Theme.FONT_NORMAL)
        self.lista_categorias.pack(pady=10)
        self.lista_categorias.bind("<<ListboxSelect>>", self.mostrar_productos_de_categoria)
        tk.Button(col_izquierda, text="Eliminar Seleccionada", command=self.eliminar_categoria, font=Theme.FONT_BOTON, bg=Theme.COLOR_MESA_OCUPADA, fg="white").pack(pady=5)
        
        tk.Label(col_derecha, text="Productos en Categoría", font=Theme.FONT_SUBTITULO).pack(pady=10)
        self.lista_productos_cat = tk.Listbox(col_derecha, height=18, font=Theme.FONT_NORMAL)
        self.lista_productos_cat.pack(fill="both", expand=True)

    def crear_widgets_productos(self, tab):
        tk.Label(tab, text="Gestionar Productos", font=Theme.FONT_TITULO).pack(pady=10)
        frame_controles = tk.Frame(tab)
        frame_controles.pack(pady=10, padx=20, fill="x")
        
        frame_entrada = tk.LabelFrame(frame_controles, text="Añadir/Editar Producto", font=Theme.FONT_NORMAL, padx=10, pady=10)
        frame_entrada.pack(side="left", fill="x", expand=True)
        
        tk.Label(frame_entrada, text="Nombre:", font=Theme.FONT_NORMAL).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_prod_nombre = tk.Entry(frame_entrada, width=40, font=Theme.FONT_NORMAL)
        self.entry_prod_nombre.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(frame_entrada, text="Precio:", font=Theme.FONT_NORMAL).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_prod_precio = tk.Entry(frame_entrada, width=20, font=Theme.FONT_NORMAL)
        self.entry_prod_precio.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        tk.Label(frame_entrada, text="Categoría:", font=Theme.FONT_NORMAL).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.combo_prod_categoria = ttk.Combobox(frame_entrada, state="readonly", width=37, font=Theme.FONT_NORMAL)
        self.combo_prod_categoria.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        self.precio_variable_var = tk.BooleanVar()
        tk.Checkbutton(frame_entrada, text="Asignar precio al vender", variable=self.precio_variable_var, font=Theme.FONT_NORMAL).grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        tk.Button(frame_entrada, text="Añadir Producto", command=self.anadir_producto, font=Theme.FONT_BOTON).grid(row=4, column=0, columnspan=2, pady=10)
        
        # --- Botón de eliminar a la derecha ---
        frame_eliminar = tk.Frame(frame_controles)
        frame_eliminar.pack(side="left", padx=(20, 0))
        tk.Button(frame_eliminar, text="Eliminar\nSeleccionado", command=self.eliminar_producto, font=Theme.FONT_BOTON, bg=Theme.COLOR_MESA_OCUPADA, fg="white", width=15, height=3).pack()

        # --- Frame inferior para la lista con scroll ---
        frame_lista = tk.Frame(tab)
        frame_lista.pack(pady=10, padx=20, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame_lista)
        scrollbar.pack(side="right", fill="y")

        self.tree_productos = ttk.Treeview(frame_lista, columns=("ID", "Nombre", "Precio", "Categoría", "Variable"), show="headings", yscrollcommand=scrollbar.set, style="Custom.Treeview")
        scrollbar.config(command=self.tree_productos.yview)

        self.tree_productos.heading("ID", text="ID"); self.tree_productos.heading("Nombre", text="Nombre")
        self.tree_productos.heading("Precio", text="Precio"); self.tree_productos.heading("Categoría", text="Categoría")
        self.tree_productos.heading("Variable", text="Precio Variable")
        self.tree_productos.column("ID", width=40, anchor="center"); self.tree_productos.column("Variable", width=100, anchor="center")
        self.tree_productos.pack(fill="both", expand=True)
        
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
            messagebox.showwarning("Campos incompletos", "Todos los campos (Nombre, Precio, Categoría) son obligatorios.")
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
            id_categoria_result = cursor.fetchone()
            if not id_categoria_result:
                messagebox.showerror("Error", "La categoría seleccionada no es válida.")
                return
            id_categoria = id_categoria_result[0]
            cursor.execute("INSERT INTO Productos (nombre, precio, id_categoria, precio_variable) VALUES (?, ?, ?, ?)", (nombre, precio, id_categoria, es_variable))
            conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"El producto '{nombre}' ya existe.")
        finally:
            conn.close()
            self.entry_prod_nombre.delete(0, tk.END)
            self.entry_prod_precio.delete(0, tk.END)
            self.precio_variable_var.set(False)
            self.cargar_productos()
            messagebox.showinfo("Éxito", f"Producto '{nombre}' añadido.")

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

# ===================================================================
# ===== CLASE VistaReporte RECONSTRUIDA DESDE CERO ==================
# ===================================================================
class VistaReporte(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=Theme.COLOR_FONDO_PRINCIPAL)
        self.controller = controller
        self.reporte_seleccionado_texto = ""

        # --- Frame Superior ---
        frame_superior = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
        frame_superior.pack(pady=(10, 15), padx=20, fill='x')
        tk.Label(frame_superior, text="Corte de Caja", font=Theme.FONT_TITULO_GRANDE, bg=Theme.COLOR_FONDO_PRINCIPAL, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(side='left', expand=True)
        tk.Button(frame_superior, text="< Volver a Mesas", font=Theme.FONT_BOTON, bg=Theme.COLOR_ACCENT_BACK, fg="black", relief="flat", command=lambda: controller.mostrar_vista(VistaMesas)).pack(side='right', ipady=5)

        # --- Contenedor Principal (PanedWindow) ---
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg="#cccccc")
        paned_window.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # --- Panel Izquierdo: Historial ---
        frame_historial = tk.Frame(paned_window, bg=Theme.COLOR_FONDO_SECUNDARIO, padx=10, pady=10)
        paned_window.add(frame_historial, width=300)
        paned_window.paneconfigure(frame_historial, minsize=280)
        tk.Label(frame_historial, text="Historial de Cortes", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO, fg=Theme.COLOR_TEXTO_PRINCIPAL).pack(pady=(0, 10), anchor="w")

        style = ttk.Style()
        style.configure("Historial.Treeview", rowheight=30, font=Theme.FONT_NORMAL, background=Theme.COLOR_FONDO_SECUNDARIO)
        style.configure("Historial.Treeview.Heading", font=Theme.FONT_BOTON)
        style.map("Historial.Treeview", background=[('selected', Theme.COLOR_ACCENT_PRIMARY)])

        tree_frame = tk.Frame(frame_historial)
        tree_frame.pack(fill='both', expand=True)
        self.tree_historial = ttk.Treeview(tree_frame, columns=("fecha",), show="headings", style="Historial.Treeview")
        self.tree_historial.heading("fecha", text="Fecha del Corte")
        self.tree_historial.column("fecha", anchor="center")
        scrollbar_hist = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_historial.yview)
        self.tree_historial.configure(yscrollcommand=scrollbar_hist.set)
        scrollbar_hist.pack(side="right", fill="y")
        self.tree_historial.pack(side="left", fill="both", expand=True)
        self.tree_historial.bind("<<TreeviewSelect>>", self.mostrar_reporte_historico)
        tk.Button(frame_historial, text="Ver Reporte del Dia", command=self.cargar_datos, bg=Theme.COLOR_ACCENT_PRIMARY, fg="white", relief="flat", font=Theme.FONT_BOTON).pack(fill='x', ipady=8, pady=(10,0))
        
        # --- Panel Derecho: Detalle ---
        frame_detalle = tk.LabelFrame(paned_window, text=" Detalle del Reporte ", font=Theme.FONT_SUBTITULO, bg=Theme.COLOR_FONDO_SECUNDARIO, padx=15, pady=15, bd=0)
        paned_window.add(frame_detalle)
        
        self.reporte_widget = tk.Text(frame_detalle, font=Theme.FONT_TICKET, wrap="word", state="disabled", bg=Theme.COLOR_FONDO_SECUNDARIO, relief="flat", height=15, bd=0)
        self.reporte_widget.pack(expand=True, fill="both")
        
        self.frame_botones_accion = tk.Frame(frame_detalle, bg=Theme.COLOR_FONDO_SECUNDARIO)
        self.frame_botones_accion.pack(pady=(15, 0), fill='x', side='bottom')

        self.btn_reporte_productos = tk.Button(self.frame_botones_accion, text="Ventas por Producto", font=Theme.FONT_BOTON, bg="#17a2b8", fg="white", relief="flat", height=2, command=self.generar_reporte_productos)
        self.btn_cerrar_caja = tk.Button(self.frame_botones_accion, text="Cerrar Caja de Hoy", font=("Helvetica", 14, "bold"), bg=Theme.COLOR_ACCENT_SUCCESS, fg="white", relief="flat", height=2, command=self.cerrar_caja_hoy)
        self.btn_reimprimir = tk.Button(self.frame_botones_accion, text="Re-imprimir Reporte", font=Theme.FONT_BOTON, bg="#6c757d", fg="white", relief="flat", height=2, command=self.reimprimir_reporte)

    def cargar_datos(self):
        self.tree_historial.selection_set(())
        self.cargar_historial_cortes()
        self.mostrar_reporte_actual()

    def cargar_historial_cortes(self):
        for item in self.tree_historial.get_children():
            self.tree_historial.delete(item)
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT corte_id FROM Ventas WHERE corte_id IS NOT NULL ORDER BY corte_id DESC")
        for row in cursor.fetchall():
            self.tree_historial.insert("", "end", values=(row[0],))
        conn.close()

    def generar_reporte_texto(self, fecha_str=None, es_historico=False):
        conn = conectar_db()
        cursor = conn.cursor()
        
        if es_historico:
            query = """
                SELECT COUNT(*), SUM(total), SUM(descuento),
                       SUM(CASE WHEN metodo_pago = 'Efectivo' THEN total ELSE 0 END),
                       SUM(CASE WHEN metodo_pago = 'Tarjeta' THEN total ELSE 0 END)
                FROM Ventas WHERE corte_id = ?
            """
            params = (fecha_str,)
            titulo = f"REPORTE HISTÓRICO - {datetime.datetime.strptime(fecha_str, '%Y-%m-%d').strftime('%d/%m/%Y')}"
        else:
            query = """
                SELECT COUNT(*), SUM(total), SUM(descuento),
                       SUM(CASE WHEN metodo_pago = 'Efectivo' THEN total ELSE 0 END),
                       SUM(CASE WHEN metodo_pago = 'Tarjeta' THEN total ELSE 0 END)
                FROM Ventas WHERE DATE(fecha_hora) = DATE('now', 'localtime') AND corte_id IS NULL
            """
            params = ()
            titulo = f"REPORTE DEL DIA - {datetime.datetime.now().strftime('%d/%m/%Y')} (ACTUAL)"
        
        cursor.execute(query, params)
        resultado = cursor.fetchone()
        conn.close()

        num_ventas, total_dia, total_descuento, total_efectivo, total_tarjeta = (resultado or (0, 0, 0, 0, 0))
        num_ventas = num_ventas or 0
        total_dia = total_dia or 0
        total_descuento = total_descuento or 0
        total_efectivo = total_efectivo or 0
        total_tarjeta = total_tarjeta or 0
        
        texto = f"{titulo}\n{'='*45}\n\n"
        texto += f"Total de Ventas (Tickets): {num_ventas}\n\n"
        texto += f"Ingresos en Efectivo: ${total_efectivo:10.2f}\n"
        texto += f"Ingresos con Tarjeta: ${total_tarjeta:10.2f}\n"
        texto += f"Total Descuentos:     ${total_descuento:10.2f}\n"
        texto += "-" * 45 + "\n"
        texto += f"VENTA TOTAL DEL DIA:  ${total_dia:10.2f}\n"
        texto += f"EFECTIVO EN CAJA:     ${total_efectivo:10.2f}\n"
        texto += "=" * 45 + "\n"
        return texto

    def generar_reporte_productos(self):
        fecha_seleccionada = None
        es_historico = False
        selection = self.tree_historial.selection()
        if selection:
            fecha_seleccionada = self.tree_historial.item(selection[0], "values")[0]
            es_historico = True

        conn = conectar_db()
        cursor = conn.cursor()

        if es_historico:
            query = """
                SELECT p.nombre, SUM(dv.cantidad), SUM(dv.cantidad * dv.precio_unitario)
                FROM Detalle_Venta dv
                JOIN Productos p ON dv.id_producto = p.id
                JOIN Ventas v ON dv.id_venta = v.id
                WHERE v.corte_id = ?
                GROUP BY p.nombre
                ORDER BY SUM(dv.cantidad) DESC
            """
            params = (fecha_seleccionada,)
            titulo = f"VENTAS POR PRODUCTO - {datetime.datetime.strptime(fecha_seleccionada, '%Y-%m-%d').strftime('%d/%m/%Y')}"
        else:
            query = """
                SELECT p.nombre, SUM(dv.cantidad), SUM(dv.cantidad * dv.precio_unitario)
                FROM Detalle_Venta dv
                JOIN Productos p ON dv.id_producto = p.id
                JOIN Ventas v ON dv.id_venta = v.id
                WHERE DATE(v.fecha_hora) = DATE('now', 'localtime') AND v.corte_id IS NULL
                GROUP BY p.nombre
                ORDER BY SUM(dv.cantidad) DESC
            """
            params = ()
            titulo = f"VENTAS POR PRODUCTO - {datetime.datetime.now().strftime('%d/%m/%Y')} (ACTUAL)"

        cursor.execute(query, params)
        productos = cursor.fetchall()
        conn.close()

        texto = f"{titulo}\n{'='*45}\n"
        texto += "Cant  Producto             Total\n"
        texto += "-"*45 + "\n"
        
        if not productos:
            texto += "No hay ventas registradas.\n"
        else:
            for nombre, cantidad, total in productos:
                nombre_corto = (nombre[:20] + '..') if len(nombre) > 22 else nombre
                texto += f"{int(cantidad):<4}  {nombre_corto:<22} ${total:>8.2f}\n"
        
        texto += "="*45 + "\n"
        ReporteProductosDialog(self, titulo, texto)

    def mostrar_reporte_actual(self):
        self.reporte_seleccionado_texto = self.generar_reporte_texto(es_historico=False)
        self.actualizar_widget_texto(self.reporte_seleccionado_texto)
        
        self.btn_reimprimir.pack_forget()
        self.btn_cerrar_caja.pack(side='left', expand=True, fill='x', padx=(5,0))
        self.btn_reporte_productos.pack(side="left", expand=True, fill='x', padx=(0,5))
        
        self.btn_cerrar_caja.config(state="normal")
        self.btn_reporte_productos.config(state="normal")

    def mostrar_reporte_historico(self, event=None):
        selection = self.tree_historial.selection()
        if not selection: return
        
        fecha_seleccionada = self.tree_historial.item(selection[0], "values")[0]
        self.reporte_seleccionado_texto = self.generar_reporte_texto(fecha_str=fecha_seleccionada, es_historico=True)
        self.actualizar_widget_texto(self.reporte_seleccionado_texto)
        
        self.btn_cerrar_caja.pack_forget()
        self.btn_reimprimir.pack(side='left', expand=True, fill='x', padx=(5,0))
        self.btn_reporte_productos.pack(side="left", expand=True, fill='x', padx=(0,5))
        
        self.btn_reimprimir.config(state="normal")
        self.btn_reporte_productos.config(state="normal")
        
    def actualizar_widget_texto(self, contenido):
        self.reporte_widget.config(state="normal")
        self.reporte_widget.delete("1.0", tk.END)
        self.reporte_widget.insert("1.0", contenido)
        self.reporte_widget.config(state="disabled")

    def cerrar_caja_hoy(self):
        reporte_a_cerrar = self.generar_reporte_texto(es_historico=False)
        if "Total de Ventas (Tickets): 0" in reporte_a_cerrar:
            messagebox.showinfo("Caja Vacía", "No hay ventas para cerrar el dia de hoy.")
            return
        
        confirmar = messagebox.askyesno("Confirmar Cierre",
                                      "Se marcarán las ventas de hoy como 'cerradas' y se imprimirá el reporte final.\n"
                                      "Esta acción no se puede deshacer.\n\n"
                                      "¿Desea continuar?")
        if confirmar:
            try:
                imprimir_ticket_fisico(reporte_a_cerrar, con_logo=True)
            finally:
                fecha_hoy_str = datetime.date.today().strftime('%Y-%m-%d')
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE Ventas SET corte_id = ? WHERE DATE(fecha_hora) = DATE('now', 'localtime') AND corte_id IS NULL",
                               (fecha_hoy_str,))
                conn.commit()
                conn.close()
                messagebox.showinfo("Cierre Exitoso", f"Corte del dia {fecha_hoy_str} finalizado.")
                self.cargar_datos()

    def reimprimir_reporte(self):
        if self.reporte_seleccionado_texto:
            imprimir_ticket_fisico(self.reporte_seleccionado_texto, con_logo=True)
        else:
            messagebox.showwarning("Sin Selección", "No hay un reporte seleccionado para imprimir.")

# --- CLASE PRINCIPAL Y EJECUCIÓN ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Punto de Venta")
        self.attributes('-fullscreen', True)
        self.configure(bg=Theme.COLOR_FONDO_PRINCIPAL)

        style = ttk.Style(self)
        style.theme_use('clam')

        self.estado_mesas = {i: "libre" for i in range(1, 15)}
        self.ordenes_abiertas = {}
        self.mesa_activa = None
        self.fullscreen_state = True
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.volver_a_mesas_global)

        container = tk.Frame(self, bg=Theme.COLOR_FONDO_PRINCIPAL)
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

    def seleccionar_mesa(self, numero_boton, valor_orden):
        self.mesa_activa = numero_boton
        if numero_boton not in self.ordenes_abiertas:
            self.ordenes_abiertas[numero_boton] = {'mesa': valor_orden, 'ticket': {}, 'total': 0.0}
            self.estado_mesas[numero_boton] = "ocupada"
            self.vistas[VistaMesas].actualizar_colores()
        self.mostrar_vista(VistaPedido)
        
    def transferir_orden(self, mesa_origen_id, mesa_destino_id):
        orden_a_mover = self.ordenes_abiertas.pop(mesa_origen_id, None)
        if orden_a_mover:
            orden_a_mover['mesa'] = str(mesa_destino_id)
            self.ordenes_abiertas[mesa_destino_id] = orden_a_mover
            
            self.estado_mesas[mesa_origen_id] = "libre"
            self.estado_mesas[mesa_destino_id] = "ocupada"
            
            self.vistas[VistaMesas].actualizar_colores()
            self.mostrar_vista(VistaMesas)
            messagebox.showinfo("Éxito", f"La orden se ha transferido a la Mesa {mesa_destino_id}.")
        else:
            messagebox.showerror("Error", "No se encontró la orden a transferir.")

    def liberar_mesa_vacia(self):
        self.unbind("<Return>")
        self.unbind("<space>")
        numero_mesa = self.mesa_activa
        if numero_mesa in self.ordenes_abiertas:
            del self.ordenes_abiertas[numero_mesa]
        
        self.estado_mesas[numero_mesa] = "libre"
        self.vistas[VistaMesas].actualizar_colores()
        self.mesa_activa = None
        self.mostrar_vista(VistaMesas)

    def finalizar_y_liberar_mesa(self):
        self.unbind("<Return>")
        numero_mesa = self.mesa_activa
        if numero_mesa in self.ordenes_abiertas:
            del self.ordenes_abiertas[numero_mesa]
        self.estado_mesas[numero_mesa] = "libre"
        self.vistas[VistaMesas].actualizar_colores()
        self.mesa_activa = None
        self.mostrar_vista(VistaMesas)
        
    def toggle_fullscreen(self, event=None):
        self.fullscreen_state = not self.fullscreen_state
        self.attributes("-fullscreen", self.fullscreen_state)
        return "break"
    
if __name__ == "__main__":
    # La verificación ahora usa las rutas correctas
    if not os.path.exists(DB_FILE) or not os.path.exists(CONFIG_FILE_PATH):
        error_msg = ""
        if not os.path.exists(CONFIG_FILE_PATH):
            error_msg += f"No se encontró el archivo de configuración '{CONFIG_FILE_PATH}'.\n"
        if not os.path.exists(DB_FILE):
            error_msg += f"No se encontró el archivo de base de datos '{DB_FILE}'.\n"
        messagebox.showerror("Error de Archivos Críticos", error_msg)
    else:
        app = App()
        app.mainloop()