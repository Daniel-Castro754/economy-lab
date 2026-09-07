from __future__ import annotations


def data_catalog() -> list[dict[str, object]]:
    return [
        {
            "id": "bcb_sgs",
            "title": "Banco Central do Brasil — SGS",
            "description": "Séries temporais do Sistema Gerenciador de Séries Temporais (SGS).",
            "identifier_label": "Código SGS",
            "examples": [
                {"series_id": "432", "title": "Meta Selic definida pelo Copom", "frequency": "daily", "unit": "% a.a."},
            ],
            "notes": [
                "Séries diárias exigem intervalo de datas nas consultas históricas extensas.",
                "O Economy Lab normaliza datas e valores numéricos, mas não altera a metodologia da série.",
            ],
        },
        {
            "id": "ibge_sidra",
            "title": "IBGE — API de dados agregados / SIDRA",
            "description": "API v3 de agregados que alimenta o SIDRA.",
            "identifier_label": "Agregado (tabela)",
            "examples": [],
            "notes": [
                "Informe agregado, períodos, variável e localidades conforme o Query Builder do IBGE.",
                "Classificações podem ser passadas no campo source_options.",
            ],
        },
        {
            "id": "world_bank",
            "title": "World Bank — Indicators API v2",
            "description": "Indicadores de desenvolvimento e macroeconomia por país.",
            "identifier_label": "Indicator code",
            "examples": [
                {"series_id": "NY.GDP.MKTP.KD.ZG", "title": "GDP growth (annual %)", "frequency": "annual", "unit": "%"},
                {"series_id": "SL.UEM.TOTL.ZS", "title": "Unemployment, total (% of total labor force)", "frequency": "annual", "unit": "%"},
            ],
            "notes": ["A API v2 não exige chave de autenticação."],
        },
        {
            "id": "ipeadata",
            "title": "Ipeadata",
            "description": "Séries macroeconômicas, sociais e regionais via API OData.",
            "identifier_label": "SERCODIGO",
            "examples": [],
            "notes": ["O conector usa ValoresSerie(SERCODIGO='...') e preserva o código original."],
        },
    ]
