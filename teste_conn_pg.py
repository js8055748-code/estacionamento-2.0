from db_postgres import conectar, obter_cursor

def teste():
    conn = conectar()
    cur = obter_cursor(conn)

    cur.execute("SELECT COUNT(*) AS total FROM estacionamentos;")
    row = cur.fetchone()
    print("Total de estacionamentos:", row["total"])

    cur.close()
    conn.close()

if __name__ == "__main__":
    teste()
