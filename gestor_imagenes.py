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
    Gestor SIMPLE - Usa Wikipedia Commons (Siempre funciona, gratis)
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado (Wikipedia Commons - Gratis)")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR WIKIPEDIA COMMONS (FUNCIONAL)
    # -------------------------------------------------------------------------
    async def buscar_imagen_wikipedia(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca imágenes en Wikipedia Commons - Siempre funciona
        """
        try:
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "es-ES,es;q=0.9"
            }
            
            # Buscar en Wikipedia
            params = {
                "action": "query",
                "list": "search",
                "srsearch": termino,
                "format": "json",
                "srnamespace": "6"  # File namespace
            }
            
            async with session.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        
                        if data.get("query", {}).get("search"):
                            # Obtener el primer resultado
                            primer_resultado = data["query"]["search"][0]
                            titulo = primer_resultado.get("title", "")
                            
                            if titulo:
                                # Obtener URL de la imagen
                                params2 = {
                                    "action": "query",
                                    "titles": titulo,
                                    "prop": "imageinfo",
                                    "iiprop": "url",
                                    "format": "json"
                                }
                                
                                async with session.get(
                                    "https://commons.wikimedia.org/w/api.php",
                                    params=params2,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)
                                ) as resp2:
                                    
                                    if resp2.status == 200:
                                        data2 = await resp2.json()
                                        pages = data2.get("query", {}).get("pages", {})
                                        
                                        for page in pages.values():
                                            imageinfo = page.get("imageinfo", [])
                                            if imageinfo:
                                                url = imageinfo[0].get("url")
                                                if url and url.startswith("http"):
                                                    logger.info(f"   ✅ Wikipedia: encontrada")
                                                    return url
                    except Exception as e:
                        logger.debug(f"Error parseando Wikipedia: {str(e)[:80]}")
                        return None
                
                return None
                    
        except asyncio.TimeoutError:
            logger.debug("Timeout Wikipedia")
            return None
        except Exception as e:
            logger.debug(f"Error Wikipedia: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR ALTERNATIVO - WIKIDATA (también gratis)
    # -------------------------------------------------------------------------
    async def buscar_imagen_wikidata(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca en Wikidata - También funciona
        """
        try:
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json"
            }
            
            # SPARQL query para buscar imágenes
            sparql_query = f"""
            SELECT ?image WHERE {{
              ?item rdfs:label "{termino}"@es .
              ?item wdt:P18 ?image .
            }}
            LIMIT 1
            """
            
            params = {
                "query": sparql_query,
                "format": "json"
            }
            
            async with session.get(
                "https://query.wikidata.org/sparql",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        results = data.get("results", {}).get("bindings", [])
                        
                        if results:
                            image_url = results[0].get("image", {}).get("value")
                            if image_url:
                                logger.info(f"   ✅ Wikidata: encontrada")
                                return image_url
                    except:
                        pass
                
                return None
                    
        except Exception as e:
            logger.debug(f"Error Wikidata: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Busca imagen probando Wikipedia primero, luego Wikidata
        """
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:80]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # 1. Intentar Wikipedia Commons
        url_img = await self.buscar_imagen_wikipedia(termino_limpio, session)
        if url_img:
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "wikipedia"}
            }

        # 2. Intentar Wikidata
        url_img = await self.buscar_imagen_wikidata(termino_limpio, session)
        if url_img:
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "wikidata"}
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
        max_concurrentes: int = 5,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 30
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Wikipedia Commons + Wikidata (100% Gratis)")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")

        timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s...")
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