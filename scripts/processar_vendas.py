"""
Script de processamento da base de vendas — Projeto Next Level

Lê o relatório de vendas (CSV, separador ';'), seleciona as 21 colunas
definidas no projeto, aplica a regra de Classe (Venda/Devolução/Bônus/
Dev.Bônus), aplica as regras de reatribuição de carteira (troca de RCA
responsável), e gera um arquivo final pronto para o dashboard.

Funciona tanto lendo de um arquivo local quanto de uma URL pública
(ex: link "Publicar na Web" do Google Sheets) — usado tanto no
desenvolvimento local quanto na automação via GitHub Actions.

Desenhado para escalar do mês vigente (poucos MB) até o histórico
completo (centenas de MB), processando em pedaços (chunks) para não
sobrecarregar a memória.
"""

import sys
import pandas as pd

# ---------------------------------------------------------------
# 1) MAPEAMENTO DE COLUNAS
#    Nomes EXATOS como vêm do link "Publicar na Web" do Google Sheets
#    (encoding correto, sem corrupção de acentuação).
# ---------------------------------------------------------------
COLUNAS_DESEJADAS = {
    "Nº Nota": "numero_nota",
    "Data Emissão": "data_emissao",
    "Código Cliente/Fornecedor": "codigo_cliente",
    "Cliente/Fornecedor": "razao_social",
    "Nome Fantasia": "nome_fantasia",
    "RCA": "rca",
    "Valor Total": "valor_total",
    "Quantidade": "quantidade",
    "Peso Líquido": "peso_liquido",
    "Classe": "classe",
    "UF": "uf",
    "Cidade": "cidade",
    "Bairro": "bairro",
    "Filial": "filial",
    "Produto": "produto",
    "Marca": "marca",
    "Departamento": "departamento",
    "Seção": "secao",
    "Família": "familia",
    "Referência": "referencia",
    "Categoria": "categoria",
}

# Nome da coluna (já renomeada/padronizada) que guarda o vendedor.
# Centralizado aqui porque a lógica de reatribuição de carteira
# precisa saber qual coluna tratar como "RCA".
COLUNA_RCA = "rca"

# ---------------------------------------------------------------
# 2) REGRA DE NEGÓCIO — CLASSE
#    Extraído do código numérico no início do texto da coluna Classe
#    Ex: "2 - VE-VENDA" -> código 2
# ---------------------------------------------------------------
CODIGO_VENDA = 2
CODIGO_DEVOLUCAO_VENDA = 4
CODIGO_BONUS = 5
CODIGO_DEVOLUCAO_BONUS = 15

# Todas as classes já confirmadas e documentadas com Fernando — mesmo as
# que são tratadas como "informativas, fora de todos os cálculos"
# (Remessa Futura, Brindes, Troca de Mercadoria, Trabalho de Campo,
# Amostra Grátis, Saída em nome da Qualy). Qualquer código de Classe que
# apareça nos dados e NÃO esteja nessa lista é sinalizado como
# "desconhecido" no resumo de checagem — para nunca mais sumir em
# silêncio dos cálculos sem ninguém notar.
CLASSES_DOCUMENTADAS = {
    2: "Venda — entra no Faturamento e na Quantidade/Peso",
    4: "Devolução de Venda — entra no Faturamento e na Quantidade/Peso",
    5: "Bônus — entra só na Quantidade/Peso",
    15: "Devolução de Bônus — entra só na Quantidade/Peso",
    11: "Troca de Mercadoria — informativa, fora de todos os cálculos",
    23: "Trabalho de Campo — informativa, fora de todos os cálculos",
    31: "Remessa Futura — informativa, fora de todos os cálculos",
    37: "Saída Amostra Grátis — informativa, fora de todos os cálculos",
    39: "Brindes — informativa, fora de todos os cálculos",
    43: "Saída em nome da Qualy — informativa, fora de todos os cálculos",
}


def extrair_codigo_classe(valor_classe: str) -> int:
    """Extrai o código numérico do início do texto da coluna Classe."""
    try:
        return int(str(valor_classe).strip().split(" ")[0])
    except (ValueError, IndexError):
        return -1  # código inválido/desconhecido/linha vazia


