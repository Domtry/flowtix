import { ChangeDetectorRef, Component, ElementRef, HostListener, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { NodeConfigComponent } from './node-config';
import { SafeSvgPipe } from './safe-svg.pipe';
import {
  CATEGORIES, NODE_TYPES, NODE_TYPE_MAP, NodeTypeDef, OPERATORS, PortDef, WfEdge, WfGraph, WfNode,
  isDefaultProcessNodeName, newId, outputsOf,
} from './workflow-catalog';
import { RUN_STATUS_LABELS, TRIGGER_LABELS } from './pipeline-labels';

const NODE_W = 210;
const ACTIVE = ['queued', 'running', 'cancelling'];

interface Pt { x: number; y: number; }

@Component({
  selector: 'app-workflow-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, NodeConfigComponent, SafeSvgPipe],
  template: `
    <div class="editor">
      <!-- toolbar -->
      <div class="toolbar">
        <a routerLink="/pipelines" class="back" title="Retour aux workflows">←</a>
        <input class="wf-name" [(ngModel)]="name" (ngModelChange)="markDirty()" />
        <label class="robot-pick" [class.missing]="!robotCode" title="Tous les processus du workflow sont exécutés par ce robot">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 4v4"/><circle cx="9" cy="14" r="1.5"/><circle cx="15" cy="14" r="1.5"/></svg>
          Robot
          <select [(ngModel)]="robotCode" (ngModelChange)="markDirty()">
            <option value="">— à choisir —</option>
            @for (r of robots; track r.code) { <option [value]="r.code">{{ r.code }} — {{ r.name }}</option> }
          </select>
        </label>
        <span class="save-state" [class.dirty]="dirty">{{ dirty ? 'Modifications non enregistrées' : 'Enregistré' }}</span>
        @if (issues.length) {
          <div class="issues-wrap">
            <button class="issues-btn" (click)="showIssues = !showIssues">⚠ {{ issues.length }} problème(s)</button>
            @if (showIssues) {
              <div class="issues-pop">
                @for (i of issues; track $index) {
                  <div class="issue-line" (click)="i.node_id && select(i.node_id); showIssues = false">
                    <strong>{{ nodeName(i.node_id) }}</strong> {{ i.message }}
                  </div>
                }
              </div>
            }
          </div>
        }
        <span class="spacer"></span>
        <div class="zoom">
          <button (click)="zoomBy(1/1.2)" title="Dézoomer">−</button>
          <span>{{ (zoom * 100) | number:'1.0-0' }}%</span>
          <button (click)="zoomBy(1.2)" title="Zoomer">+</button>
          <button (click)="fit()" title="Tout afficher">⤢</button>
        </div>
        <button class="icon-del" (click)="deleteWorkflow()" title="Supprimer ce workflow">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </button>
        @if (hasSchedule()) {
          <button class="btn-ghost sched" [class.on]="scheduleActive()" (click)="toggleSchedule()"
                  [title]="scheduleActive() ? 'Les lancements planifiés sont actifs' : 'Les lancements planifiés sont suspendus'">
            {{ scheduleActive() ? '⏸ Suspendre le planning' : '▶ Reprendre le planning' }}
          </button>
        }
        <button class="btn-secondary" (click)="save()" [disabled]="!dirty || saving">Enregistrer</button>
        @if (activeRun()) {
          <button class="btn-danger" (click)="stopAll()" [disabled]="stopping" title="Arrêter l'exécution en cours (et celles en attente)">
            ■ {{ stopping ? 'Arrêt…' : 'Arrêter' }}
          </button>
        } @else {
          <button class="btn-primary" (click)="run()" [disabled]="dirty || !!issues.length || !hasManual()"
                  [title]="runTitle()">▶ Lancer</button>
        }
      </div>

      @if (error) { <div class="banner error" (click)="error = ''">{{ error }}</div> }

      <div class="main">
        <!-- palette -->
        <aside class="palette">
          <input class="search" [(ngModel)]="search" placeholder="Rechercher un bloc…" />
          @for (cat of categories; track cat) {
            @if (paletteItems(cat).length) {
              <div class="cat">{{ cat }}</div>
              @for (t of paletteItems(cat); track t.type) {
                <div class="pal-item" draggable="true" (dragstart)="onPaletteDrag($event, t)" (click)="addAtCenter(t)"
                     [title]="t.description">
                  <span class="pal-icon" [style.color]="t.color">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" [innerHTML]="t.icon | safeSvg"></svg>
                  </span>
                  {{ t.label }}
                </div>
              }
            }
          }
          <p class="pal-hint">Glissez un bloc sur la toile, puis reliez une sortie (●) à l'entrée d'un autre bloc.</p>
        </aside>

        <!-- canvas -->
        <div class="canvas" #canvas (mousedown)="onCanvasDown($event)" (wheel)="onWheel($event)"
             (dragover)="$event.preventDefault()" (drop)="onDrop($event)">
          <div class="world" [style.transform]="'translate(' + pan.x + 'px,' + pan.y + 'px) scale(' + zoom + ')'">
            <!-- large drawing area: browsers don't hit-test SVG content outside its box -->
            <svg class="edges"><g transform="translate(50000,50000)">
              @for (e of graph.edges; track e.id) {
                <g (mousedown)="$event.stopPropagation(); selectEdge(e.id)">
                  <path class="hit" [attr.d]="edgePath(e)"></path>
                  <path class="edge" [class.sel]="selectedEdge === e.id" [class.active]="edgeActive(e)" [attr.d]="edgePath(e)"></path>
                </g>
              }
              @if (connecting) {
                <path class="edge temp" [attr.d]="curve(portPos(connecting.node, connecting.port, 'out'), connecting.to)"></path>
              }
            </g></svg>

            @for (n of graph.nodes; track n.id) {
              <div class="node" [style.left.px]="n.position.x" [style.top.px]="n.position.y"
                   [style.height.px]="nodeH(n)" [style.--c]="nodeColor(n)" [class.end]="n.type === 'flow.end'"
                   [class.sel]="selectedNode === n.id" [class.has-issue]="nodeIssues(n.id).length"
                   [attr.data-run]="runResult(n.id)?.status"
                   (mousedown)="onNodeDown($event, n)" (mouseup)="onNodeUp($event, n)" (dblclick)="select(n.id)">
                @if (n.type.startsWith('trigger.')) { <span class="n-tag">DÉBUT</span> }
                @if (n.type === 'flow.end') { <span class="n-tag">FIN</span> }
                <div class="n-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" [innerHTML]="def(n).icon | safeSvg"></svg>
                </div>
                <div class="n-text" [title]="tooltip(n)">
                  <div class="n-name">{{ displayName(n) }}</div>
                  <div class="n-sub">{{ summary(n) }}</div>
                </div>
                @if (runResult(n.id); as r) {
                  <div class="n-badge" [attr.data-status]="r.status" [title]="r.error || ''">{{ outTotal(r) }}</div>
                }
                @for (p of def(n).inputs; track p.id; let i = $index) {
                  <div class="port in" [style.top.px]="portY(n, i, def(n).inputs.length)"
                       (mouseup)="onPortUp($event, n, p.id)" (mousedown)="$event.stopPropagation()">
                    @if (p.label) { <span class="p-label in">{{ p.label }}</span> }
                  </div>
                }
                @for (p of outs(n); track p.id; let i = $index) {
                  <div class="port out" [style.top.px]="portY(n, i, outs(n).length)" [attr.data-port]="p.id"
                       (mousedown)="startConnect($event, n, p.id)">
                    @if (p.label) { <span class="p-label">{{ p.label }}@if (runResult(n.id)?.items_out?.[p.id] != null) { · {{ runResult(n.id).items_out[p.id] }} }</span> }
                  </div>
                }
              </div>
            }
          </div>

          @if (!graph.nodes.length) {
            <div class="empty">Commencez par ajouter un déclencheur depuis la palette.</div>
          }

          @if (quickAdd) {
            <div class="quick" [style.left.px]="quickAdd.sx" [style.top.px]="quickAdd.sy" (mousedown)="$event.stopPropagation()">
              <input [(ngModel)]="quickSearch" placeholder="Ajouter un bloc…" autofocus />
              <div class="quick-list">
                @for (t of quickItems(); track t.type) {
                  <div class="pal-item" (click)="quickPick(t)">
                    <span class="pal-icon" [style.color]="t.color">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" [innerHTML]="t.icon | safeSvg"></svg>
                    </span>{{ t.label }}
                  </div>
                }
              </div>
            </div>
          }

          @if (selectedEdge) {
            <!-- mousedown must not reach the canvas, which would deselect the edge first -->
            <button class="edge-del btn-danger btn-sm" (mousedown)="$event.stopPropagation()"
                    (click)="deleteEdge(selectedEdge)">Supprimer la connexion</button>
          }
        </div>

        <!-- config panel -->
        @if (selectedNodeObj(); as sn) {
          <aside class="side">
            <app-node-config [node]="sn" [pipelineId]="id" [fields]="fieldsFor(sn.id)" [issues]="nodeIssues(sn.id)"
              [hasApiKey]="hasApiKey" [runResult]="runResult(sn.id)" [runItems]="runItemsFor(sn.id)"
              [robotCode]="robotCode"
              (changed)="markDirty()" (close)="selectedNode = null" (remove)="deleteNode($event.id)"
              (duplicate)="duplicateNode($event)" (retry)="retry($event)" (filesChanged)="loadFiles()"
              (keyCreated)="hasApiKey = true" />
          </aside>
        }
      </div>

      <!-- runs -->
      <div class="runs" [class.open]="runsOpen">
        <div class="runs-head" (click)="runsOpen = !runsOpen">
          <span>Exécutions</span>
          @if (selectedRun) {
            <span class="badge" [attr.data-status]="selectedRun.status">{{ statusLabel(selectedRun.status) }}</span>
            <span class="muted">{{ selectedRun.created_at | date:'dd/MM HH:mm:ss' }} · {{ triggerLabel(selectedRun.trigger) }}</span>
            @if (selectedRun.error) { <span class="err">{{ selectedRun.error }}</span> }
          }
          <span class="spacer"></span>
          @if (selectedRun) {
            <span (click)="$event.stopPropagation()" class="run-actions">
              @if (isActive(selectedRun)) { <button class="btn-danger btn-sm" (click)="cancel()">Annuler</button> }
              @for (f of selectedRun.files || []; track f.id) {
                <a class="btn-ghost btn-sm" [href]="fileUrl(f.id)" download>⬇ {{ f.filename }}</a>
              }
              @if (selectedRun.items?.length) { <a class="btn-ghost btn-sm" [href]="reportUrl()" download>Rapport CSV</a> }
              <button class="btn-ghost btn-sm" (click)="selectedRun = null">Masquer</button>
            </span>
          }
          <span class="chev">{{ runsOpen ? '▾' : '▴' }}</span>
        </div>
        @if (runsOpen) {
          <div class="runs-list">
            @if (!runs.length) { <span class="muted">Aucune exécution.</span> }
            @for (r of runs; track r.id) {
              <div class="run-chip" [class.on]="selectedRun?.id === r.id" (click)="openRun(r.id)">
                <span class="badge" [attr.data-status]="r.status">{{ statusLabel(r.status) }}</span>
                <span>{{ r.created_at | date:'dd/MM HH:mm' }}</span>
                <span class="muted">{{ triggerLabel(r.trigger) }}</span>
                @if (r.succeeded || r.failed) { <span class="muted">{{ r.succeeded }} ok · {{ r.failed }} échec</span> }
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; height: 100vh; }
    .editor { display: flex; flex-direction: column; height: 100vh; }
    .toolbar { display: flex; align-items: center; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--border-color); background: var(--bg-primary); }
    .back { color: var(--text-muted); text-decoration: none; font-size: 18px; }
    .wf-name { font-weight: 600; font-size: 15px; background: transparent; border: 1px solid transparent; width: 280px; }
    .wf-name:hover, .wf-name:focus { border-color: var(--border-color); }
    .save-state { font-size: 12px; color: var(--text-muted); }
    .robot-pick { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: #10b981;
      background: rgba(16,185,129,.1); border: 1px solid rgba(16,185,129,.35); border-radius: 8px; padding: 3px 4px 3px 10px; }
    .robot-pick select { width: auto; max-width: 280px; padding: 3px 6px; font-size: 12px; }
    .robot-pick.missing { color: var(--color-red); background: var(--color-red-bg); border-color: var(--color-red); }
    .save-state.dirty { color: var(--color-amber); }
    .spacer { flex: 1; }
    .issues-wrap { position: relative; }
    .issues-btn { background: var(--color-red-bg); color: var(--color-red); border: none; border-radius: 12px; padding: 3px 10px; font-size: 12px; cursor: pointer; }
    .issues-pop { position: absolute; top: 30px; left: 0; z-index: 30; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); width: 380px; max-height: 300px; overflow: auto; box-shadow: 0 8px 24px rgba(0,0,0,.4); }
    .issue-line { padding: 8px 12px; font-size: 12px; border-bottom: 1px solid var(--border-color); cursor: pointer; }
    .issue-line:hover { background: var(--bg-hover); }
    .sched { font-size: 12px; border: 1px solid var(--border-color); border-radius: 6px; padding: 6px 10px; }
    .sched.on { color: var(--color-amber); border-color: rgba(251,191,36,.4); }
    .icon-del { background: none; border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 6px; width: 32px; height: 32px; padding: 0; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    .icon-del svg { flex-shrink: 0; }
    .icon-del:hover { color: var(--color-red); border-color: var(--color-red); background: var(--color-red-bg); }
    .zoom { display: flex; align-items: center; gap: 2px; font-size: 12px; color: var(--text-muted); }
    .zoom button { background: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-primary); width: 26px; height: 26px; border-radius: 4px; cursor: pointer; }
    .zoom span { width: 42px; text-align: center; }
    .banner { padding: 8px 16px; font-size: 13px; cursor: pointer; }
    .banner.error { background: var(--color-red-bg); color: var(--color-red); }
    .main { flex: 1; display: flex; min-height: 0; }
    .palette { width: 210px; border-right: 1px solid var(--border-color); background: var(--bg-primary); overflow-y: auto; padding: 10px; flex-shrink: 0; }
    .search { width: 100%; margin-bottom: 8px; }
    .cat { font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin: 12px 4px 4px; font-weight: 700; }
    .pal-item { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: var(--radius-md); font-size: 13px; cursor: grab; user-select: none; }
    .pal-item:hover { background: var(--bg-hover); }
    .pal-icon { display: flex; }
    .pal-hint { font-size: 11px; color: var(--text-muted); margin-top: 16px; }
    .canvas { flex: 1; position: relative; overflow: hidden; background-color: var(--bg-page);
      background-image: radial-gradient(circle, rgba(148,163,184,.18) 1px, transparent 1px); background-size: 20px 20px; cursor: grab; }
    .canvas:active { cursor: grabbing; }
    .world { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
    svg.edges { position: absolute; left: -50000px; top: -50000px; width: 100000px; height: 100000px; overflow: visible; pointer-events: none; }
    .edge { fill: none; stroke: #64748b; stroke-width: 2; pointer-events: none; }
    .edge.sel { stroke: var(--color-indigo); stroke-width: 3; }
    .edge.active { stroke: var(--color-green); }
    .edge.temp { stroke: var(--color-indigo); stroke-dasharray: 6 4; }
    .hit { fill: none; stroke: transparent; stroke-width: 14; cursor: pointer; pointer-events: stroke; }
    .node { position: absolute; width: 210px; /* = NODE_W */ background: var(--bg-secondary); border: 1px solid var(--border-color); border-left: 4px solid var(--c);
      border-radius: 8px; display: flex; align-items: center; gap: 10px; padding: 0 12px; box-sizing: border-box; cursor: move; user-select: none; box-shadow: 0 2px 8px rgba(0,0,0,.25); }
    .node.sel { outline: 2px solid var(--color-indigo); outline-offset: 2px; }
    .node.has-issue { border-color: var(--color-red); border-left-color: var(--color-red); }
    .node[data-run=success] { box-shadow: 0 0 0 2px var(--color-green); }
    .node[data-run=warning] { box-shadow: 0 0 0 2px var(--color-amber); }
    .node[data-run=error] { box-shadow: 0 0 0 2px var(--color-red); }
    .n-icon { color: var(--c); display: flex; flex-shrink: 0; }
    .n-tag { position: absolute; top: -9px; left: 10px; font-size: 9px; font-weight: 800; letter-spacing: .08em;
      padding: 1px 6px; border-radius: 6px; background: var(--c); color: #0b1020; }
    .node.end { border-radius: 26px; border-left-width: 1px; border-color: var(--c); }
    .n-text { min-width: 0; flex: 1; }
    .n-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .n-sub { font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .n-badge { position: absolute; top: -9px; right: -9px; min-width: 20px; height: 20px; border-radius: 10px; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; padding: 0 5px; background: var(--color-green); color: #052e16; }
    .n-badge[data-status=warning] { background: var(--color-amber); color: #422006; }
    .n-badge[data-status=error] { background: var(--color-red); color: #450a0a; }
    .port { position: absolute; width: 12px; height: 12px; border-radius: 50%; background: var(--bg-page); border: 2px solid #94a3b8; transform: translateY(-50%); cursor: crosshair; z-index: 2; }
    .port:hover { border-color: var(--color-indigo); background: var(--color-indigo); }
    .port.in { left: -7px; }
    .port.out { right: -7px; }
    .port.out[data-port=error], .port.out[data-port=false], .port.out[data-port=rejected] { border-color: var(--color-red); }
    .port.out[data-port=success], .port.out[data-port=true], .port.out[data-port=kept] { border-color: var(--color-green); }
    .p-label { position: absolute; left: 16px; top: -3px; font-size: 10px; color: var(--text-muted); white-space: nowrap; pointer-events: none; }
    .p-label.in { left: auto; right: 16px; }
    .empty { position: absolute; top: 45%; width: 100%; text-align: center; color: var(--text-muted); font-size: 14px; pointer-events: none; }
    .quick { position: absolute; z-index: 20; width: 230px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.45); }
    .quick input { width: 100%; margin-bottom: 6px; }
    .quick-list { max-height: 260px; overflow: auto; }
    .quick .pal-item { cursor: pointer; padding: 5px 6px; font-size: 12px; }
    .edge-del { position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%); }
    .side { width: 380px; border-left: 1px solid var(--border-color); background: var(--bg-primary); flex-shrink: 0; overflow: hidden; }
    .runs { border-top: 1px solid var(--border-color); background: var(--bg-primary); }
    .runs-head { display: flex; align-items: center; gap: 10px; padding: 8px 16px; font-size: 13px; cursor: pointer; }
    .runs-head > span:first-child { font-weight: 600; }
    .run-actions { display: flex; gap: 6px; align-items: center; }
    .chev { color: var(--text-muted); }
    .runs-list { display: flex; gap: 8px; padding: 0 16px 12px; overflow-x: auto; }
    .run-chip { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; border: 1px solid var(--border-color); border-radius: var(--radius-md); font-size: 12px; cursor: pointer; white-space: nowrap; }
    .run-chip.on { border-color: var(--color-indigo); }
    .muted { color: var(--text-muted); font-size: 12px; }
    .err { color: var(--color-red); font-size: 12px; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; background: var(--color-gray-bg); color: var(--text-secondary); width: fit-content; }
    .badge[data-status=succeeded] { background: var(--color-green-bg); color: var(--color-green); }
    .badge[data-status=failed] { background: var(--color-red-bg); color: var(--color-red); }
    .badge[data-status=partial] { background: var(--color-amber-bg); color: var(--color-amber); }
    .badge[data-status=running], .badge[data-status=queued], .badge[data-status=cancelling] { background: var(--color-blue-bg); color: var(--color-blue); }
  `]
})
export class WorkflowEditorComponent implements OnInit, OnDestroy {
  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLDivElement>;

