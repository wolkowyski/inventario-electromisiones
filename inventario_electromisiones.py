#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de extracción para Inventario Electro Misiones (PrestaShop).
Genera PDF y CSV, y gestiona el histórico para comparar cambios.
"""
import argparse
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://www.electromisiones.com.ar"
DOMINIO = "electromisiones.com.ar"
PROGRESO = "progreso_inventario.json"
HISTORICO = "inventario_anterior.json"
PDF_OUT = "inventario_electromisiones.pdf"
CSV_OUT = "inventario_electromisiones.csv"

TIMEOUT = (8, 25)
MAX_PAGINAS = 150
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JSON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

RE_CAT = re.compile(r"^/(\d+)-[\w\-]+$")
RE_PROD = re.compile(r"/(\d+)-[^/]+\.html$")

ERRORES = []
SESION = requests.Session()


def sopa(html):
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def configurar_sesion(workers):
    SESION.headers.update({"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9"})
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=False,
    )
    adapter = HTTPAdapter(pool_connections=workers, pool_maxsize=workers, max_retries=retry)
    SESION.mount("https://", adapter)
    SESION.mount("http://", adapter)


def get(url, **kw):
    try:
        r = SESION.get(url, timeout=TIMEOUT, **kw)
        if r.status_code in (403, 429):
            ERRORES.append(f"HTTP {r.status_code}: {url}")
        return r
    except requests.RequestException as e:
        ERRORES.append(f"{type(e).__name__}: {url}")
        return None


def limpiar_url(u):
    return urljoin(BASE + "/", u.strip()).split("#")[0].split("?")[0]


def limpiar_txt(s):
    return " ".join(str(s).split())


def es_del_sitio(u):
    return urlparse(u).netloc.lower().replace("www.", "") == DOMINIO


def id_de_producto(url):
    m = RE_PROD.search(urlparse(url).path)
    return m.group(1) if m else ""


def descubrir_categorias():
    cats = {"2": f"{BASE}/2-inicio"}
    r = get(BASE)
    if r is not None and r.status_code == 200:
        soup = sopa(r.text)
        for a in soup.find_all("a", href=True):
            u = limpiar_url(a["href"])
            if not es_del_sitio(u):
                continue
            m = RE_CAT.match(urlparse(u).path)
            if m:
                cats[m.group(1)] = u
    return cats


def escanear_categoria(url):
    hallados = {}
    pagina = 1
    while pagina <= MAX_PAGINAS:
        r = get(url, params={"page": pagina, "resultsPerPage": 36}, headers=JSON_HEADERS)
        if r is None or r.status_code != 200:
            break
        nuevos = 0

        if "json" in r.headers.get("Content-Type", "").lower():
            try:
                data = r.json()
            except ValueError:
                break
            lista = data.get("products") or []
            for it in lista:
                link = limpiar_url(it.get("url") or it.get("canonical_url") or "")
                pid = str(it.get("id_product") or "") or id_de_producto(link)
                if not pid or pid in hallados:
                    continue
                ref = it.get("reference") or it.get("reference_to_display") or ""
                hallados[pid] = {
                    "url": link,
                    "nombre": limpiar_txt(it.get("name") or ""),
                    "codigo": str(ref).strip(),
                }
                nuevos += 1
            paginas_total = (data.get("pagination") or {}).get("pages_count")
            if not lista or nuevos == 0:
                break
            if paginas_total and pagina >= int(paginas_total):
                break
        else:
            soup = sopa(r.text)
            for a in soup.find_all("a", href=True):
                link = limpiar_url(a["href"])
                pid = id_de_producto(link)
                if pid and es_del_sitio(link) and pid not in hallados:
                    hallados[pid] = {"url": link, "nombre": "", "codigo": ""}
                    nuevos += 1
            if nuevos == 0:
                break
        pagina += 1
    return hallados


def urls_desde_sitemap():
    encontrados, vistos = {}, set()
    pendientes = [f"{BASE}/1_index_sitemap.xml", f"{BASE}/sitemap.xml"]
    while pendientes:
        u = pendientes.pop()
        if u in vistos:
            continue
        vistos.add(u)
        r = get(u)
        if r is None or r.status_code != 200:
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text):
            loc = loc.replace("&amp;", "&")
            if urlparse(loc).path.endswith(".xml"):
                pendientes.append(loc)
            else:
                pid = id_de_producto(loc)
                if pid and es_del_sitio(loc):
                    encontrados[pid] = limpiar_url(loc)
    return encontrados


def extraer_ficha(url):
    r = get(url)
    if r is None or r.status_code != 200:
        return None
    soup = sopa(r.text)
    nombre, codigo = "", ""

    el = soup.select_one("#product-details[data-product]") or soup.select_one("[data-product]")
    if el:
        try:
            d = json.loads(el["data-product"])
            codigo = str(d.get("reference") or d.get("reference_to_display") or "").strip()
            nombre = d.get("name") or ""
        except (ValueError, TypeError):
            pass

    if not codigo:
        for sel in (".product-reference span", "#product_reference span", '[itemprop="sku"]'):
            e = soup.select_one(sel)
            if e:
                codigo = (e.get("content") or e.get_text(strip=True) or "").strip()
                if codigo:
                    break

    if not codigo:
        for sc in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(sc.string or "")
            except ValueError:
                continue
            for d in (data if isinstance(data, list) else [data]):
                if isinstance(d, dict) and d.get("sku"):
                    codigo = str(d["sku"]).strip()
                    break
            if codigo:
                break

    if not codigo:
        m = re.search(r"(?:Referencia|REF\.?)\s*:?\s*([A-Za-z0-9][\w\-./]{1,40})",
                      soup.get_text(" ", strip=True))
        if m:
            codigo = m.group(1)

    if not nombre:
        h1 = soup.find("h1")
        nombre = h1.get_text(strip=True) if h1 else ""
    if not (nombre or codigo):
        return None
    return {"nombre": limpiar_txt(nombre), "codigo": codigo}


def cargar(ruta=PROGRESO):
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def guardar(prods, ruta=PROGRESO):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prods, f, ensure_ascii=False)
    os.replace(tmp, ruta)


def fusionar(prods, nuevos):
    for pid, d in nuevos.items():
        actual = prods.setdefault(pid, {"url": d["url"], "nombre": "", "codigo": ""})
        for k in ("nombre", "codigo"):
            if d.get(k) and not actual.get(k):
                actual[k] = d[k]


def calcular_diferencias(anterior, actual):
    """Compara el inventario actual con el anterior por ID de producto."""
    if not anterior:
        return {"nuevos": len(actual), "bajas": 0, "modificados": 0, "hay_anterior": False}
    nuevos = sum(1 for pid in actual if pid not in anterior)
    bajas = sum(1 for pid in anterior if pid not in actual)
    modificados = 0
    for pid, act in actual.items():
        if pid in anterior:
            ant = anterior[pid]
            if ant.get("codigo") != act.get("codigo") or ant.get("nombre") != act.get("nombre"):
                modificados += 1
    return {"nuevos": nuevos, "bajas": bajas, "modificados": modificados, "hay_anterior": True}


_TRANS = str.maketrans({"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
                        "″": '"', "′": "'", "Ω": "Ohm", "…": "...", "•": "-",
                        "≥": ">=", "≤": "<=", "\u00a0": " "})


def a_latin1(s):
    return s.translate(_TRANS).encode("latin-1", "replace").decode("latin-1")


class InventarioPDF(FPDF):
    def __init__(self, total):
        super().__init__()
        self.total = total

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 6, f"Inventario Electro Misiones - {self.total} articulos (Referencia / Nombre)",
                  new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(230, 230, 230)
        self.cell(30, 6, "Referencia", border=1, fill=True)
        self.cell(165, 6, "Nombre del articulo", border=1, new_x="LMARGIN", new_y="NEXT", fill=True)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}} - Ctrl+F para buscar por nombre o referencia",
                  align="C")


def ajustar(pdf, txt, ancho):
    if pdf.get_string_width(txt) <= ancho:
        return txt
    while txt and pdf.get_string_width(txt + "...") > ancho:
        txt = txt[:-1]
    return txt + "..."


def generar_pdf(lista, salida=PDF_OUT, progreso=None):
    pdf = InventarioPDF(len(lista))
    pdf.set_margins(left=7.5, top=10, right=7.5)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 7.5)
    total = len(lista)
    for i, p in enumerate(lista, 1):
        cod = ajustar(pdf, a_latin1(p["codigo"] or "S/REF"), 27.8)
        nom = ajustar(pdf, a_latin1(p["nombre"]), 162.8)
        pdf.cell(30, 5, cod, border=1)
        pdf.cell(165, 5, nom, border=1, new_x="LMARGIN", new_y="NEXT")
        if progreso and (i % 100 == 0 or i == total):
            progreso(i, total, pdf.page_no())
    paginas = pdf.page_no()
    pdf.output(salida)
    return paginas


def generar_csv(lista, salida=CSV_OUT):
    with open(salida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["referencia", "nombre", "url"])
        for p in lista:
            w.writerow([p["codigo"], p["nombre"], p["url"]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    print("Ejecución directa por consola. Usa 'inventario_gui.py' para la interfaz completa.")