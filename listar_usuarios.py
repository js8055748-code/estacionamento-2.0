from database import conectar


def listar_usuarios():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, email, estacionamento_id, role, bloqueado FROM usuarios")
    rows = cur.fetchall()
    conn.close()

    print("Usuários cadastrados:")
    for r in rows:
        print(
            f"id={r[0]}, nome={r[1]}, email={r[2]}, "
            f"estacionamento_id={r[3]}, role={r[4]}, bloqueado={r[5]}"
        )


if __name__ == "__main__":
    listar_usuarios()
