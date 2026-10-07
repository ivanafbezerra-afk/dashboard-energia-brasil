from pathlib import Path
import pandas as pd
import geopandas as gpd

PASTA = Path(r"C:\dashboard-energia-brasil")
PASTA_SAIDA = PASTA / "dados_tratados"

# 1. Ler as usinas
print("Lendo as usinas...")

dados = pd.read_csv(
    PASTA_SAIDA / "usinas_operacao.csv",
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    dtype={"CEG": "string"}
)

for coluna in ["Latitude", "Longitude"]:
    dados[coluna] = pd.to_numeric(
        dados[coluna].astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )

# Identificador de cada linha para evitar duplicidade
dados["ID_Linha"] = range(len(dados))

coordenadas_ok = (
    dados["Latitude"].between(-90, 90)
    & dados["Longitude"].between(-180, 180)
    & ~(
        dados["Latitude"].eq(0)
        & dados["Longitude"].eq(0)
    )
)

# 2. Transformar coordenadas em pontos
# Longitude = X; latitude = Y
# ref: EPSG:4326
pontos = gpd.GeoDataFrame(
    dados.loc[coordenadas_ok].copy(),
    geometry=gpd.points_from_xy(
        dados.loc[coordenadas_ok, "Longitude"],
        dados.loc[coordenadas_ok, "Latitude"]
    ),
    crs="EPSG:4326"
)

# 3. Ler os estados
arquivos = list(
    (PASTA / "dados_brutos" / "estados").rglob("BR_UF_2024.shp")
)

if len(arquivos) != 1:
    raise FileNotFoundError("Confira o shapefile dos estados.")

estados = gpd.read_file(arquivos[0])

# Transformar os pontos para o sistema da malha
pontos = pontos.to_crs(estados.crs)

# 4. Comparar os pontos com os polígonos estaduais
print("Comparando pontos e estados...")

cruzamento = gpd.sjoin(
    pontos,
    estados[["SIGLA_UF", "geometry"]],
    how="left",
    predicate="intersects"
)

# Um ponto em divisa pode intersectar mais de uma UF
ufs_por_linha = cruzamento.groupby("ID_Linha")["SIGLA_UF"].agg(
    lambda valores: sorted(set(valores.dropna()))
)

resultado = dados.copy()
resultado["UF_Espacial"] = resultado["ID_Linha"].map(
    ufs_por_linha.apply(lambda ufs: ";".join(ufs))
).fillna("")

resultado["Status_Localizacao"] = "Sem coordenadas utilizáveis"

for indice in resultado.index[coordenadas_ok]:
    ufs = ufs_por_linha.get(resultado.at[indice, "ID_Linha"], [])
    uf_cadastro = str(resultado.at[indice, "UF"]).strip().upper()

    if len(ufs) == 0:
        status = "Sem correspondência na malha"
    elif len(ufs) > 1:
        status = "Múltiplas UFs: revisar divisa"
    elif ufs[0] == uf_cadastro:
        status = "UF compatível"
    else:
        status = "UF divergente"

    resultado.at[indice, "Status_Localizacao"] = status

# 5. Exportar uma tabela de conferência separada
arquivo_saida = PASTA_SAIDA / "validacao_localizacao.csv"

resultado.drop(columns="ID_Linha").to_csv(
    arquivo_saida,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    index=False
)

print("\nRESULTADO DA CONFERÊNCIA:")
print(resultado["Status_Localizacao"].value_counts().to_string())
print("\nTotal de registros:", len(resultado))
print("\nTabela salva em:", arquivo_saida)

# Separar os registros que precisam de revisão espacial
revisar = resultado[
    resultado["Status_Localizacao"].isin([
        "UF divergente",
        "Sem correspondência na malha",
        "Múltiplas UFs: revisar divisa"
    ])
].copy()

colunas_revisao = [
    "CEG", "Usina", "Fonte", "UF", "UF_Espacial",
    "Latitude", "Longitude", "Status_Localizacao"
]

revisar[colunas_revisao].to_csv(
    PASTA_SAIDA / "usinas_revisar_localizacao.csv",
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    index=False
)

print("\nPRIMEIROS CASOS PARA REVISÃO:")
print(revisar[colunas_revisao].head(10).to_string(index=False))

# Exportar os pontos sinalizados para revisão no QGIS
ids_revisao = revisar["ID_Linha"]

pontos_revisao = pontos[
    pontos["ID_Linha"].isin(ids_revisao)
].copy()

pontos_revisao = pontos_revisao.merge(
    resultado[[
        "ID_Linha",
        "UF_Espacial",
        "Status_Localizacao"
    ]],
    on="ID_Linha",
    how="left",
    validate="one_to_one"
)

arquivo_gpkg = PASTA_SAIDA / "revisao_localizacao.gpkg"

pontos_revisao.to_file(
    arquivo_gpkg,
    layer="usinas_revisar",
    driver="GPKG"
)

print("\nPontos exportados para o QGIS:", len(pontos_revisao))
print("Arquivo:", arquivo_gpkg)