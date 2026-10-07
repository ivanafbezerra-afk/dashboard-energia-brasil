from pathlib import Path
from html import escape
import webbrowser

import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import FastMarkerCluster


# 1. Caminhos dos arquivos
PASTA_PROJETO = Path(r"C:\dashboard-energia-brasil")

ARQUIVO_CSV = (
    PASTA_PROJETO / "dados_tratados" / "usinas_operacao.csv"
)

PASTA_MAPAS = PASTA_PROJETO / "mapas"
PASTA_MAPAS.mkdir(parents=True, exist_ok=True)

ARQUIVO_MAPA = PASTA_MAPAS / "mapa_usinas_brasil.html"

if not ARQUIVO_CSV.exists():
    raise FileNotFoundError(
        f"CSV não encontrado. Confira este caminho:\n{ARQUIVO_CSV}"
    )


# Simplificação apenas para visualização
TOLERANCIA_ESTADOS_M = 200
TOLERANCIA_TRANSMISSAO_M = 50


def preparar_geometrias_mapa(tabela, tolerancia_m, nome):
    if tabela.geometry.isna().any() or tabela.geometry.is_empty.any():
        raise ValueError(f"{nome}: existem geometrias ausentes ou vazias.")
    projetada = tabela.to_crs(epsg=5880).copy()
    simplificadas = projetada.geometry.simplify(
        tolerance=tolerancia_m,
        preserve_topology=True
    )
    # Se a simplificação gerar problema, manter a geometria desse registro.
    utilizaveis = (
        simplificadas.notna()
        & ~simplificadas.is_empty
        & simplificadas.is_valid
    )
    projetada.loc[utilizaveis, "geometry"] = simplificadas.loc[utilizaveis]
    resultado = projetada.to_crs(epsg=4326)
    if len(resultado) != len(tabela):
        raise ValueError(f"{nome}: a quantidade de registros mudou.")
    print(f"{nome}: {len(resultado):,} registros; simplificação de {tolerancia_m} m")
    return resultado


# 2. Ler a tabela tratada
print("Lendo o CSV...")

dados = pd.read_csv(
    ARQUIVO_CSV,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    dtype={"CEG": "string"}
)

colunas_necessarias = [
    "CEG", "Usina", "UF", "Fonte",
    "Potencia_MW", "Latitude", "Longitude"
]

faltantes = [
    coluna for coluna in colunas_necessarias
    if coluna not in dados.columns
]

if faltantes:
    raise ValueError(f"Colunas ausentes no CSV: {faltantes}")


# 3. Converter coordenadas e potência para números
for coluna in ["Latitude", "Longitude", "Potencia_MW"]:
    dados[coluna] = pd.to_numeric(
        dados[coluna].astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )


# 4. Selecionar registros com coordenadas utilizáveis
coordenadas_ok = (
    dados["Latitude"].between(-90, 90)
    & dados["Longitude"].between(-180, 180)
    & ~(
        dados["Latitude"].eq(0)
        & dados["Longitude"].eq(0)
    )
)

usinas_mapa = dados.loc[
    coordenadas_ok & dados["Fonte"].isin(["Solar", "Eólica"])
].copy()

if usinas_mapa.empty:
    raise ValueError("Nenhuma usina com coordenadas utilizáveis.")

print(f"Registros no CSV: {len(dados):,}")
print(f"Registros para o mapa: {len(usinas_mapa):,}")


# 5. Criar o mapa
mapa = folium.Map(
    location=[-14.5, -53],
    zoom_start=4,
    tiles="OpenStreetMap",
    control_scale=True
)

# 5.1. Adicionar limites estaduais do IBGE
print("Lendo os limites estaduais...")

PASTA_ESTADOS = PASTA_PROJETO / "dados_brutos" / "estados"

arquivos_estados = list(
    PASTA_ESTADOS.rglob("BR_UF_2024.shp")
)

if len(arquivos_estados) != 1:
    raise FileNotFoundError(
        "Esperava encontrar exatamente um BR_UF_2024.shp "
        f"em {PASTA_ESTADOS}, mas encontrei "
        f"{len(arquivos_estados)}."
    )

