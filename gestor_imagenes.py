import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
from pathlib import Path
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    def __init__(self, directorio_imagenes: str, github_token: str = None, github_repo: str = None):
        self.directorio_imagenes = directorio_imagenes
        Path(directorio_imagenes).mkdir(parents=True, exist_ok=True)
        self.cache_file = os.path.join(directorio_imagenes, "descargadas.json")
        self.progreso_file = os.path.join(directorio_imagenes, "progreso.json")
        self.cache = self._cargar_cache()
        self.progreso = self._cargar_progreso()

    # ------------------------------------------------------------------
    # CACHÉ y PROGRESO
    # ------------------------------------------------------------------

    def _cargar_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _guardar_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def _cargar_progreso(self) -> dict:
        if os.path.exists(self.progreso_file):
            try:
                with open(self.progreso_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"procesados": 0, "total": 0, "ultimo_lote": 0}
        return {"procesados": 0, "total": 0, "ultimo_lote": 0}

    def _guardar_progreso(self):
        with open(self.progreso_file, 'w', encoding='utf-8') as f:
            json.dump(self.progreso, f, indent=2)

    # ------------------------------------------------------------------
    # BUSCADOR DE IMÁGENES (DUCKDUCKGO – GRATIS)
    # ------------------------------------------------------------------

    async def buscar_imagen_duckduckgo(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca imagen GRATIS usando DuckDuckGo.
        TOTALMENTE AUTOMÁTICO – SIN API KEY.
        """
        try:
            await asyncio.sleep(random.uniform(1.0, 2.2))  # retraso aleatorio

            # 1) Obtener token `vqd`
            async with session.get("https://duckduckgo.com/", params={"q": termino}) as resp:
                html = await resp.text()

            m = re.search(r'vqd=([\d-]+)&', html)
            if not m:
                return None

            vqd = m.group(1)

            # 2) Petición JSON con resultados
            url_json = "https://duckduckgo.com/i.js"
            params = {"q": termino, "vqd": vqd, "o": "json", "p": "1"}

            headers = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Mozilla/5.0 (X11; Linux x86_64)"
                ])
            }

            async with session.get(url_json, params=params, headers=headers) as resp:
                data = await resp.json()

            if "results" in data and data["results"]:
                return data["results"][0]["image"]

            return None

        except Exception as e:
            logger.error(f"❌ Error DuckDuckGo: {e}")
            return None

    # ------------------------------------------------------------------
    # VERIFICACIÓN
    # ------------------------------------------------------------------

    async def verificar_url_imagen(self, url: str, session: aiohttp.ClientSession) -> bool:
        try:
            async with session.head(url, timeout=10) as resp:
                if resp.status == 200:
                    tipo = resp.headers.get("Content-Type", "").lower()
                    return "image" in tipo
        except:
            pass
        return False

    # ------------------------------------------------------------------
    # PROCESAR PRODUCTO
    # ------------------------------------------------------------------

    async def procesar_producto(self, codigo: str, nombre: str, descripcion: str, session: aiohttp.ClientSession) -> dict:

        # 1) Revisar caché
        if codigo in self.cache:
            cached = self.cache[codigo]
            return {
                "Codigo": codigo,  # ✅ Cambio: mayúscula
                "Nombre": nombre,   # ✅ Cambio: mayúscula
                "Descripcion": descripcion,  # ✅ Cambio: mayúscula
                "imagen": {  # ✅ Estructura correcta
                    "url_github": cached.get("url_github"),
                    "existe": bool(cached.get("url_github")),
                    "fuente": "cache"
                }
            }

        # ✅ USAR NOMBRE si no hay Descripcion
        termino = (descripcion or nombre or "").strip()

        if not termino:
            return {
                "Codigo": codigo,
                "Nombre": nombre,
                "Descripcion": descripcion,
                "imagen": {
                    "url_github": None,
                    "existe": False,
                    "fuente": "sin_descripcion"
                }
            }

        # 2) Buscar imagen gratis (DDG)
        url_img = await self.buscar_imagen_duckduckgo(termino, session)

        # 3) Verificar existencia
        if url_img:
            if not await self.verificar_url_imagen(url_img, session):
                url_img = None

        # 4) Guardar en caché
        if url_img:
            self.cache[codigo] = {
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": url_img,
                "fecha": datetime.now().isoformat()
            }
            self._guardar_cache()

        return {
            "Codigo": codigo,
            "Nombre": nombre,
            "Descripcion": descripcion,
            "imagen": {
                "url_github": url_img,
                "existe": bool(url_img),
                "fuente": "duckduckgo" if url_img else "no_encontrada"
            }
        }

    # ------------------------------------------------------------------
    # PROCESAMIENTO POR LOTES
    # ------------------------------------------------------------------

    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 2,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 120
    ) -> list[dict]:

        total = len(productos)
        self.progreso["total"] = total

        resultados = []

        async with aiohttp.ClientSession() as session:
            for i in range(0, total, productos_por_lote):

                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1

                logger.info(f"\n📦 LOTE {lote_num} - {len(lote)} productos...")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        return await self.procesar_producto(
                            prod.get("Codigo"),
                            prod.get("Nombre"),
                            prod.get("Descripcion", prod.get("Nombre")),  # ✅ Usar Nombre si no hay Descripcion
                            session
                        )

                tareas = [procesar_con_limite(p) for p in lote]
                lote_result = await asyncio.gather(*tareas, return_exceptions=False)

                resultados.extend(lote_result)

                # Actualizar progreso
                self.progreso["procesados"] = len(resultados)
                self.progreso["ultimo_lote"] = lote_num
                self._guardar_progreso()

                # ✅ Contar imágenes encontradas correctamente
                imagenes_encontradas = sum(
                    1 for r in lote_result 
                    if r.get('imagen', {}).get('existe')
                )
                
                logger.info(f"   ✔ Lote {lote_num} completado. Imágenes: {imagenes_encontradas}/{len(lote)}")

                if (i + productos_por_lote) < total:
                    logger.info(f"   ⏸️ Pausa {pausa_entre_lotes} segundos…")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info("\n🎉 PROCESAMIENTO TOTAL COMPLETADO 🎉")
        return resultados

    def obtener_progreso(self) -> dict:
        p = self.progreso
        total = max(p.get("total", 1), 1)
        return {
            "procesados": p.get("procesados", 0),
            "total": p.get("total", 0),
            "porcentaje": round((p.get("procesados", 0) / total) * 100, 2),
            "ultimo_lote": p.get("ultimo_lote", 0)
        }