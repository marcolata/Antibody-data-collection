# Importar librerias

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests
import re
import time

# ==========================================
# FUNCIONES INTERNAS (PRIVADAS)
# ==========================================

def _buscar_peso_uniprot(nombre_producto):
    """Consulta la API de UniProt como respaldo bioinformático."""
    print(f"    -> [ALERTA] Consultando base mundial UniProt para: {nombre_producto}...")
    try:
        nombre_limpio = re.sub(r'\s*(antibody|n-term|c-term|polyclonal|monoclonal|recombinant).*', '', nombre_producto, flags=re.IGNORECASE).strip()
        url = "https://rest.uniprot.org/uniprotkb/search"
        parametros = {
            "query": f"({nombre_limpio}) AND (reviewed:true) AND (organism_id:9606)",
            "size": 1,
            "fields": "sequence"
        }
        
        respuesta = requests.get(url, params=parametros, timeout=10)
        respuesta.raise_for_status() 
        data = respuesta.json()
        
        if data.get('results'):
            masa_daltons = data['results'][0].get('sequence', {}).get('molWeight')
            if masa_daltons:
                return f"~{round(masa_daltons / 1000)} kDa (Rescatado vía UniProt)"
            
        return "No encontrado en bases externas"
    except Exception as e:
        return f"Fallo en lectura de base externa: {str(e)}"


def _extractor_visual(texto_visible, keyword, palabra_a_evitar=None):
    """Extrae datos leyendo visualmente la pantalla, ignorando el HTML."""
    lineas = [linea.strip() for linea in texto_visible.split('\n') if linea.strip()]
    
    for i, linea in enumerate(lineas):
        if keyword.lower() in linea.lower():
            partes = re.split(f'{keyword}s?[.:]?', linea, flags=re.IGNORECASE)
            if len(partes) > 1 and partes[1].strip():
                sobrante = partes[1].strip(" :-\t")
                if len(sobrante) < 300 and keyword.lower() not in sobrante.lower():
                    if palabra_a_evitar and palabra_a_evitar.lower() in sobrante.lower(): continue
                    return sobrante
            
            if i + 1 < len(lineas):
                siguiente_linea = lineas[i+1].strip()
                if len(siguiente_linea) < 400 and not siguiente_linea.endswith(":"):
                    if palabra_a_evitar and palabra_a_evitar.lower() in siguiente_linea.lower(): continue
                    return siguiente_linea
                    
    return "No encontrado"

# ==========================================
# FUNCIÓN PRINCIPAL 
# ==========================================

def genetex_antibodies(numero_catalogo):
    """
    Función maestra. Recibe un número de catálogo de GeneTex y devuelve 
    un diccionario con todos los datos biológicos extraídos.
    """
    opciones = uc.ChromeOptions()
    driver = uc.Chrome(options=opciones, version_main=147)
    
    try:
        driver.get("https://www.genetex.com/")
        time.sleep(5) # Evasión de Cloudflare
        
        inputs = driver.find_elements(By.XPATH, "//input[@type='text' or @type='search']")
        search_box = next((inp for inp in inputs if inp.is_displayed()), None)
                
        if not search_box:
            return {"Catálogo": numero_catalogo, "Error": "Barra de búsqueda no visible."}
            
        search_box.clear()
        search_box.send_keys(numero_catalogo)
        search_box.send_keys(Keys.RETURN)
        time.sleep(6) 
        
        try:
            titulo = driver.find_element(By.TAG_NAME, 'h1').text
        except:
            titulo = "No encontrado"
            
        if "No Results were found" in titulo or "404" in titulo:
            return {"Catálogo": numero_catalogo, "Marca": "GeneTex", "Error": "Producto descontinuado."}
            
        texto_visible = driver.find_element(By.TAG_NAME, 'body').text
        datos = {"Catálogo": numero_catalogo, "Marca": "GeneTex", "Nombre": titulo}
        
        # --- Reactividad ---
        react = _extractor_visual(texto_visible, "Species Reactivity")
        datos['Reactividad'] = react if react != "No encontrado" else _extractor_visual(texto_visible, "Reactivity")
        
        # --- Aplicaciones y Diluciones ---
        apps_raw = _extractor_visual(texto_visible, "Applications")
        if apps_raw == "No encontrado": apps_raw = _extractor_visual(texto_visible, "Tested Applications")
            
        dil = _extractor_visual(texto_visible, "Recommended Dilution")
        if dil == "No encontrado": dil = _extractor_visual(texto_visible, "Dilution")
            
        patron_dilucion = r'\d+:\d+(?:-\d+:\d+)?|\d+(?:\.\d+)?\s*[-~]\s*\d+(?:\.\d+)?\s*(?:u|µ)g/ml'
        
        if dil != "No encontrado":
            datos['Diluciones'] = dil
            datos['Aplicaciones'] = apps_raw
        else:
            diluciones_encontradas = re.findall(patron_dilucion, apps_raw, re.IGNORECASE)
            if diluciones_encontradas:
                datos['Diluciones'] = ", ".join(diluciones_encontradas)
                datos['Aplicaciones'] = re.sub(patron_dilucion, '', apps_raw, flags=re.IGNORECASE).replace('  ', ' ').strip(' ,')
            else:
                dil_texto = re.findall(r'([A-Za-z-]{2,6}\s*1:\d+(?:[-~]1:\d+)?|\d+(?:\.\d+)?\s*[-~]\s*\d+(?:\.\d+)?\s*(?:u|µ)g/ml)', texto_visible, re.IGNORECASE)
                datos['Diluciones'] = " | ".join(set(dil_texto)) if dil_texto else "No encontrado"
                datos['Aplicaciones'] = apps_raw
        
        # --- Host e Isotipo ---
        host = _extractor_visual(texto_visible, "Host")
        isotipo = _extractor_visual(texto_visible, "Isotype")
        if host != "No encontrado" and isotipo != "No encontrado":
            datos['Host / Isotipo'] = f"{host} ({isotipo})"
        elif host != "No encontrado":
            datos['Host / Isotipo'] = host
        else:
            datos['Host / Isotipo'] = isotipo
        
        # --- Peso Molecular ---
        mw = _extractor_visual(texto_visible, "Observed MW")
        if mw == "No encontrado": mw = _extractor_visual(texto_visible, "Calculated MW")
        if mw == "No encontrado": mw = _extractor_visual(texto_visible, "Molecular Weight")
        
        if mw == "No encontrado":
            pesos = re.findall(r'(\d{2,3}\s*kDa)', texto_visible, re.IGNORECASE)
            mw = f"{pesos[0]} (Extraído)" if pesos else "No encontrado"
            
        datos['Peso Molecular'] = mw

        # --- Rescate UniProt ---
        if datos['Peso Molecular'] == "No encontrado":
            datos['Peso Molecular'] = _buscar_peso_uniprot(datos['Nombre'])

        return datos

    except Exception as e:
        return {"Catálogo": numero_catalogo, "Marca": "GeneTex", "Error": str(e)}
        
    finally:
        driver.quit()