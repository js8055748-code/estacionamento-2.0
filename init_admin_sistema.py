from usuario import Usuario

def criar_admin():
    nome = "Admin Sistema"
    email = "diamondduck.emp@gmail.com"  # e-mail novo, que nunca usamos
    senha = "Vinhos430@"
    estacionamento_id = 1
    role = "ADMIN_SISTEMA"

    Usuario.criar_usuario(nome, email, senha, estacionamento_id=estacionamento_id, role=role)
    print(f"Admin criado: {email} / {senha}")

    

if __name__ == "__main__":
    criar_admin()
