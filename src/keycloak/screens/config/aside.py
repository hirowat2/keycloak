"""Menu lateral do sistema, em seções, com os grupos que podem ver cada item."""

GRUPOS_CONSULTA = ["Admin", "Master", "Tech", "Limited"]
GRUPOS_EDICAO = ["Admin", "Master", "Tech"]

SECOES = [
    {
        "titulo": "Comercial",
        "itens": [
            {"href": "/app/painel/", "label": "Painel comercial", "icon": "fa-solid fa-chart-pie", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/propostas/", "label": "Propostas", "icon": "fa-solid fa-file-signature", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/contratos/", "label": "Contratos", "icon": "fa-solid fa-file-contract", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/ndas/", "label": "NDAs", "icon": "fa-solid fa-user-shield", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/historico/", "label": "Histórico", "icon": "fa-solid fa-clock-rotate-left", "required_groups": GRUPOS_CONSULTA},
        ],
    },
    {
        "titulo": "Cadastros",
        "itens": [
            {"href": "/app/clientes/", "label": "Clientes", "icon": "fa-solid fa-address-book", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/catalogo/", "label": "Produtos e serviços", "icon": "fa-solid fa-box-open", "required_groups": GRUPOS_CONSULTA},
        ],
    },
    {
        "titulo": "Integração e ajuda",
        "itens": [
            {"href": "/app/sincronizacao/", "label": "Sincronização", "icon": "fa-solid fa-cloud-arrow-down", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/metodologia/", "label": "Metodologia", "icon": "fa-solid fa-diagram-project", "required_groups": GRUPOS_CONSULTA},
        ],
    },
    {
        "titulo": "Sistema",
        "itens": [
            {"href": "/admin/", "label": "Administração", "icon": "fa-solid fa-gear", "required_groups": ["Admin"]},
        ],
    },
]
