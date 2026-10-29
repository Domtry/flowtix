"""Node types, their ports, and graph validation."""

from collections import defaultdict

from .. import cron
from .expressions import OPERATORS

# type -> (input ports, output ports)
NODE_TYPES: dict[str, tuple[list[str], list[str]]] = {
    "trigger.manual": ([], ["main"]),
    "trigger.schedule": ([], ["main"]),
    "trigger.webhook": ([], ["main"]),
    "robot.run": (["main"], ["success", "error"]),
    "logic.if": (["main"], ["true", "false"]),
    "logic.switch": (["main"], []),  # outputs come from its cases, see output_ports()
    "logic.loop": (["main"], ["item", "done"]),
    "logic.wait": (["main"], ["main"]),
    "logic.merge": (["a", "b"], ["main"]),
    "data.read_file": (["main"], ["main"]),
    "data.filter": (["main"], ["kept", "rejected"]),
    "data.set": (["main"], ["main"]),
    "data.write_file": (["main"], ["main"]),
    "http.request": (["main"], ["success", "error"]),
    "email.send": (["main"], ["main"]),
    "ai.prompt": (["main"], ["main"]),
    "flow.end": (["main"], []),  # closing point: success or failure of the run
}
TRIGGERS = {"trigger.manual", "trigger.schedule", "trigger.webhook"}
MAX_NODES = 200
SWITCH_OPS = {"equals", "contains", "starts_with"}


def output_ports(node: dict) -> list[str]:
    if node.get("type") == "logic.switch":
        cases = (node.get("config") or {}).get("cases") or []
        return [c.get("id") for c in cases if c.get("id")] + ["default"]
    return NODE_TYPES[node["type"]][1]


def _config_issues(node: dict) -> list[str]:
    t, c = node["type"], node.get("config") or {}
    issues: list[str] = []
    if t == "trigger.schedule":
        if not c.get("cron"):
            issues.append("Planification : expression cron manquante")
        else:
            try:
                cron.parse(c["cron"])
            except ValueError as exc:
                issues.append(f"Planification invalide : {exc}")
    elif t == "flow.end" and c.get("result", "success") not in ("success", "failure"):
        issues.append("Résultat de fin invalide")
    elif t == "robot.run" and not c.get("process_id"):
        issues.append("Choisissez le processus à exécuter")
    elif t == "logic.switch":
        if not c.get("field"):
            issues.append("Indiquez le champ qui détermine la branche (ex. Option)")
        if c.get("op", "equals") not in SWITCH_OPS:
            issues.append("Comparaison invalide")
        cases = c.get("cases") or []
        if not cases:
            issues.append("Ajoutez au moins un cas")
        ids = [x.get("id") for x in cases]
        if len(set(ids)) != len(ids) or not all(ids) or "default" in ids:
            issues.append("Identifiants de cas invalides")
        if any(not str(x.get("value", "")).strip() for x in cases):
            issues.append("Un cas n'a pas de valeur")
    elif t in ("logic.if", "data.filter"):
        rules = c.get("rules") or []
        if not rules:
            issues.append("Ajoutez au moins une règle")
        for r in rules:
            if not r.get("field"):
                issues.append("Une règle n'a pas de champ")
            if r.get("op") not in OPERATORS:
                issues.append(f"Opérateur inconnu : {r.get('op')}")
    elif t == "logic.loop":
        try:
            if int(c.get("batch_size", 1)) < 1:
                raise ValueError
        except (TypeError, ValueError):
            issues.append("Taille de lot invalide")
    elif t == "logic.wait":
        try:
            if not 0 <= float(c.get("seconds", 0)) <= 3600:
                raise ValueError
        except (TypeError, ValueError):
            issues.append("Durée d'attente invalide (0 à 3600 s)")
    elif t == "data.read_file" and not c.get("file_id"):
        issues.append("Choisissez le fichier à lire")
    elif t == "data.write_file" and not c.get("filename"):
        issues.append("Nom du fichier de résultat manquant")
    elif t == "http.request":
        if not (c.get("url") or "").strip():
            issues.append("URL manquante")
        if c.get("method", "GET") not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            issues.append("Méthode HTTP invalide")
    elif t == "email.send":
        if not (c.get("to") or "").strip():
            issues.append("Destinataire manquant")
        if not (c.get("subject") or "").strip():
            issues.append("Objet manquant")
    elif t == "ai.prompt":
        if not c.get("model"):
            issues.append("Choisissez un modèle")
        if not (c.get("prompt") or "").strip():
            issues.append("Instruction (prompt) manquante")
        if not (c.get("output_field") or "").strip():
            issues.append("Champ de résultat manquant")
    return issues


