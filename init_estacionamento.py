from database import conectar, criar_tabelas

def criar_estacionamento_padrao():
    criar_tabelas()  # garante que as tabelas existem
    conn = conectar()
    cur = conn.cursor()

    # verifica se já existe algum estacionamento
    cur.execute("SELECT COUNT(*) FROM estacionamentos")
    total = cur.fetchone()[0]

    if total == 0:
        cur.execute("""
            INSERT INTO estacionamentos (nome, documento, codigo, telefone, email, ativo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Estacionamento Padrão",
            "00000000000000",
            "PADRAO",
            "31999999999",
            "contato@padrao.com",
            1
        ))
        conn.commit()
        print("Estacionamento Padrão criado com sucesso (id = 1).")
    else:
        print("Já existe estacionamento cadastrado. Nenhuma ação executada.")

    conn.close()

if __name__ == "__main__":
    criar_estacionamento_padrao()
