import asyncio
import aiohttp
import logging
import random
from bs4 import BeautifulSoup
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesGoogle:
    """
    Gestor de imágenes usando Google Images
    """
    def __init__(self):
        logger.info("✅ Gestor inicializado (Google Images)")

    # -------------------------------------------------------------------------
    # 🔍 BUSCAR IMAGEN EN GOOGLE
    # -------------------------------------------------------------------------
    async def buscar_imagen_google(self, nombre: str, session: aiohttp.ClientSession) -> str:
        """
        Busca la primera imagen en Google Images usando el nombre exacto
        """
        if not nombre or not nombre.strip():
            return None
        
        query = urllib.parse.quote(nombre.strip())
        url = f"https://www.google.com/search?tbm=isch&q={query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            # Espera aleatoria para evitar bloqueos
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ Error {resp.status} al buscar: {nombre}")
                    return None
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                images = soup.find_all("img")
                if len(images) < 2:
                    return None
                # La primera imagen real suele estar en la segunda etiqueta <img>
                return images[1].get("src")
        except Exception as e:
            logger.error(f"❌ Error al buscar imagen '{nombre}': {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Procesa un producto y obtiene la URL de la imagen
        """
        nombre_limpio = nombre.strip() if nombre else ""
        if not nombre_limpio:
            return {"Codigo": codigo, "imagen": {"existe": False, "url_github": None}}
        
        logger.info(f"🔍 {codigo}: '{nombre_limpio[:60]}'")
        url_img = await self.buscar_imagen_google(nombre_limpio, session)

        if url_img:
            logger.info(f"   ✅ Imagen encontrada")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "google", "termino_busqueda": nombre_limpio}
            }

        logger.info("   ❌ Sin resultados")
        return {"Codigo": codigo, "imagen": {"existe": False, "url_github": None}}

    # -------------------------------------------------------------------------
    # 🔁 PROCESAR LOTES
    # -------------------------------------------------------------------------
    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 3,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 30
    ) -> list[dict]:
        total = len(productos)
        resultados = []
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS (Google Images)")

        connector = aiohttp.TCPConnector(limit_per_host=3, ssl=False)
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1
                lotes_totales = (total + productos_por_lote - 1) // productos_por_lote

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num}/{lotes_totales} - {len(lote)} productos")
                logger.info(f"{'='*60}")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        return await self.procesar_producto(
                            prod.get("Codigo", ""),
                            prod.get("Nombre", ""),
                            session
                        )

                tareas = [procesar_con_limite(p) for p in lote]
                lote_result = await asyncio.gather(*tareas, return_exceptions=True)
                lote_result = [r for r in lote_result if isinstance(r, dict)]
                resultados.extend(lote_result)

                encontradas = sum(1 for r in lote_result if r.get("imagen", {}).get("existe"))
                logger.info(f"\n✅ Lote {lote_num} completado")
                logger.info(f"   Procesados: {len(lote_result)}/{len(lote)}")
                logger.info(f"   Encontradas: {encontradas}")
                logger.info(f"   Tasa éxito: {(encontradas/len(lote_result)*100):.1f}%" if lote_result else "0%")

                if (i + productos_por_lote) < total:
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info("\n🎉 PROCESAMIENTO COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get("imagen", {}).get("existe"))
        logger.info(f"   Total procesados: {len(resultados)}")
        logger.info(f"   Imágenes encontradas: {total_encontradas}")
        logger.info(f"   Tasa éxito: {(total_encontradas/len(resultados)*100 if resultados else 0):.1f}%\n")
        return resultados

    # -------------------------------------------------------------------------
    # 📊 PROGRESO (opcional)
    # -------------------------------------------------------------------------
    def obtener_progreso(self):
        return {"procesados": 0, "total": 0, "porcentaje": 0, "ultimo_lote": 0}
