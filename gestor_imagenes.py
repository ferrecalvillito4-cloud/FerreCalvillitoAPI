import asyncio
import aiohttp
import logging
import random
from bs4 import BeautifulSoup
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GestorImagenes:
    def __init__(self):
        logger.info("🟢 Gestor inicializado (Yandex + Google fallback)")

    # -------------------------------------------------------
    #   🔍 YANDEX IMAGE SEARCH (PRIMARIO)
    # -------------------------------------------------------
    async def buscar_yandex(self, nombre: str, session: aiohttp.ClientSession):
        if not nombre.strip():
            return None

        query = urllib.parse.quote(nombre.strip())
        url = f"https://yandex.com/images/search?text={query}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            await asyncio.sleep(random.uniform(0.3, 0.8))
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    return None

                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                img_tag = soup.find("img", {"class": "serp-item__thumb"})
                if not img_tag:
                    return None

                src = img_tag.get("src")
                if src.startswith("//"):
                    src = "https:" + src

                return src

        except Exception:
            return None

    # -------------------------------------------------------
    #   🔍 GOOGLE IMAGE SEARCH (BACKUP)
    # -------------------------------------------------------
    async def buscar_google(self, nombre: str, session: aiohttp.ClientSession):
        if not nombre.strip():
            return None

        query = urllib.parse.quote(nombre.strip())
        url = f"https://www.google.com/search?tbm=isch&q={query}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            await asyncio.sleep(random.uniform(0.3, 0.9))
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    return None

                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                imgs = soup.find_all("img")

                if len(imgs) >= 2:
                    return imgs[1].get("src")

        except Exception:
            return None

        return None

    # -------------------------------------------------------
    #   🔁 PROCESAR PRODUCTO
    # -------------------------------------------------------
    async def procesar_producto(self, producto, session):
        codigo = producto.get("Codigo", "").strip()
        nombre = producto.get("Nombre", "").strip()

        if not nombre:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        logger.info(f"🔍 {codigo}: {nombre[:60]}")

        # 1️⃣ Intentar Yandex
        url = await self.buscar_yandex(nombre, session)
        if url:
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True,
                    "url_github": url,
                    "fuente": "yandex",
                    "termino_busqueda": nombre
                }
            }

        # 2️⃣ Fallback a Google
        url = await self.buscar_google(nombre, session)
        if url:
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True,
                    "url_github": url,
                    "fuente": "google",
                    "termino_busqueda": nombre
                }
            }

        return {
            "Codigo": codigo,
            "imagen": {"existe": False, "url_github": None}
        }

    # -------------------------------------------------------
    #   🔁 PROCESAR LOTES (35,000 productos)
    # -------------------------------------------------------
    async def procesar_lote(self, productos):
        resultados = []

        connector = aiohttp.TCPConnector(limit_per_host=3, ssl=False)
        session_timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=session_timeout
        ) as session:

            sem = asyncio.Semaphore(3)  # 3 búsquedas simultáneas

            async def procesar(prod):
                async with sem:
                    return await self.procesar_producto(prod, session)

            tareas = [procesar(p) for p in productos]

            resultados = await asyncio.gather(*tareas)

        return resultados