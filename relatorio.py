from database import conectar

# enquanto não temos login multi-tenant, usamos o estacionamento padrão
ESTACIONAMENTO_PADRAO_ID = 1


class Relatorio:
    @classmethod
    def clientes(cls, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.id,
                c.nome,
                c.cpf,
                c.placa,
                c.tipo,
                IFNULL(m.valor, 0)
            FROM clientes c
            LEFT JOIN movimentacoes m
                ON m.placa = c.placa
               AND m.estacionamento_id = c.estacionamento_id
            WHERE c.estacionamento_id = ?
            ORDER BY c.nome
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @classmethod
    def movimentacoes(cls, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id,
                placa,
                entrada,
                saida,
                valor
            FROM movimentacoes
            WHERE estacionamento_id = ?
            ORDER BY id DESC
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @classmethod
    def faturamento_total(cls, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM movimentacoes
            WHERE valor IS NOT NULL
              AND estacionamento_id = ?
        """, (estacionamento_id,))
        total = cur.fetchone()[0]
        conn.close()
        return total

    @classmethod
    def faturamento_por_dia(cls, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                substr(entrada, 1, 10) AS dia,   -- YYYY-MM-DD
                COALESCE(SUM(valor), 0) AS total
            FROM movimentacoes
            WHERE valor IS NOT NULL
              AND estacionamento_id = ?
            GROUP BY dia
            ORDER BY dia
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @classmethod
    def faturamento_do_dia(cls, data_iso, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        """
        data_iso no formato 'YYYY-MM-DD'
        """
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM movimentacoes
            WHERE valor IS NOT NULL
              AND substr(entrada, 1, 10) = ?
              AND estacionamento_id = ?
        """, (data_iso, estacionamento_id))
        total = cur.fetchone()[0]
        conn.close()
        return total

    @classmethod
    def faturamento_do_mes(cls, ano_mes_iso, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        """
        ano_mes_iso no formato 'YYYY-MM' (ex: '2026-03')
        """
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM movimentacoes
            WHERE valor IS NOT NULL
              AND substr(entrada, 1, 7) = ?
              AND estacionamento_id = ?
        """, (ano_mes_iso, estacionamento_id))
        total = cur.fetchone()[0]
        conn.close()
        return total

    @classmethod
    def movimentacao_do_dia(cls, dia_iso, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        """
        dia_iso no formato 'YYYY-MM-DD' (bate com substr(entrada,1,10))
        Retorna: lista de (placa, entrada_iso, valor)
        """
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                placa,
                entrada,
                COALESCE(valor, 0) AS valor
            FROM movimentacoes
            WHERE substr(entrada, 1, 10) = ?
              AND valor IS NOT NULL
              AND estacionamento_id = ?
            ORDER BY entrada
        """, (dia_iso, estacionamento_id))
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def todos_movimentos(estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT placa, entrada, saida, valor
            FROM movimentacoes
            WHERE estacionamento_id = ?
            ORDER BY entrada ASC
        """, (estacionamento_id,))
        dados = cur.fetchall()
        conn.close()
        return dados

    @staticmethod
    def recebimentos_em_aberto(estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT placa, entrada, COALESCE(valor, 0)
            FROM movimentacoes
            WHERE (valor IS NULL OR valor = 0)
              AND estacionamento_id = ?
            ORDER BY entrada ASC
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def recebimentos(estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT substr(entrada, 1, 10) as data, placa, valor
            FROM movimentacoes
            WHERE valor IS NOT NULL AND valor > 0
              AND estacionamento_id = ?
            ORDER BY entrada DESC
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @classmethod
    def top5_clientes(cls, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.nome, c.placa, COUNT(m.id) AS usos,
                   COALESCE(SUM(m.valor), 0) AS total_pago
            FROM clientes c
            JOIN movimentacoes m
              ON m.placa = c.placa
             AND m.estacionamento_id = c.estacionamento_id
            WHERE m.entrada >= date('now', '-30 days')
              AND m.valor IS NOT NULL
              AND m.valor > 0
              AND c.estacionamento_id = ?
            GROUP BY c.nome, c.placa
            ORDER BY usos DESC, total_pago DESC
            LIMIT 5
        """, (estacionamento_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
