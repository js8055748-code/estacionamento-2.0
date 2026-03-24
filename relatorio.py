from datetime import datetime
from db_postgres import conectar, obter_cursor


class Relatorio:
    @staticmethod
    def movimentacao_do_dia(dia_iso, estacionamento_id):
        """
        Retorna lista de (placa, entrada, valor_float) do dia informado.
        dia_iso: string 'DD-MM-YYYY'
        """
        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute(
                """
                SELECT
                    placa,
                    entrada,
                    valor
                FROM movimentacoes
                WHERE estacionamento_id = %s
                  AND entrada LIKE %s || '%%'
                ORDER BY entrada;
                """,
                (estacionamento_id, dia_iso),
            )
            registros = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        # Normaliza valor para float, nunca None
        resultado = []
        for r in registros:
            placa = r["placa"]
            entrada = r["entrada"]
            valor = r["valor"]
            valor_float = float(valor) if valor is not None else 0.0
            resultado.append((placa, entrada, valor_float))

        return resultado

    @staticmethod
    def faturamento_por_dia(estacionamento_id, limite_dias=30):
        """
        Retorna lista de (dia_iso, total_float) para últimos N dias.
        Considera apenas movimentações com saída registrada.
        """
        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute(
                """
                SELECT
                    SUBSTRING(saida FROM 1 FOR 10) AS dia,
                    COALESCE(SUM(CAST(valor AS NUMERIC)), 0) AS total
                FROM movimentacoes
                WHERE estacionamento_id = %s
                  AND saida IS NOT NULL
                GROUP BY SUBSTRING(saida FROM 1 FOR 10)
                ORDER BY dia DESC
                LIMIT %s;
                """,
                (estacionamento_id, limite_dias),
            )
            dados = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        resultado = []
        for d in dados:
            dia = d["dia"]
            total = d["total"]
            total_float = float(total) if total is not None else 0.0
            resultado.append((dia, total_float))

        return resultado

    @staticmethod
    def todos_movimentos(estacionamento_id):
        """
        Retorna lista de (placa, entrada, saida, valor_float)
        de todas as movimentações do estacionamento.
        """
        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute(
                """
                SELECT
                    placa,
                    entrada,
                    saida,
                    valor
                FROM movimentacoes
                WHERE estacionamento_id = %s
                ORDER BY entrada;
                """,
                (estacionamento_id,),
            )
            dados = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        resultado = []
        for d in dados:
            placa = d["placa"]
            entrada = d["entrada"]
            saida = d["saida"]
            valor = d["valor"]
            valor_float = float(valor) if valor is not None else 0.0
            resultado.append((placa, entrada, saida, valor_float))

        return resultado
    print("OBRIGADO E VOLTE SEMPRE")
