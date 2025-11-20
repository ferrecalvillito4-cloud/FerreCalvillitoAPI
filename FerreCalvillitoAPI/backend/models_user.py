# models_user.py
import json
import os
from typing import Optional

DB_USERS = os.path.join(os.path.dirname(__file__), "data_users.json")

def _leer():
    if not os.path.exists(DB_USERS):
        return {}
    with open(DB_USERS, "r", encoding="utf-8") as f:
        return json.load(f)

def _guardar(data):
    with open(DB_USERS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def crear_usuario(correo: str, nombre: str, password_hashed: str):
    data = _leer()
    if correo in data:
        return False
    data[correo] = {"nombre": nombre, "password": password_hashed, "carrito": []}
    _guardar(data)
    return True

def obtener_usuario(correo: str) -> Optional[dict]:
    return _leer().get(correo)

def guardar_carrito(correo: str, carrito: list):
    data = _leer()
    if correo not in data: return False
    data[correo]["carrito"] = carrito
    _guardar(data)
    return True

def obtener_carrito(correo: str):
    u = obtener_usuario(correo)
    return u.get("carrito", []) if u else []
