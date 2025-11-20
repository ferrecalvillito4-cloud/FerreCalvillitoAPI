# en tu main o nuevo archivo routers/auth.py
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from auth_utils import hash_password, verify_password, create_token, decode_token
import models_user

app = FastAPI(...)  # ya tienes esto

class RegistroRequest(BaseModel):
    nombre: str
    correo: EmailStr
    password: str

class LoginRequest(BaseModel):
    correo: EmailStr
    password: str

@app.post("/auth/registro")
async def registro(req: RegistroRequest):
    if models_user.obtener_usuario(req.correo):
        raise HTTPException(status_code=400, detail="Correo ya registrado")
    hashed = hash_password(req.password)
    ok = models_user.crear_usuario(req.correo, req.nombre, hashed)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo crear usuario")
    token = create_token({"correo": req.correo, "nombre": req.nombre})
    return {"token": token, "nombre": req.nombre}

@app.post("/auth/login")
async def login(req: LoginRequest):
    u = models_user.obtener_usuario(req.correo)
    if not u or not verify_password(req.password, u["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_token({"correo": req.correo, "nombre": u["nombre"]})
    return {"token": token, "nombre": u["nombre"]}

# Dependencia sencilla para recuperar correo del header Authorization: Bearer <token>
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Falta cabecera Authorization")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Formato Authorization inválido")
    payload = decode_token(parts[1])
    if not payload or "correo" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    return payload

# Endpoints para carrito persistente
from typing import List, Any

@app.get("/usuario/carrito")
async def obtener_carrito_usuario(user=Depends(get_current_user)):
    correo = user["correo"]
    carrito = models_user.obtener_carrito(correo)
    return {"carrito": carrito}

@app.post("/usuario/carrito")
async def guardar_carrito_usuario(payload: dict, user=Depends(get_current_user)):
    # payload expected: { "carrito": [ {Codigo, Nombre, Precio, Existencia, cantidad}, ... ] }
    correo = user["correo"]
    ok = models_user.guardar_carrito(correo, payload.get("carrito", []))
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo guardar carrito")
    return {"mensaje": "Carrito guardado"}
