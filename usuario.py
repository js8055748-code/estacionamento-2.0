import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "estacionamento.db"
ESTACIONAMENTO_PADRAO_ID = 1  # valor padrão


def conectar():
    caminho = os.path.join(os.path.dirname(__file__), DB_NAME)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn


class Usuario:
    @staticmethod
    def criar_usuario(nome, email, senha, estacionamento_id=ESTACIONAMENTO_PADRAO_ID, role="OPERADOR"):
        conn = conectar()
        cur = conn.cursor()

        senha_hash = generate_password_hash(senha)
        cur.execute("""
            INSERT INTO usuarios (nome, email, senha, estacionamento_id, role, bloqueado, precisa_definir_senha)
            VALUES (?, ?, ?, ?, ?, 0, 1)
        """, (nome, email, senha_hash, estacionamento_id, role))

        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return user_id

    @staticmethod
    def criar_usuario_responsavel(nome, email, senha, estacionamento_id):
        """
        Atalho para criar o usuário responsável do estacionamento.
        """
        if not nome or not email or not senha or estacionamento_id is None:
            raise ValueError("Dados incompletos para criar usuário responsável.")

        role = "USUARIO"  # papel do responsável
        return Usuario.criar_usuario(nome, email, senha, estacionamento_id=estacionamento_id, role=role)

    @staticmethod
    def definir_primeira_senha(user_id, nova_senha):
        conn = conectar()
        cur = conn.cursor()
        senha_hash = generate_password_hash(nova_senha)
        cur.execute("""
            UPDATE usuarios
            SET senha = ?, precisa_definir_senha = 0
            WHERE id = ?
        """, (senha_hash, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def buscar_por_email(email):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, email, senha, estacionamento_id, role, bloqueado, precisa_definir_senha
            FROM usuarios
            WHERE email = ?
        """, (email,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def verificar_login(email, senha):
        user = Usuario.buscar_por_email(email)
        if user is None:
            return None

        senha_hash = user["senha"]  # coluna 'senha' guarda o hash

        if not check_password_hash(senha_hash, senha):
            return None

        if user["bloqueado"]:
            return None

        return {
            "id": user["id"],
            "nome": user["nome"],
            "email": user["email"],
            "estacionamento_id": user["estacionamento_id"],
            "role": user["role"],
            # se quiser usar precisa_definir_senha no login, você pode incluir aqui também:
            # "precisa_definir_senha": user["precisa_definir_senha"],
        }
