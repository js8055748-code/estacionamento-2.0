import sqlite3
import os

DB_NAME = "estacionamento.db"

# enquanto não temos login multi-tenant, usamos um estacionamento padrão
ESTACIONAMENTO_PADRAO_ID = 1

def conectar():
    caminho = os.path.join(os.path.dirname(__file__), DB_NAME)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn

class Clientes:
    @staticmethod
    def cadastrar(nome, cpf, placa, tipo, mensalista=0, valor_mensalidade=None, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clientes (nome, cpf, placa, tipo, mensalista, valor_mensalidade, estacionamento_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nome, cpf, placa, tipo, mensalista, valor_mensalidade, estacionamento_id))
        conn.commit()
        conn.close()

    @staticmethod
    def listar(estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, cpf, placa, tipo
            FROM clientes
            WHERE estacionamento_id = ?
        """, (estacionamento_id,))
        clientes = cur.fetchall()
        conn.close()
        return clientes

    @staticmethod
    def atualizar(id_cliente, nome, cpf, placa, tipo, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            UPDATE clientes
            SET nome = ?, cpf = ?, placa = ?, tipo = ?
            WHERE id = ? AND estacionamento_id = ?
        """, (nome, cpf, placa, tipo, id_cliente, estacionamento_id))
        conn.commit()
        conn.close()

    @staticmethod
    def excluir(id_cliente, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM clientes
            WHERE id = ? AND estacionamento_id = ?
        """, (id_cliente, estacionamento_id))
        conn.commit()
        conn.close()
