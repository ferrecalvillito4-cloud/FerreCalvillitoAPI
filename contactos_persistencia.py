import os
import json
import threading
from datetime import datetime
from uuid import uuid4

# =============================
# 📁 Configuración de archivos
# =============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIRECCIONES_FILE = os.path.join(SCRIPT_DIR, "direcciones.json")
TELEFONOS_FILE = os.path.join(SCRIPT_DIR, "telefonos.json")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backups")

# Crear directorio de backups si no existe
os.makedirs(BACKUP_DIR, exist_ok=True)

# =============================
# 🧠 Estado global
# =============================
direcciones = []
telefonos = []
lock = threading.RLock()  # Lock para thread-safety

# =============================
# 📝 Funciones auxiliares
# =============================

def crear_backup(archivo_path, tipo="archivo"):
    """Crea un backup antes de guardar"""
    if os.path.exists(archivo_path):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = os.path.basename(archivo_path).replace(".json", "")
            backup_path = os.path.join(BACKUP_DIR, f"{nombre_archivo}_backup_{timestamp}.json")
            
            with open(archivo_path, "r", encoding="utf-8") as f:
                backup_data = f.read()
            
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(backup_data)
            
            print(f"💾 Backup creado ({tipo}): {os.path.basename(backup_path)}")
        except Exception as e:
            print(f"⚠️ Error creando backup ({tipo}): {e}")


def _guardar_archivo(archivo_path, datos, tipo="datos"):
    """
    Guarda datos a un archivo de forma SEGURA (atomic write)
    """
    try:
        print(f"\n{'='*60}")
        print(f"💾 GUARDANDO {tipo.upper()}")
        print(f"   Archivo: {os.path.basename(archivo_path)}")
        print(f"   Items: {len(datos)}")
        
        # 1️⃣ Backup del anterior
        crear_backup(archivo_path, tipo=tipo)
        
        # 2️⃣ Escribir a temporal
        temp_file = archivo_path + ".tmp"
        
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Escrito a temporal")
        
        # 3️⃣ Verificar temporal
        with open(temp_file, "r", encoding="utf-8") as f:
            verificacion = json.load(f)
        
        print(f"   ✅ Verificación: {len(verificacion)} items")
        
        # 4️⃣ Reemplazar original
        if os.path.exists(archivo_path):
            os.remove(archivo_path)
        
        os.rename(temp_file, archivo_path)
        print(f"   ✅ Archivo guardado exitosamente")
        
        # 5️⃣ Verificación final
        with open(archivo_path, "r", encoding="utf-8") as f:
            verificacion_final = json.load(f)
        
        print(f"✅ {tipo.upper()} GUARDADO: {len(verificacion_final)} items")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ ERROR guardando {tipo}: {e}")
        # Limpiar temporal si existe
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        raise


def _cargar_archivo(archivo_path, tipo="datos"):
    """
    Carga datos de un archivo de forma segura
    """
    print(f"\n🔍 CARGANDO {tipo.upper()}")
    print(f"   Ruta: {archivo_path}")
    print(f"   Existe: {os.path.exists(archivo_path)}")
    
    if os.path.exists(archivo_path):
        try:
            with open(archivo_path, "r", encoding="utf-8") as f:
                contenido = f.read()
                
            if not contenido.strip():
                print(f"   ⚠️ Archivo vacío")
                return []
            
            datos = json.loads(contenido)
            resultado = datos if isinstance(datos, list) else []
            
            print(f"✅ Cargados {len(resultado)} {tipo}s")
            if resultado and isinstance(resultado[0], dict):
                print(f"   Campos disponibles: {list(resultado[0].keys())}")
            
            return resultado
            
        except json.JSONDecodeError as e:
            print(f"❌ Error de JSON en {tipo}: {e}")
            return []
        except Exception as e:
            print(f"❌ Error cargando {tipo}: {e}")
            return []
    else:
        print(f"⚠️ Archivo no existe - se creará en primer guardado")
        return []


# =============================
# 📍 FUNCIONES PARA DIRECCIONES
# =============================

def cargar_direcciones():
    """Carga direcciones desde archivo"""
    global direcciones
    with lock:
        direcciones = _cargar_archivo(DIRECCIONES_FILE, tipo="dirección")


def guardar_direcciones():
    """Guarda direcciones al archivo"""
    global direcciones
    with lock:
        _guardar_archivo(DIRECCIONES_FILE, direcciones, tipo="direcciones")


