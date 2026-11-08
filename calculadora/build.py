"""Gera dist/: um HTML autocontido (scripts embutidos) a partir de src/index.html."""
import re, pathlib
base = pathlib.Path(__file__).parent
src = (base / 'src' / 'index.html').read_text(encoding='utf-8')
def inline(m):
    code = (base / 'src' / m.group(1)).read_text(encoding='utf-8')
    return f'<script>\n{code}\n</script>'
page = re.sub(r'<!--INLINE:([\w/.-]+)-->', inline, src)
out = base / 'dist'; out.mkdir(exist_ok=True)
(out / 'rescisao-artifact.html').write_text(page, encoding='utf-8')
standalone = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n'
  + page + '\n</body>\n</html>\n')
(out / 'calculadora-rescisao.html').write_text(standalone, encoding='utf-8')
print('ok', len(page))