estados = gpd.read_file(arquivos_estados[0])

if estados.crs is None:
    raise ValueError("A malha estadual está sem sistema de coordenadas.")

# Selecionar os campos que aparecerão no mapa.
estados_mapa = estados[
    ["NM_UF", "SIGLA_UF", "geometry"]
].copy()
estados_mapa = preparar_geometrias_mapa(
    estados_mapa, TOLERANCIA_ESTADOS_M, "Limites estaduais"
)

folium.GeoJson(
    data=estados_mapa.to_json(),
    name="Limites estaduais — IBGE 2024",
    overlay=True,
    show=True,
    style_function=lambda feature: {
        "color": "#555555",
        "weight": 1.2,
        "opacity": 0.8,
        "fillOpacity": 0
    },
    highlight_function=lambda feature: {
        "color": "#222222",
        "weight": 2.5,
        "fillOpacity": 0.05
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["NM_UF", "SIGLA_UF"],
        aliases=["Estado:", "UF:"],
        sticky=False
    )
).add_to(mapa)

print(f"Limites estaduais adicionados: {len(estados_mapa)} UFs")

# 6. Definir como cada marcador aparece no navegador
callback = """
function(row) {
    var icone = L.divIcon({
        className: '',
        html: '<div style="background:' + row[3] +
              ';width:10px;height:10px;border-radius:50%;' +
              'border:1px solid white;"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });

    var marcador = L.marker(
        [row[0], row[1]],
        {icon: icone}
    );

    marcador.bindPopup(row[2], {maxWidth: 300});
    return marcador;
}
"""

cores = {
    "Eólica": "#0072B2",
    "Solar": "#D4B900"
}


# 7. Criar uma camada para cada fonte
for fonte, cor in cores.items():
    grupo = usinas_mapa.loc[usinas_mapa["Fonte"].eq(fonte)]
    pontos = []

    for usina in grupo.itertuples(index=False):
        if pd.isna(usina.Potencia_MW):
            potencia = "Não informada"
        else:
            potencia = (
                f"{usina.Potencia_MW:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
                + " MW"
            )

        popup = (
            f"<b>{escape(str(usina.Usina))}</b><br>"
            f"CEG: {escape(str(usina.CEG))}<br>"
            f"Estado: {escape(str(usina.UF))}<br>"
            f"Fonte: {escape(fonte)}<br>"
            f"Potência fiscalizada: {potencia}"
        )

        pontos.append([
            float(usina.Latitude),
            float(usina.Longitude),
            popup,
            cor
        ])

    if pontos:
        FastMarkerCluster(
            data=pontos,
            callback=callback,
            name=f"{fonte} ({len(pontos):,} registros)",
            options={
                "chunkedLoading": True,
                "maxClusterRadius": 40
            }
        ).add_to(mapa)

    print(f"Camada {fonte}: {len(pontos):,} registros")

# 7.1. Adicionar linhas de transmissão da EPE
print("Lendo as linhas de transmissão...")

PASTA_TRANSMISSAO = (
    PASTA_PROJETO / "dados_brutos" / "transmissao"
)

arquivos_transmissao = list(
    PASTA_TRANSMISSAO.rglob("*.shp")
)

if len(arquivos_transmissao) != 1:
    raise ValueError(
        "Esperava encontrar um shapefile de transmissão, "
        f"mas encontrei {len(arquivos_transmissao)}."
    )

linhas = gpd.read_file(arquivos_transmissao[0])

if linhas.crs is None:
    raise ValueError(
        "As linhas de transmissão estão sem sistema de coordenadas."
    )

#  cópia para exibição no mapa.
linhas_mapa = linhas[
    ["Nome", "Concession", "Tensao", "geometry"]
].copy()

for coluna in ["Nome", "Concession"]:
    linhas_mapa[coluna] = linhas_mapa[coluna].apply(
        lambda valor: (
            "Não informado"
            if pd.isna(valor)
            else escape(str(valor))
        )
    )

