# ⚡ Inventario Electro Misiones

> Herramienta automatizada de scraping y generación de inventarios para catálogos PrestaShop, con interfaz gráfica moderna en Tkinter, vista previa interactiva y exportación a PDF y CSV.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-Tkinter%20(Pure)-orange)](#-interfaz-gráfica)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Output](https://img.shields.io/badge/Export-PDF%20%7C%20CSV-green)](#-archivos-de-salida)

---

## 📌 Descripción

Esta aplicación permite extraer el catálogo completo de productos de tiendas web basadas en PrestaShop (configurada por defecto para [Electro Misiones](https://www.electromisiones.com.ar)), resolviendo códigos de referencia comercial (SKU), nombres de artículos y enlaces canónicos.

Cuenta con un motor de scraping multihilo optimizado, un dashboard de monitoreo en tiempo real, un comparador inteligente de stock entre ejecuciones y generación de documentos listos para impresión y consulta rápida.

---

## ✨ Características principales

### 🚀 Extracción concurrente y resiliente

- Paginación directa consumiendo los endpoints JSON de PrestaShop, con fallback automático a parsing HTML mediante BeautifulSoup.
- Ingesta paralela mediante `ThreadPoolExecutor`, con control configurable de conexiones simultáneas (*workers*) para reducir la probabilidad de errores HTTP 429/403.
- Extracción complementaria desde `sitemap.xml` para capturar artículos que no figuren en los menús de categorías.
- Lectura selectiva de fichas individuales únicamente para los productos que no expongan su referencia en los listados generales.

### 🖥️ Interfaz gráfica moderna (Tkinter puro)

- Funciona de forma nativa sin dependencias pesadas de entornos visuales externos.
- Selector de tema **oscuro/claro**, con cambio dinámico en caliente y adaptación de la barra de título en Windows 10/11.
- Vista previa interactiva de hoja tipo PDF, con animación y desplazamiento en tiempo real mientras avanza la descarga.
- **Buscador instantáneo** integrado en la vista previa para consultar referencias y nombres sin necesidad de abrir visores externos.
- Escala gráfica adaptativa (*DPI Aware*) para monitores Full HD y 4K.

### 📊 Auditoría y comparativa de cambios

- Compara automáticamente el inventario actual con la ejecución previa mediante `inventario_anterior.json`.
- Informa métricas detalladas: altas de nuevos productos, bajas de artículos discontinuados y modificaciones de nombres o códigos de referencia.

### 📄 Archivos de salida profesionales

- **PDF tabulado:** formato ordenado alfabéticamente (A–Z), con encabezados por página, paginación continua y compatibilidad con búsqueda por texto (`Ctrl + F`).
- **CSV estructurado:** delimitado por punto y coma (`;`) y codificado en `utf-8-sig` para abrir directamente en Microsoft Excel sin problemas de tildes o caracteres especiales.

---

## 📁 Estructura del repositorio

```text
inventario-electromisiones/
├── inventario_gui.py             # Interfaz visual, renderizado, animaciones y buscador
├── inventario_electromisiones.py # Motor de red, parser PrestaShop, lógica de scraping y exportación
├── .gitignore                    # Reglas de exclusión de binarios, caché y datos locales
├── LICENSE                       # Licencia MIT
└── README.md                     # Documentación del proyecto
```

## 🛠️ Instalación y uso local

### Requisitos previos

- Python 3.10 o superior.

### 1. Clonar el repositorio

```bash
git clone https://github.com/wolkowyski/inventario-electromisiones.git
cd inventario-electromisiones
```

### 2. Instalar dependencias

```bash
python -m pip install requests beautifulsoup4 lxml fpdf2
```

### 3. Ejecutar la aplicación

Para iniciar la interfaz gráfica:

```bash
python inventario_gui.py
```

También es posible ejecutar el motor directamente desde la línea de comandos:

```bash
# Corrida completa
python inventario_electromisiones.py

# Prueba rápida (1 categoría y 3 fichas de muestra)
python inventario_electromisiones.py --probar

# Limitar conexiones en redes lentas o servidores estrictos
python inventario_electromisiones.py --workers 4

# Borrar el progreso previo y reiniciar desde cero
python inventario_electromisiones.py --reiniciar
```

## 📦 Compilación a ejecutable (.exe)

Para distribuir la aplicación a usuarios que no dispongan de Python instalado, se puede empaquetar en un único ejecutable utilizando PyInstaller.

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name "InventarioElectroMisiones" inventario_gui.py
```

El ejecutable resultante quedará en la carpeta `dist/` con el nombre `InventarioElectroMisiones.exe`.

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
