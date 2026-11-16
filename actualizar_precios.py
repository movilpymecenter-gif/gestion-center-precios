#!/usr/bin/env python3
"""Actualiza precios.json desde los spans públicos de Gestión Center Cloud."""
import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

ORIGEN = 'https://www.gestioncentercloud.com.ar/'
ARCHIVO = Path(__file__).resolve().parent / 'precios.json'
IDENTIFICADORES = {
    'cloud_lite': 'lblPlanCloudLite',
    'cloud_pro': 'lblPlanCloudPro',
    'cloud_premium': 'lblPlanCloudPremium',
    'usuario_adicional': 'lblUserAdicLite',
}

def extraer(html, identificador):
    patron = rf'<span\b(?=[^>]*\bid\s*=\s*[\"\']{re.escape(identificador)}[\"\'])[^>]*>(.*?)</span\s*>'
    coincidencias = re.findall(patron, html, flags=re.I | re.S)
    if len(coincidencias) != 1:
        raise ValueError(f'{identificador}: se esperó un único elemento, se encontraron {len(coincidencias)}')
    texto = unescape(re.sub(r'<[^>]+>', '', coincidencias[0])).strip()
    if not re.fullmatch(r'\$?\s*\d[\d.,\s]*', texto):
        raise ValueError(f'{identificador}: formato inesperado: {texto!r}')
    numero = re.sub(r'[^0-9]', '', texto)
    valor = int(numero)
    if not 1000 <= valor <= 100000000:
        raise ValueError(f'{identificador}: valor fuera de rango: {valor}')
    return valor

def main():
    if not ARCHIVO.exists():
        raise FileNotFoundError(f'No existe {ARCHIVO}')
    actuales = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    for clave in IDENTIFICADORES:
        if not isinstance(actuales.get(clave), int) or actuales[clave] <= 0:
            raise ValueError(f'Precio actual inválido: {clave}')

    peticion = Request(ORIGEN, headers={'User-Agent': 'Mozilla/5.0 (compatible; GestionCenterPriceMonitor/1.0)'})
    with urlopen(peticion, timeout=30) as respuesta:
        codificacion = respuesta.headers.get_content_charset() or 'utf-8'
        html = respuesta.read().decode(codificacion, errors='replace')

    nuevos = {clave: extraer(html, identificador) for clave, identificador in IDENTIFICADORES.items()}
    # Protección ante errores de extracción o cambios extremos accidentales.
    for clave, nuevo in nuevos.items():
        anterior = actuales[clave]
        if not 0.5 <= nuevo / anterior <= 2.0:
            raise ValueError(f'{clave}: variación inusual ({anterior} -> {nuevo}); revisión manual necesaria')

    if all(actuales[clave] == nuevos[clave] for clave in IDENTIFICADORES):
        print('Sin cambios: precios.json permanece intacto.')
        return

    print('Cambios detectados:')
    for clave, nuevo in nuevos.items():
        if actuales[clave] != nuevo:
            print(f'  {clave}: {actuales[clave]} -> {nuevo}')
    actuales.update(nuevos)
    ARCHIVO.write_text(json.dumps(actuales, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('precios.json actualizado.')

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: no se actualizó precios.json: {error}', file=sys.stderr)
        sys.exit(1)
