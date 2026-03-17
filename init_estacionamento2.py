from database import conectar, criar_tabelas
from usuario import Usuario

def criar_estacionamento_e_usuario():
    criar_tabelas()  # garante que as tabelas existem

    conn = conectar()
    cur = conn.cursor()

    # ATENÇÃO: escolha um codigo que NÃO está na lista de estacionamentos
    nome_est = "Estacionamento Teste Final"
    documento_est = "99999999999999"
    codigo_est = "TESTEFINAL"  # certifique-se que não existe
    telefone_est = "31990000000"
    email_est = "contato@testefinal.com"

    cur.execute("""
        INSERT INTO estacionamentos (nome, documento, codigo, telefone, email, ativo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nome_est,
        documento_est,
        codigo_est,
        telefone_est,
        email_est,
        1
    ))
    novo_estacionamento_id = cur.lastrowid
    conn.commit()
    conn.close()

    print(f"Novo estacionamento criado com id = {novo_estacionamento_id}, codigo = {codigo_est}")

    # Agora cria o usuário, lembrando que a tabela 'usuarios' está vazia
    nome_usuario = "Admin Teste Final"
    email_usuario = "admin.testefinal@example.com"  # e-mail que NÃO existia
    senha_usuario = "senha123"

    Usuario.criar_usuario(
        nome_usuario,
        email_usuario,
        senha_usuario,
        estacionamento_id=novo_estacionamento_id
    )

    print(f"Usuário '{nome_usuario}' criado para o estacionamento {novo_estacionamento_id}.")
    print(f"E-mail: {email_usuario} | Senha: {senha_usuario}")

if __name__ == "__main__":
    criar_estacionamento_e_usuario()
