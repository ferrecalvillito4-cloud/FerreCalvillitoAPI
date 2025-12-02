import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor SIMPLIFICADO de imágenes.
    Solo busca URLs y las guarda en GitHub (sin descargar archivos).
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        # ✅ No necesita directorio físico, solo caché en memoria
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado (solo URLs)")

    async def buscar_imagen_duckduckgo(self, termino: str, session: aiohttp.ClientSession) -> str:
        """Busca imagen en DuckDuckGo y devuelve la URL"""
        try:
            await asyncio.sleep(random.uniform(1.0, 2.2))

            # 1) Obtener token vqd
            async with session.get("https://duckduckgo.com/", params={"q": termino}, timeout=10) as resp:
                html = await resp.text()

            m = re.search(r'vqd=([\d-]+)&', html)
            if not m:
                return None

            vqd = m.group(1)

            # 2) Petición de imágenes
            url_json = "https://duckduckgo.com/i.js"
            params = {"q": termino, "vqd": vqd, "o": "json", "p": "1"}
            headers = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                ])
            }

            async with session.get(url_json, params=params, headers=headers, timeout=10) as resp:
                data = await resp.json()

            if "results" in data and data["results"]:
                url_imagen = data["results"][0]["image"]
                
                # 3) Verificar que la URL funcione
                try:
                    async with session.head(url_imagen, timeout=5) as test:
                        if test.status == 200:
                            return url_imagen
                except:
                    pass

            return None

        except Exception as e:
            logger.debug(f"Error DuckDuckGo: {e}")
            return None

    async def procesar_producto(self, codigo: str, nombre: str, descripcion: str, session: aiohttp.ClientSession) -> dict:
        """Busca URL de imagen para un producto usando solo el Nombre"""
        
        # ✅ Usar solo el nombre (tus productos no tienen Descripcion)
        termino = nombre.strip() if nombre else ""

        if not termino:
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": False,
                    "url_github": None
                }
            }

        # Limpiar el nombre (quitar caracteres especiales al inicio)
        termino_limpio = termino.lstrip('/').strip()
        logger.info(f"🔍 {codigo}: '{termino_limpio[:60]}'")

        # 2) Buscar imagen
        url_img = await self.buscar_imagen_duckduckgo(termino_limpio, session)

        if url_img:
            logger.info(f"   ✅ Encontrada")
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True,
                    "url_github": url_img
                }
            }
        else:
            logger.info(f"   ❌ Sin resultados")
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": False,
                    "url_github": None
                }
            }

    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 3,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 120
    ) -> list[dict]:
        """Procesa un lote de productos y devuelve resultados"""
        
        total = len(productos)
        resultados = []

        async with aiohttp.ClientSession() as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num} - {len(lote)} productos")
                logger.info(f"{'='*60}")

                # Limitar concurrencia
                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        return await self.procesar_producto(
                            prod.get("Codigo", ""),
                            prod.get("Nombre", ""),  # ✅ Solo usa Nombre
                            "",  # Descripcion vacío (no existe en tus productos)
                            session
                        )

                # Procesar lote
                tareas = [procesar_con_limite(p) for p in lote]
                lote_result = await asyncio.gather(*tareas, return_exceptions=True)
                
                # Filtrar errores
                lote_result = [r for r in lote_result if isinstance(r, dict)]
                resultados.extend(lote_result)

                # Contar éxitos
                encontradas = sum(1 for r in lote_result if r.get('imagen', {}).get('existe'))
                
                logger.info(f"\n✅ Lote {lote_num} completado")
                logger.info(f"   Imágenes: {encontradas}/{len(lote)}")
                logger.info(f"   Total: {len(resultados)}/{total}")

                # Pausa entre lotes
                if (i + productos_por_lote) < total:
                    logger.info(f"\n⏸️ Pausa de {pausa_entre_lotes}s...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        logger.info(f"   Total: {len(resultados)}")
        logger.info(f"   Encontradas: {sum(1 for r in resultados if r.get('imagen', {}).get('existe'))}")
        logger.info(f"{'='*60}\n")
        
        return resultados

    def obtener_progreso(self) -> dict:
        """Devuelve progreso básico"""
        return {
            "procesados": 0,
            "total": 0,
            "porcentaje": 0,
            "ultimo_lote": 0
        }