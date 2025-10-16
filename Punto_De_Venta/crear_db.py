import sqlite3
import os

DB_FILE = "pos_database.db"

def crear_y_poblar_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # --- CREACIÓN DE TABLAS (AQUÍ ESTÁ LA CORRECCIÓN) ---
    cursor.execute('CREATE TABLE Categorias (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE)')
    
    cursor.execute('''
        CREATE TABLE Productos (
            id INTEGER PRIMARY KEY, 
            nombre TEXT NOT NULL UNIQUE, 
            precio REAL NOT NULL, 
            id_categoria INTEGER, 
            precio_variable BOOLEAN DEFAULT 0, 
            FOREIGN KEY (id_categoria) REFERENCES Categorias(id)
        )''')
        
    cursor.execute('''
        CREATE TABLE Ventas (
            id INTEGER PRIMARY KEY, 
            id_mesa INTEGER NOT NULL, 
            total REAL NOT NULL, 
            metodo_pago TEXT, 
            descuento REAL DEFAULT 0, 
            paga_con REAL DEFAULT 0, 
            corte_id TEXT,  -- <--- ¡ESTA ES LA COLUMNA QUE FALTABA!
            fecha_hora TIMESTAMP
        )''')
        
    cursor.execute('''
        CREATE TABLE Detalle_Venta (
            id INTEGER PRIMARY KEY, 
            id_venta INTEGER, 
            id_producto INTEGER, 
            cantidad INTEGER NOT NULL, 
            precio_unitario REAL NOT NULL, 
            FOREIGN KEY (id_venta) REFERENCES Ventas(id), 
            FOREIGN KEY (id_producto) REFERENCES Productos(id)
        )''')
    
    # --- DATOS DEL MENÚ ---
    menu = {
        'ENTRADAS':[('Empanadas (Minilla y camarón c/ queso)',135.0,0),('Empanadas de queso',95.0,0),('Minilla',145.0,0),('Consomé especial',180.0,0),('Orden de tortillas al ajo',50.0,0),('Nuggets',195.0,0)],
        'CALDOS':[('Caldos de chilpachole',210.0,0),('Sopa de mariscos',240.0,0),('Caldo de camarón',210.0,0)],
        'CAMARONES DE RÍO Y MAR':[('Cam. Río/Mar Para pelar 1/2 kg',350.0,0),('Cam. Río/Mar Para pelar 1 kg',595.0,0),('Cam. Río/Mar Al ajo 1/2 kg',350.0,0),('Cam. Río/Mar Al ajo 1 kg',595.0,0),('Cam. Río/Mar Enchipotlados 1/2 kg',375.0,0),('Cam. Río/Mar Enchipotlados 1 kg',650.0,0),('Cam. Río/Mar A la chilpaya 1/2 kg',375.0,0),('Cam. Río/Mar A la chilpaya 1 kg',650.0,0),('Cam. Río/Mar Al chiltepín 1/2 kg',375.0,0),('Cam. Río/Mar Al chiltepín 1 kg',650.0,0)],
        'OSTRAS':[('Almejas (7 pzas.)',350.0,0),('Almejas coronadas',450.0,0)],
        'CAMARONES AL GUSTO':[('Camarones al ajo',210.0,0),('Camarones a la mantequilla',210.0,0),('Camarones al ajillo',220.0,0),('Camarones enchipotlados',240.0,0),('Camarones empanizados',240.0,0),('Camarones al tornado',240.0,0)],
        'ESPECIALIDADES DE LA CASA':[('Aguachile 1/2',240.0,0),('Aguachile Ord',340.0,0),('Aguachile de abulón 1/2',290.0,0),('Aguachile de abulón Ord',550.0,0),('Tumba barda',280.0,0),('Consomé de caracol',195.0,0),('Aguachile verde 1/2',220.0,0),('Aguachile verde Ord',330.0,0),('Aguachile rojo 1/2',220.0,0),('Aguachile rojo Ord',330.0,0),('Aguachile negro 1/2',220.0,0),('Aguachile negro Ord',300.0,0),('Hueva de lisa, naca',235.0,0)],
        'ENSALADAS':[('Ensalada de mariscos Med',335.0,0),('Ensalada de mariscos Gde',450.0,0),('Ensalada de camarón Med',350.0,0),('Ensalada de camarón Gde',450.0,0),('Jaiba a la mayonesa Gde',280.0,0)],
        'TACOS':[('Tacos de Pulpo (3 pzas.)',160.0,0),('Tacos al gobernador (3 pzas.)',160.0,0)],
        'MOJARRAS':[('Mojarra al ajo',0.0,1),('Mojarra a la sal',0.0,1),('Mojarra frita',0.0,1),('Mojarra al chiltepín',0.0,1),('Mojarra enchipotlada',0.0,1)],
        'PULPOS':[('Pulpo encebollado y al ajo',235.0,0),('Pulpo asado',255.0,0),('Pulpo al chiltepín',255.0,0),('Pulpo a la chilpaya',260.0,0)],
        'COCTELERÍA':[('Ceviche Med',120.0,0),('Ceviche Gde',170.0,0),('Coctel Ostión Med',130.0,0),('Coctel Ostión Gde',185.0,0),('Coctel Camarón Med',140.0,0),('Coctel Camarón Gde',195.0,0),('Coctel Caracol Med',140.0,0),('Coctel Caracol Gde',195.0,0),('Coctel Pulpo Med',160.0,0),('Coctel Pulpo Gde',210.0,0),('Campechano Med',155.0,0),('Campechano Gde',210.0,0),('Vuelve a la vida',220.0,0),('Ojo rojo Gde',210.0,0)],
        'BEBIDAS / CERVEZAS':[('Corona 1/2',45.0,0),('Victoria 1/2',45.0,0),('Modelo especial 1/2',60.0,0),('Modelo negra 1/2',60.0,0),('Ultra 1/2',55.0,0),('Corona 1/4',25.0,0),('Victoria 1/4',25.0,0),('Michelada',85.0,0),('Michelada c/ clamato',95.0,0),('Clamato preparado',80.0,0),('Chelada',65.0,0),('Trancazo',120.0,0),('Refresco',40.0,0),('Coca-Cola',45.0,0),('Botella de agua',20.0,0),('Agua mineral',35.0,0),('Mineral topochico',45.0,0),('Vaso de agua',40.0,0),('1/2 jarra de agua',95.0,0),('1/2 limonada mineral',140.0,0),('1 Lt limonada mineral',175.0,0),('1 Lt jarra de agua',145.0,0)],
        'POSTRES':[('Flan',55.0,0),('Carlota',45.0,0)],
        'EXTRAS':[('Tortilla',20.0,0),('Tostadas',20.0,0),('Aderezo',25.0,0)]
    }
    for cat, prods in menu.items():
        cursor.execute("INSERT INTO Categorias (nombre) VALUES (?)", (cat,))
        id_cat = cursor.lastrowid
        for nombre, precio, variable in prods:
            cursor.execute("INSERT INTO Productos (nombre, precio, id_categoria, precio_variable) VALUES (?,?,?,?)", (nombre, precio, id_cat, variable))
    
    conn.commit()
    conn.close()
    print(f"Base de datos '{DB_FILE}' creada y poblada con éxito.")

if __name__ == "__main__":
    crear_y_poblar_db()