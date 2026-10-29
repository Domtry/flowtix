export interface PortDef { id: string; label: string; }

export interface NodeTypeDef {
  type: string;
  label: string;
  category: string;
  description: string;
  color: string;
  icon: string;          // SVG inner markup, 24x24 viewBox, stroke icons
  inputs: PortDef[];
  outputs: PortDef[];
  defaults: () => any;
}

export interface WfNode { id: string; type: string; name: string; position: { x: number; y: number }; config: any; }
export interface WfEdge { id: string; source: string; source_port: string; target: string; target_port: string; }
export interface WfGraph { nodes: WfNode[]; edges: WfEdge[]; }

const MAIN_IN = [{ id: 'main', label: '' }];
const MAIN_OUT = [{ id: 'main', label: '' }];

export const CATEGORIES = ['Début et fin', 'Processus', 'Logique', 'Données', 'Intégrations'];

export const NODE_TYPES: NodeTypeDef[] = [
  {
    type: 'trigger.manual', label: 'Début — manuel', category: 'Début et fin', color: '#6366f1',
    description: 'Démarre le workflow avec le bouton « Lancer ».',
    icon: '<polygon points="7 4 19 12 7 20 7 4"/>',
    inputs: [], outputs: MAIN_OUT, defaults: () => ({}),
  },
  {
    type: 'trigger.schedule', label: 'Début — planifié', category: 'Début et fin', color: '#6366f1',
    description: 'Démarre le workflow selon un planning (cron).',
    icon: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>',
    inputs: [], outputs: MAIN_OUT, defaults: () => ({ cron: '0 8 * * 1-5', enabled: false }),
  },
  {
    type: 'trigger.webhook', label: 'Début — appel API', category: 'Début et fin', color: '#6366f1',
    description: 'Démarre le workflow quand un autre système appelle son URL (avec une clé).',
    icon: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    inputs: [], outputs: MAIN_OUT, defaults: () => ({}),
  },
  {
    type: 'flow.end', label: 'Fin', category: 'Début et fin', color: '#64748b',
    description: "Point de clôture d'une branche : termine le workflow avec succès ou en échec, avec un message.",
    icon: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    inputs: MAIN_IN, outputs: [], defaults: () => ({ result: 'success', message: '' }),
  },
  {
    type: 'robot.run', label: 'Exécuter un processus', category: 'Processus', color: '#10b981',
    description: 'Le robot du workflow rejoue un de ses processus enregistrés pour chaque élément, jusqu\'à la fin, en tapant les valeurs des champs.',
    icon: '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 4v4"/><circle cx="9" cy="14" r="1.5"/><circle cx="15" cy="14" r="1.5"/>',
    inputs: MAIN_IN, outputs: [{ id: 'success', label: 'succès' }, { id: 'error', label: 'erreur' }],
    defaults: () => ({ process_id: '', version_id: '', mapping: {}, keep_session: false, start_step_id: '' }),
  },
  {
    type: 'logic.if', label: 'Condition (Si)', category: 'Logique', color: '#f59e0b',
    description: 'Envoie chaque élément vers « vrai » ou « faux » selon des règles.',
    icon: '<path d="M6 3v6a6 6 0 0 0 6 6h6"/><polyline points="15 12 18 15 15 18"/><path d="M6 21v-6"/>',
    inputs: MAIN_IN, outputs: [{ id: 'true', label: 'vrai' }, { id: 'false', label: 'faux' }],
    defaults: () => ({ combine: 'and', rules: [{ field: '', op: 'equals', value: '' }] }),
  },
  {
    type: 'logic.switch', label: 'Aiguillage', category: 'Logique', color: '#f59e0b',
    description: 'Une sortie par valeur d\'un champ (ex. l\'option Santé) : chaque élément part vers le processus de son cas, les autres vers « autre ».',
    icon: '<circle cx="5" cy="12" r="2"/><path d="M7 12h4"/><path d="M11 12l6-6h2"/><path d="M11 12h8"/><path d="M11 12l6 6h2"/>',
    inputs: MAIN_IN, outputs: [],  // see outputsOf()
    defaults: () => ({ field: '', op: 'equals', cases: [{ id: newId('c'), value: '', label: '' }] }),
  },
  {
    type: 'logic.loop', label: 'Boucle', category: 'Logique', color: '#f59e0b',
    description: 'Traite les éléments un par un (ou par lots). Reliez la fin du traitement à l\'entrée de la boucle.',
    icon: '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    inputs: MAIN_IN, outputs: [{ id: 'item', label: 'élément' }, { id: 'done', label: 'terminé' }],
    defaults: () => ({ batch_size: 1 }),
  },
  {
    type: 'logic.wait', label: 'Attendre', category: 'Logique', color: '#f59e0b',
    description: 'Fait une pause avant de continuer.',
    icon: '<path d="M6 2h12M6 22h12M7 2v4l5 6 5-6V2M7 22v-4l5-6 5 6v4"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT, defaults: () => ({ seconds: 5 }),
  },
  {
    type: 'logic.merge', label: 'Fusionner', category: 'Logique', color: '#f59e0b',
    description: 'Regroupe deux branches (A puis B) en une seule.',
    icon: '<path d="M6 3v6a6 6 0 0 0 6 6"/><path d="M18 3v6a6 6 0 0 1-6 6v6"/>',
    inputs: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }], outputs: MAIN_OUT, defaults: () => ({}),
  },
  {
    type: 'data.read_file', label: 'Lire un fichier', category: 'Données', color: '#0ea5e9',
    description: 'Charge les lignes d\'un fichier Excel ou CSV : un élément par ligne.',
    icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT, defaults: () => ({ file_id: '', sheet: null }),
  },
  {
    type: 'data.filter', label: 'Filtrer', category: 'Données', color: '#0ea5e9',
    description: 'Garde les éléments qui respectent les règles.',
    icon: '<polygon points="22 3 2 3 10 12.5 10 19 14 21 14 12.5 22 3"/>',
    inputs: MAIN_IN, outputs: [{ id: 'kept', label: 'gardés' }, { id: 'rejected', label: 'écartés' }],
    defaults: () => ({ combine: 'and', rules: [{ field: '', op: 'not_empty', value: '' }] }),
  },
  {
    type: 'data.set', label: 'Modifier les champs', category: 'Données', color: '#0ea5e9',
    description: 'Ajoute, calcule, renomme ou supprime des champs.',
    icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT,
    defaults: () => ({ operations: [{ op: 'set', field: '', value: '', case: '' }], keep_only: '' }),
  },
  {
    type: 'data.write_file', label: 'Écrire un fichier', category: 'Données', color: '#0ea5e9',
    description: 'Enregistre les éléments dans un fichier Excel ou CSV téléchargeable après le run.',
    icon: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT, defaults: () => ({ filename: 'resultat', format: 'xlsx' }),
  },
  {
    type: 'http.request', label: 'Requête HTTP', category: 'Intégrations', color: '#8b5cf6',
    description: 'Appelle une API externe et ajoute sa réponse à l\'élément.',
    icon: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z"/>',
    inputs: MAIN_IN, outputs: [{ id: 'success', label: 'succès' }, { id: 'error', label: 'erreur' }],
    defaults: () => ({ method: 'GET', url: '', headers: [], body: '', per_item: true, response_field: 'reponse' }),
  },
  {
    type: 'email.send', label: 'Envoyer un e-mail', category: 'Intégrations', color: '#8b5cf6',
    description: 'Envoie un e-mail (un récapitulatif, ou un par élément).',
    icon: '<rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 6 12 13 2 6"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT,
    defaults: () => ({ to: '', subject: '', body: '', mode: 'once' }),
  },
  {
    type: 'ai.prompt', label: 'IA locale', category: 'Intégrations', color: '#8b5cf6',
    description: 'Demande au modèle local (Ollama) d\'analyser, classer ou extraire une information.',
    icon: '<path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/>',
    inputs: MAIN_IN, outputs: MAIN_OUT,
    defaults: () => ({ model: '', prompt: '', output_field: 'resultat_ia', json: false, max_tokens: 256, timeout_s: 180, think: false }),
  },
];

