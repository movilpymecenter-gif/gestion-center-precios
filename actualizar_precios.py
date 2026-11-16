#!/usr/bin/env python3
"""Sincroniza precios públicos; ante errores no modifica precios.json."""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ORIGEN = 'https://www.gestioncentercloud.com.ar/'
ARCHIVO = Path(__file__).resolve().parent / 'precios.json'
IDS = {'cloud_lite': 'lblPlanCloudLite', 'cloud_pro': 'lblPlanCloudPro', 'cloud_premium': 'lblPlanCloudPremium', 'usuario_adicional': 'lblUserAdicLite'}

class Lector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.valores = {v: [] for v in IDS.values()}
        self.activo = None
        self.buffer = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'span':
            identificador = dict(attrs).get('id', '')
            if identificador in self.valores:
                self.activo = identificador
                self.buffer = []
    def handle_data(self, data):
        if self.activo:
            self.buffer.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'span' and self.activo:
            self.valores[self.activo].append(''.join(self.buffer).strip())
            self.activo = None
            self.buffer = []

def precio(texto, identificador):
    if not re.fullmatch(r'\$?\s*\d[\d.,\s]*', texto):
        raise ValueError(f'{identificador}: texto inesperado {texto!r}')
    numero = int(re.sub(r'\D', '', texto))
    if not 1000 <= numero <= 100000000:
        raise ValueError(f'{identificador}: valor fuera de rango')
    return numero

def main():
    actuales = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    for clave in IDS:
        if type(actuales.get(clave)) is not int or actuales[clave] <= 0:
            raise ValueError(f'Precio actual inválido: {clave}')
    solicitud = Request(ORIGEN, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-AR,es;q=0.9,en;q=0.7',
    })
    with urlopen(solicitud, timeout=30) as respuesta:
        contenido = respuesta.read()
        tipo = respuesta.headers.get('Content-Type', '')
        codificacion = respuesta.headers.get_content_charset() or 'utf-8'
        print(f'HTTP {respuesta.status}; URL final: {respuesta.url}; bytes: {len(contenido)}; tipo: {tipo}')
    html = contenido.decode(codificacion, errors='replace')
    lector = Lector()
    lector.feed(html)
    nuevos = {}
    for clave, identificador in IDS.items():
        encontrados = lector.valores[identificador]
        if len(encontrados) != 1:
            print('Diagnóstico: título HTML:', re.findall(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)[:1])
            print('Diagnóstico: aparece sección Planes:', 'id="Planes"' in html or 'id="planes"' in html)
            raise ValueError(f'{identificador}: encontrados {len(encontrados)} elementos')
        nuevos[clave] = precio(encontrados[0], identificador)
    for clave, nuevo in nuevos.items():
        anterior = actuales[clave]
        if not 0.5 <= nuevo / anterior <= 2:
            raise ValueError(f'{clave}: variación inusual {anterior} -> {nuevo}; revisión manual necesaria')
    cambios = {clave: (actuales[clave], nuevo) for clave, nuevo in nuevos.items() if actuales[clave] != nuevo}
    if not cambios:
        print('Sin cambios: precios.json permanece intacto.')
        return
    for clave, (anterior, nuevo) in cambios.items():
        print(f'{clave}: {anterior} -> {nuevo}')
    actuales.update(nuevos)
    ARCHIVO.write_text(json.dumps(actuales, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('precios.json actualizado.')

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: no se actualizó precios.json: {error}', file=sys.stderr)
        sys.exit(1)
