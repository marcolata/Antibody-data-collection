import requests
from bs4 import BeautifulSoup
import re
import time

def proteintech_antibodies(lista_catalogos):
    """
    Recibe una lista de catálogos, extrae su información de Proteintech
    y devuelve una lista de diccionarios con los resultados.
    """
    
    # --- 1. Función auxiliar anidada para extraer texto ---
    def extraer_especificacion(soup, keyword, palabra_a_evitar=None):
        patron = re.compile(keyword, re.IGNORECASE)
        etiquetas = soup.find_all(string=patron)
        posibles_valores = []
        
        for texto in etiquetas:
            if len(texto.strip()) > 35: continue 
                
            tr = texto.find_parent('tr')
            if tr:
                celdas = tr.find_all(['th', 'td'])
                for i, celda in enumerate(celdas):
                    if keyword.lower() in celda.get_text().lower() and i + 1 < len(celdas):
                        for br in celdas[i+1].find_all("br"):
                            br.replace_with(" | ")
                        valor = celdas[i+1].get_text(" ", strip=True)
                        if palabra_a_evitar and palabra_a_evitar.lower() in valor.lower(): continue
                        posibles_valores.append(valor)
                continue
                
            contenedor = texto.find_parent(['li', 'p', 'div', 'td'])
            if contenedor:
                for br in contenedor.find_all("br"):
                    br.replace_with(" | ")
                texto_completo = contenedor.get_text(" ", strip=True)
                partes = re.split(patron, texto_completo, maxsplit=1)
                
                if len(partes) > 1:
                    sobrante = partes[1].strip(" :-\n")
                    if 0 < len(sobrante) < 250: 
                        if palabra_a_evitar and palabra_a_evitar.lower() in sobrante.lower(): continue
                        posibles_valores.append(sobrante)

        if posibles_valores:
            validos = [v for v in posibles_valores if len(v) > 2]
            if validos:
                mejor = max(validos, key=len)
                mejor = re.sub(r'See \d+ publications? below', ',', mejor, flags=re.IGNORECASE)
                mejor = re.sub(r'\s*\|\s*', ' | ', mejor)
                mejor = re.sub(r'\s*,\s*', ', ', mejor)
                mejor = re.sub(r'(,\s*)+', ', ', mejor)
                return mejor.strip(" ,|")
                
        return "No encontrado"

    # --- 2. Función auxiliar anidada para buscar un solo anticuerpo ---
    def buscar_anticuerpo(numero_catalogo):
        url = f"https://www.ptglab.com/products/{numero_catalogo}.htm"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.encoding = 'utf-8' 
            response.raise_for_status() 
            soup = BeautifulSoup(response.text, 'html.parser')
            
            datos = {"Catálogo": numero_catalogo}
            
            h1 = soup.find('h1')
            datos['Nombre'] = h1.get_text(strip=True) if h1 else "No encontrado"
            
            react = extraer_especificacion(soup, "Tested Reactivity")
            datos['Reactividad'] = react if react != "No encontrado" else extraer_especificacion(soup, "Reactivity")
            
            apps = extraer_especificacion(soup, "Tested Applications", "dilution")
            datos['Aplicaciones'] = apps if apps != "No encontrado" else extraer_especificacion(soup, "Applications", "dilution")
            
            iso = extraer_especificacion(soup, "Host / Isotype")
            datos['Isotipo'] = iso if iso != "No encontrado" else extraer_especificacion(soup, "Isotype")
            
            dil = extraer_especificacion(soup, "Recommended Dilution")
            datos['Diluciones'] = dil if dil != "No encontrado" else extraer_especificacion(soup, "Dilution")
            
            mw_calculado = extraer_especificacion(soup, "Calculated MW")
            mw_observado = extraer_especificacion(soup, "Observed MW")
            
            if mw_calculado != "No encontrado" and mw_observado != "No encontrado":
                datos['Peso Molecular'] = f"Calculado: {mw_calculado} | Observado: {mw_observado}"
            elif mw_calculado != "No encontrado":
                datos['Peso Molecular'] = f"Calculado: {mw_calculado}"
            elif mw_observado != "No encontrado":
                datos['Peso Molecular'] = f"Observado: {mw_observado}"
            else:
                mw_general = extraer_especificacion(soup, "Molecular Weight")
                datos['Peso Molecular'] = mw_general if mw_general != "No encontrado" else extraer_especificacion(soup, "MW")

            return datos

        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                return {"Catálogo": numero_catalogo, "Nombre": "Error 404: Descontinuado o no existe"}
            return {"Catálogo": numero_catalogo, "Nombre": f"Error HTTP {response.status_code}"}
        except Exception as e:
            return {"Catálogo": numero_catalogo, "Nombre": f"Error de conexión: {e}"}

    # --- 3. Lógica principal de ejecución ---
    resultados_totales = []
    print(f"\nIniciando búsqueda de {len(lista_catalogos)} anticuerpos...")
    
    for i, catalogo in enumerate(lista_catalogos, 1):
        print("\n" + "=" * 80)
        print(f"[{i}/{len(lista_catalogos)}] ANALIZANDO CATÁLOGO: {catalogo}")
        print("=" * 80)
        
        datos = buscar_anticuerpo(catalogo)
        
        if datos:
            resultados_totales.append(datos) # Guardamos el diccionario en la lista
            for clave, valor in datos.items():
                print(f"• {clave.upper()}: {valor}")
        else:
            print(f"No se pudo extraer información para {catalogo}.")
            
        if i < len(lista_catalogos):
            time.sleep(2)
            
    print("\n" + "=" * 80)
    print(" BÚSQUEDA FINALIZADA ".center(80, "="))
    print("=" * 80 + "\n")
    
    return resultados_totales # Retornamos los datos para usarlos en otro archivo