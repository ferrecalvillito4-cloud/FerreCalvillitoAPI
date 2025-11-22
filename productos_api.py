import os
import json
import threading
from datetime import datetime

# =============================
# 📁 Configuración de archivos
# =============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTOS_FILE = os.path.join(SCRIPT_DIR, "productos.json")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backups")

# Crear directorio de backups si no existe
os.makedirs(BACKUP_DIR, exist_ok=True)

# =============================
# 🧠 Estado global
# =============================
productos_api = []
lock = threading.RLock()  # Lock para evitar condiciones de carrera

# =============================
# 📝 Funciones de persistencia
# =============================

def crear_backup():
    """Crea un backup de productos.json antes de guardarlo"""
    if os.path.exists(PRODUCTOS_FILE):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"productos_backup_{timestamp}.json")
            
            with open(PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                backup_data = f.read()
            
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(backup_data)
            
            print(f"💾 Backup creado: {backup_path}")
        except Exception as e:
            print(f"⚠️ Error creando backup: {e}")


def cargar_productos_api():
    """
    Carga los productos desde productos.json al iniciar la API
    """
    global productos_api
    
    print(f"\n{'='*70}")
    print(f"🔍 INICIANDO CARGA DE PRODUCTOS")
    print(f"   Ruta buscada: {PRODUCTOS_FILE}")
    print(f"   Existe: {os.path.exists(PRODUCTOS_FILE)}")
    
    with lock:
        if os.path.exists(PRODUCTOS_FILE):
            try:
                with open(PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                    contenido = f.read()
                    print(f"   Tamaño del archivo: {len(contenido)} bytes")
                    
                    if not contenido.strip():
                        print(f"   ⚠️ Archivo vacío")
                        productos_api = []
                    else:
                        datos = json.loads(contenido)
                        productos_api = datos if isinstance(datos, list) else []
                
                print(f"✅ Cargados {len(productos_api)} productos")
                if productos_api:
                    print(f"   Primer producto: {productos_api[0].get('Codigo', 'N/A')} - {productos_api[0].get('Nombre', 'N/A')}")
                    print(f"   Campos disponibles: {list(productos_api[0].keys())}")
                
            except json.JSONDecodeError as e:
                print(f"❌ Error de JSON: {e}")
                productos_api = []
            except Exception as e:
                print(f"❌ Error al cargar: {e}")
                productos_api = []
        else:
            productos_api = []
            print(f"⚠️ Archivo no existe - se creará en primer guardado")
    
    print(f"{'='*70}\n")


def guardar_productos_api():
    """
    Guarda la lista de productos en productos.json de forma SEGURA
    """
    global productos_api
    
    print(f"\n{'='*70}")
    print(f"💾 GUARDANDO PRODUCTOS")
    print(f"   Total a guardar: {len(productos_api)}")
    
    with lock:
        try:
            # 1️⃣ Crear backup de lo anterior
            crear_backup()
            
            # 2️⃣ Guardar a archivo temporal primero
            temp_file = PRODUCTOS_FILE + ".tmp"
            
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(productos_api, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Escrito a archivo temporal")
            
            # 3️⃣ Verificar que el temporal se escribió correctamente
            with open(temp_file, "r", encoding="utf-8") as f:
                verificacion = json.load(f)
            
            print(f"   ✅ Verificación de temporal OK ({len(verificacion)} items)")
            
            # 4️⃣ Reemplazar archivo original
            if os.path.exists(PRODUCTOS_FILE):
                os.remove(PRODUCTOS_FILE)
            
            os.rename(temp_file, PRODUCTOS_FILE)
            print(f"   ✅ Archivo reemplazado exitosamente")
            
            # 5️⃣ Verificación final
            with open(PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                verificacion_final = json.load(f)
            
            print(f"✅ GUARDADO EXITOSO: {len(verificacion_final)} productos en {PRODUCTOS_FILE}")
            
            # 6️⃣ Info del archivo
            size_mb = os.path.getsize(PRODUCTOS_FILE) / (1024 * 1024)
            print(f"   Tamaño: {size_mb:.2f} MB")
            
        except Exception as e:
            print(f"❌ ERROR AL GUARDAR: {e}")
            # Limpiar temporal si falló
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise
    
    print(f"{'='*70}\n")


def obtener_productos_api():
    """
    Devuelve una COPIA de la lista de productos (thread-safe)
    """
    with lock:
        return productos_api.copy() if productos_api else []


def actualizar_productos_api(nueva_lista):
    """
    Actualiza la lista de productos de forma segura
    """
    global productos_api
    
    print(f"\n{'='*70}")
    print(f"🔄 ACTUALIZANDO PRODUCTOS")
    print(f"   Anterior: {len(productos_api)} items")
    print(f"   Nuevo: {len(nueva_lista)} items")
    
    with lock:
        productos_api = nueva_lista if isinstance(nueva_lista, list) else []
        print(f"   ✅ Variable global actualizada")
    
    # Guardar inmediatamente
    guardar_productos_api()
    
    print(f"{'='*70}\n")


def limpiar_productos():
    """Limpia todos los productos y guarda"""
    global productos_api
    
    with lock:
        productos_api = []
    
    guardar_productos_api()
    print(f"🗑️ Productos limpiados y guardados")


# =============================
# 🧹 Inicialización automática
# =============================
print(f"\n{'#'*70}")
print(f"# MÓDULO productos_api INICIALIZADO")
print(f"# Ruta: {SCRIPT_DIR}")
print(f"# Archivo: {PRODUCTOS_FILE}")
print(f"# Backups: {BACKUP_DIR}")
print(f"{'#'*70}\n")