def processar_arquivo(caminho_ou_url: str, tamanho_chunk: int = 50_000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Lê o CSV em pedaços (chunks) — de um caminho local OU de uma URL —,
    aplica seleção de colunas e regra de negócio, e retorna DOIS DataFrames:
      1) df_valido: linhas íntegras, prontas para os cálculos
      2) df_erros: linhas malformadas (ex: arquivo truncado no meio),
         isoladas para revisão manual — nunca entram no cálculo principal

    O pandas já sabe ler tanto arquivos locais quanto URLs http(s)
    transparentemente — não precisamos de lógica separada para cada caso.
    """
    colunas_processadas = []
    linhas_com_erro = []

    leitor = pd.read_csv(
        caminho_ou_url,
        sep=",",  # o link "Publicar na Web" do Google Sheets usa vírgula como
                  # separador (formato CSV padrão), com aspas envolvendo campos
                  # que contêm vírgula — ex: números decimais "104,85".
                  # Isso é diferente do arquivo bruto original (separado por ";").
        encoding="utf-8",
        chunksize=tamanho_chunk,
        dtype=str,  # ler tudo como texto primeiro; convertemos números manualmente depois
        low_memory=False,
        on_bad_lines="warn",  # nunca quebra o script; sinaliza linha problemática
    )

    # Colunas (já renomeadas) que precisam estar presentes para a linha ser
    # considerada válida. Não usamos "a última coluna do arquivo está vazia"
    # como sinal de truncamento, porque a última coluna real ("Vendedor")
    # está SEMPRE vazia por padrão no sistema de origem — usaríamos um sinal
    # que nunca é verdadeiro para nenhuma linha válida.
    COLUNAS_ESSENCIAIS = ["numero_nota", "data_emissao", "rca", "valor_total", "classe"]

    for pedaco in leitor:
        colunas_existentes = [c for c in COLUNAS_DESEJADAS if c in pedaco.columns]
        pedaco_filtrado = pedaco[colunas_existentes].rename(
            columns={c: COLUNAS_DESEJADAS[c] for c in colunas_existentes}
        )

        colunas_essenciais_presentes = [c for c in COLUNAS_ESSENCIAIS if c in pedaco_filtrado.columns]
        mascara_suspeita = pedaco_filtrado[colunas_essenciais_presentes].isna().any(axis=1)

        pedaco_erros = pedaco_filtrado[mascara_suspeita].copy()
        pedaco_valido = pedaco_filtrado[~mascara_suspeita].copy()

        if len(pedaco_erros) > 0:
            linhas_com_erro.append(pedaco_erros)

        colunas_processadas.append(pedaco_valido)

    df = pd.concat(colunas_processadas, ignore_index=True) if colunas_processadas else pd.DataFrame()
    df_erros = pd.concat(linhas_com_erro, ignore_index=True) if linhas_com_erro else pd.DataFrame()

    # --- Conversões de tipo (só no conjunto válido) ---
    for col in ["valor_total", "quantidade", "peso_liquido"]:
        df[col] = (
            df[col]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

    df["data_emissao"] = pd.to_datetime(df["data_emissao"], format="%m/%d/%Y", errors="coerce")
    df["codigo_classe"] = df["classe"].apply(extrair_codigo_classe)

    return df, df_erros


def aplicar_reatribuicao_carteira(df: pd.DataFrame, caminho_regras: str) -> pd.DataFrame:
    """
    Aplica as regras de reatribuição de carteira (troca de RCA responsável).

    O arquivo de regras é um CSV pequeno, mantido manualmente, com colunas:
      - tipo_criterio: o NOME de qualquer coluna do df já processado
                       (ex: "rca", "cidade", "marca", "codigo_cliente")
      - valor: o valor que identifica as linhas afetadas
      - rca_original: (opcional) só aplica a regra se o RCA atual for esse
      - rca_novo: o RCA que deve substituir o original

    Isso é genérico de propósito: novos tipos de critério no futuro (ex:
    "familia") não exigem mudança neste código, só uma linha nova no CSV
    de regras.
    """
    try:
        regras = pd.read_csv(caminho_regras, dtype=str)
    except FileNotFoundError:
        print(f"Aviso: arquivo de regras de reatribuição '{caminho_regras}' não encontrado. Nenhuma reatribuição aplicada.")
        return df

    df = df.copy()

    for _, regra in regras.iterrows():
        coluna = regra["tipo_criterio"]
        valor = regra["valor"]
        rca_original = regra.get("rca_original")
        rca_novo = regra["rca_novo"]

        if coluna not in df.columns:
            print(f"Aviso: critério de reatribuição '{coluna}' não existe nas colunas processadas. Regra ignorada.")
            continue

        mascara = df[coluna] == valor
        if pd.notna(rca_original) and str(rca_original).strip() != "":
            mascara = mascara & (df[COLUNA_RCA] == rca_original)

        df.loc[mascara, COLUNA_RCA] = rca_novo

    return df


def calcular_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica as fórmulas de negócio definidas no projeto:
    - Faturamento = Venda(2) + Devolução(4)
    - Quantidade/Peso = Venda(2) + Devolução(4) + Bônus(5) + DevBônus(15)

    IMPORTANTE: o sistema de origem já registra Devolução de Venda e
    Devolução de Bonificação com sinal NEGATIVO nativamente (ex: uma
    devolução de R$ 100 já vem como -100,00, não como +100,00). Por isso
    NÃO aplicamos nenhuma inversão de sinal aqui — só somamos os valores
    como vêm, filtrando para as classes relevantes. Aplicar uma inversão
    de sinal por cima do que já é negativo geraria um erro de sinal duplo
    (transformaria devoluções em valores positivos, inflando o resultado).
    """
    df = df.copy()

    classes_faturamento = {CODIGO_VENDA, CODIGO_DEVOLUCAO_VENDA}
    classes_qtd_peso = {CODIGO_VENDA, CODIGO_DEVOLUCAO_VENDA, CODIGO_BONUS, CODIGO_DEVOLUCAO_BONUS}

    pertence_faturamento = df["codigo_classe"].isin(classes_faturamento)
    pertence_qtd_peso = df["codigo_classe"].isin(classes_qtd_peso)

    df["faturamento_ajustado"] = df["valor_total"].where(pertence_faturamento, 0.0)
    df["quantidade_ajustada"] = df["quantidade"].where(pertence_qtd_peso, 0.0)
    df["peso_ajustado"] = df["peso_liquido"].where(pertence_qtd_peso, 0.0)

    return df


