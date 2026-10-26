"""Prompt templates for RPA AI tasks."""

from __future__ import annotations

from .models import AiTask

SYSTEM_PROMPT = (
    "Tu es un assistant IA intégré dans une plateforme RPA (FlowtTix). "
    "Tu analyses des captures d'écran, des données et des scénarios d'automatisation. "
    "Réponds de manière concise et structurée en JSON quand demandé."
)

TASK_TEMPLATES: dict[AiTask, str] = {
    AiTask.CLASSIFY: (
        "Classifie l'élément suivant parmi les catégories: {categories}.\n"
        "Données: {data}\n"
        "Réponds en JSON: {{\"category\": \"...\", \"confidence\": 0.0}}"
    ),
    AiTask.EXTRACT: (
        "Extrais les informations suivantes depuis le contenu:\n"
        "Champs à extraire: {fields}\n"
        "Contenu: {data}\n"
        "Réponds en JSON avec les champs demandés."
    ),
    AiTask.SUMMARIZE: (
        "Résume le contenu suivant en {max_length} mots maximum:\n{data}"
    ),
    AiTask.GENERATE: "{prompt}",
    AiTask.DECIDE: (
        "Étant donné le contexte suivant, quelle action est la plus appropriée?\n"
        "Contexte: {context}\n"
        "Actions possibles: {actions}\n"
        "Réponds en JSON: {{\"action\": \"...\", \"reason\": \"...\"}}"
    ),
    AiTask.REPAIR_SELECTOR: (
        "Le sélecteur CSS/XPath suivant ne fonctionne plus:\n"
        "Sélecteur: {selector}\n"
        "HTML de la page (extrait): {html}\n"
        "Propose un nouveau sélecteur qui cible le même élément.\n"
        "Réponds en JSON: {{\"selector\": \"...\", \"strategy\": \"css|xpath\", \"confidence\": 0.0}}"
    ),
    AiTask.DESCRIBE_SCREEN: (
        "Décris ce que tu vois dans cette capture d'écran.\n"
        "Identifie les éléments interactifs (boutons, champs, liens) et leur état.\n"
        "Réponds en JSON: {{\"description\": \"...\", \"elements\": [...]}}"
    ),
}


def build_prompt(task: AiTask, context: dict) -> str:
    template = TASK_TEMPLATES.get(task, "{prompt}")
    try:
        return template.format(**context)
    except KeyError:
        return context.get("prompt", template)
