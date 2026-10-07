from pathlib import Path
import geopandas as gpd

PASTA_ESTADOS = Path(
    r"C:\dashboard-energia-brasil\dados_brutos\estados"
)

# Procurar o shapefile, mesmo se a extração criou uma subpasta
arquivos = list(PASTA_ESTADOS.rglob("BR_UF_2024.shp"))

if len(arquivos) != 1:
    raise FileNotFoundError(
        "Esperava encontrar um BR_UF_2024.shp na pasta estados. "
        f"Encontrei {len(arquivos)}. Confira a extração do ZIP."
    )

estados = gpd.read_file(arquivos[0])

print("Arquivo carregado:", arquivos[0])
print("Quantidade de unidades da Federação:", len(estados))
print("Sistema de coordenadas:", estados.crs)
print("Colunas disponíveis:", estados.columns.tolist())
print(estados.head())
