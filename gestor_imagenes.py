import asyncio
import aiohttp
import logging
import random
from bs4 import BeautifulSoup
import urllib.parse
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GestorImagenesProductos:
    def __init__(self):
        logger.info("🟢 Gestor inicializado (Yandex + Google + DuckDuckGo fallback)")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    # -------------------------------------------------------
    #   🔍 YANDEX IMAGE SEARCH (PRIMARIO)
    # -------------------------------------------------------
    async def buscar_yandex(self, nombre: str, session: aiohttp.ClientSession):
        if not nombre.strip():
            return None

        query = urllib.parse.quote(nombre.strip())
        url = f"https://yandex.com/images/search?text={query}"

        try:
            await asyncio.sleep(random.uniform(0.5, 1.2))
            async with session.get(url, headers=self.headers, timeout=20) as resp:
                if resp.status != 200:
                    logger.debug(f"Yandex status: {resp.status}")
                    return None

                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                # Buscar en múltiples formatos de Yandex
                img_tag = (
                    soup.find("img", {"class": "serp-item__thumb"}) or
                    soup.find("img", {"class": "MMImage-Origin"}) or
                    soup.find("img", {"class": "serp-item__thumb-img"})
                )
                
                if img_tag:
                    src = img_tag.get("src") or img_tag.get("data-src")
                    if src:
                        if src.startswith("//"):
                            src = "https:" + src
                        if src.startswith("http"):
                            return src

                # Buscar en data de la página
                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string and "serp-item" in script.string:
                        matches = re.findall(r'"url":"(https?://[^"]+)"', script.string)
                        if matches:
                            return matches[0].replace("\\/", "/")

        except asyncio.TimeoutError:
            logger.debug(f"Timeout en Yandex: {nombre[:40]}")
        except Exception as e:
            logger.debug(f"Error Yandex: {str(e)[:100]}")
        
        return None

    # -------------------------------------------------------
    #   🔍 GOOGLE IMAGE SEARCH (BACKUP)
    # -------------------------------------------------------
    async def buscar_google(self, nombre: str, session: aiohttp.ClientSession):
        if not nombre.strip():
            return None

        query = urllib.parse.quote(nombre.strip())
        url = f"https://www.google.com/search?tbm=isch&q={query}"

        try:
            await asyncio.sleep(random.uniform(0.5, 1.3))
            async with session.get(url, headers=self.headers, timeout=20) as resp:
                if resp.status != 200:
                    return None

                html = await resp.text()
                
                # Buscar URLs en el JSON embebido
                matches = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html)
                for match in matches:
                    if "gstatic" not in match and len(match) > 50:
                        return match.split("?")[0]

                # Fallback: buscar imgs
                soup = BeautifulSoup(html, "html.parser")
                imgs = soup.find_all("img")
                
                for img in imgs[1:5]:  # Saltar el logo de Google
                    src = img.get("src") or img.get("data-src")
                    if src and src.startswith("http") and len(src) > 50:
                        return src

        except asyncio.TimeoutError:
            logger.debug(f"Timeout en Google: {nombre[:40]}")
        except Exception as e:
            logger.debug(f"Error Google: {str(e)[:100]}")
        
        return None

    # -------------------------------------------------------
    #   🔍 DUCKDUCKGO IMAGE SEARCH (BACKUP 2)
    # -------------------------------------------------------
    async def buscar_duckduckgo(self, nombre: str, session: aiohttp.ClientSession):
        if not nombre.strip():
            return None

        query = urllib.parse.quote(nombre.strip())
        
        try:
            # Primero obtener el token
            await asyncio.sleep(random.uniform(0.5, 1.0))
            url1 = f"https://duckduckgo.com/?q={query}&iax=images&ia=images"
            
            async with session.get(url1, headers=self.headers, timeout=15) as resp:
                if resp.status != 200:
                    return None
                
                html = await resp.text()
                vqd_match = re.search(r'vqd="([^"]+)"', html)
                if not vqd_match:
                    vqd_match = re.search(r'vqd=(\d+-\d+-\d+)', html)
                
                if not vqd_match:
                    return None
                
                vqd = vqd_match.group(1)
            
            # Ahora buscar imágenes
            await asyncio.sleep(random.uniform(0.3, 0.7))
            url2 = f"https://duckduckgo.com/i.js?q={query}&vqd={vqd}&l=us-en&p=1"
            
            async with session.get(url2, headers=self.headers, timeout=15) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                if data.get("results"):
                    return data["results"][0].get("image")
                    
        except Exception as e:
            logger.debug(f"Error DuckDuckGo: {str(e)[:100]}")
        
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
            logger.info(f"✅ {codigo}: Yandex")
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
            logger.info(f"✅ {codigo}: Google")
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True,
                    "url_github": url,
                    "fuente": "google",
                    "termino_busqueda": nombre
                }
            }

        # 3️⃣ Fallback a DuckDuckGo
        url = await self.buscar_duckduckgo(nombre, session)
        if url:
            logger.info(f"✅ {codigo}: DuckDuckGo")
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True,
                    "url_github": url,
                    "fuente": "duckduckgo",
                    "termino_busqueda": nombre
                }
            }

        logger.warning(f"❌ {codigo}: Sin imagen")
        return {
            "Codigo": codigo,
            "imagen": {"existe": False, "url_github": None}
        }

    # -------------------------------------------------------
    #   🔁 PROCESAR LOTES (35,000 productos)
    # -------------------------------------------------------
    async def procesar_lote(self, productos, concurrencia=2):
        """
        Procesa productos en lotes con límite de concurrencia ajustable
        
        Args:
            productos: Lista de productos a procesar
            concurrencia: Número de búsquedas simultáneas (default: 2)
        """
        resultados = []
        total = len(productos)

        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=2,
            ttl_dns_cache=300,
            ssl=False
        )
        
        session_timeout = aiohttp.ClientTimeout(
            total=None,  # Sin límite total
            connect=15,
            sock_read=20
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=session_timeout,
            headers=self.headers
        ) as session:

            sem = asyncio.Semaphore(concurrencia)

            async def procesar(idx, prod):
                async with sem:
                    try:
                        resultado = await self.procesar_producto(prod, session)
                        if (idx + 1) % 100 == 0:
                            logger.info(f"📊 Progreso: {idx + 1}/{total} ({(idx+1)/total*100:.1f}%)")
                        return resultado
                    except Exception as e:
                        logger.error(f"Error procesando {prod.get('Codigo')}: {e}")
                        return {
                            "Codigo": prod.get("Codigo", ""),
                            "imagen": {"existe": False, "url_github": None}
                        }

            tareas = [procesar(i, p) for i, p in enumerate(productos)]
            resultados = await asyncio.gather(*tareas, return_exceptions=True)
            
            # Filtrar excepciones
            resultados = [r for r in resultados if not isinstance(r, Exception)]

        exitosos = sum(1 for r in resultados if r.get("imagen", {}).get("existe"))
        logger.info(f"✅ Completado: {exitosos}/{total} imágenes encontradas ({exitosos/total*100:.1f}%)")

        return resultados


# -------------------------------------------------------
#   💡 EJEMPLO DE USO
# -------------------------------------------------------
async def main():
    productos = [
        {"Codigo": "001", "Nombre": "iPhone 15 Pro"},
        {"Codigo": "002", "Nombre": "Samsung Galaxy S24"},
        {"Codigo": "003", "Nombre": "MacBook Pro M3"},
        {"Codigo": "004", "Nombre": "PlayStation 5"},
        {"Codigo": "005", "Nombre": "Nintendo Switch OLED"},
    ]

    gestor = GestorImagenesProductos()
    resultados = await gestor.procesar_lote(productos, concurrencia=2)

    print("\n" + "="*60)
    print("RESULTADOS:")
    print("="*60)
    for r in resultados:
        print(f"\n{r['Codigo']}: {r['imagen'].get('fuente', 'NO ENCONTRADA')}")
        if r['imagen']['existe']:
            print(f"  URL: {r['imagen']['url_github'][:80]}...")


if __name__ == "__main__":
    asyncio.run(main())