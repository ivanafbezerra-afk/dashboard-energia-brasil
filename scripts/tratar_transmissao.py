from pathlib import Path
import pandas as pd
import geopandas as gpd

PASTA_PROJETO = Path(r"C:\dashboard-energia-brasil")
PASTA_BRUTOS = PASTA_PROJETO / "dados_brutos" / "transmissao"
PASTA_SAIDA = PASTA_PROJETO / "dados_tratados"
PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

arquivos = list(PASTA_BRUTOS.rglob("*.shp"))

if len(arquivos) != 1:
    raise ValueError(
        f"Esperava um shapefile, mas encontrei {len(arquivos)}."
    )

print("Lendo as linhas de transmissão...")
linhas = gpd.read_file(arquivos[0])

# Tabela sem geometria para Power BI
tabela = pd.DataFrame(
    linhas[["Nome", "Concession", "Tensao"]].copy()
)

tabela = tabela.rename(columns={
    "Nome": "Linha",
    "Concession": "Concessionaria",
    "Tensao": "Tensao_kV"
})

# Identificador de cada registro neste arquivo.
tabela.insert(0, "ID_Registro", range(1, len(tabela) + 1))

for coluna in ["Linha", "Concessionaria"]:
    tabela[coluna] = (
        tabela[coluna]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("Não informado")
    )

tabela["Tensao_kV"] = pd.to_numeric(
    tabela["Tensao_kV"].astype(str).str.replace(
        ",", ".", regex=False
    ),
    errors="coerce"
)

def rotulo_tensao(valor):
    if pd.isna(valor) or valor <= 0:
        return "Não informada / revisar"
    return f"{valor:g} kV".replace(".", ",")

tabela["Classe_Tensao"] = tabela["Tensao_kV"].apply(
    rotulo_tensao
)

tabela["Fonte_Dados"] = "EPE — Base Existente"
tabela["Data_Download"] = "2026-10-07"

arquivo_saida = PASTA_SAIDA / "transmissao_base_existente.csv"

tabela.to_csv(
    arquivo_saida,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    index=False
)

resumo = (
    tabela.groupby("Classe_Tensao", dropna=False)
    .size()
    .reset_index(name="Quantidade_Registros")
    .sort_values("Quantidade_Registros", ascending=False)
)

print("\nQuantidade de registros:", len(tabela))
print("\nRegistros por tensão:")
print(resumo.to_string(index=False))
print("\nArquivo criado:")
print(arquivo_saida)