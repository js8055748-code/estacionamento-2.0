from database import conectar

def adicionar_coluna_bloqueado():
    conn = conectar()
    cur = conn.cursor()

    # Tenta adicionar a coluna 'bloqueado' com valor padrão 0 (desbloqueado)
    try:
        cur.execute("ALTER TABLE usuarios ADD COLUMN bloqueado INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        print("Coluna 'bloqueado' adicionada com sucesso à tabela 'usuarios'.")
    except Exception as e:
        print("Erro ao adicionar coluna 'bloqueado':", e)

    conn.close()

if __name__ == "__main__":
    adicionar_coluna_bloqueado()