def formatar_tensao(valor):
    numero = pd.to_numeric(str(valor).replace(",", "."), errors="coerce")
    if pd.isna(numero) or numero <= 0:
        return "Não informada / revisar"
    return f"{numero:g} kV".replace(".", ",")

linhas_mapa["Tensao"] = linhas_mapa["Tensao"].apply(
    formatar_tensao
)

linhas_mapa = preparar_geometrias_mapa(
    linhas_mapa, TOLERANCIA_TRANSMISSAO_M, "Transmissão"
)

campos = ["Nome", "Concession", "Tensao"]
rotulos = ["Linha:", "Concessionária:", "Tensão:"]

folium.GeoJson(
    data=linhas_mapa.to_json(),
    name=f"Transmissão — EPE ({len(linhas_mapa):,} registros)",
    overlay=True,
    show=False,
    style_function=lambda feature: {
        "color": "#7B3294",
        "weight": 2,
        "opacity": 0.8
    },
    highlight_function=lambda feature: {
        "color": "#B35806",
        "weight": 4,
        "opacity": 1
    },
    tooltip=folium.GeoJsonTooltip(
        fields=campos,
        aliases=rotulos,
        sticky=False
    ),
    popup=folium.GeoJsonPopup(
        fields=campos,
        aliases=rotulos,
        max_width=350
    )
).add_to(mapa)

print(
    f"Linhas de transmissão adicionadas: "
    f"{len(linhas_mapa)} registros"
)

# 8. Controle para ativar e desativar as fontes
folium.LayerControl(collapsed=False).add_to(mapa)


# 9. Legenda e informações do projeto
legenda = """
<div style="
    position:fixed;
    bottom:35px;
    left:15px;
    z-index:9999;
    background:white;
    padding:12px;
    border:1px solid #bbb;
    border-radius:6px;
    font-family:Arial;
    font-size:12px;
    max-width:280px;
">
    <b>Usinas solares e eólicas em operação</b><br><br>
    <span style="color:#0072B2;">●</span> Eólica<br>
    <span style="color:#D4B900;">●</span> Solar<br><br>
    <span style="color:#7B3294;">━</span> Linhas de transmissão<br>
    Fonte: ANEEL — SIGA<br>
    Transmissão: EPE — Base Existente<br>
    Limites estaduais: IBGE — malha 2024<br>
    Referência das usinas: 05/10/2026<br>
    Download da transmissão: 07/10/2026<br>
    Potência fiscalizada em MW.<br>
    Recorte: UFV e EOL em operação; não inclui MMGD.<br>
    Apenas registros com coordenadas utilizáveis.<br>
    Agrupamentos mostram a quantidade de registros.<br>
    Geometrias simplificadas para visualização.<br><br>
    Elaboração: Ivana Bezerra
</div>
"""

mapa.get_root().html.add_child(folium.Element(legenda))


# 10. Salvar e abrir o resultado
print("Salvando o mapa...")

mapa.save(str(ARQUIVO_MAPA))

print(f"Mapa criado:\n{ARQUIVO_MAPA}")
tamanho_mb = ARQUIVO_MAPA.stat().st_size / (1024 ** 2)
print(f"Tamanho do HTML: {tamanho_mb:.2f} MB")

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread

# Se o script já abriu um servidor neste console, encerrar antes.
if "servidor_mapa" in globals():
    servidor_mapa.shutdown()
    servidor_mapa.server_close()

# Servir somente a pasta mapas, no próprio computador.
handler = partial(
    SimpleHTTPRequestHandler,
    directory=str(PASTA_MAPAS)
)

servidor_mapa = ThreadingHTTPServer(
    ("127.0.0.1", 0),
    handler
)

Thread(
    target=servidor_mapa.serve_forever,
    daemon=True
).start()

porta = servidor_mapa.server_address[1]
endereco = f"http://127.0.0.1:{porta}/{ARQUIVO_MAPA.name}"

print(f"Abra o mapa neste endereço: {endereco}")
webbrowser.open(endereco)