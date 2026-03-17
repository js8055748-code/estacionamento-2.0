from database import conectar

def listar_estacionamentos():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, endereco, vagas_totais, bloqueado FROM estacionamentos")
    rows = cur.fetchall()
    conn.close()

    print("Estacionamentos cadastrados:")
    for r in rows:
        print(
            f"id={r[0]}, nome={r[1]}, endereco={r[2]}, "
            f"vagas_totais={r[3]}, bloqueado={r[4]}"
        )

if __name__ == "__main__":
    listar_estacionamentos()