def obtener_direcciones():
    """Devuelve copia de direcciones (thread-safe)"""
    with lock:
        return direcciones.copy()


def agregar_direccion(calle, numero, colonia, ciudad, estado, cp):
    """Agrega una dirección y la guarda"""
    global direcciones
    
    nueva_dir = {
        "id": str(uuid4()),
        "calle": calle,
        "numero": numero,
        "colonia": colonia,
        "ciudad": ciudad,
        "estado": estado,
        "cp": cp,
        "fecha_creacion": datetime.now().isoformat()
    }
    
    with lock:
        direcciones.append(nueva_dir)
    
    guardar_direcciones()
    print(f"✅ Dirección agregada: {nueva_dir['id']}")
    return nueva_dir


def actualizar_direccion(id_dir, calle, numero, colonia, ciudad, estado, cp):
    """Actualiza una dirección existente"""
    global direcciones
    
    with lock:
        direccion = next((d for d in direcciones if d.get("id") == id_dir), None)
        if not direccion:
            return None
        
        direccion.update({
            "calle": calle,
            "numero": numero,
            "colonia": colonia,
            "ciudad": ciudad,
            "estado": estado,
            "cp": cp,
            "fecha_actualizacion": datetime.now().isoformat()
        })
    
    guardar_direcciones()
    print(f"✅ Dirección actualizada: {id_dir}")
    return direccion


def eliminar_direccion(id_dir):
    """Elimina una dirección"""
    global direcciones
    
    with lock:
        direcciones = [d for d in direcciones if d.get("id") != id_dir]
    
    guardar_direcciones()
    print(f"✅ Dirección eliminada: {id_dir}")


def limpiar_direcciones():
    """Limpia todas las direcciones"""
    global direcciones
    with lock:
        direcciones = []
    guardar_direcciones()
    print(f"🗑️ Direcciones limpiadas")


# =============================
# 📞 FUNCIONES PARA TELÉFONOS
# =============================

def cargar_telefonos():
    """Carga teléfonos desde archivo"""
    global telefonos
    with lock:
        telefonos = _cargar_archivo(TELEFONOS_FILE, tipo="teléfono")


def guardar_telefonos():
    """Guarda teléfonos al archivo"""
    global telefonos
    with lock:
        _guardar_archivo(TELEFONOS_FILE, telefonos, tipo="teléfonos")


def obtener_telefonos():
    """Devuelve copia de teléfonos (thread-safe)"""
    with lock:
        return telefonos.copy()


def agregar_telefono(numero, descripcion=""):
    """Agrega un teléfono y lo guarda"""
    global telefonos
    
    nuevo_tel = {
        "id": str(uuid4()),
        "numero": numero,
        "descripcion": descripcion,
        "fecha_creacion": datetime.now().isoformat()
    }
    
    with lock:
        telefonos.append(nuevo_tel)
    
    guardar_telefonos()
    print(f"✅ Teléfono agregado: {nuevo_tel['id']}")
    return nuevo_tel


def actualizar_telefono(id_tel, numero, descripcion=""):
    """Actualiza un teléfono existente"""
    global telefonos
    
    with lock:
        telefono = next((t for t in telefonos if t.get("id") == id_tel), None)
        if not telefono:
            return None
        
        telefono.update({
            "numero": numero,
            "descripcion": descripcion,
            "fecha_actualizacion": datetime.now().isoformat()
        })
    
    guardar_telefonos()
    print(f"✅ Teléfono actualizado: {id_tel}")
    return telefono


def eliminar_telefono(id_tel):
    """Elimina un teléfono"""
    global telefonos
    
    with lock:
        telefonos = [t for t in telefonos if t.get("id") != id_tel]
    
    guardar_telefonos()
    print(f"✅ Teléfono eliminado: {id_tel}")


def limpiar_telefonos():
    """Limpia todos los teléfonos"""
    global telefonos
    with lock:
        telefonos = []
    guardar_telefonos()
    print(f"🗑️ Teléfonos limpiados")


# =============================
# 🚀 INICIALIZACIÓN
# =============================
print(f"\n{'#'*70}")
print(f"# MÓDULO contactos_persistencia INICIALIZADO")
print(f"# Script dir: {SCRIPT_DIR}")
print(f"# Direcciones: {DIRECCIONES_FILE}")
print(f"# Teléfonos: {TELEFONOS_FILE}")
print(f"# Backups: {BACKUP_DIR}")
print(f"{'#'*70}\n")