def validate(graph: dict, robot_code: str | None = None,
             process_robots: dict[str, str | None] | None = None) -> list[dict]:
    """Return [{"node_id": id|None, "message": str}]; empty means runnable.

    process_robots ({process_id: robot_code}) enables the robot checks: every
    process node must run a process of the workflow's robot.
    """
    issues: list[dict] = []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if len(nodes) > MAX_NODES:
        return [{"node_id": None, "message": f"Trop de blocs (maximum {MAX_NODES})"}]

    by_id: dict[str, dict] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid or nid in by_id:
            issues.append({"node_id": nid, "message": "Identifiant de bloc manquant ou en double"})
            continue
        if n.get("type") not in NODE_TYPES:
            issues.append({"node_id": nid, "message": f"Type de bloc inconnu : {n.get('type')}"})
            continue
        by_id[nid] = n
        for msg in _config_issues(n):
            issues.append({"node_id": nid, "message": msg})

    if not any(n["type"] in TRIGGERS for n in by_id.values()):
        issues.append({"node_id": None, "message": "Ajoutez un point de démarrage (Début manuel, planifié ou API)"})
    if not any(n["type"] == "flow.end" for n in by_id.values()):
        issues.append({"node_id": None, "message": "Ajoutez un point de clôture (bloc Fin)"})

    process_nodes = [n for n in by_id.values() if n["type"] == "robot.run"]
    if process_nodes and not robot_code:
        issues.append({"node_id": None, "message": "Choisissez le robot du workflow"})
    if process_robots is not None:
        for n in process_nodes:
            pid = (n.get("config") or {}).get("process_id")
            if not pid:
                continue
            if pid not in process_robots:
                issues.append({"node_id": n["id"], "message": "Ce processus n'existe plus"})
            elif robot_code and process_robots[pid] and process_robots[pid] != robot_code:
                issues.append({"node_id": n["id"],
                               "message": f"Ce processus appartient au robot {process_robots[pid]}, "
                                          f"pas à {robot_code}"})

    adjacency: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for e in edges:
        src, tgt = by_id.get(e.get("source")), by_id.get(e.get("target"))
        if not src or not tgt:
            issues.append({"node_id": None, "message": "Une connexion pointe vers un bloc inexistant"})
            continue
        if e.get("source_port", "main") not in output_ports(src):
            issues.append({"node_id": src["id"], "message": f"Sortie inconnue : {e.get('source_port')}"})
        if e.get("target_port", "main") not in NODE_TYPES[tgt["type"]][0]:
            issues.append({"node_id": tgt["id"], "message": "Ce bloc n'accepte pas de connexion entrante ici"})
        incoming[tgt["id"]] += 1
        # edges into a loop node are the loop's return path: they don't make a cycle
        if tgt["type"] != "logic.loop":
            adjacency[src["id"]].append(tgt["id"])

    for nid, n in by_id.items():
        if n["type"] not in TRIGGERS and incoming[nid] == 0:
            issues.append({"node_id": nid, "message": "Bloc non relié : il ne sera jamais exécuté"})

    # cycles are only allowed through a loop node
    state: dict[str, int] = {}

    def visit(nid: str) -> bool:
        state[nid] = 1
        for nxt in adjacency[nid]:
            if state.get(nxt) == 1 or (state.get(nxt) is None and visit(nxt)):
                return True
        state[nid] = 2
        return False

    for nid in by_id:
        if state.get(nid) is None and visit(nid):
            issues.append({"node_id": None, "message": "Boucle infinie : un retour en arrière doit passer par un bloc « Boucle »"})
            break
    return issues
