export const RUN_STATUS_LABELS: Record<string, string> = {
  queued: 'En attente', running: 'En cours', cancelling: 'Annulation…',
  succeeded: 'Réussi', partial: 'Partiel', failed: 'Échec', cancelled: 'Annulé',
};

export const ITEM_STATUS_LABELS: Record<string, string> = {
  pending: 'À faire', running: 'En cours', succeeded: 'Réussi', failed: 'Échec', skipped: 'Non traité',
};

export const TRIGGER_LABELS: Record<string, string> = {
  manual: 'manuel', schedule: 'planifié', api: 'API', retry: 'relance',
};

export const CRON_PRESETS = [
  { label: 'Tous les jours ouvrés à 8h', cron: '0 8 * * 1-5' },
  { label: 'Tous les jours à 7h', cron: '0 7 * * *' },
  { label: 'Toutes les heures (8h-18h, jours ouvrés)', cron: '0 8-18 * * 1-5' },
  { label: 'Toutes les 30 minutes', cron: '*/30 * * * *' },
  { label: 'Chaque lundi à 9h', cron: '0 9 * * 1' },
  { label: 'Le 1er du mois à 6h', cron: '0 6 1 * *' },
];
