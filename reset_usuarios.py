from database import conectar

def reset_usuarios():
    conn = conectar()
    cur = conn.cursor()

    # Apaga todos os usuários
    cur.execute("DELETE FROM usuarios")

    conn.commit()
    conn.close()
    print("Tabela 'usuarios' limpa com sucesso.")

if __name__ == "__main__":
    reset_usuarios()
