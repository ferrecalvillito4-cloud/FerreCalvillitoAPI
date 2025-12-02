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
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado (solo URLs)")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR DE IMÁGENES DUCKDUCKGO 2025 (FUNCIONA)
    # -------------------------------------------------------------------------
    async def buscar_imagen_duckduckgo(self, termino: str, session: aiohttp.ClientSession) -> str:
        """Versión actualizada 2025 — obtiene imagen usando DuckDuckGo"""

        try:
            # 1. Obtener el vqd
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "es-ES,es;q=0.9"
            }

            async with session.get("https://duckduckgo.com/", params={"q": termino}, headers=headers, timeout=10) as resp:
                html = await resp.text()

            # Regex actualizado para vqd 2024–2025
            m = re.search(r'vqd=([\d-]+)\;', html)
            if not m:
                return None

            vqd = m.group(1)

            # 2. Endpoint de imágenes
            params = {
                "q": termino,
                "vqd": vqd,
                "o": "json",
                "ia": "images",
                "iax": "images"
            }

            headers2 = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                ]),
                "Accept": "application/json"
            }

            async with session.get("https://duckduckgo.com/i.js", params=params, headers=headers2, timeout=10) as resp:
                data = await resp.json()

            # 3. Validar
            if "results" not in data or len(data["results"]) == 0:
                return None

            url_imagen = data["results"][0]["image"]

            # 4. NO HEAD -> muchos servidores lo bloquean
            return url_imagen

        except Exception as e:
            logger.debug(f"Error DuckDuckGo: {e}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR UN SOLO PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, descripcion: str, session: aiohttp.ClientSession) -> dict:
        """Busca URL de imagen para un producto usando solo el Nombre."""
        
        termino = nombre.strip() if nombre else ""

        if not termino:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()
        logger.info(f"🔍 {codigo}: '{termino_limpio[:60]}'")

        # Buscar imagen
        url_img = await self.buscar_imagen_duckduckgo(termino_limpio, session)

        if url_img:
            logger.info("   ✅ Encontrada")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img}
            }

        logger.info("   ❌ Sin resultados")
        return {
            "Codigo": codigo,
            "imagen": {"existe": False, "url_github": None}
        }

    # -------------------------------------------------------------------------
    # 🔁 PROCESAR LOTES
    # -------------------------------------------------------------------------
    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 3,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 120
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")

        async with aiohttp.ClientSession() as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num} - {len(lote)} productos")
                logger.info(f"{'='*60}")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        try:
                            return await self.procesar_producto(
                                prod.get("Codigo", ""),
                                prod.get("Nombre", ""),
                                "",
                                session
                            )
                        except Exception as e:
                            logger.error(f"❌ Error procesando {prod.get('Codigo')}: {e}")
                            return {
                                "Codigo": prod.get("Codigo"),
                                "imagen": {"existe": False, "url_github": None}
                            }

                tareas = [procesar_con_limite(p) for p in lote]
                
                lote_result = await asyncio.gather(*tareas, return_exceptions=True)
                lote_result = [r for r in lote_result if isinstance(r, dict)]
                resultados.extend(lote_result)

                encontradas = sum(1 for r in lote_result if r.get('imagen', {}).get('existe'))

                logger.info(f"\n✅ Lote {lote_num} completado")
                logger.info(f"   Procesados: {len(lote_result)}/{len(lote)}")
                logger.info(f"   Imágenes encontradas: {encontradas}")
                logger.info(f"   Total acumulado: {len(resultados)}/{total}")

                if (i + productos_por_lote) < total:
                    logger.info(f"\n⏸️ Pausa de {pausa_entre_lotes}s antes del siguiente lote...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        logger.info(f"   Total procesados: {len(resultados)}")
        logger.info(f"   Imágenes encontradas: {sum(1 for r in resultados if r.get('imagen', {}).get('existe'))}")
        logger.info(f"{'='*60}\n")
        
        return resultados

    # -------------------------------------------------------------------------
    # 📊 PROGRESO
    # -------------------------------------------------------------------------
    def obtener_progreso(self) -> dict:
        return {
            "procesados": 0,
            "total": 0,
            "porcentaje": 0,
            "ultimo_lote": 0
        }