export const NODE_TYPE_MAP: Record<string, NodeTypeDef> =
  Object.fromEntries(NODE_TYPES.map(t => [t.type, t]));

export const OPERATORS: { id: string; label: string; unary?: boolean }[] = [
  { id: 'equals', label: 'est égal à' },
  { id: 'not_equals', label: 'est différent de' },
  { id: 'contains', label: 'contient' },
  { id: 'not_contains', label: 'ne contient pas' },
  { id: 'starts_with', label: 'commence par' },
  { id: 'ends_with', label: 'se termine par' },
  { id: 'empty', label: 'est vide', unary: true },
  { id: 'not_empty', label: 'n\'est pas vide', unary: true },
  { id: 'gt', label: 'est supérieur à' },
  { id: 'gte', label: 'est supérieur ou égal à' },
  { id: 'lt', label: 'est inférieur à' },
  { id: 'lte', label: 'est inférieur ou égal à' },
  { id: 'regex', label: 'correspond à (regex)' },
];

export function newId(prefix: string): string {
  return prefix + Math.random().toString(36).slice(2, 10);
}

/** Output ports of a node: fixed by type, except the switch whose cases are its outputs. */
export function outputsOf(n: WfNode): PortDef[] {
  if (n.type === 'logic.switch') {
    const cases: any[] = n.config?.cases || [];
    return [...cases.map(c => ({ id: c.id, label: (c.label || c.value || '?').toString() })),
            { id: 'default', label: 'autre' }];
  }
  return NODE_TYPE_MAP[n.type]?.outputs || [];
}

export function isDefaultProcessNodeName(name: string): boolean {
  return /^Exécuter (un|le) (robot|processus)( \d+)?$/.test((name || '').trim());
}
