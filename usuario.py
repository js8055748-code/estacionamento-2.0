from db_postgres import conectar, obter_cursor


class Usuario:
    @staticmethod
    def verificar_login(email, senha_clara):
        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute(
                """
                SELECT
                    id,
                    nome,
                    email,
                    login,
                    senha_hash,
                    perfil      AS role,
                    estacionamento_id,
                    FALSE       AS precisa_definir_senha
                FROM usuarios
                WHERE email = %s
                  AND ativo = TRUE
                LIMIT 1;
                """,
                (email,),
            )
            user = cur.fetchone()
        finally:
            cur.close()
            conn.close()

        if not user:
            return None

        # Comparação simples (sem hash) por enquanto
        if senha_clara != user["senha_hash"]:
            return None

        return user

    @staticmethod
    def definir_primeira_senha(user_id, nova_senha):
        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute(
                """
                UPDATE usuarios
                SET senha_hash = %s
                WHERE id = %s;
                """,
                (nova_senha, user_id),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
