"""Repara los INSERT '*U' que deja dwg2dxf (LibreDWG 0.13.3) con bloques dinámicos. Parchea el texto del DXF:
el JSON de dwgread trae el handle del block_header de cada INSERT; en el DXF ese handle es el BLOCK_RECORD
del bloque *Unnn (código 5 de la tabla BLOCK_RECORD). Solo para pruebas."""
import json, sys
dxf, js, out = sys.argv[1:4]
d = json.loads(open(js, 'rb').read().decode('latin-1'), strict=False)
ref = {o['handle'][2]: o['block_header'][3] for o in d['OBJECTS'] if o.get('entity') == 'INSERT' and o.get('block_header')}
L = open(dxf, 'rb').read().decode('latin-1').split('\n')
pares = [(L[i].strip(), L[i + 1]) for i in range(0, len(L) - 1, 2)]
# BLOCK_RECORD: handle -> nombre
brn, i = {}, 0
while i < len(pares):
    if pares[i] == ('0', 'BLOCK_RECORD') or (pares[i][0] == '0' and pares[i][1].strip() == 'BLOCK_RECORD'):
        h = n = None; j = i + 1
        while j < len(pares) and pares[j][0] != '0':
            if pares[j][0] == '5': h = int(pares[j][1].strip(), 16)
            if pares[j][0] == '2' and n is None: n = pares[j][1].strip()
            j += 1
        if h is not None: brn[h] = n
        i = j
    else:
        i += 1
ok = bad = 0
i = 0
while i < len(pares):
    if pares[i][0] == '0' and pares[i][1].strip() == 'INSERT':
        h = None; j = i + 1
        while j < len(pares) and pares[j][0] != '0':
            if pares[j][0] == '5' and h is None: h = int(pares[j][1].strip(), 16)
            if pares[j][0] == '2' and pares[j][1].strip() == '*U':
                n = brn.get(ref.get(h))
                if n: pares[j] = ('2', n); ok += 1
                else: bad += 1
            j += 1
        i = j
    else:
        i += 1
open(out, 'wb').write('\n'.join(f'{c}\n{v}' for c, v in pares).encode('latin-1') + b'\n')
print('reparados', ok, 'sin reparar', bad)
