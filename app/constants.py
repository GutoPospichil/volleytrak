EVENT_KIND_LABELS = {
    "serve": "Saque",
    "reception": "Recepção",
    "set": "Levantamento",
    "attack": "Ataque",
    "block": "Bloqueio",
    "dig": "Defesa",
    "error": "Erro",
    "point": "Ponto",
    "touch": "Toque (auto)",
    "other": "Outro",
}

MANUAL_EVENT_KINDS = {
    key: value for key, value in EVENT_KIND_LABELS.items() if key != "touch"
}

STATUS_LABELS = {
    "uploaded": "Aguardando",
    "processing": "Processando",
    "done": "Concluído",
    "error": "Erro",
}

CLIP_REJECTION_LABELS = {
    "dead_time": "Tempo morto",
    "ball_on_floor": "Bola no chão",
    "not_rally": "Não é rally",
    "bad_cut": "Corte errado",
    "half_rally": "Rally pela metade",
    "duplicate": "Duplicado",
    "other": "Outro",
}

CALIBRATION_MODES = {
    "full": {
        "label": "Quadra inteira (4 cantos)",
        "point_labels": [
            "Fundo esquerdo",
            "Fundo direito",
            "Frente direito",
            "Frente esquerdo",
        ],
        "court_points": [(0.0, 0.0), (0.0, 9.0), (18.0, 9.0), (18.0, 0.0)],
        "hint": "Clique nos 4 cantos da quadra, começando pelo fundo esquerdo e seguindo em sentido horário.",
    },
    "far_attack": {
        "label": "Fundo + ataque do fundo",
        "point_labels": [
            "Fundo esquerdo",
            "Fundo direito",
            "Ataque fundo direito",
            "Ataque fundo esquerdo",
        ],
        "court_points": [(0.0, 0.0), (0.0, 9.0), (6.0, 9.0), (6.0, 0.0)],
        "hint": "Clique nos cantos da linha de fundo e depois nos cantos da linha de ataque do lado distante.",
    },
    "center": {
        "label": "Fundo + linha central",
        "point_labels": [
            "Fundo esquerdo",
            "Fundo direito",
            "Central direito",
            "Central esquerdo",
        ],
        "court_points": [(0.0, 0.0), (0.0, 9.0), (9.0, 9.0), (9.0, 0.0)],
        "hint": "Clique nos cantos da linha de fundo e depois nos cantos da linha central, sob a rede.",
    },
    "near_attack": {
        "label": "Fundo + ataque da frente",
        "point_labels": [
            "Fundo esquerdo",
            "Fundo direito",
            "Ataque frente direito",
            "Ataque frente esquerdo",
        ],
        "court_points": [(0.0, 0.0), (0.0, 9.0), (12.0, 9.0), (12.0, 0.0)],
        "hint": "Clique nos cantos da linha de fundo e depois nos cantos da linha de ataque do lado próximo.",
    },
}
