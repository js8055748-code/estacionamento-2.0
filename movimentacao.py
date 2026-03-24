from datetime import datetime
import math

from db_postgres import conectar, obter_cursor
from cliente import Clientes  # se ainda for usado

ESTACIONAMENTO_PADRAO_ID = 1


def calcular_valor_estadia(entrada, saida, tabela_preco):
    """
    entrada, saida: datetime
    tabela_preco: dict com campos
      - taxa_inicial
      - minutos_inicial
      - taxa_fracao
      - minutos_fracao
      - diaria (pode ser None)
      - pernoite (pode ser None, ainda não usamos)
    """
    duracao_min = (saida - entrada).total_seconds() / 60.0

    taxa_inicial = tabela_preco["taxa_inicial"]
    minutos_inicial = tabela_preco["minutos_inicial"]
    taxa_fracao = tabela_preco["taxa_fracao"]
    minutos_fracao = tabela_preco["minutos_fracao"]
    diaria = tabela_preco["diaria"]
    pernoite = tabela_preco["pernoite"]

    # se existir diária e passou de 24h, cobra por diárias
    if diaria is not None and duracao_min >= 24 * 60:
        dias = math.ceil(duracao_min / (24 * 60))
        return float(dias) * float(diaria)

    # regra normal: inicial + frações
    if duracao_min <= minutos_inicial:
        return float(taxa_inicial)

    valor = float(taxa_inicial)
    minutos_restantes = duracao_min - minutos_inicial

    if minutos_fracao > 0 and taxa_fracao is not None:
        fracoes = math.ceil(minutos_restantes / minutos_fracao)
        valor += fracoes * float(taxa_fracao)

    return valor


class Movimentacao:
    @staticmethod
    def registrar_entrada(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        agora = datetime.now().isoformat(timespec="seconds")

        conn = conectar()
        cur = obter_cursor(conn)
        try:
            cur.execute("""
                INSERT INTO movimentacoes (placa, entrada, estacionamento_id)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (placa, agora, estacionamento_id))
            row = cur.fetchone()
            mov_id = row["id"]
            conn.commit()
            return mov_id
        finally:
            cur.close()
            conn.close()

    #@staticmethod
    #def registrar_saida(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        conn = conectar()
        cur = obter_cursor(conn)
        try:
            # busca dados do cliente do MESMO estacionamento
            cur.execute("""
                SELECT mensalista, valor_mensalidade
                FROM clientes
                WHERE placa = %s
                  AND estacionamento_id = %s
            """, (placa, estacionamento_id))
            cli = cur.fetchone()

            mensalista = 0
            valor_mensalidade = None
            if cli:
                mensalista = cli["mensalista"]
                valor_mensalidade = cli["valor_mensalidade"]

            # busca última movimentação em aberto dessa placa no MESMO estacionamento
            cur.execute("""
                SELECT id, entrada
                FROM movimentacoes
                WHERE placa = %s
                  AND estacionamento_id = %s
                  AND (saida IS NULL OR saida = '')
                ORDER BY id DESC
                LIMIT 1
            """, (placa, estacionamento_id))
            mov = cur.fetchone()

            if not mov:
                return None

            mov_id = mov["id"]
            entrada_iso = mov["entrada"]
            saida_iso = datetime.now().isoformat(timespec="seconds")

            if mensalista:
                valor = 0.0
            else:
                valor = 10.0  # ainda regra fixa aqui; pagamento usa tabela

            cur.execute("""
                UPDATE movimentacoes
                SET saida = %s, valor = %s
                WHERE id = %s
                  AND estacionamento_id = %s
            """, (saida_iso, valor, mov_id, estacionamento_id))

            conn.commit()
            return valor
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def registrar_pagamento(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        conn = conectar()
        cur = obter_cursor(conn)
        try:
            # 1) busca movimentação em aberto da placa no MESMO estacionamento
            cur.execute("""
                SELECT id, entrada
                FROM movimentacoes
                WHERE placa = %s
                  AND estacionamento_id = %s
                  AND (saida IS NULL OR saida = '')
                ORDER BY id DESC
                LIMIT 1
            """, (placa, estacionamento_id))
            row = cur.fetchone()

            if row is None:
                raise ValueError("Nenhuma movimentação em aberto para essa placa.")

            mov_id = row["id"]
            entrada_str = row["entrada"]
            entrada = datetime.fromisoformat(entrada_str)
            saida = datetime.now()

            # 2) buscar tabela de preço padrão do estacionamento
            cur.execute("""
                SELECT
                    tp.taxa_inicial,
                    tp.minutos_inicial,
                    tp.taxa_fracao,
                    tp.minutos_fracao,
                    tp.diaria,
                    tp.pernoite
                FROM configuracoes c
                JOIN tabelas_precos tp
                  ON tp.id = c.tabela_preco_padrao_id
                WHERE c.estacionamento_id = %s
                  AND tp.ativo = TRUE
                LIMIT 1
            """, (estacionamento_id,))
            tabela = cur.fetchone()

            if tabela is None:
                raise ValueError("Tabela de preços padrão não configurada para este estacionamento.")

            # 3) calcular valor com base na tabela de preços
            valor = calcular_valor_estadia(entrada, saida, tabela)

            # 4) atualizar movimentação com saída e valor
            cur.execute("""
                UPDATE movimentacoes
                SET saida = %s, valor = %s
                WHERE id = %s
                  AND estacionamento_id = %s
            """, (saida.isoformat(sep=" "), valor, mov_id, estacionamento_id))

            conn.commit()
            return valor
        finally:
            cur.close()
            conn.close()
