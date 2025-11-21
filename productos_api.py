import os
import json

PRODUCTOS_FILE = os.path.join(os.path.dirname(__file__), "productos.json")

# Lista global de productos
productos_api = []

def cargar_productos_api():
    """
    Carga los productos desde productos.json al iniciar la API
    """
    global productos_api
    
    print(f"🔍 Buscando productos en: {PRODUCTOS_FILE}")
    
    if os.path.exists(PRODUCTOS_FILE):
        try:
            with open(PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
                productos_api = datos if isinstance(datos, list) else []
            print(f"📦 Cargados {len(productos_api)} productos desde productos.json")
            if productos_api:
                print(f"   Primer producto: {productos_api[0]}")
        except Exception as e:
            productos_api = []
            print(f"❌ Error al cargar productos.json: {e}")
    else:
        productos_api = []
        print(f"⚠️ No se encontró productos.json en: {PRODUCTOS_FILE}")
        print(f"   Se creará cuando admin envíe productos")

def guardar_productos_api():
    """
    Guarda la lista de productos en productos.json
    """
    global productos_api
    try:
        with open(PRODUCTOS_FILE, "w", encoding="utf-8") as f:
            json.dump(productos_api, f, indent=2, ensure_ascii=False)
        print(f"✅ Guardados {len(productos_api)} productos en productos.json")
        
        # Verificar inmediatamente lo que se guardó
        with open(PRODUCTOS_FILE, "r", encoding="utf-8") as f:
            verificacion = json.load(f)
        print(f"🔍 Verificación: {len(verificacion)} productos en archivo")
        
    except Exception as e:
        print(f"❌ Error al guardar productos.json: {e}")

def obtener_productos_api():
    """
    Devuelve la lista actual de productos
    """
    global productos_api
    return productos_api if productos_api else []