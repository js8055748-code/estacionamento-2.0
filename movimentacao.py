from datetime import datetime

from database import conectar
from cliente import Clientes

# enquanto não temos login multi-tenant, usamos o estacionamento padrão
ESTACIONAMENTO_PADRAO_ID = 1

class Movimentacao:
    @staticmethod
    def registrar_entrada(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        agora = datetime.now().isoformat(timespec="seconds")

        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO movimentacoes (placa, entrada, estacionamento_id)
            VALUES (?, ?, ?)
        """, (placa, agora, estacionamento_id))
        mov_id = cur.lastrowid
        conn.commit()
        conn.close()

        return mov_id

    @staticmethod
    def registrar_saida(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        conn = conectar()
        cur = conn.cursor()

        # busca dados do cliente do MESMO estacionamento
        cur.execute("""
            SELECT mensalista, valor_mensalidade
            FROM clientes
            WHERE placa = ?
              AND estacionamento_id = ?
        """, (placa, estacionamento_id))
        cli = cur.fetchone()

        mensalista = 0
        valor_mensalidade = None
        if cli:
            mensalista, valor_mensalidade = cli

        # busca última movimentação em aberto dessa placa no MESMO estacionamento
        cur.execute("""
            SELECT id, entrada
            FROM movimentacoes
            WHERE placa = ?
              AND estacionamento_id = ?
              AND (saida IS NULL OR saida = '')
            ORDER BY id DESC
            LIMIT 1
        """, (placa, estacionamento_id))
        mov = cur.fetchone()

        if not mov:
            conn.close()
            return None

        mov_id, entrada_iso = mov
        saida_iso = datetime.now().isoformat(timespec="seconds")

        if mensalista:
            valor = 0.0
        else:
            valor = 10.0  # regra fixa por enquanto

        cur.execute("""
            UPDATE movimentacoes
            SET saida = ?, valor = ?
            WHERE id = ?
              AND estacionamento_id = ?
        """, (saida_iso, valor, mov_id, estacionamento_id))

        conn.commit()
        conn.close()

        return valor

    @staticmethod
    def registrar_pagamento(placa, estacionamento_id=ESTACIONAMENTO_PADRAO_ID):
        placa = placa.strip().upper()
        if not placa:
            raise ValueError("Placa não informada.")

        conn = conectar()
        cur = conn.cursor()

        # busca movimentação em aberto da placa no MESMO estacionamento
        cur.execute("""
            SELECT id, entrada
            FROM movimentacoes
            WHERE placa = ?
              AND estacionamento_id = ?
              AND (saida IS NULL OR saida = '')
            ORDER BY id DESC
            LIMIT 1
        """, (placa, estacionamento_id))
        row = cur.fetchone()

        if row is None:
            conn.close()
            raise ValueError("Nenhuma movimentação em aberto para essa placa.")

        mov_id, entrada_str = row

        entrada = datetime.fromisoformat(entrada_str)
        agora = datetime.now()
        horas = (agora - entrada).total_seconds() / 3600
        horas_cobradas = max(1, int(horas + 0.9999))
        valor = horas_cobradas * 10.0  # mesma regra de preço

        cur.execute("""
            UPDATE movimentacoes
            SET saida = ?, valor = ?
            WHERE id = ?
              AND estacionamento_id = ?
        """, (agora.isoformat(sep=" "), valor, mov_id, estacionamento_id))

        conn.commit()
        conn.close()

        return valor