  id = '';
  name = '';
  graph: WfGraph = { nodes: [], edges: [] };
  issues: any[] = [];
  hasApiKey = false;
  dirty = false;
  saving = false;
  error = '';
  showIssues = false;

  categories = CATEGORIES;
  search = '';
  pan: Pt = { x: 40, y: 40 };
  zoom = 1;
  selectedNode: string | null = null;
  selectedEdge: string | null = null;

  connecting: { node: WfNode; port: string; to: Pt } | null = null;
  quickAdd: { sx: number; sy: number; world: Pt; from?: { node: WfNode; port: string } } | null = null;
  quickSearch = '';

  runs: any[] = [];
  selectedRun: any = null;
  runsOpen = true;

  private files: any[] = [];
  robotCode = '';
  robots: any[] = [];
  private processes: Record<string, { name: string; robot_code: string | null }> = {};
  private drag: { kind: 'pan' | 'node'; start: Pt; origin: Pt; node?: WfNode; moved: boolean } | null = null;
  private timer: any;

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router,
              private cdr: ChangeDetectorRef) {}

  // ------------------------------------------------------------------ load/save

  ngOnInit() {
    this.id = this.route.snapshot.paramMap.get('id') || '';
    this.api.getPipeline(this.id).subscribe({
      next: p => {
        this.name = p.name;
        this.robotCode = p.robot_code || '';
        this.graph = p.graph;
        this.issues = p.issues;
        this.hasApiKey = p.has_api_key;
        setTimeout(() => this.fit());
        this.cdr.detectChanges();
      },
      error: () => { this.error = 'Workflow introuvable'; this.cdr.detectChanges(); },
    });
    this.api.getRobots().subscribe(r => { this.robots = r; this.cdr.detectChanges(); });
    this.api.getProcesses().subscribe(ps => {
      ps.forEach((p: any) => this.processes[p.id] = { name: p.name, robot_code: p.robot_code || null });
      this.cdr.detectChanges();
    });
    this.loadFiles();
    this.refreshRuns(true);
    this.timer = setInterval(() => this.poll(), 2000);
  }

  ngOnDestroy() { clearInterval(this.timer); }

  @HostListener('window:beforeunload', ['$event'])
  beforeUnload(e: BeforeUnloadEvent) { if (this.dirty) { e.preventDefault(); } }

  loadFiles() {
    this.api.getPipelineFiles(this.id).subscribe(f => { this.files = f; this.cdr.detectChanges(); });
  }

  markDirty() {
    this.dirty = true;
    // a removed switch case takes its connections with it
    const before = this.graph.edges.length;
    this.graph.edges = this.graph.edges.filter(e => {
      const src = this.nodeById(e.source);
      return !src || this.outs(src).some(p => p.id === e.source_port);
    });
    if (this.selectedEdge && this.graph.edges.length !== before && !this.graph.edges.some(e => e.id === this.selectedEdge)) {
      this.selectedEdge = null;
    }
  }

  save(after?: () => void) {
    this.saving = true;
    this.api.updatePipeline(this.id, { name: this.name, robot_code: this.robotCode, graph: this.graph }).subscribe({
      next: p => {
        this.issues = p.issues;
        this.dirty = false;
        this.saving = false;
        after?.();
        this.cdr.detectChanges();
      },
      error: e => { this.error = e.error?.detail || 'Enregistrement impossible'; this.saving = false; this.cdr.detectChanges(); },
    });
  }

  run() {
    this.api.runPipeline(this.id).subscribe({
      next: r => { this.runsOpen = true; this.openRun(r.id); this.refreshRuns(); },
      error: e => { this.error = e.error?.detail || 'Lancement impossible'; this.cdr.detectChanges(); },
    });
  }

  // ------------------------------------------------------------------ runs

  refreshRuns(selectLatest = false) {
    this.api.getPipelineRuns(this.id).subscribe(r => {
      this.runs = r;
      if (selectLatest && r.length && ACTIVE.includes(r[0].status)) this.openRun(r[0].id);
      this.cdr.detectChanges();
    });
  }

  private pollTick = 0;

  private poll() {
    // runs started by the planning or by API appear by themselves and get followed live
    if (++this.pollTick % 3 === 0 || this.runs.some(r => this.isActive(r))) {
      this.api.getPipelineRuns(this.id).subscribe(runs => {
        this.runs = runs;
        const active = runs.find(r => this.isActive(r));
        if (active && (!this.selectedRun || !this.isActive(this.selectedRun))) {
          this.runsOpen = true;
          this.openRun(active.id);
        }
        this.cdr.detectChanges();
      });
    }
    if (this.selectedRun && this.isActive(this.selectedRun)) this.openRun(this.selectedRun.id);
  }

  stopping = false;

  stopAll() {
    this.stopping = true;
    this.api.stopPipeline(this.id).subscribe({
      next: () => { this.stopping = false; this.refreshRuns(); if (this.selectedRun) this.openRun(this.selectedRun.id); },
      error: e => { this.stopping = false; this.error = e.error?.detail || 'Arrêt impossible'; this.cdr.detectChanges(); },
    });
  }

  hasSchedule() { return this.graph.nodes.some(n => n.type === 'trigger.schedule'); }
  scheduleActive() { return this.graph.nodes.some(n => n.type === 'trigger.schedule' && n.config?.enabled); }

  toggleSchedule() {
    const enable = !this.scheduleActive();
    this.api.setPipelineSchedule(this.id, enable).subscribe({
      next: () => {
        // saved server-side already: mirror it locally without marking the graph dirty
        this.graph.nodes.filter(n => n.type === 'trigger.schedule').forEach(n => n.config.enabled = enable);
        this.cdr.detectChanges();
      },
      error: e => { this.error = e.error?.detail || 'Modification impossible'; this.cdr.detectChanges(); },
    });
  }

  openRun(runId: string) {
    this.api.getPipelineRun(runId).subscribe(r => { this.selectedRun = r; this.cdr.detectChanges(); });
  }

  cancel() {
    this.api.cancelPipelineRun(this.selectedRun.id).subscribe({
      next: () => this.openRun(this.selectedRun.id),
      error: e => { this.error = e.error?.detail || 'Annulation impossible'; this.cdr.detectChanges(); },
    });
  }

  retry(nodeId: string) {
    this.api.retryFailedPipelineRun(this.selectedRun.id, nodeId).subscribe({
      next: r => { this.openRun(r.id); this.refreshRuns(); },
      error: e => { this.error = e.error?.detail || 'Relance impossible'; this.cdr.detectChanges(); },
    });
  }

  runResult(nodeId: string) { return this.selectedRun?.node_results?.[nodeId] || null; }
  runItemsFor(nodeId: string) { return (this.selectedRun?.items || []).filter((i: any) => i.node_id === nodeId); }
  outTotal(r: any) { return Object.values(r.items_out || {}).reduce((a: number, b: any) => a + (b as number), 0); }
  edgeActive(e: WfEdge) { return !!this.runResult(e.source)?.items_out?.[e.source_port]; }
  isActive(r: any) { return ACTIVE.includes(r?.status); }
  activeRun() { return this.runs.some(r => this.isActive(r)); }
  hasManual() { return this.graph.nodes.some(n => n.type === 'trigger.manual'); }
  runTitle() {
    if (this.dirty) return 'Enregistrez avant de lancer';
    if (this.issues.length) return 'Corrigez les problèmes signalés';
    if (!this.hasManual()) return 'Ajoutez un déclencheur « Lancement manuel »';
    if (this.activeRun()) return 'Un run est déjà en cours';
    return 'Lancer le workflow';
  }
  reportUrl() { return this.api.pipelineRunReportUrl(this.selectedRun.id); }
  fileUrl(id: string) { return this.api.pipelineFileDownloadUrl(id); }
  statusLabel(s: string) { return RUN_STATUS_LABELS[s] || s; }
  triggerLabel(t: string) { return TRIGGER_LABELS[t] || t; }

  // ------------------------------------------------------------------ graph helpers

  def(n: WfNode): NodeTypeDef { return NODE_TYPE_MAP[n.type] || NODE_TYPE_MAP['logic.wait']; }
  outs(n: WfNode): PortDef[] { return outputsOf(n); }
  nodeH(n: WfNode) { return Math.max(58, 26 * Math.max(this.def(n).inputs.length, this.outs(n).length) + 16); }
  portY(n: WfNode, i: number, count: number) { return this.nodeH(n) * (i + 1) / (count + 1); }

  portPos(n: WfNode, port: string, side: 'in' | 'out'): Pt {
    const ports = side === 'in' ? this.def(n).inputs : this.outs(n);
    const i = Math.max(0, ports.findIndex(p => p.id === port));
    return { x: n.position.x + (side === 'out' ? NODE_W : 0), y: n.position.y + this.portY(n, i, ports.length) };
  }

  curve(a: Pt, b: Pt) {
    const dx = Math.max(60, Math.abs(b.x - a.x) / 2);
    return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
  }

  edgePath(e: WfEdge) {
    const s = this.nodeById(e.source), t = this.nodeById(e.target);
    if (!s || !t) return '';
    return this.curve(this.portPos(s, e.source_port, 'out'), this.portPos(t, e.target_port, 'in'));
  }

  nodeById(id: string) { return this.graph.nodes.find(n => n.id === id); }
  selectedNodeObj() { return this.selectedNode ? this.nodeById(this.selectedNode) || null : null; }
  nodeName(id: string | null) { return id ? (this.nodeById(id)?.name || '') + ' :' : ''; }
  nodeIssues(id: string) { return this.issues.filter(i => i.node_id === id).map(i => i.message); }

  summary(n: WfNode): string {
    const c = n.config || {};
    switch (n.type) {
      case 'trigger.schedule': return `${c.cron || '—'} · ${c.enabled ? 'actif' : 'inactif'}`;
      case 'trigger.webhook': return this.hasApiKey ? 'clé configurée' : 'clé à générer';
      case 'robot.run': {
        const p = this.processes[c.process_id];
        if (!c.process_id) return 'processus à choisir';
        if (!p) return 'processus introuvable';
        const session = c.keep_session ? 'session conservée' : 'lance l\'application';
        return `${session} · ${c.version_id ? 'version fixée' : 'dernière version'}`;
      }
      case 'flow.end':
        return c.result === 'failure' ? 'termine en échec' : 'termine avec succès';
      case 'logic.switch': {
        const n = (c.cases || []).length;
        return c.field ? `${c.field} : ${n} cas + autre` : 'champ à choisir';
      }
      case 'logic.if': case 'data.filter': {
        const r = (c.rules || [])[0];
        if (!r?.field) return 'règle à définir';
        const op = OPERATORS.find(o => o.id === r.op)?.label || r.op;
        return `${r.field} ${op} ${r.value || ''}${c.rules.length > 1 ? ' …' : ''}`;
      }
      case 'logic.loop': return `${c.batch_size || 1} par tour`;
      case 'logic.wait': return `${c.seconds || 0} s`;
      case 'data.read_file': return this.files.find(f => f.id === c.file_id)?.filename || 'fichier à choisir';
      case 'data.set': return `${(c.operations || []).filter((o: any) => o.field).length} opération(s)`;
      case 'data.write_file': return `${c.filename || 'resultat'}.${c.format || 'xlsx'}`;
      case 'http.request': return `${c.method || 'GET'} ${c.url || ''}`;
      case 'email.send': return c.to || 'destinataire à définir';
      case 'ai.prompt': return c.model || 'modèle à choisir';
      default: return this.def(n).label;
    }
  }

  nodeColor(n: WfNode): string {
    if (n.type === 'flow.end') return n.config?.result === 'failure' ? '#f87171' : '#34d399';
    return this.def(n).color;
  }

  deleteWorkflow() {
    const runs = this.runs.length ? ` et ses ${this.runs.length} exécution(s)` : '';
    if (!confirm(`Supprimer le workflow « ${this.name} »${runs} ? Cette action est définitive.`)) return;
    this.api.deletePipeline(this.id).subscribe({
      next: () => { this.dirty = false; this.router.navigate(['/pipelines']); },
      error: e => { this.error = e.error?.detail || 'Suppression impossible'; this.cdr.detectChanges(); },
    });
  }

  /** A robot node still carrying its generic name shows the process it runs instead. */
  displayName(n: WfNode): string {
    if (n.type === 'robot.run' && isDefaultProcessNodeName(n.name)) {
      return this.processes[n.config?.process_id]?.name || n.name;
    }
    return n.name;
  }

  tooltip(n: WfNode): string {
    if (n.type !== 'robot.run') return `${n.name} — ${this.def(n).label}`;
    const p = this.processes[n.config?.process_id];
    if (!p) return `${n.name} — aucun processus choisi`;
    return `${n.name}\nProcessus : ${p.name}\nRobot : ${this.robotCode || p.robot_code || 'par défaut'}\n`
      + (n.config.version_id ? 'Version fixée' : 'Toujours la dernière version')
      + (n.config.keep_session ? '\nContinue dans la session en cours' : '');
  }

  /** Field names a node can use: produced upstream (file columns, computed fields) or seen in the last run. */
  fieldsFor(nodeId: string): string[] {
    const out = new Set<string>();
    const seen = new Set<string>();
    const stack = this.graph.edges.filter(e => e.target === nodeId).map(e => e.source);
    while (stack.length) {
      const id = stack.pop()!;
      if (seen.has(id)) continue;
      seen.add(id);
      const n = this.nodeById(id);
      if (!n) continue;
      const c = n.config || {};
      if (n.type === 'data.read_file') this.files.find(f => f.id === c.file_id)?.columns?.forEach((x: string) => out.add(x));
      if (n.type === 'data.set') (c.operations || []).forEach((o: any) => { if (o.op === 'set' && o.field) out.add(o.field); if (o.op === 'rename' && o.to) out.add(o.to); });
      if (n.type === 'http.request') { out.add(c.response_field || 'reponse'); out.add('_http_status'); }
      if (n.type === 'ai.prompt' && c.output_field) out.add(c.output_field);
      if (n.type === 'robot.run') { out.add('_execution_id'); out.add('_erreur'); }
      if (n.type === 'trigger.schedule') out.add('declenche_le');
      stack.push(...this.graph.edges.filter(e => e.target === id).map(e => e.source));
    }
    (this.runResult(nodeId)?.sample_in || []).forEach((item: any) => Object.keys(item || {}).forEach(k => out.add(k)));
    return [...out].sort((a, b) => a.localeCompare(b));
  }

  paletteItems(cat: string) {
    const q = this.search.trim().toLowerCase();
    return NODE_TYPES.filter(t => t.category === cat && (!q || t.label.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)));
  }

  quickItems() {
    const q = this.quickSearch.trim().toLowerCase();
    return NODE_TYPES.filter(t => (!this.quickAdd?.from || t.inputs.length) && (!q || t.label.toLowerCase().includes(q)));
  }

  // ------------------------------------------------------------------ editing

  addNode(t: NodeTypeDef, at: Pt): WfNode {
    const sameType = this.graph.nodes.filter(n => n.type === t.type).length;
    const node: WfNode = {
      id: newId('n'), type: t.type, name: sameType ? `${t.label} ${sameType + 1}` : t.label,
      position: { x: Math.round(at.x / 10) * 10, y: Math.round(at.y / 10) * 10 }, config: t.defaults(),
    };
    this.graph.nodes.push(node);
    this.selectedNode = node.id;
    this.selectedEdge = null;
    this.markDirty();
    return node;
  }

  addAtCenter(t: NodeTypeDef) {
    const r = this.canvasRef.nativeElement.getBoundingClientRect();
    const c = this.toWorld(r.left + r.width / 2, r.top + r.height / 2);
    this.addNode(t, { x: c.x - NODE_W / 2 + (this.graph.nodes.length % 5) * 20, y: c.y - 30 + (this.graph.nodes.length % 5) * 20 });
  }

  onPaletteDrag(ev: DragEvent, t: NodeTypeDef) { ev.dataTransfer?.setData('text/node-type', t.type); }

  onDrop(ev: DragEvent) {
    ev.preventDefault();
    const t = NODE_TYPE_MAP[ev.dataTransfer?.getData('text/node-type') || ''];
    if (!t) return;
    const p = this.toWorld(ev.clientX, ev.clientY);
    this.addNode(t, { x: p.x - NODE_W / 2, y: p.y - 29 });
  }

  connect(from: WfNode, fromPort: string, to: WfNode, toPort: string) {
    if (from.id === to.id || !this.def(to).inputs.some(p => p.id === toPort)) return;
    const dup = this.graph.edges.some(e => e.source === from.id && e.source_port === fromPort && e.target === to.id && e.target_port === toPort);
    if (dup) return;
    this.graph.edges.push({ id: newId('e'), source: from.id, source_port: fromPort, target: to.id, target_port: toPort });
    this.markDirty();
  }

  deleteNode(id: string) {
    this.graph.nodes = this.graph.nodes.filter(n => n.id !== id);
    this.graph.edges = this.graph.edges.filter(e => e.source !== id && e.target !== id);
    if (this.selectedNode === id) this.selectedNode = null;
    this.markDirty();
  }

  deleteEdge(id: string) {
    this.graph.edges = this.graph.edges.filter(e => e.id !== id);
    this.selectedEdge = null;
    this.markDirty();
  }

  duplicateNode(n: WfNode) {
    const copy: WfNode = { ...JSON.parse(JSON.stringify(n)), id: newId('n'), name: `${n.name} (copie)`,
                           position: { x: n.position.x + 30, y: n.position.y + 90 } };
    this.graph.nodes.push(copy);
    this.selectedNode = copy.id;
    this.markDirty();
  }

  select(id: string) { this.selectedNode = id; this.selectedEdge = null; }
  selectEdge(id: string) { this.selectedEdge = id; this.selectedNode = null; this.quickAdd = null; }

  // ------------------------------------------------------------------ mouse

  private toWorld(clientX: number, clientY: number): Pt {
    const r = this.canvasRef.nativeElement.getBoundingClientRect();
    return { x: (clientX - r.left - this.pan.x) / this.zoom, y: (clientY - r.top - this.pan.y) / this.zoom };
  }

  onCanvasDown(ev: MouseEvent) {
    if (ev.button !== 0) return;
    this.quickAdd = null;
    this.selectedEdge = null;
    this.drag = { kind: 'pan', start: { x: ev.clientX, y: ev.clientY }, origin: { ...this.pan }, moved: false };
  }

  onNodeDown(ev: MouseEvent, n: WfNode) {
    if (ev.button !== 0) return;
    ev.stopPropagation();
    this.quickAdd = null;
    this.drag = { kind: 'node', node: n, start: { x: ev.clientX, y: ev.clientY }, origin: { ...n.position }, moved: false };
  }

  startConnect(ev: MouseEvent, n: WfNode, port: string) {
    ev.stopPropagation();
    ev.preventDefault();
    this.quickAdd = null;
    this.connecting = { node: n, port, to: this.toWorld(ev.clientX, ev.clientY) };
  }

  onPortUp(ev: MouseEvent, n: WfNode, port: string) {
    if (!this.connecting) return;
    ev.stopPropagation();
    this.connect(this.connecting.node, this.connecting.port, n, port);
    this.connecting = null;
  }

  onNodeUp(ev: MouseEvent, n: WfNode) {
    if (this.connecting) {
      // dropped on the node body: use its first input
      const first = this.def(n).inputs[0];
      if (first) this.connect(this.connecting.node, this.connecting.port, n, first.id);
      this.connecting = null;
      ev.stopPropagation();
    }
  }

  @HostListener('window:mousemove', ['$event'])
  onMove(ev: MouseEvent) {
    if (this.connecting) {
      this.connecting.to = this.toWorld(ev.clientX, ev.clientY);
      return;
    }
    if (!this.drag) return;
    const dx = ev.clientX - this.drag.start.x, dy = ev.clientY - this.drag.start.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) this.drag.moved = true;
    if (this.drag.kind === 'pan') {
      this.pan = { x: this.drag.origin.x + dx, y: this.drag.origin.y + dy };
    } else if (this.drag.node && this.drag.moved) {
      this.drag.node.position = {
        x: Math.round((this.drag.origin.x + dx / this.zoom) / 10) * 10,
        y: Math.round((this.drag.origin.y + dy / this.zoom) / 10) * 10,
      };
    }
  }

  @HostListener('window:mouseup', ['$event'])
  onUp(ev: MouseEvent) {
    if (this.connecting) {
      // released on empty canvas: offer to create a connected node there (like n8n)
      const r = this.canvasRef.nativeElement.getBoundingClientRect();
      if (ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom) {
        this.quickAdd = { sx: ev.clientX - r.left, sy: ev.clientY - r.top, world: this.toWorld(ev.clientX, ev.clientY),
                          from: { node: this.connecting.node, port: this.connecting.port } };
        this.quickSearch = '';
      }
      this.connecting = null;
      return;
    }
    if (this.drag?.kind === 'node' && this.drag.node) {
      if (this.drag.moved) this.markDirty();
      else this.select(this.drag.node.id);
    } else if (this.drag?.kind === 'pan' && !this.drag.moved) {
      this.selectedNode = null;
    }
    this.drag = null;
  }

  quickPick(t: NodeTypeDef) {
    if (!this.quickAdd) return;
    const node = this.addNode(t, { x: this.quickAdd.world.x, y: this.quickAdd.world.y - 29 });
    const from = this.quickAdd.from;
    if (from && t.inputs.length) this.connect(from.node, from.port, node, t.inputs[0].id);
    this.quickAdd = null;
  }

  onWheel(ev: WheelEvent) {
    ev.preventDefault();
    const r = this.canvasRef.nativeElement.getBoundingClientRect();
    this.zoomAt(ev.deltaY < 0 ? 1.1 : 1 / 1.1, ev.clientX - r.left, ev.clientY - r.top);
  }

  zoomBy(f: number) {
    const r = this.canvasRef.nativeElement.getBoundingClientRect();
    this.zoomAt(f, r.width / 2, r.height / 2);
  }

  private zoomAt(f: number, cx: number, cy: number) {
    const z = Math.min(2, Math.max(0.25, this.zoom * f));
    this.pan = { x: cx - (cx - this.pan.x) * (z / this.zoom), y: cy - (cy - this.pan.y) * (z / this.zoom) };
    this.zoom = z;
  }

  fit() {
    const nodes = this.graph.nodes;
    const r = this.canvasRef.nativeElement.getBoundingClientRect();
    if (!nodes.length || !r.width) { this.pan = { x: 40, y: 40 }; this.zoom = 1; return; }
    const minX = Math.min(...nodes.map(n => n.position.x)), minY = Math.min(...nodes.map(n => n.position.y));
    const maxX = Math.max(...nodes.map(n => n.position.x + NODE_W)), maxY = Math.max(...nodes.map(n => n.position.y + this.nodeH(n)));
    const pad = 80;
    this.zoom = Math.min(1.2, Math.max(0.3, Math.min((r.width - pad * 2) / (maxX - minX || 1), (r.height - pad * 2) / (maxY - minY || 1))));
    this.pan = { x: (r.width - (maxX - minX) * this.zoom) / 2 - minX * this.zoom, y: (r.height - (maxY - minY) * this.zoom) / 2 - minY * this.zoom };
    this.cdr.detectChanges();
  }

  @HostListener('window:keydown', ['$event'])
  onKey(ev: KeyboardEvent) {
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes((ev.target as HTMLElement)?.tagName);
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
      ev.preventDefault();
      if (this.dirty) this.save();
      return;
    }
    if (typing) return;
    if (ev.key === 'Delete' || ev.key === 'Backspace') {
      if (this.selectedEdge) this.deleteEdge(this.selectedEdge);
      else if (this.selectedNode) this.deleteNode(this.selectedNode);
    } else if (ev.key === 'Escape') {
      this.connecting = null; this.quickAdd = null; this.selectedEdge = null; this.selectedNode = null;
    }
  }
}
