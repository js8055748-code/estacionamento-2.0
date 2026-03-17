from database import conectar

def bloquear(estacionamento_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE estacionamentos SET ativo = 0 WHERE id = ?", (estacionamento_id,))
    conn.commit()
    conn.close()
    print(f"Estacionamento {estacionamento_id} bloqueado.")

if __name__ == "__main__":
    bloquear(1)  # troque pelo id que quiser bloquear
