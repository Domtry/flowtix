import { ChangeDetectorRef, Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { NODE_TYPE_MAP, OPERATORS, isDefaultProcessNodeName, newId, outputsOf } from './workflow-catalog';
import { CRON_PRESETS, ITEM_STATUS_LABELS } from './pipeline-labels';

@Component({
  selector: 'app-node-config',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    @if (node) {
    <div class="panel">
      <div class="head">
        <span class="dot" [style.background]="def.color"></span>
        <input class="name" [(ngModel)]="node.name" (ngModelChange)="emit()" />
        <button class="icon-btn" title="Fermer" (click)="close.emit()">✕</button>
      </div>
      <p class="desc">{{ def.description }}</p>

      @if (runResult) {
        <div class="tabs">
          <button [class.on]="tab === 'config'" (click)="tab = 'config'">Paramètres</button>
          <button [class.on]="tab === 'data'" (click)="tab = 'data'">Données du run</button>
        </div>
      }

      @if (tab === 'config' || !runResult) {
      <div class="body">
        @for (msg of issues; track msg) { <div class="issue">{{ msg }}</div> }

        @switch (node.type) {
          @case ('trigger.manual') {
            <p class="muted">Utilisez le bouton « Lancer » de la barre d'outils. Le workflow démarre avec un élément vide.</p>
          }

          @case ('trigger.schedule') {
            <label>Modèle</label>
            <select [ngModel]="''" (ngModelChange)="node.config.cron = $event; emit()">
              <option value="">— Choisir un modèle —</option>
              @for (p of presets; track p.cron) { <option [value]="p.cron">{{ p.label }}</option> }
            </select>
            <label>Expression cron</label>
            <input class="mono" [(ngModel)]="node.config.cron" (ngModelChange)="emit()" placeholder="0 8 * * 1-5" />
            <span class="hint">minute heure jour mois jour-semaine — heure d'Abidjan (UTC)</span>
            <label class="check"><input type="checkbox" [(ngModel)]="node.config.enabled" (ngModelChange)="emit()" /> Planification active</label>
            <span class="hint">Si un run est encore en cours à l'heure prévue, ce lancement est ignoré.</span>
          }

          @case ('trigger.webhook') {
            <div class="row">
              <button class="btn-secondary btn-sm" (click)="newKey()">{{ hasApiKey ? 'Régénérer la clé' : 'Générer une clé' }}</button>
              @if (hasApiKey && !apiKey) { <span class="hint">Une clé existe (affichée seulement à sa création).</span> }
            </div>
            @if (apiKey) {
              <div class="warn">Copiez la clé, elle ne sera plus affichée :<code>{{ apiKey }}</code></div>
            }
            <label>Appel</label>
            <pre class="code">{{ curlRun() }}</pre>
            <span class="hint">{{ bodyHint }}</span>
            <label>Suivre le run</label>
            <pre class="code">{{ curlStatus() }}</pre>
          }

          @case ('robot.run') {
            @if (!robotCode) {
              <div class="issue">Choisissez d'abord le robot du workflow (en haut, à côté du nom).</div>
            }
            <label>Processus{{ robotCode ? ' du robot ' + robotCode : '' }}</label>
            <select [(ngModel)]="node.config.process_id" (ngModelChange)="onProcessChange()">
              <option value="">— Choisir —</option>
              @for (p of robotProcesses(); track p.id) { <option [value]="p.id">{{ p.name }}</option> }
            </select>
            @if (robotCode && processes.length && !robotProcesses().length) {
              <span class="hint">Aucun processus enregistré pour ce robot : enregistrez-en un depuis « Processes ».</span>
            }
            @if (currentProcess(); as cp) {
              @if (robotCode && cp.robot_code && cp.robot_code !== robotCode) {
                <div class="issue">Ce processus a été enregistré pour le robot {{ cp.robot_code }}.</div>
              }
            }
            @if (node.config.process_id) {
              <label>Version</label>
              <select [(ngModel)]="node.config.version_id" (ngModelChange)="loadRobot(); emit()">
                <option value="">Toujours la dernière</option>
                @for (v of versions; track v.id) { <option [value]="v.id">v{{ v.version }} ({{ v.status }})</option> }
              </select>
              <label class="check session">
                <input type="checkbox" [(ngModel)]="node.config.keep_session" (ngModelChange)="emit()" />
                Continuer dans la session en cours (ne pas relancer l'application)
              </label>
              @if (node.config.keep_session) {
                <label>Reprendre à l'étape</label>
                <select [(ngModel)]="node.config.start_step_id" (ngModelChange)="emit()">
                  <option value="">Juste après l'ouverture de l'application</option>
                  @for (s of processSteps; track s.step_id) {
                    <option [value]="s.step_id">#{{ s.index }} {{ s.label }}{{ s.window_title && s.label.indexOf(s.window_title) < 0 ? ' — ' + s.window_title : '' }}</option>
                  }
                </select>
                <span class="hint">L'application doit déjà être ouverte (par un bloc précédent ou un run antérieur).
                  Choisissez l'étape qui suit la connexion pour ne pas se reconnecter, ex. le clic sur le menu du formulaire.
                  Chaque élément reprend à cette étape.</span>
              }
              <label>Valeurs à taper</label>
              <span class="hint">Pour chaque saisie enregistrée : laissez vide pour taper la valeur enregistrée, ou indiquez un champ, ex. {{ '{{' }}Login{{ '}}' }}.</span>
              @if (!visibleFields().length) { <p class="muted">Aucune saisie de texte {{ node.config.keep_session ? 'après l\'étape de reprise' : 'enregistrée' }}.</p> }
              @for (f of visibleFields(); track f.step_id) {
                <div class="map-row">
                  <div class="map-ctx">
                    <span class="muted">#{{ f.index }}</span>
                    {{ f.after_click ? 'Après « ' + f.after_click + ' »' : f.window_title }}
                    <span class="mono rec">{{ f.recorded_value }}</span>
                  </div>
                  <div class="with-picker">
                    <input class="mono" [(ngModel)]="node.config.mapping[f.step_id]" (ngModelChange)="emit()" placeholder="valeur enregistrée" />
                    <ng-container *ngTemplateOutlet="picker; context: { obj: node.config.mapping, key: f.step_id, replace: true }"></ng-container>
                  </div>
                </div>
              }
            }
          }

          @case ('flow.end') {
            <label>Résultat</label>
            <select [(ngModel)]="node.config.result" (ngModelChange)="emit()">
              <option value="success">Terminé avec succès</option>
              <option value="failure">Terminé en échec</option>
            </select>
            <label>Message (facultatif)</label>
            <textarea rows="3" [(ngModel)]="node.config.message" (ngModelChange)="emit()"
              placeholder="{{ '{{' }}nombre{{ '}}' }} contrat(s) non traité(s), ex. {{ '{{' }}Nom{{ '}}' }}"></textarea>
            <ng-container *ngTemplateOutlet="picker; context: { obj: node.config, key: 'message' }"></ng-container>
            <span class="hint">Si des éléments arrivent sur une Fin « en échec », le run est marqué en échec
              (ou partiel si d'autres ont fini avec succès) et ce message s'affiche dans l'historique.
              {{ '{{' }}nombre{{ '}}' }} = nombre d'éléments arrivés ici.</span>
          }

          @case ('logic.switch') {
            <label>Champ qui détermine la branche</label>
            <input [(ngModel)]="node.config.field" (ngModelChange)="emit()" placeholder="Option" [attr.list]="'fields-' + node.id" />
            <label>Le champ…</label>
            <select [(ngModel)]="node.config.op" (ngModelChange)="emit()">
              <option value="equals">est égal à</option>
              <option value="contains">contient</option>
              <option value="starts_with">commence par</option>
            </select>
            <label>Cas (une sortie chacun)</label>
            @for (c of node.config.cases; track c.id; let i = $index) {
              <div class="row">
                <input [(ngModel)]="c.value" (ngModelChange)="emit()" placeholder="valeur, ex. Confort" />
                <input [(ngModel)]="c.label" (ngModelChange)="emit()" placeholder="nom de la sortie (facultatif)" />
                <button class="icon-btn" title="Retirer ce cas (et ses connexions)" (click)="node.config.cases.splice(i, 1); emit()">✕</button>
              </div>
            }
            <button class="btn-ghost btn-sm" (click)="addCase()">+ Cas</button>
            <span class="hint">Chaque élément part vers le premier cas correspondant (sans tenir compte des majuscules) ;
              les autres sortent par « autre ». Reliez chaque sortie au processus de la variante.</span>
          }

          @case ('logic.if') { <ng-container *ngTemplateOutlet="rules"></ng-container> }
          @case ('data.filter') { <ng-container *ngTemplateOutlet="rules"></ng-container> }

          @case ('logic.loop') {
            <label>Éléments par tour</label>
            <input type="number" min="1" [(ngModel)]="node.config.batch_size" (ngModelChange)="emit()" />
            <span class="hint">« élément » : relie le traitement d'un tour ; reliez la fin de ce traitement à l'entrée de la Boucle.
              « terminé » : tous les éléments, une fois la boucle finie.</span>
          }

          @case ('logic.wait') {
            <label>Durée (secondes)</label>
            <input type="number" min="0" max="3600" [(ngModel)]="node.config.seconds" (ngModelChange)="emit()" />
          }

          @case ('logic.merge') {
            <p class="muted">Attend les deux branches puis transmet les éléments de A suivis de ceux de B.
              Si une branche n'a rien produit, transmet l'autre seule.</p>
          }

          @case ('data.read_file') {
            <label>Fichier</label>
            <div class="row">
              <select [(ngModel)]="node.config.file_id" (ngModelChange)="node.config.sheet = null; loadPreview(); emit()">
                <option value="">— Choisir —</option>
                @for (f of files; track f.id) { <option [value]="f.id">{{ f.filename }} ({{ f.row_count ?? '?' }} lignes)</option> }
              </select>
              <label class="btn-secondary btn-sm file-btn">Importer…
                <input type="file" accept=".xlsx,.xls,.xlsm,.csv" (change)="upload($event)" hidden />
              </label>
            </div>
            @if (uploading) { <span class="hint">Lecture du fichier…</span> }
            @if (preview?.sheets?.length > 1) {
              <label>Onglet</label>
              <select [ngModel]="node.config.sheet || preview.sheets[0]" (ngModelChange)="node.config.sheet = $event; loadPreview(); emit()">
                @for (s of preview.sheets; track s) { <option [value]="s">{{ s }}</option> }
              </select>
            }
            @if (preview?.error) { <div class="issue">{{ preview.error }}</div> }
            @if (preview?.columns?.length) {
              <span class="hint">{{ preview.row_count }} ligne(s) — colonnes : {{ preview.columns.join(', ') }}</span>
              <div class="table-wrap"><table>
                <thead><tr>@for (c of preview.columns; track c) { <th>{{ c }}</th> }</tr></thead>
                <tbody>@for (r of preview.preview; track $index) { <tr>@for (c of preview.columns; track c) { <td>{{ r[c] }}</td> }</tr> }</tbody>
              </table></div>
            }
          }

          @case ('data.set') {
            @for (op of node.config.operations; track $index; let i = $index) {
              <div class="op">
                <div class="row">
                  <select [(ngModel)]="op.op" (ngModelChange)="emit()" class="op-kind">
                    <option value="set">Définir</option>
                    <option value="rename">Renommer</option>
                    <option value="remove">Supprimer</option>
                  </select>
                  <input [(ngModel)]="op.field" (ngModelChange)="emit()" placeholder="champ" [attr.list]="'fields-' + node.id" />
                  <button class="icon-btn" title="Retirer" (click)="node.config.operations.splice(i, 1); emit()">✕</button>
                </div>
                @if (op.op === 'set') {
                  <div class="with-picker">
                    <input [(ngModel)]="op.value" (ngModelChange)="emit()" placeholder="valeur, ex. {{ '{{' }}Prénom{{ '}}' }} {{ '{{' }}Nom{{ '}}' }}" />
                    <ng-container *ngTemplateOutlet="picker; context: { obj: op, key: 'value' }"></ng-container>
                  </div>
                  <select [(ngModel)]="op.case" (ngModelChange)="emit()">
                    <option value="">Tel quel</option>
                    <option value="upper">MAJUSCULES</option>
                    <option value="lower">minuscules</option>
                    <option value="capitalize">Initiales En Majuscule</option>
                    <option value="trim">Sans espaces autour</option>
                  </select>
                }
                @if (op.op === 'rename') {
                  <input [(ngModel)]="op.to" (ngModelChange)="emit()" placeholder="nouveau nom" />
                }
              </div>
            }
            <button class="btn-ghost btn-sm" (click)="node.config.operations.push({ op: 'set', field: '', value: '', case: '' }); emit()">+ Opération</button>
            <label>Ne garder que ces champs (facultatif)</label>
            <input [(ngModel)]="node.config.keep_only" (ngModelChange)="emit()" placeholder="Nom, Montant, Statut" />
          }

          @case ('data.write_file') {
            <label>Nom du fichier</label>
            <input [(ngModel)]="node.config.filename" (ngModelChange)="emit()" placeholder="resultat" />
            <label>Format</label>
            <select [(ngModel)]="node.config.format" (ngModelChange)="emit()">
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="csv">CSV (;)</option>
            </select>
            <span class="hint">Le fichier est téléchargeable dans le détail du run. Les éléments continuent vers le bloc suivant.</span>
          }

          @case ('http.request') {
            <div class="row">
              <select [(ngModel)]="node.config.method" (ngModelChange)="emit()" class="method">
                @for (m of ['GET','POST','PUT','PATCH','DELETE']; track m) { <option [value]="m">{{ m }}</option> }
              </select>
              <input class="mono" [(ngModel)]="node.config.url" (ngModelChange)="emit()" placeholder="https://api.exemple.ci/clients/{{ '{{' }}Code{{ '}}' }}" />
            </div>
            <label>En-têtes</label>
            @for (h of node.config.headers; track $index; let i = $index) {
              <div class="row">
                <input [(ngModel)]="h.key" (ngModelChange)="emit()" placeholder="Authorization" />
                <input [(ngModel)]="h.value" (ngModelChange)="emit()" placeholder="valeur" />
                <button class="icon-btn" (click)="node.config.headers.splice(i, 1); emit()">✕</button>
              </div>
            }
            <button class="btn-ghost btn-sm" (click)="node.config.headers.push({ key: '', value: '' }); emit()">+ En-tête</button>
            @if (['POST','PUT','PATCH'].includes(node.config.method)) {
              <label>Corps</label>
              <textarea class="mono" rows="5" [(ngModel)]="node.config.body" (ngModelChange)="emit()" placeholder='{"nom": "{{ "{{" }}Nom{{ "}}" }}"}'></textarea>
              <ng-container *ngTemplateOutlet="picker; context: { obj: node.config, key: 'body' }"></ng-container>
            }
            <label>Champ qui reçoit la réponse</label>
            <input [(ngModel)]="node.config.response_field" (ngModelChange)="emit()" />
            <label class="check"><input type="checkbox" [(ngModel)]="node.config.per_item" (ngModelChange)="emit()" /> Un appel par élément (sinon un seul appel)</label>
          }

          @case ('email.send') {
            @if (smtpMissing) {
              <div class="issue">Aucun serveur e-mail configuré. <a routerLink="/settings">Le configurer dans Settings</a></div>
            }
            <label>Destinataires (séparés par ;)</label>
            <input [(ngModel)]="node.config.to" (ngModelChange)="emit()" placeholder="equipe@sanlam.ci" />
            <label>Objet</label>
            <div class="with-picker">
              <input [(ngModel)]="node.config.subject" (ngModelChange)="emit()" placeholder="Saisies terminées : {{ '{{' }}nombre{{ '}}' }} contrats" />
              <ng-container *ngTemplateOutlet="picker; context: { obj: node.config, key: 'subject' }"></ng-container>
            </div>
            <label>Message</label>
            <textarea rows="6" [(ngModel)]="node.config.body" (ngModelChange)="emit()"></textarea>
            <ng-container *ngTemplateOutlet="picker; context: { obj: node.config, key: 'body' }"></ng-container>
            <label>Envoi</label>
            <select [(ngModel)]="node.config.mode" (ngModelChange)="emit()">
              <option value="once">Un seul e-mail (champ {{ '{{' }}nombre{{ '}}' }} = nombre d'éléments)</option>
              <option value="per_item">Un e-mail par élément</option>
            </select>
          }

          @case ('ai.prompt') {
            <label>Modèle</label>
            <select [(ngModel)]="node.config.model" (ngModelChange)="emit()">
              <option value="">— Choisir —</option>
              @for (m of models; track m.name) { <option [value]="m.name">{{ m.name }} {{ m.parameter_size ? '(' + m.parameter_size + ')' : '' }}</option> }
            </select>
            @if (!models.length) { <span class="hint">Aucun modèle trouvé sur Ollama.</span> }
            <label>Instruction</label>
            <textarea rows="6" [(ngModel)]="node.config.prompt" (ngModelChange)="emit()"
              placeholder="Classe ce sinistre dans une catégorie (auto, habitation, santé) : {{ '{{' }}Description{{ '}}' }}"></textarea>
            <ng-container *ngTemplateOutlet="picker; context: { obj: node.config, key: 'prompt' }"></ng-container>
            <label>Champ qui reçoit la réponse</label>
            <input [(ngModel)]="node.config.output_field" (ngModelChange)="emit()" />
            <label class="check"><input type="checkbox" [(ngModel)]="node.config.json" (ngModelChange)="emit()" /> Réponse au format JSON (pour extraire plusieurs champs)</label>
            <div class="grid2">
              <div><label>Longueur max. (tokens)</label><input type="number" [(ngModel)]="node.config.max_tokens" (ngModelChange)="emit()" /></div>
              <div><label>Délai max. (s)</label><input type="number" [(ngModel)]="node.config.timeout_s" (ngModelChange)="emit()" /></div>
            </div>
            <label class="check"><input type="checkbox" [(ngModel)]="node.config.think" (ngModelChange)="emit()" /> Laisser le modèle « réfléchir » (plus lent)</label>
          }
        }
      </div>
      } @else {
      <div class="body">
        <div class="stats">
          <span class="badge" [attr.data-status]="runResult.status">{{ statusLabel(runResult.status) }}</span>
          <span>{{ runResult.items_in }} en entrée</span>
          @for (p of outPorts(); track p.id) {
            <span>→ {{ runResult.items_out?.[p.id] || 0 }} {{ p.label || 'en sortie' }}</span>
          }
          <span class="muted">{{ runResult.duration_ms | number }} ms</span>
        </div>
        @if (runResult.error) { <div class="issue">{{ runResult.error }}</div> }
        @if (runItems.length) {
          <label>Exécutions du robot</label>
          <div class="table-wrap"><table>
            <thead><tr><th>#</th><th>Données</th><th>Statut</th><th></th></tr></thead>
            <tbody>
              @for (it of runItems; track it.id) {
                <tr>
                  <td class="muted">{{ it.row_index + 1 }}</td>
                  <td class="small">{{ summary(it.row_data) }}@if (it.error) { <div class="err">{{ it.error }}</div> }</td>
                  <td><span class="badge" [attr.data-status]="it.status">{{ itemLabel(it.status) }}</span></td>
                  <td>@if (it.execution_id) { <a [routerLink]="['/executions', it.execution_id]">Détail</a> }</td>
                </tr>
              }
            </tbody>
          </table></div>
          @if (hasFailures()) {
            <button class="btn-secondary btn-sm" (click)="retry.emit(node.id)">Relancer les éléments en échec</button>
          }
        }
        @if (runResult.sample_in?.length) {
          <label>Entrée (aperçu)</label>
          <pre class="code json">{{ runResult.sample_in | json }}</pre>
        }
        @for (p of outPorts(); track p.id) {
          @if (runResult.sample_out?.[p.id]?.length) {
            <label>Sortie {{ p.label }} (aperçu)</label>
            <pre class="code json">{{ runResult.sample_out[p.id] | json }}</pre>
          }
        }
      </div>
      }

      <div class="foot">
        <button class="btn-ghost btn-sm" (click)="duplicate.emit(node)">Dupliquer</button>
        <button class="btn-ghost btn-sm danger" (click)="remove.emit(node)">Supprimer le bloc</button>
      </div>

      <datalist [id]="'fields-' + node.id">@for (f of fields; track f) { <option [value]="f"></option> }</datalist>

      <ng-template #rules>
        <label>Les éléments vont vers « {{ node.type === 'logic.if' ? 'vrai' : 'gardés' }} » si</label>
        <select [(ngModel)]="node.config.combine" (ngModelChange)="emit()">
          <option value="and">toutes les règles sont vraies</option>
          <option value="or">au moins une règle est vraie</option>
        </select>
        @for (r of node.config.rules; track $index; let i = $index) {
          <div class="rule">
            <input [(ngModel)]="r.field" (ngModelChange)="emit()" placeholder="champ" [attr.list]="'fields-' + node.id" />
            <select [(ngModel)]="r.op" (ngModelChange)="emit()">
              @for (o of operators; track o.id) { <option [value]="o.id">{{ o.label }}</option> }
            </select>
            @if (!isUnary(r.op)) { <input [(ngModel)]="r.value" (ngModelChange)="emit()" placeholder="valeur ou {{ '{{' }}champ{{ '}}' }}" /> }
            <button class="icon-btn" (click)="node.config.rules.splice(i, 1); emit()">✕</button>
          </div>
        }
        <button class="btn-ghost btn-sm" (click)="node.config.rules.push({ field: '', op: 'equals', value: '' }); emit()">+ Règle</button>
        <span class="hint">Comparaisons sans tenir compte des majuscules ; les nombres acceptent « 1 000,50 ».</span>
      </ng-template>

      <ng-template #picker let-obj="obj" let-key="key" let-replace="replace">
        @if (fields.length) {
          <select class="picker" [ngModel]="''" (ngModelChange)="insert(obj, key, $event, replace)" title="Insérer un champ">
            <option value="">+ champ</option>
            @for (f of fields; track f) { <option [value]="f">{{ f }}</option> }
          </select>
        }
      </ng-template>
    </div>
    }
  `,
  styles: [`
    .panel { display: flex; flex-direction: column; height: 100%; }
    .head { display: flex; align-items: center; gap: 8px; padding: 14px 16px 6px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .name { flex: 1; font-weight: 600; font-size: 14px; background: transparent; border: 1px solid transparent; padding: 4px 6px; }
    .name:hover, .name:focus { border-color: var(--border-color); }
    .desc { font-size: 12px; color: var(--text-muted); margin: 0 16px 8px; }
    .tabs { display: flex; gap: 4px; margin: 0 16px; border-bottom: 1px solid var(--border-color); }
    .tabs button { background: none; border: none; color: var(--text-muted); padding: 8px 10px; cursor: pointer; font-size: 12px; border-bottom: 2px solid transparent; }
    .tabs button.on { color: var(--text-primary); border-bottom-color: var(--color-indigo); }
    .body { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; }
    .body > * { flex-shrink: 0; } /* the body scrolls; its blocks must keep their height */
    label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); font-weight: 600; margin-top: 8px; }
    label.session { margin-top: 12px; padding: 8px 10px; border: 1px solid rgba(16,185,129,.35); border-radius: var(--radius-md); background: rgba(16,185,129,.08); }
    label.check { text-transform: none; letter-spacing: 0; font-size: 13px; color: var(--text-primary); font-weight: 400; display: flex; gap: 6px; align-items: center; }
    input, select, textarea { width: 100%; }
    input[type=checkbox] { width: auto; flex-shrink: 0; }
    textarea { resize: vertical; }
    .hint { font-size: 11px; color: var(--text-muted); }
    .muted { color: var(--text-muted); font-size: 12px; }
    .small { font-size: 12px; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .row { display: flex; gap: 6px; align-items: center; }
    .row > input, .row > select { flex: 1; }
    .method { max-width: 90px; flex: 0 0 90px !important; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .issue { background: var(--color-red-bg); color: var(--color-red); padding: 6px 10px; border-radius: var(--radius-md); font-size: 12px; }
    .issue a { color: inherit; text-decoration: underline; }
    .warn { background: var(--color-amber-bg); color: var(--color-amber); padding: 8px 10px; border-radius: var(--radius-md); font-size: 12px; display: flex; flex-direction: column; gap: 6px; }
    .warn code { font-family: var(--font-mono); color: var(--text-primary); word-break: break-all; }
    pre.code { background: var(--bg-page); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 8px 10px; font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; word-break: break-all; margin: 0; }
    pre.json { max-height: 220px; overflow: auto; }
    .rule, .op { display: flex; flex-direction: column; gap: 4px; padding: 8px; border: 1px solid var(--border-color); border-radius: var(--radius-md); position: relative; }
    .rule { padding-right: 32px; }
    .rule .icon-btn { position: absolute; top: 6px; right: 6px; }
    .op-kind { max-width: 120px; flex: 0 0 120px !important; }
    .map-row { display: flex; flex-direction: column; gap: 4px; padding: 6px 0; border-bottom: 1px solid var(--border-color); }
    .map-ctx { font-size: 12px; }
    .rec { color: var(--text-muted); margin-left: 6px; }
    .with-picker { display: flex; gap: 4px; }
    .with-picker > input { flex: 1; }
    .picker { width: auto; max-width: 110px; font-size: 11px; }
    .icon-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 2px 6px; border-radius: 4px; }
    .icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
    .file-btn { cursor: pointer; white-space: nowrap; margin: 0; text-transform: none; letter-spacing: 0;
      font-size: 12px; font-weight: 500; color: var(--text-primary); padding: 7px 12px; flex-shrink: 0; }
    .table-wrap { overflow: auto; max-height: 240px; border: 1px solid var(--border-color); border-radius: var(--radius-md); }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { text-align: left; font-size: 10px; text-transform: uppercase; color: var(--text-muted); padding: 6px 8px; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; background: var(--bg-secondary); }
    td { padding: 6px 8px; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
    td.small { white-space: normal; }
    .err { color: var(--color-red); }
    .stats { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; font-size: 12px; }
    .badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; background: var(--color-gray-bg); color: var(--text-secondary); }
    .badge[data-status=success], .badge[data-status=succeeded] { background: var(--color-green-bg); color: var(--color-green); }
    .badge[data-status=error], .badge[data-status=failed] { background: var(--color-red-bg); color: var(--color-red); }
    .badge[data-status=warning] { background: var(--color-amber-bg); color: var(--color-amber); }
    .badge[data-status=running] { background: var(--color-blue-bg); color: var(--color-blue); }
    .foot { display: flex; justify-content: space-between; padding: 10px 16px; border-top: 1px solid var(--border-color); }
    .danger { color: var(--color-red); }
  `]
})
export class NodeConfigComponent implements OnChanges {
  // `any`: nested ng-templates lose the @if (node) narrowing under strict templates
  @Input() node: any = null;
  @Input() pipelineId = '';
  @Input() fields: string[] = [];
  @Input() issues: string[] = [];
  @Input() hasApiKey = false;
  @Input() robotCode = '';
  @Input() runResult: any = null;
  @Input() runItems: any[] = [];
  @Output() changed = new EventEmitter<void>();
  @Output() close = new EventEmitter<void>();
  @Output() remove = new EventEmitter<any>();
  @Output() duplicate = new EventEmitter<any>();
  @Output() retry = new EventEmitter<string>();
  @Output() filesChanged = new EventEmitter<void>();
  @Output() keyCreated = new EventEmitter<void>();

  tab: 'config' | 'data' = 'config';
  presets = CRON_PRESETS;
  operators = OPERATORS;
  processes: any[] = [];
  versions: any[] = [];
  robotFields: any[] = [];
  processSteps: any[] = [];
  private autoSession = false;
  files: any[] = [];
  preview: any = null;
  models: any[] = [];
  smtpMissing = false;
  uploading = false;
  apiKey = '';
  origin = window.location.origin;
  private lastNodeId = '';

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  get def() { return NODE_TYPE_MAP[this.node!.type]; }

  ngOnChanges(ch: SimpleChanges) {
    if (!this.node) return;
    if (this.node.id !== this.lastNodeId) {
      this.lastNodeId = this.node.id;
      this.tab = this.runResult ? 'data' : 'config';
      this.apiKey = '';
      this.preview = null;
      this.load();
    } else if (ch['runResult'] && this.runResult && !ch['runResult'].previousValue) {
      this.tab = 'data';
    }
  }

  private load() {
    const t = this.node!.type;
    if (t === 'robot.run') {
      this.api.getProcesses().subscribe(p => { this.processes = p; this.cdr.detectChanges(); });
      this.loadRobot();
    } else if (t === 'data.read_file') {
      this.loadFiles();
      this.loadPreview();
    } else if (t === 'ai.prompt') {
      this.api.aiModels().subscribe({ next: m => { this.models = m; this.cdr.detectChanges(); }, error: () => this.models = [] });
    } else if (t === 'email.send') {
      this.api.getSmtp().subscribe(s => { this.smtpMissing = !s?.host; this.cdr.detectChanges(); });
    }
  }

  currentProcess() {
    return this.processes.find(p => p.id === this.node?.config?.process_id) || null;
  }

  /** Processes of the workflow's robot (plus those recorded without a robot). */
  robotProcesses() {
    const current = this.node?.config?.process_id;
    return this.processes.filter(p => !this.robotCode || !p.robot_code || p.robot_code === this.robotCode || p.id === current);
  }

  /** Inputs actually typed: when continuing a session, those before the resume step are skipped. */
  visibleFields() {
    const c = this.node?.config;
    if (!c?.keep_session) return this.robotFields;
    let start: number;
    if (c.start_step_id) {
      start = this.processSteps.find(s => s.step_id === c.start_step_id)?.index ?? 0;
    } else {
      start = this.processSteps.find(s => !['browser.navigate', 'browser.wait'].includes(s.type))?.index ?? 0;
    }
    return this.robotFields.filter(f => f.index >= start);
  }

  addCase() {
    this.node.config.cases.push({ id: newId('c'), value: '', label: '' });
    this.emit();
  }

  onProcessChange() {
    const c = this.node.config;
    c.version_id = '';
    c.mapping = {};
    c.start_step_id = '';
    this.autoSession = true;
    // a generic name is replaced by the process name, so the canvas tells processes apart
    const p = this.currentProcess();
    if (p && isDefaultProcessNodeName(this.node.name)) {
      this.node.name = p.name;
    }
    this.loadRobot();
    this.emit();
  }

  loadRobot() {
    const c = this.node!.config;
    this.robotFields = [];
    c.version_id ??= '';  // converted pipelines store null; '' selects "Toujours la dernière"
    c.start_step_id ??= '';
    this.processSteps = [];
    if (!c.process_id) return;
    this.api.getProcessSteps(c.process_id, c.version_id || null).subscribe(s => {
      this.processSteps = s;
      if (this.autoSession) {
        // a process recorded "in the open session" has no opening step: it must continue one
        this.autoSession = false;
        const continues = s.length > 0 && !s.some(x => x.type === 'browser.navigate');
        if (continues && !c.keep_session) { c.keep_session = true; this.emit(); }
      }
      // a version change may remove the chosen step: fall back to "after opening"
      if (c.start_step_id && !s.some(x => x.step_id === c.start_step_id)) { c.start_step_id = ''; this.emit(); }
      this.cdr.detectChanges();
    });
    this.api.getVersions(c.process_id).subscribe(v => { this.versions = [...v].sort((a, b) => b.version - a.version); this.cdr.detectChanges(); });
    this.api.getRobotFields(c.process_id, c.version_id || null).subscribe(f => {
      this.robotFields = f;
      c.mapping = c.mapping || {};
      for (const field of f) { c.mapping[field.step_id] ??= ''; }
      this.cdr.detectChanges();
    });
  }

  loadFiles() {
    this.api.getPipelineFiles(this.pipelineId).subscribe(f => { this.files = f; this.cdr.detectChanges(); });
  }

  loadPreview() {
    const c = this.node!.config;
    this.preview = null;
    if (!c.file_id) return;
    this.api.getPipelineFile(c.file_id, c.sheet).subscribe({
      next: p => { this.preview = p; this.cdr.detectChanges(); },
      error: () => { this.preview = { error: 'Fichier introuvable : importez-le à nouveau' }; this.cdr.detectChanges(); },
    });
  }

  upload(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.uploading = true;
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = String(reader.result).split(',')[1] || '';
      this.api.uploadPipelineFile(this.pipelineId, file.name, b64).subscribe({
        next: f => {
          this.uploading = false;
          this.node!.config.file_id = f.id;
          this.node!.config.sheet = null;
          this.preview = f;
          this.loadFiles();
          this.filesChanged.emit();
          this.emit();
        },
        error: e => { this.uploading = false; this.preview = { error: e.error?.detail || 'Fichier refusé' }; this.cdr.detectChanges(); },
      });
    };
    reader.readAsDataURL(file);
  }

  newKey() {
    if (this.hasApiKey && !confirm('La clé actuelle ne fonctionnera plus. Continuer ?')) return;
    this.api.regeneratePipelineKey(this.pipelineId).subscribe(r => {
      this.apiKey = r.api_key;
      this.keyCreated.emit();
      this.cdr.detectChanges();
    });
  }

  insert(obj: any, key: string, field: string, replace = false) {
    if (!field) return;
    const tag = '{{' + field + '}}';
    obj[key] = replace || !obj[key] ? tag : `${obj[key]} ${tag}`;
    this.emit();
  }

  bodyHint = '{"rows": [...]} : un élément par ligne. Un autre objet JSON : un seul élément. Corps vide : un élément vide.';

  curlRun() {
    return `curl -X POST ${this.origin}/api/v1/pipelines/${this.pipelineId}/trigger \\\n`
      + `  -H "X-API-Key: ${this.apiKey || '<clé>'}" \\\n`
      + `  -H "Content-Type: application/json" \\\n`
      + `  -d '{"rows": [{"Nom": "KOUASSI"}]}'`;
  }

  curlStatus() {
    return `curl ${this.origin}/api/v1/pipelines/${this.pipelineId}/trigger/<run_id> -H "X-API-Key: <clé>"`;
  }

  emit() { this.changed.emit(); }
  isUnary(op: string) { return OPERATORS.find(o => o.id === op)?.unary; }
  outPorts() { return outputsOf(this.node); }
  hasFailures() { return this.runItems.some(i => i.status === 'failed' || i.status === 'skipped'); }
  statusLabel(s: string) { return ({ success: 'OK', warning: 'Avec erreurs', error: 'Erreur' } as any)[s] || s; }
  itemLabel(s: string) { return ITEM_STATUS_LABELS[s] || s; }
  summary(row: any) {
    return Object.entries(row || {}).filter(([k]) => !k.startsWith('_')).slice(0, 4).map(([k, v]) => `${k}: ${v}`).join(' · ');
  }
}
