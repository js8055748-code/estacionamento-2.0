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

from usuario import Usuario
from cliente import Clientes
from movimentacao import Movimentacao
from relatorio import Relatorio
from database import criar_tabelas, conectar


app = Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = "secret-estacionamento"  # troque em produção

ESTACIONAMENTO_PADRAO_ID = None  # não força estacionamento padrão


# ------------------- AUXILIARES -------------------
def get_estacionamento_id():
    # Sempre tenta usar o estacionamento do usuário logado
    return session.get("estacionamento_id")


def estacionamento_ativo_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        est_id = get_estacionamento_id()

        # Se não houver estacionamento na sessão, NÃO tratamos como bloqueado
        if not est_id:
            flash(
                "Usuário sem estacionamento associado. Fale com o administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT ativo FROM estacionamentos WHERE id = ?", (est_id,))
        row = cur.fetchone()
        conn.close()

        # Se o estacionamento não existir, não tratamos como bloqueado
        if row is None:
            flash(
                "Estacionamento não encontrado. Verifique com o administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        # ÚNICO caso de bloqueio: ativo = 0
        if row["ativo"] == 0:
            flash(
                "Este estacionamento está bloqueado pelo administrador.",
                "erro",
            )
            return redirect(url_for("index"))

        # ativo = 1 → acesso liberado
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

        # se precisa definir senha, mandar para tela própria
        if user.get("precisa_definir_senha") == 1:
            session["primeiro_acesso_user_id"] = user["id"]
            flash("Defina sua senha para acessar o sistema.", "info")
            return redirect(url_for("definir_primeira_senha"))

        # guarda informações na sessão
        session["user_id"] = user["id"]
        session["user_nome"] = user["nome"]
        session["estacionamento_id"] = user["estacionamento_id"]
        session["role"] = user["role"]

        flash(f"Bem-vindo, {user['nome']}!", "sucesso")

        # se for administrador do sistema, vai direto para a tela de estacionamentos
        if user["role"] == "ADMIN_SISTEMA":
            return redirect(url_for("admin_estacionamentos"))

        # demais usuários vão para a página inicial
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

    # GET: buscar e-mail para mostrar na tela
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT email FROM usuarios WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    email = row[0] if row else ""

    return render_template("definir_senha.html", email=email)


@app.route("/convite/<int:user_id>")
def convite_definir_senha(user_id):
    """
    Link que o admin envia ao responsável. Ao acessar, o responsável cai direto
    na tela de definir senha, com o e-mail já travado.
    """
    session["primeiro_acesso_user_id"] = user_id
    return redirect(url_for("definir_primeira_senha"))


# ------------------- ADMIN ESTACIONAMENTOS -------------------
@app.route("/admin/estacionamentos")
@role_required("ADMIN_SISTEMA")
def admin_estacionamentos():
    conn = conectar()
    cur = conn.cursor()
    # traz também o id do usuário responsável (role USUARIO) se existir
    cur.execute(
        """
        SELECT
            e.id,
            e.nome,
            e.codigo,
            e.ativo,
            u.id AS responsavel_id
        FROM estacionamentos e
        LEFT JOIN usuarios u
          ON u.estacionamento_id = e.id
         AND u.role = 'USUARIO'
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
        cur = conn.cursor()

        # 1) Verificar se já existe usuário com esse e-mail
        cur.execute(
            "SELECT id FROM usuarios WHERE email = ?",
            (responsavel_email,),
        )
        existente = cur.fetchone()
        if existente:
            conn.close()
            flash(
                "Já existe um usuário cadastrado com esse e-mail. "
                "Use outro e-mail ou aproveite o usuário existente.",
                "erro",
            )
            return redirect(url_for("admin_estacionamentos"))

        # 2) Criar estacionamento
        cur.execute(
            """
            INSERT INTO estacionamentos
                (nome, documento, codigo, telefone, email, ativo, proprietario_nome, proprietario_contato)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (nome, cnpj, codigo, telefone, email, proprietario_nome, proprietario_contato),
        )
        est_id = cur.lastrowid
        conn.commit()
        conn.close()

        # 3) Criar usuário responsável vinculado ao estacionamento
        senha_temp = "temp123"
        user_id_resp = Usuario.criar_usuario_responsavel(
            nome=proprietario_nome or nome,
            email=responsavel_email,
            senha=senha_temp,
            estacionamento_id=est_id,
        )

        flash(
            "Estacionamento e usuário responsável criados com sucesso.",
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
        cur = conn.cursor()
        cur.execute("DELETE FROM estacionamentos WHERE id = ?", (est_id,))
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
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            nome,
            documento,           -- CNPJ
            codigo,
            telefone,
            email,
            proprietario_nome,
            proprietario_contato,
            ativo
        FROM estacionamentos
        WHERE id = ?
        """,
        (est_id,),
    )
    est = cur.fetchone()
    conn.close()

    if est is None:
        flash("Estacionamento não encontrado.", "erro")
        return redirect(url_for("admin_estacionamentos"))

    return render_template("detalhes_estacionamento.html", est=est)


# ------------------- ADMIN USUÁRIOS -------------------
@app.route("/admin/usuarios")
@role_required("ADMIN_SISTEMA")
def admin_usuarios():
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nome, email, role, bloqueado
        FROM usuarios
        ORDER BY id
        """
    )
    usuarios = cur.fetchall()
    conn.close()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@app.route("/admin/estacionamentos/<int:est_id>/bloquear", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def bloquear_estacionamento_route(est_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE estacionamentos SET ativo = 0 WHERE id = ?", (est_id,))
    conn.commit()
    conn.close()
    flash(f"Estacionamento {est_id} bloqueado.", "sucesso")
    return redirect(url_for("admin_estacionamentos"))


@app.route("/admin/estacionamentos/<int:est_id>/desbloquear", methods=["POST"])
@role_required("ADMIN_SISTEMA")
def desbloquear_estacionamento_route(est_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE estacionamentos SET ativo = 1 WHERE id = ?", (est_id,))
    conn.commit()
    conn.close()
    flash(f"Estacionamento {est_id} desbloqueado.", "sucesso")
    return redirect(url_for("admin_estacionamentos"))


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
    # alias para manter compatibilidade com templates antigos
    return novo_cliente()


# ------------------- MOVIMENTAÇÃO -------------------
@app.route("/movimentacao")
@estacionamento_ativo_required
def movimentacao():
    return render_template("movimentacao.html")


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

        # gerar ticket de entrada em PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Ticket de Entrada - Estacionamento", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"ID movimentacao: {mov_id}", ln=True)
        pdf.cell(0, 8, f"Placa: {placa}", ln=True)
        pdf.cell(
            0,
            8,
            f"Data/Hora entrada: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            ln=True,
        )
        pdf.ln(5)
        pdf.cell(
            0,
            8,
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


@app.route("/movimentacao/saida", methods=["POST"])
@estacionamento_ativo_required
def registrar_saida():
    placa = request.form.get("placa", "").strip().upper()

    if not placa:
        flash("Informe a placa.", "erro")
        return redirect(url_for("movimentacao"))

    try:
        estacionamento_id = get_estacionamento_id()
        valor = Movimentacao.registrar_saida(
            placa,
            estacionamento_id=estacionamento_id,
        )

        if valor is None:
            flash("Nenhuma entrada em aberto para essa placa.", "erro")
            return redirect(url_for("movimentacao"))

        flash(f"Saída registrada para {placa}. Valor: R$ {valor:.2f}", "sucesso")

        # gerar ticket de saída em PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Ticket de Saida - Estacionamento", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Placa: {placa}", ln=True)
        pdf.cell(
            0,
            8,
            f"Data/Hora saida: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            ln=True,
        )
        pdf.cell(0, 8, f"Valor a pagar: R$ {valor:.2f}", ln=True)
        pdf.ln(5)
        pdf.cell(0, 8, "Obrigado pela preferencia!", ln=True)

        pdf_bytes = pdf.output(dest="S")
        buffer = BytesIO(pdf_bytes)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"ticket_saida_{placa}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Erro ao registrar saída: {e}", "erro")
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
        flash(f"Pagamento registrado para {placa}: R$ {valor:.2f}", "sucesso")
    except Exception as e:
        flash(f"Erro ao registrar pagamento: {e}", "erro")

    return redirect(url_for("movimentacao"))


# ------------------- RELATÓRIO DIÁRIO -------------------
@app.route("/relatorio/diario")
@estacionamento_ativo_required
def relatorio_diario():
    dia = request.args.get("dia", date.today().isoformat())
    estacionamento_id = get_estacionamento_id()
    registros = Relatorio.movimentacao_do_dia(
        dia,
        estacionamento_id=estacionamento_id,
    )
    total = sum(float(r[2] or 0) for r in registros)
    return render_template(
        "relatorio_diario.html",
        dia=dia,
        registros=registros,
        total=total,
    )


# ------------------- DASHBOARD -------------------
@app.route("/dashboard")
@estacionamento_ativo_required
def dashboard():
    dia = date.today().isoformat()
    estacionamento_id = get_estacionamento_id()
    registros = Relatorio.movimentacao_do_dia(
        dia,
        estacionamento_id=estacionamento_id,
    )
    total = sum(float(r[2] or 0) for r in registros)
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

        for placa, entrada, saida, valor in dados:
            dt = datetime.fromisoformat(entrada)
            dia = dt.strftime("%d/%m/%Y")
            semana = f"Semana {dt.isocalendar()[1]} - {dt.year}"
            mes = dt.strftime("%m/%Y")
            dias[dia].append((placa, entrada, saida, valor))
            semanas[semana].append((placa, entrada, saida, valor))
            meses[mes].append((placa, entrada, saida, valor))
            total_geral += float(valor or 0)

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

        # --------- Por Dia ---------
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Dia", ln=True)
        pdf.set_font("Arial", "", 10)
        for dia, lista in sorted(dias.items()):
            total_dia = sum(float(l[3] or 0) for l in lista)
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
                pdf.cell(30, 7, f"{valor:.2f}" if valor else "0.00", 1)
                pdf.ln()

            pdf.ln(2)
            pdf.set_font("Arial", "", 10)
        pdf.ln(5)

        # --------- Por Semana ---------
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Semana", ln=True)
        pdf.set_font("Arial", "", 10)
        for semana, lista in sorted(semanas.items()):
            total_semana = sum(float(l[3] or 0) for l in lista)
            pdf.cell(0, 7, f"{semana} - Total: R$ {total_semana:.2f}", ln=True)
        pdf.ln(5)

        # --------- Por Mês ---------
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Movimentação por Mês", ln=True)
        pdf.set_font("Arial", "", 10)
        for mes, lista in sorted(meses.items()):
            total_mes = sum(float(l[3] or 0) for l in lista)
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


# ------------------- MAIN -------------------
if __name__ == "__main__":
    criar_tabelas()
    app.run(debug=True)
