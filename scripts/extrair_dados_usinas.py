from pathlib import Path
import pandas as pd

# Caminho completo do CSV
caminho = Path(
    r"C:\dashboard-energia-brasil\dados_brutos\siga-empreendimentos-geracao-diario.csv"
)

# Confere se o arquivo está nessa pasta
if not caminho.is_file():
    raise FileNotFoundError(
        f"Arquivo não encontrado. Confira o caminho:\n{caminho}"
    )

print("Lendo o CSV...")

# Abre a tabela 
dados = pd.read_csv(
    caminho,
    sep=";",
    encoding="utf-8-sig",
    decimal=","
)

print("\nArquivo carregado!")
print("Quantidade de linhas:", dados.shape[0])
print("Quantidade de colunas:", dados.shape[1])

print("\nRegistros por tipo de geração:")
print(dados["SigTipoGeracao"].value_counts())

print("\nRegistros por fase da usina:")
print(dados["DscFaseUsina"].value_counts())

# Seleciona solar (UFV) e eólica (EOL) - em operação
usinas = dados.loc[
    dados["SigTipoGeracao"].isin(["UFV", "EOL"])
    & dados["DscFaseUsina"].eq("Operação")
].copy()

# Cria uma coluna com nomes simplidicados
usinas["Fonte"] = usinas["SigTipoGeracao"].map({
    "UFV": "Solar",
    "EOL": "Eólica"
})

print("\nUSINAS SOLARES E EÓLICAS EM OPERAÇÃO")
print("Total de registros:", len(usinas))

print("\nQuantidade por fonte:")
print(usinas["Fonte"].value_counts())

# Confere se o código identificador se repete
print("\nRegistros sem código CEG:")
print(usinas["CodCEG"].isna().sum())

print("\nCódigos CEG repetidos:")
print(usinas["CodCEG"].dropna().duplicated().sum())

print("\nAmostra dos dados selecionados:")
print(
    usinas[
        ["NomEmpreendimento", "SigUFPrincipal", "Fonte", "DscFaseUsina"]
    ].head(10).to_string(index=False)
)

# Converte a potência para número.
usinas["Potencia_Fiscalizada_kW"] = pd.to_numeric(
    usinas["MdaPotenciaFiscalizadaKw"]
    .astype("string")
    .str.replace(",", ".", regex=False),
    errors="coerce"
)

# 1 MW = 1.000 kW
usinas["Potencia_MW"] = usinas["Potencia_Fiscalizada_kW"] / 1000

# Confere possíveis problemas antes de somar
print("\nCONFERÊNCIA DA POTÊNCIA")
print("Valores ausentes ou não numéricos:",
      usinas["Potencia_MW"].isna().sum())
print("Valores negativos:",
      usinas["Potencia_MW"].lt(0).sum())
print("Valores iguais a zero:",
      usinas["Potencia_MW"].eq(0).sum())
print("Registros sem UF:",
      usinas["SigUFPrincipal"].isna().sum())

# Resumo por fonte
resumo_fonte = (
    usinas.groupby("Fonte", dropna=False)
    .agg(
        Quantidade_Usinas=("CodCEG", "nunique"),
        Potencia_MW=("Potencia_MW", lambda x: x.sum(min_count=1))
    )
    .reset_index()
)

# Resumo por estado e fonte
resumo_estado = (
    usinas.groupby(["SigUFPrincipal", "Fonte"], dropna=False)
    .agg(
        Quantidade_Usinas=("CodCEG", "nunique"),
        Potencia_MW=("Potencia_MW", lambda x: x.sum(min_count=1))
    )
    .reset_index()
    .rename(columns={"SigUFPrincipal": "UF"})
    .sort_values("Potencia_MW", ascending=False)
)

print("\nRESUMO POR FONTE — POTÊNCIA EM MW")
print(resumo_fonte.round(2).to_string(index=False))

print("\n10 MAIORES COMBINAÇÕES DE ESTADO E FONTE")
print(resumo_estado.head(10).round(2).to_string(index=False))

# Pasta dos arquivos tratados
pasta_saida = Path(r"C:\dashboard-energia-brasil\dados_tratados")
pasta_saida.mkdir(parents=True, exist_ok=True)

# Seleciona as colunas do dashboard
base_dashboard = usinas[
    [
        "CodCEG",
        "NomEmpreendimento",
        "SigUFPrincipal",
        "Fonte",
        "DscFaseUsina",
        "Potencia_MW",
        "DatGeracaoConjuntoDados"
    ]
].rename(columns={
    "CodCEG": "CEG",
    "NomEmpreendimento": "Usina",
    "SigUFPrincipal": "UF",
    "DscFaseUsina": "Fase",
    "DatGeracaoConjuntoDados": "Data_Referencia"
})

# Salva a base detalhada e os dois resumos
tabelas = {
    "usinas_operacao.csv": base_dashboard,
    "resumo_fonte.csv": resumo_fonte,
    "resumo_estado.csv": resumo_estado
}

for nome, tabela in tabelas.items():
    destino = pasta_saida / nome

    tabela.to_csv(
        destino,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    print("Arquivo salvo:", destino)
    
# Converte as coordenadas da base original para números
base_dashboard["Latitude"] = pd.to_numeric(
    usinas["NumCoordNEmpreendimento"]
    .astype("string")
    .str.replace(",", ".", regex=False),
    errors="coerce"
)

base_dashboard["Longitude"] = pd.to_numeric(
    usinas["NumCoordEEmpreendimento"]
    .astype("string")
    .str.replace(",", ".", regex=False),
    errors="coerce"
)

# Verificação inicial: coordenadas dentro dos limites globais
coordenadas_validas = (
    base_dashboard["Latitude"].between(-90, 90)
    & base_dashboard["Longitude"].between(-180, 180)
    & ~(
        base_dashboard["Latitude"].eq(0)
        & base_dashboard["Longitude"].eq(0)
    )
).fillna(False)

print("\nCONFERÊNCIA DAS COORDENADAS")
print("Total de usinas:", len(base_dashboard))
print("Com coordenadas válidas:", coordenadas_validas.sum())
print("Com coordenadas ausentes ou inválidas:",
      (~coordenadas_validas).sum())

# Remove somente as coordenadas inválidas - as usinas continuam na tabela e nos indicadores
base_dashboard.loc[
    ~coordenadas_validas, ["Latitude", "Longitude"]
] = float("nan")

# Atualiza o mesmo CSV usado no Power BI
base_dashboard.to_csv(
    pasta_saida / "usinas_operacao.csv",
    index=False,
    sep=";",
    decimal=",",
    encoding="utf-8-sig"
)

print("\nCSV atualizado com Latitude e Longitude!")