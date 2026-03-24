import sqlite3
import os

DB_NAME = "estacionamento.db"
caminho = os.path.join(os.path.dirname(__file__), DB_NAME)

conn = sqlite3.connect(caminho)
cur = conn.cursor()

email_resp = "teste3@teste3.com"

print("USUARIO RESPONSÁVEL:")
cur.execute("""
    SELECT id, nome, email, estacionamento_id, role
    FROM usuarios
    WHERE email = ?
""", (email_resp,))
user = cur.fetchone()
print(user)

if not user:
    print("Nenhum usuário encontrado com esse e-mail.")
    conn.close()
    exit()

est_id = user[3]

print("\nESTACIONAMENTO ANTES:")
cur.execute("""
    SELECT id, nome, ativo
    FROM estacionamentos
    WHERE id = ?
""", (est_id,))
est = cur.fetchone()
print(est)

if not est:
    print("Nenhum estacionamento encontrado com esse id.")
    conn.close()
    exit()

# Força ativo = 1
cur.execute("UPDATE estacionamentos SET ativo = 1 WHERE id = ?", (est_id,))
conn.commit()

print("\nESTACIONAMENTO DEPOIS:")
cur.execute("""
    SELECT id, nome, ativo
    FROM estacionamentos
    WHERE id = ?
""", (est_id,))
est2 = cur.fetchone()
print(est2)

conn.close()
print("\nAjuste concluído.")
