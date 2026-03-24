from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    session,
)
from datetime import date, datetime
from io import BytesIO
from collections import defaultdict
from matplotlib.figure import Figure
from fpdf import FPDF
from functools import wraps

from db_postgres import conectar, obter_cursor
from usuario import Usuario
from cliente import Clientes
from movimentacao import Movimentacao
from relatorio import Relatorio

# Criação da app, apontando pastas de static e templates
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)
app.config["DEBUG"] = True
app.secret_key = "secret-estacionamento"  # troque em produção


# ------------------- AUXILIARES -------------------
def get_estacionamento_id():
    return session.get("estacionamento_id")


def estacionamento_ativo_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        est_id = get_estacionamento_id()

        if not est_id:
            flash(
                "Usuário sem estacionamento associado. Fale com o administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        conn = conectar()
        cur = obter_cursor(conn)
        cur.execute("SELECT ativo FROM estacionamentos WHERE id = %s", (est_id,))
        row = cur.fetchone()
        conn.close()

        if row is None:
            flash(
                "Estacionamento não encontrado. Verifique com o administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        if not row["ativo"]:
            flash(
                "Este estacionamento está bloqueado pelo administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        return view_func(*args, **kwargs)

    return wrapper


def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") != role_name:
                flash("Acesso não autorizado.", "erro")
                return redirect(url_for("login"))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# ------------------- AUTENTICAÇÃO -------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()

        user = Usuario.verificar_login(email, senha)
        if user is None:
            flash("E-mail ou senha inválidos.", "erro")
            return redirect(url_for("login"))

        if user.get("precisa_definir_senha") == 1:
            session["primeiro_acesso_user_id"] = user["id"]
            flash("Defina sua senha para acessar o sistema.", "info")
            return redirect(url_for("definir_primeira_senha"))

        session["user_id"] = user["id"]
        session["user_nome"] = user["nome"]
        session["estacionamento_id"] = user["estacionamento_id"]
        session["role"] = user["role"]
        session["responsavel_nome"] = user["nome"]

        flash(f"Bem-vindo, {user['nome']}!", "sucesso")

        if user["role"] == "ADMIN_SISTEMA":
            return redirect(url_for("admin_estacionamentos"))

        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("login"))


@app.route("/definir-senha", methods=["GET", "POST"])
def definir_primeira_senha():
    user_id = session.get("primeiro_acesso_user_id")
    if not user_id:
        flash("Sessão de definição de senha expirada ou inválida.", "erro")
        return redirect(url_for("login"))

    if request.method == "POST":
        senha = request.form.get("senha", "").strip()
        confirmar = request.form.get("confirmar", "").strip()

        if not senha:
            flash("Informe a senha.", "erro")
            return redirect(url_for("definir_primeira_senha"))

        if senha != confirmar:
            flash("As senhas não conferem.", "erro")
            return redirect(url_for("definir_primeira_senha"))

        Usuario.definir_primeira_senha(user_id, senha)
        session.pop("primeiro_acesso_user_id", None)
        flash("Senha definida com sucesso. Faça login.", "sucesso")
        return redirect(url_for("login"))

    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute("SELECT email FROM usuarios WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    email = row["email"] if row else ""

    return render_template("definir_senha.html", email=email)


@app.route("/convite/<int:user_id>")
def convite_definir_senha(user_id):
    session["primeiro_acesso_user_id"] = user_id
    return redirect(url_for("definir_primeira_senha"))


# ------------------- ADMIN ESTACIONAMENTOS -------------------
@app.route("/admin/estacionamentos")
@role_required("ADMIN_SISTEMA")
def admin_estacionamentos():
    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute(
        """
        SELECT
            e.id,
            e.nome,
            e.cnpj,
            e.telefone,
            e.email,
            e.ativo,
            u.id AS responsavel_id
        FROM estacionamentos e
        LEFT JOIN usuarios u
          ON u.estacionamento_id = e.id
         AND u.perfil = 'ADMIN_ESTACIONAMENTO'
        ORDER BY e.id
        """
    )
    estacionamentos = cur.fetchall()
    conn.close()
    return render_template(
        "admin_estacionamentos.html",
        estacionamentos=estacionamentos,
    )


@app.route("/admin/estacionamentos/novo", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def criar_estacionamento_route():
    nome = request.form.get("nome", "").strip()
    codigo = request.form.get("codigo", "").strip()
    cnpj = request.form.get("cnpj", "").strip()
    telefone = request.form.get("telefone", "").strip()
    email = request.form.get("email", "").strip()
    proprietario_nome = request.form.get("proprietario_nome", "").strip()
    proprietario_contato = request.form.get("proprietario_contato", "").strip()
    responsavel_email = request.form.get("responsavel_email", "").strip().lower()

    if not nome or not codigo or not responsavel_email:
        flash("Nome, código e e-mail do responsável são obrigatórios.", "erro")
        return redirect(url_for("admin_estacionamentos"))

    try:
        conn = conectar()
        cur = obter_cursor(conn)

        # 1) Verificar se já existe usuário com esse e-mail
        cur.execute(
            "SELECT id FROM usuarios WHERE email = %s",
            (responsavel_email,),
        )
        existente = cur.fetchone()
        if existente:
            cur.close()
            conn.close()
            flash(
                "Já existe um usuário cadastrado com esse e-mail. "
                "Use outro e-mail ou aproveite o usuário existente.",
                "erro",
            )
            return redirect(url_for("admin_estacionamentos"))

        # 2) Criar estacionamento (modelo novo)
        cur.execute(
            """
            INSERT INTO estacionamentos
                (nome, cnpj, telefone, email, endereco, ativo)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id;
            """,
            (nome, cnpj, telefone, email, ""),
        )
        est_row = cur.fetchone()
        est_id = est_row["id"]

        # 3) Criar configuração padrão
        cur.execute(
            """
            INSERT INTO configuracoes (
                estacionamento_id,
                tolerancia_minutos,
                minuto_inicial,
                minuto_fracao,
                cobra_fracao_na_saida,
                permite_pernoite,
                gera_ticket_entrada,
                imprime_comprovante
            ) VALUES (%s, 10, 30, 15, TRUE, TRUE, TRUE, TRUE)
            RETURNING id;
            """,
            (est_id,),
        )
        config_row = cur.fetchone()
        config_id = config_row["id"]

        # 4) Criar tabela de preço padrão
        cur.execute(
            """
            INSERT INTO tabelas_precos (
                estacionamento_id,
                nome,
                vigencia_inicio,
                vigencia_fim,
                taxa_inicial,
                minutos_inicial,
                taxa_fracao,
                minutos_fracao,
                diaria,
                pernoite,
                ativo
            ) VALUES (
                %s,
                'Padrão',
                CURRENT_DATE,
                NULL,
                10.00,
                60,
                3.00,
                15,
                35.00,
                25.00,
                TRUE
            )
            RETURNING id;
            """,
            (est_id,),
        )
        tabela_padrao_row = cur.fetchone()
        tabela_padrao_id = tabela_padrao_row["id"]

        # 5) Vincular tabela padrão à configuração
        cur.execute(
            """
            UPDATE configuracoes
            SET tabela_preco_padrao_id = %s
            WHERE id = %s;
            """,
            (tabela_padrao_id, config_id),
        )

        # 6) Criar usuário responsável vinculado ao estacionamento
        senha_temp = "temp123"
        cur.execute(
            """
            INSERT INTO usuarios (
                estacionamento_id,
                nome,
                login,
                email,
                senha_hash,
                perfil,
                ativo
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE
            )
            RETURNING id;
            """,
            (
                est_id,
                proprietario_nome or nome,
                responsavel_email,
                responsavel_email,
                senha_temp,
                "ADMIN_ESTACIONAMENTO",
            ),
        )
        user_resp_row = cur.fetchone()
        user_id_resp = user_resp_row["id"]

        conn.commit()
        cur.close()
        conn.close()

        flash(
            "Estacionamento, configuração, tabela de preço padrão e usuário responsável criados com sucesso.",
            "sucesso",
        )
    except Exception as e:
        flash(f"Erro ao criar estacionamento: {e}", "erro")

    return redirect(url_for("admin_estacionamentos"))


@app.route("/admin/estacionamentos/<int:est_id>/excluir", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def excluir_estacionamento_route(est_id):
    try:
        conn = conectar()
        cur = obter_cursor(conn)
        cur.execute("DELETE FROM estacionamentos WHERE id = %s", (est_id,))
        conn.commit()
        conn.close()
        flash(f"Estacionamento {est_id} excluído com sucesso.", "sucesso")
    except Exception as e:
        flash(f"Erro ao excluir estacionamento: {e}", "erro")

    return redirect(url_for("admin_estacionamentos"))


@app.route("/admin/estacionamentos/<int:est_id>")
@role_required("ADMIN_SISTEMA")
def detalhes_estacionamento(est_id):
    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute(
        """
        SELECT
            id,
            nome,
            cnpj,
            telefone,
            email,
            endereco,
            ativo
        FROM estacionamentos
        WHERE id = %s
        """,
        (est_id,),
    )
    est = cur.fetchone()
    conn.close()

    if est is None:
        flash("Estacionamento não encontrado.", "erro")
        return redirect(url_for("admin_estacionamentos"))

    return render_template("detalhes_estacionamento.html", est=est)


@app.route("/admin/estacionamentos/<int:est_id>/bloquear", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def bloquear_estacionamento_route(est_id):
    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute("UPDATE estacionamentos SET ativo = FALSE WHERE id = %s", (est_id,))
    conn.commit()
    conn.close()
    flash(f"Estacionamento {est_id} bloqueado.", "sucesso")
    return redirect(url_for("admin_estacionamentos"))


@app.route("/admin/estacionamentos/<int:est_id>/desbloquear", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def desbloquear_estacionamento_route(est_id):
    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute("UPDATE estacionamentos SET ativo = TRUE WHERE id = %s", (est_id,))
    conn.commit()
    conn.close()
    flash(f"Estacionamento {est_id} desbloqueado.", "sucesso")
    return redirect(url_for("admin_estacionamentos"))


@app.route("/admin/usuarios/<int:user_id>/bloquear", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def bloquear_usuario_route(user_id):
    try:
        conn = conectar()
        cur = obter_cursor(conn)

        # Pega o estacionamento do usuário
        cur.execute(
            "SELECT estacionamento_id FROM usuarios WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            flash("Usuário não encontrado.", "erro")
            conn.close()
            return redirect(url_for("admin_usuarios"))

        est_id = row["estacionamento_id"]

        # Bloqueia o usuário
        cur.execute(
            "UPDATE usuarios SET ativo = FALSE WHERE id = %s",
            (user_id,),
        )

        # Bloqueia o estacionamento vinculado
        if est_id:
            cur.execute(
                "UPDATE estacionamentos SET ativo = FALSE WHERE id = %s",
                (est_id,),
            )

        conn.commit()
        conn.close()
        flash("Usuário e estacionamento bloqueados com sucesso.", "sucesso")
    except Exception as e:
        flash(f"Erro ao bloquear usuário/estacionamento: {e}", "erro")

    return redirect(url_for("admin_usuarios"))


# ------------------- ADMIN USUÁRIOS -------------------
@app.route("/admin/usuarios")
@role_required("ADMIN_SISTEMA")
def admin_usuarios():
    conn = conectar()
    cur = obter_cursor(conn)
    cur.execute(
        """
        SELECT
            id,
            nome,
            email,
            login,
            perfil,
            estacionamento_id,
            ativo
        FROM usuarios
        ORDER BY id
        """
    )
    usuarios = cur.fetchall()
    conn.close()
    return render_template("admin_usuarios.html", usuarios=usuarios)


# ------------------- INDEX -------------------
@app.route("/")
def index():
    return render_template("index.html")


# ------------------- CLIENTES -------------------
@app.route("/clientes")
@estacionamento_ativo_required
def listar_clientes():
    estacionamento_id = get_estacionamento_id()
    clientes = Clientes.listar(estacionamento_id=estacionamento_id)
    return render_template("clientes.html", clientes=clientes)


@app.route("/clientes/novo", methods=["POST"])
@estacionamento_ativo_required
def novo_cliente():
    nome = request.form.get("nome", "").strip()
    cpf = request.form.get("cpf", "").strip()
    placa = request.form.get("placa", "").strip()
    tipo = request.form.get("tipo", "").strip()

    if not nome or not cpf or not placa:
        flash("Nome, CPF e Placa são obrigatórios.", "erro")
        return redirect(url_for("listar_clientes"))

    try:
        estacionamento_id = get_estacionamento_id()
        Clientes.cadastrar(
            nome,
            cpf,
            placa,
            tipo,
            estacionamento_id=estacionamento_id,
        )
        flash("Cliente cadastrado com sucesso!", "sucesso")
    except Exception as e:
        flash(f"Erro ao cadastrar cliente: {e}", "erro")

    return redirect(url_for("listar_clientes"))


@app.route("/clientes/cadastrar", methods=["POST"])
@estacionamento_ativo_required
def cadastrar_cliente():
    return novo_cliente()


# ------------------- MOVIMENTAÇÃO -------------------
@app.route("/movimentacao")
@estacionamento_ativo_required
def movimentacao():
    return render_template("movimentacao.html")


from flask import jsonify

LARGURA_TICKET = 90  # mm
ALTURA_TICKET = 100  # mm


@app.route("/movimentacao/entrada", methods=["POST"])
@estacionamento_ativo_required
def registrar_entrada():
    placa = request.form.get("placa", "").strip().upper()

    if not placa:
        flash("Informe a placa.", "erro")
        return redirect(url_for("movimentacao"))

    try:
        estacionamento_id = get_estacionamento_id()
        mov_id = Movimentacao.registrar_entrada(
            placa,
            estacionamento_id=estacionamento_id,
        )

        pdf = FPDF(orientation="P", unit="mm", format=(90, 100))
        pdf.add_page()

        # Cabeçalho com nome do estacionamento
        nome_est = session.get("estacionamento_nome", "Estacionamento:")
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, nome_est, ln=True, align="C")
        pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, ln=True, align="C")
        pdf.ln(4)

        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, "Ticket de Entrada", ln=True, align="C")
        pdf.ln(4)

        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"ID movimentacao: {mov_id}", ln=True)
        pdf.cell(0, 6, f"Placa: {placa}", ln=True)
        pdf.cell(
            0,
            6,
            f"Data/Hora entrada: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            ln=True,
        )
        pdf.ln(4)
        pdf.cell(
            0,
            6,
            "Guarde este ticket para apresentacao na saida.",
            ln=True,
        )

        pdf_bytes = pdf.output(dest="S")
        buffer = BytesIO(pdf_bytes)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"ticket_entrada_{placa}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Erro ao registrar entrada: {e}", "erro")
        return redirect(url_for("movimentacao"))


@app.route("/movimentacao/pagamento", methods=["POST"])
@estacionamento_ativo_required
def registrar_pagamento():
    placa = request.form.get("placa", "").strip().upper()

    if not placa:
        flash("Informe a placa.", "erro")
        return redirect(url_for("movimentacao"))

    try:
        estacionamento_id = get_estacionamento_id()
        valor = Movimentacao.registrar_pagamento(
            placa,
            estacionamento_id=estacionamento_id,
        )

        if valor is None:
            flash("Nenhuma movimentação em aberto para essa placa.", "erro")
            return redirect(url_for("movimentacao"))

        # Gerar ticket de pagamento em PDF
        pdf = FPDF(orientation="P", unit="mm", format=(80, 120))
        pdf.add_page()

        nome_est = session.get("estacionamento_nome", "ESTACIONAMENTO XYZ")
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, nome_est, ln=True, align="C")
        pdf.ln(2)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Ticket de Pagamento", ln=True, align="C")
        pdf.ln(4)

        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"Placa: {placa}", ln=True)
        pdf.cell(
            0,
            6,
            f"Data/Hora pagamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            ln=True,
        )
        pdf.cell(0, 6, f"Valor pago: R$ {valor:.2f}", ln=True)
        pdf.ln(4)
        pdf.cell(0, 6, "Obrigado pela preferência!", ln=True)

        pdf_bytes = pdf.output(dest="S")
        buffer = BytesIO(pdf_bytes)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"ticket_pagamento_{placa}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Erro ao registrar pagamento: {e}", "erro")
        return redirect(url_for("movimentacao"))


# ------------------- RELATÓRIO E DASHBOARD -------------------
@app.route("/relatorio/diario")
@estacionamento_ativo_required
def relatorio_diario():
    dia = request.args.get("dia", date.today().isoformat())
    estacionamento_id = get_estacionamento_id()
    registros = Relatorio.movimentacao_do_dia(
        dia,
        estacionamento_id=estacionamento_id,
    )
    total = sum(r[2] for r in registros)

    return render_template(
        "relatorio_diario.html",
        dia=dia,
        registros=registros,
        total=total,
    )


@app.route("/dashboard")
@estacionamento_ativo_required
def dashboard():
    dia = date.today().isoformat()
    estacionamento_id = get_estacionamento_id()
    registros = Relatorio.movimentacao_do_dia(
        dia,
        estacionamento_id=estacionamento_id,
    )
    total = sum(r[2] for r in registros)

    return render_template("dashboard.html", dia=dia, registros=registros, total=total)


@app.route("/dashboard/grafico.png")
@estacionamento_ativo_required
def grafico_faturamento_diario():
    estacionamento_id = get_estacionamento_id()
    dados = Relatorio.faturamento_por_dia(estacionamento_id=estacionamento_id)

    fig = Figure(figsize=(5, 3), dpi=100)
    ax = fig.add_subplot(111)

    if not dados:
        ax.set_title("Sem dados")
    else:
        dias = [d[0] for d in dados]
        valores = [d[1] for d in dados]
        ax.bar(dias, valores, color="#10aa3e")
        ax.set_title("Faturamento por dia")
        ax.set_xlabel("Data")
        ax.set_ylabel("Total (R$)")
        ax.tick_params(axis="x", rotation=45)

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/dashboard/relatorio-completo.pdf")
@estacionamento_ativo_required
def dashboard_relatorio_completo_pdf():
    try:
        estacionamento_id = get_estacionamento_id()
        dados = Relatorio.todos_movimentos(estacionamento_id=estacionamento_id)

        if not dados:
            flash("Não há dados de movimentação.", "erro")
            return redirect(url_for("dashboard"))

        dias = defaultdict(list)
        semanas = defaultdict(list)
        meses = defaultdict(list)
        total_geral = 0.0

        # dados: (placa, entrada, saida, valor_float)
        for placa, entrada, saida, valor in dados:
            dt = datetime.fromisoformat(entrada)
            dia = dt.strftime("%d/%m/%Y")
            semana = f"Semana {dt.isocalendar()[1]} - {dt.year}"
            mes = dt.strftime("%m/%Y")

            dias[dia].append((placa, entrada, saida, valor))
            semanas[semana].append((placa, entrada, saida, valor))
            meses[mes].append((placa, entrada, saida, valor))

            total_geral += valor or 0.0

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(
            0,
            10,
            "Relatório Completo de Movimentação",
            ln=True,
            align="C",
        )
        pdf.ln(5)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, f"Total Geral: R$ {total_geral:.2f}", ln=True)
        pdf.ln(5)

        # Por Dia
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Dia", ln=True)
        pdf.set_font("Arial", "", 10)
        for dia, lista in sorted(dias.items()):
            total_dia = sum(l[3] for l in lista)
            pdf.cell(0, 7, f"{dia} - Total: R$ {total_dia:.2f}", ln=True)

            pdf.set_font("Arial", "", 9)
            pdf.cell(30, 7, "Placa", 1)
            pdf.cell(55, 7, "Entrada", 1)
            pdf.cell(55, 7, "Saída", 1)
            pdf.cell(30, 7, "Valor", 1)
            pdf.ln()

            for placa, entrada, saida, valor in lista:
                pdf.cell(30, 7, str(placa), 1)
                pdf.cell(55, 7, str(entrada), 1)
                pdf.cell(55, 7, str(saida) if saida else "-", 1)
                pdf.cell(30, 7, f"{(valor or 0.0):.2f}", 1)
                pdf.ln()

            pdf.ln(2)
            pdf.set_font("Arial", "", 10)
        pdf.ln(5)

        # Por Semana
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Semana", ln=True)
        pdf.set_font("Arial", "", 10)
        for semana, lista in sorted(semanas.items()):
            total_semana = sum(l[3] for l in lista)
            pdf.cell(0, 7, f"{semana} - Total: R$ {total_semana:.2f}", ln=True)
        pdf.ln(5)

        # Por Mês
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Mês", ln=True)
        pdf.set_font("Arial", "", 10)
        for mes, lista in sorted(meses.items()):
            total_mes = sum(l[3] for l in lista)
            pdf.cell(0, 7, f"{mes} - Total: R$ {total_mes:.2f}", ln=True)
        pdf.ln(5)

        pdf_bytes = pdf.output(dest="S")
        buffer = BytesIO(pdf_bytes)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="relatorio_completo_movimentacao.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Falha ao gerar PDF: {e}", "erro")
        return redirect(url_for("dashboard"))
    
@app.route("/test-templates")
def test_templates():
    import os
    from flask import current_app
    return f"root={current_app.root_path}, templates={os.listdir(current_app.template_folder)}"



# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
