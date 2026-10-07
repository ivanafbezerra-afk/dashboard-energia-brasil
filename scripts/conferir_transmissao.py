from pathlib import Path
import geopandas as gpd

PASTA = Path(
    r"C:\dashboard-energia-brasil\dados_brutos\transmissao"
)

arquivos = list(PASTA.rglob("*.shp"))

if len(arquivos) != 1:
    raise ValueError(
        f"Esperava encontrar um shapefile, mas encontrei {len(arquivos)}.\n"
        f"Arquivos: {arquivos}"
    )

arquivo = arquivos[0]

print("Lendo:", arquivo.name)

linhas = gpd.read_file(arquivo)

print("\nQuantidade de registros:", len(linhas))
print("\nSistema de coordenadas:", linhas.crs)

print("\nTipos de geometria:")
print(linhas.geom_type.value_counts())

print("\nColunas disponíveis:")
print(linhas.columns.tolist())

print("\nPrimeiros 3 registros:")
print(linhas.drop(columns="geometry").head(3).to_string(index=False))

print("\nGeometrias ausentes:", linhas.geometry.isna().sum())
print("Geometrias vazias:", linhas.geometry.is_empty.sum())
print("Geometrias inválidas:", (~linhas.geometry.is_valid).sum())