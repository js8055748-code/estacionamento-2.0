import sqlite3
import os

DB_NAME = "estacionamento.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

def conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS estacionamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            documento TEXT,
            codigo TEXT NOT NULL UNIQUE,
            telefone TEXT,
            email TEXT,
            proprietario_nome TEXT,
            proprietario_contato TEXT,
            ativo INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            estacionamento_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'OPERADOR',
            bloqueado INTEGER NOT NULL DEFAULT 0,
            precisa_definir_senha INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL,
            placa TEXT NOT NULL,
            tipo TEXT NOT NULL,
            mensalista INTEGER DEFAULT 0,
            valor_mensalidade REAL,
            estacionamento_id INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            entrada TEXT NOT NULL,
            saida TEXT,
            valor REAL,
            estacionamento_id INTEGER NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()
