import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ModuleNotFoundError:
    try:
        import psycopg2_binary as psycopg2
        from psycopg2_binary.extras import RealDictCursor
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Nenhum driver Postgres encontrado. "
            "Certifique-se de que psycopg2-binary está instalado no ambiente."
        ) from e



# Configuração do banco
# Valores padrão para desenvolvimento local
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "estacionamento_saas")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "Vinhos430@")


def conectar():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    return conn


def obter_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)
