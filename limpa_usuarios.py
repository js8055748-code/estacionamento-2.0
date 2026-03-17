import sqlite3
import os

DB_NAME = "estacionamento.db"
caminho = os.path.join(os.path.dirname(__file__), DB_NAME)

conn = sqlite3.connect(caminho)
cur = conn.cursor()

# Veja primeiro os usuários atuais
print("ANTES:")
for row in cur.execute("SELECT id, nome, email, role, estacionamento_id FROM usuarios"):
    print(row)

# ===== AJUSTE AQUI O ID DO ADMIN =====
ID_ADMIN = 1  # se seu admin não for id 1, troque esse número

cur.execute("DELETE FROM usuarios WHERE id <> ?", (ID_ADMIN,))
conn.commit()

print("\nDEPOIS:")
for row in cur.execute("SELECT id, nome, email, role, estacionamento_id FROM usuarios"):
    print(row)

conn.close()
print("\nLimpeza concluída.")
