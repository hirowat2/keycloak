"""Menu lateral do sistema, em seções, com os grupos que podem ver cada item."""

GRUPOS_CONSULTA = ["Admin", "Limited"]

SECOES = [
    {
        "titulo": "Assistente",
        "itens": [
            {"href": "/app/painel/", "label": "Painel", "icon": "fa-solid fa-gauge", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/realm/", "label": "1 · Realm e apps", "icon": "fa-solid fa-layer-group", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/grupos/", "label": "2 · Grupos e roles", "icon": "fa-solid fa-users-gear", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/sso/", "label": "3 · SSO corporativo", "icon": "fa-solid fa-building-shield", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/mapeamento/", "label": "4 · Grupos do SSO", "icon": "fa-solid fa-diagram-project", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/conferir/", "label": "5 · Conferir", "icon": "fa-solid fa-list-check", "required_groups": GRUPOS_CONSULTA},
        ],
    },
    {
        "titulo": "Manutenção",
        "itens": [
            {"href": "/app/migracao/", "label": "Migração da VM", "icon": "fa-solid fa-truck-arrow-right", "required_groups": GRUPOS_CONSULTA},
            {"href": "/app/historico/", "label": "Histórico", "icon": "fa-solid fa-clock-rotate-left", "required_groups": GRUPOS_CONSULTA},
        ],
    },
    {
        "titulo": "Sistema",
        "itens": [
            {"href": "/admin/", "label": "Administração", "icon": "fa-solid fa-gear", "required_groups": ["Admin"]},
        ],
    },
]
