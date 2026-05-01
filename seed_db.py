"""Run once to initialize the database and set your PIX key."""
import sys
from database import init_db, set_pix_key, get_pix_key

init_db()

if len(sys.argv) > 1:
    pix_key = sys.argv[1]
    set_pix_key(pix_key)
    print(f"PIX key definida: {pix_key}")
else:
    current = get_pix_key()
    if current:
        print(f"PIX key atual: {current}")
        print("Para alterar: python seed_db.py <nova-chave-pix>")
    else:
        print("Banco inicializado. Defina sua chave PIX:")
        print("  python seed_db.py <sua-chave-pix>")
