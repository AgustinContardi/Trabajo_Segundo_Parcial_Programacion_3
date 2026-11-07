import sys
sys.path.insert(0, '.')
from app.modules.libros.router import router, router_admin
print('libros: OK')
print('router routes:', len(router.routes))
print('router_admin routes:', len(router_admin.routes))
for r in router_admin.routes:
    methods = sorted(r.methods) if r.methods else 'N/A'
    print(f'  {methods} -> {r.path}')