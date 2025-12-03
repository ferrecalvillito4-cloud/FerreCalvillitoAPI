import os
import json
import asyncio
import aiohttp
from datetime import datetime
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor FUNCIONAL - Pexels API (imágenes REALES, gratis, permite automatización)
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        # Pexels API key - GRATIS, permite automatización
        # Registrate en https://www.pexels.com/api/
        self.pexels_key = os.getenv("PEXELS_API_KEY", "7uKpeg5kqPkJgnpyd4Uq5F6kSj0rt5GJH9RPZLJbqN2i6hfWBfO3IdeZ")
        logger.info("✅ Gestor inicializado (Pexels API - Imágenes reales + Automatización permitida)")

    # -------------------------------------------------------------------------
    # 🔍 BUSCAR EN PEXELS (IMÁGENES REALES)
    # -------------------------------------------------------------------------
    async def buscar_imagen_pexels(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca imágenes REALES en Pexels API
        Pexels permite automatización, es gratis y tiene alto límite
        """
        try:
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            headers = {
                "Authorization": self.pexels_key,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            
            params = {
                "query": termino,
                "per_page": 1,
                "page": 1
            }
            
            async with session.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=12)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        
                        if data.get("photos") and len(data["photos"]) > 0:
                            # Obtener URL de la imagen
                            img = data["photos"][0]
                            url = img.get("src", {}).get("large")
                            
                            if url and url.startswith("http"):
                                logger.info(f"   ✅ Imagen real encontrada")
                                return url
                    except Exception as e:
                        logger.debug(f"Error parseando Pexels: {str(e)[:80]}")
                        return None
                
                elif resp.status == 401:
                    logger.debug("Pexels: API key inválida o no configurada")
                    return None
                else:
                    logger.debug(f"Pexels respondió: {resp.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.debug("Timeout Pexels")
            return None
        except Exception as e:
            logger.debug(f"Error Pexels: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Busca imagen REAL en Pexels según el nombre del producto
        """
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:100]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # Buscar en Pexels
        url_img = await self.buscar_imagen_pexels(termino_limpio, session)
        
        if url_img:
            logger.info(f"   ✅ Encontrada")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "pexels"}
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
        pausa_entre_lotes: int = 60
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Pexels API (imágenes REALES de productos)")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")
        logger.info(f"   ✅ Pexels permite automatización sin restricciones")

        timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=10)
        
        connector = aiohttp.TCPConnector(limit_per_host=3, ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1
                lotes_totales = (total // productos_por_lote) + (1 if total % productos_por_lote else 0)

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num}/{lotes_totales} - {len(lote)} productos")
                logger.info(f"{'='*60}")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        try:
                            return await self.procesar_producto(
                                prod.get("Codigo", ""),
                                prod.get("Nombre", ""),
                                session
                            )
                        except Exception as e:
                            logger.error(f"❌ {prod.get('Codigo')}: {str(e)[:50]}")
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
                logger.info(f"   Encontradas: {encontradas}")
                logger.info(f"   Total acumulado: {len(resultados)}/{total}")

                if (i + productos_por_lote) < total:
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s antes del siguiente lote...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get('imagen', {}).get('existe'))
        tasa = (total_encontradas/len(resultados)*100) if resultados else 0
        logger.info(f"   Total procesados: {len(resultados)}")
        logger.info(f"   Imágenes encontradas: {total_encontradas}")
        logger.info(f"   Tasa éxito: {tasa:.1f}%")
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