if __name__ == "__main__":
    # Uso: python processar_vendas.py <caminho_ou_url> [caminho_regras_reatribuicao]
    entrada = sys.argv[1] if len(sys.argv) > 1 else "amostra_jun26.csv"
    caminho_regras = sys.argv[2] if len(sys.argv) > 2 else "regras_reatribuicao.csv"

    print(f"Processando: {entrada}")
    df, df_erros = processar_arquivo(entrada)
    print(f"Total de linhas válidas: {len(df)}")
    print(f"Total de linhas com erro (isoladas, fora do cálculo): {len(df_erros)}")

    df = aplicar_reatribuicao_carteira(df, caminho_regras)
    df = calcular_metricas(df)

    df.to_csv("vendas_processadas_detalhe.csv", index=False)
    print("\nArquivo 'vendas_processadas_detalhe.csv' salvo.")

    # Formato consumido pelo dashboard (GitHub Pages lê isso direto via
    # JavaScript, sem precisar de nenhuma biblioteca extra de CSV).
    colunas_dashboard = [
        "numero_nota", "data_emissao", "codigo_cliente", "razao_social",
        "nome_fantasia", "rca", "uf", "cidade", "bairro", "filial",
        "produto", "marca", "departamento", "secao", "familia",
        "referencia", "categoria", "codigo_classe",
        "faturamento_ajustado", "quantidade_ajustada", "peso_ajustado",
    ]
    df_dashboard = df[[c for c in colunas_dashboard if c in df.columns]].copy()
    df_dashboard["data_emissao"] = df_dashboard["data_emissao"].dt.strftime("%Y-%m-%d")
    df_dashboard.to_json("vendas_dashboard.json", orient="records", force_ascii=False)
    print("Arquivo 'vendas_dashboard.json' salvo (formato consumido pelo dashboard).")

    if len(df_erros) > 0:
        df_erros.to_csv("linhas_com_erro.csv", index=False)
        print(f"Arquivo 'linhas_com_erro.csv' salvo com {len(df_erros)} linha(s) para revisão manual.")

    print("\n--- RESUMO DE CHECAGEM ---")
    print("Faturamento total (Venda + Devolução):", round(df["faturamento_ajustado"].sum(), 2))
    print("Quantidade total ajustada:", round(df["quantidade_ajustada"].sum(), 2))
    print("Peso líquido total ajustado:", round(df["peso_ajustado"].sum(), 2))
    print("\nDistribuição por código de Classe encontrado:")
    print(df["codigo_classe"].value_counts())

    # Alerta para classes nunca vistas/documentadas antes — para nunca mais
    # uma Classe nova "desaparecer" dos cálculos sem ninguém perceber.
    codigos_no_dado = set(df["codigo_classe"].unique())
    codigos_desconhecidos = codigos_no_dado - set(CLASSES_DOCUMENTADAS.keys())
    if codigos_desconhecidos:
        print("\n⚠️  ATENÇÃO: classe(s) de Classe NUNCA documentada(s) encontrada(s)!")
        for codigo in sorted(codigos_desconhecidos):
            qtd = (df["codigo_classe"] == codigo).sum()
            texto = df[df["codigo_classe"] == codigo]["classe"].iloc[0] if qtd > 0 else "?"
            print(f"   Código {codigo} ('{texto}'): {qtd} linha(s) — sendo EXCLUÍDA de todos os cálculos por padrão até alguém confirmar o tratamento correto.")
    print("\nTotal de RCAs distintos:", df[COLUNA_RCA].nunique())
