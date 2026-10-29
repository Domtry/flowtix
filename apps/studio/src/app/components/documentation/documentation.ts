import { AfterViewInit, Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

interface TocEntry { id: string; title: string; children?: { id: string; title: string }[]; }

@Component({
  selector: 'app-documentation',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="doc">
      <!-- table of contents -->
      <nav class="toc">
        <div class="toc-title">Documentation</div>
        <input class="search" [(ngModel)]="query" (ngModelChange)="filter()" placeholder="Rechercher…" />
        @if (query && !matches) { <div class="no-match">Aucun résultat</div> }
        @for (s of toc; track s.id) {
          <a class="toc-item" [class.active]="active === s.id" [class.dim]="hidden.has(s.id)" (click)="go(s.id)">{{ s.title }}</a>
          @for (c of s.children || []; track c.id) {
            <a class="toc-sub" [class.active]="active === c.id" [class.dim]="hidden.has(s.id)" (click)="go(c.id)">{{ c.title }}</a>
          }
        }
      </nav>

      <main class="content" #content (scroll)="onScroll()">

        <!-- ================================================================ -->
        <section id="overview">
          <h1>Comment fonctionne FlowtTix</h1>
          <p class="lead">FlowtTix automatise les saisies répétitives dans vos applications (portail SANLAM, ORASS…) :
            vous montrez une fois au robot ce qu'il faut faire, puis il le refait pour chaque ligne de vos données,
            à la demande, selon un planning ou sur appel d'un autre système.</p>

          <div class="flow">
            <div class="flow-box"><span class="num">1</span><strong>Robot</strong><span>la plateforme pilotée<br/>(ex. SANLAM_PORTAL)</span></div>
            <div class="flow-arrow">→</div>
            <div class="flow-box"><span class="num">2</span><strong>Processus</strong><span>une suite d'actions<br/>enregistrée une fois</span></div>
            <div class="flow-arrow">→</div>
            <div class="flow-box"><span class="num">3</span><strong>Workflow</strong><span>données + conditions<br/>+ processus enchaînés</span></div>
            <div class="flow-arrow">→</div>
            <div class="flow-box"><span class="num">4</span><strong>Exécutions</strong><span>suivi, résultats,<br/>relance des échecs</span></div>
          </div>

          <h3>Les quatre notions à retenir</h3>
          <dl class="defs">
            <dt>Robot</dt><dd>La plateforme à automatiser : quelle application lancer, avec quel moteur, et quelle fenêtre surveiller.
              Un robot = une plateforme (ex. <code>SANLAM_PORTAL</code> pour le portail et ORASS).</dd>
            <dt>Processus</dt><dd>Une suite d'actions enregistrée en vous regardant faire : clics, saisies, touches.
              Chaque nouvel enregistrement crée une <em>version</em> ; les workflows utilisent par défaut la dernière.</dd>
            <dt>Workflow</dt><dd>L'enchaînement complet : <em>Début → données → conditions → processus → Fin</em>.
              Tous les processus d'un workflow sont exécutés par le même robot.</dd>
            <dt>Exécution (run)</dt><dd>Un lancement du workflow. Chaque bloc y affiche ce qu'il a reçu et produit ;
              chaque passage d'un processus y est tracé avec son résultat.</dd>
          </dl>
        </section>

        <!-- ================================================================ -->
        <section id="quickstart">
          <h2>Démarrage rapide</h2>
          <ol class="steps">
            <li><strong>Vérifier le robot</strong> — menu <a routerLink="/robots">Robots</a> : le robot de votre plateforme existe
              (code, exécutable, URL, mot-clé de fenêtre).</li>
            <li><strong>Enregistrer un processus</strong> — menu <a routerLink="/processes">Processes</a> → créer un processus →
              <em>Record</em> → choisir le robot → <em>Start Recording</em>, faire la saisie une fois, puis <em>Stop</em>.</li>
            <li><strong>Tester le processus seul</strong> — bouton <em>Run</em> sur le processus.</li>
            <li><strong>Créer un workflow</strong> — menu <a routerLink="/pipelines">Workflows</a> → <em>Nouveau workflow</em> (nom + robot).
              Il s'ouvre avec <em>Début → Fin</em> : insérez vos blocs entre les deux.</li>
            <li><strong>Brancher les données</strong> — bloc <em>Lire un fichier</em> (Excel/CSV), puis dans le bloc
              <em>Exécuter un processus</em>, associez chaque saisie à une colonne : <code>{{ '{{' }}Nom{{ '}}' }}</code>.</li>
            <li><strong>Enregistrer et lancer</strong> — <em>Enregistrer</em>, puis <em>▶ Lancer</em>. Suivez le run en bas de l'écran.</li>
          </ol>
          <div class="callout info">L'agent navigateur doit tourner sur le poste qui pilote les applications
            (<code>cd agents/browser &amp;&amp; python run.py</code>). Il n'y a qu'une souris et un clavier :
            les exécutions passent toujours <strong>une par une</strong>, dans l'ordre.</div>
        </section>

        <!-- ================================================================ -->
        <section id="robots">
          <h2>Robots</h2>
          <p>Un robot décrit <strong>la plateforme</strong> à piloter. On le choisit à l'enregistrement d'un processus et à la création d'un workflow.</p>
          <table>
            <thead><tr><th>Champ</th><th>Rôle</th></tr></thead>
            <tbody>
              <tr><td>Code</td><td>Identifiant unique et stable, ex. <code>SANLAM_PORTAL</code>.</td></tr>
              <tr><td>Moteur</td><td><strong>Subprocess</strong> : pilote le bureau Windows (souris, clavier, images) — fonctionne avec toute application,
                y compris Java (ORASS) et Firefox. <strong>Playwright / Selenium</strong> : pilotent un navigateur dédié (pages web uniquement).</td></tr>
              <tr><td>Chemin exécutable</td><td>L'application à lancer (ex. <code>firefox.exe</code>).</td></tr>
              <tr><td>URL par défaut</td><td>La page ouverte au lancement (ex. le portail SANLAM).</td></tr>
              <tr><td>Titre fenêtre (filtre)</td><td>Mot-clé présent dans le titre des fenêtres de la plateforme (ex. <code>sanlam</code>).</td></tr>
            </tbody>
          </table>
        </section>

        <!-- ================================================================ -->
        <section id="recording">
          <h2>Enregistrer un processus</h2>
          <p>Pendant l'enregistrement, FlowtTix observe ce que vous faites dans l'application :</p>
          <ul>
            <li><strong>Chaque clic</strong>, avec une photo de l'élément cliqué et de son entourage (360 × 200 px) : c'est cette image
              qui permettra au robot de retrouver l'élément, même si la fenêtre a bougé ou que la résolution a changé.</li>
            <li><strong>Le trajet de la souris</strong> entre deux clics et ses pauses : indispensable pour les menus qui s'ouvrent au survol
              (Branches → sous-menu → élément).</li>
            <li><strong>Le texte tapé</strong>, regroupé par champ (accents, AltGr, majuscules compris), et les touches spéciales (Tab, Entrée…).</li>
            <li><strong>La fenêtre</strong> de chaque action, pour que le robot sache où taper et quelle fenêtre mettre au premier plan.</li>
          </ul>
          <p>Les clics dans le Studio FlowtTix, VS Code ou un terminal sont ignorés.</p>

          <h3 id="recording-session">Continuer dans la session en cours</h3>
          <p>Case <em>« Continuer dans la session en cours — ne pas lancer l'application »</em> sur l'écran d'enregistrement :
            l'application n'est pas relancée, l'enregistrement démarre dans la fenêtre déjà ouverte. Le processus obtenu ne contient
            ni ouverture ni connexion : c'est la bonne méthode pour enregistrer une <strong>variante</strong> (ex. une option Santé)
            qui s'enchaîne après un processus de connexion dans un workflow.</p>

          <h3 id="recording-tips">Bonnes pratiques</h3>
          <ul class="tips">
            <li>Avant de commencer, attendez que la fenêtre soit <strong>complètement affichée et agrandie</strong> : l'image de référence sera nette.</li>
            <li>Dans un menu en cascade, marquez une <strong>courte pause</strong> sur l'élément parent avant d'aller dans le sous-menu.</li>
            <li>Laissez l'application <strong>finir de charger</strong> entre deux écrans (sablier, ouverture de module).</li>
            <li>Un processus = une tâche précise. Préférez plusieurs petits processus (connexion, saisie Santé Confort, saisie Santé Premium…)
              enchaînés dans un workflow plutôt qu'un seul processus géant.</li>
            <li>Après l'enregistrement, testez avec <em>Run</em> avant de l'utiliser dans un workflow.</li>
          </ul>
        </section>

        <!-- ================================================================ -->
        <section id="replay">
          <h2>Comment le robot rejoue</h2>
          <p>Le robot ne clique jamais « à des coordonnées » : il <strong>cherche l'élément à l'écran</strong>.</p>
          <ol>
            <li><strong>Il met la bonne fenêtre au premier plan</strong> et attend qu'elle ait fini de se dessiner.</li>
            <li><strong>Il refait le trajet de la souris</strong> enregistré depuis le clic précédent (ouverture des sous-menus).</li>
            <li><strong>Il cherche l'élément</strong> dans la fenêtre, par comparaison d'images à plusieurs échelles (tolère un autre écran,
              une autre résolution, une mise à l'échelle Windows différente, un élément surligné ou non).
              La position dans la fenêtre peut <em>confirmer</em> une image presque identique, jamais la remplacer.</li>
            <li><strong>Il clique et vérifie que l'écran a réagi</strong>. Si l'application était occupée et a ignoré le clic, il réessaie (3 fois).</li>
            <li><strong>Pour une saisie</strong>, il attend que la fenêtre attendue soit active puis tape le texte touche par touche.</li>
          </ol>
          <div class="callout warn">Si l'élément n'est pas trouvé avec certitude en 15 secondes, l'étape <strong>échoue</strong>
            (« Element introuvable à l'écran ») plutôt que de cliquer au mauvais endroit.</div>
        </section>

        <!-- ================================================================ -->
        <section id="workflows">
          <h2>Workflows</h2>
          <p>Un workflow est un schéma de blocs reliés par des flèches. Les données circulent de bloc en bloc sous forme
            d'<strong>éléments</strong> : en général, un élément = une ligne de votre fichier.</p>

          <h3 id="editor">L'éditeur</h3>
          <table>
            <tbody>
              <tr><td>Ajouter un bloc</td><td>Glisser depuis la palette de gauche (ou cliquer dessus).</td></tr>
              <tr><td>Relier deux blocs</td><td>Tirer depuis une sortie <span class="dot">●</span> (à droite) jusqu'à l'entrée d'un autre bloc.
                Lâcher dans le vide propose de créer le bloc suivant, déjà relié.</td></tr>
              <tr><td>Configurer</td><td>Cliquer sur un bloc : son panneau s'ouvre à droite.</td></tr>
              <tr><td>Supprimer</td><td>Sélectionner un bloc ou une connexion puis touche <kbd>Suppr</kbd> (ou bouton du panneau).</td></tr>
              <tr><td>Se déplacer</td><td>Glisser le fond de la toile ; molette pour zoomer ; <kbd>⤢</kbd> pour tout afficher.</td></tr>
              <tr><td>Enregistrer</td><td>Bouton <em>Enregistrer</em> ou <kbd>Ctrl</kbd>+<kbd>S</kbd>.</td></tr>
              <tr><td>Robot du workflow</td><td>En haut, à côté du nom : tous les processus seront exécutés par ce robot.</td></tr>
            </tbody>
          </table>
          <p>Les <strong>problèmes</strong> (bloc non configuré, bloc non relié…) sont listés en haut de l'éditeur ; tant qu'il en reste,
            le bouton <em>Lancer</em> est désactivé. Cliquez sur un problème pour ouvrir le bloc concerné.</p>

          <h3 id="start-end">Début et Fin</h3>
          <p>Chaque workflow a au moins un <span class="tag start">DÉBUT</span> et une <span class="tag end">FIN</span>.</p>
          <ul>
            <li><strong>Début — manuel</strong> : lancé par le bouton <em>▶ Lancer</em>.</li>
            <li><strong>Début — planifié</strong> : lancé automatiquement selon un planning (voir <a (click)="go('triggers')">Déclenchement</a>).</li>
            <li><strong>Début — appel API</strong> : lancé par un autre système, avec ses propres données.</li>
            <li><strong>Fin</strong> : clôture une branche, <em>avec succès</em> ou <em>en échec</em>, avec un message facultatif.
              Si des éléments arrivent sur une Fin « en échec », le run est marqué en échec (ou partiel) et le message s'affiche dans l'historique.</li>
          </ul>

          <h3 id="blocks">Les blocs</h3>
          <table class="blocks">
            <thead><tr><th>Bloc</th><th>Ce qu'il fait</th><th>Sorties</th></tr></thead>
            <tbody>
              <tr class="cat"><td colspan="3">Processus</td></tr>
              <tr><td>Exécuter un processus</td><td>Le robot rejoue le processus choisi pour <em>chaque</em> élément, en tapant les valeurs indiquées.</td><td>succès / erreur</td></tr>
              <tr class="cat"><td colspan="3">Logique</td></tr>
              <tr><td>Condition (Si)</td><td>Envoie chaque élément vers « vrai » ou « faux » selon des règles.</td><td>vrai / faux</td></tr>
              <tr><td>Aiguillage</td><td>Une sortie par valeur d'un champ (ex. <code>Option</code> = Essentiel, Confort, Premium) + « autre ».</td><td>un cas chacun + autre</td></tr>
              <tr><td>Boucle</td><td>Traite les éléments un par un (ou par lots) : reliez la fin du traitement à l'entrée de la boucle.</td><td>élément / terminé</td></tr>
              <tr><td>Attendre</td><td>Pause de quelques secondes.</td><td>—</td></tr>
              <tr><td>Fusionner</td><td>Regroupe deux branches en une (A puis B).</td><td>—</td></tr>
              <tr class="cat"><td colspan="3">Données</td></tr>
              <tr><td>Lire un fichier</td><td>Charge un Excel/CSV : un élément par ligne (dates en jj/mm/aaaa, zéros en tête conservés).</td><td>—</td></tr>
              <tr><td>Filtrer</td><td>Garde les éléments qui respectent les règles.</td><td>gardés / écartés</td></tr>
              <tr><td>Modifier les champs</td><td>Ajoute, calcule (<code>{{ '{{' }}Prénom{{ '}}' }} {{ '{{' }}Nom{{ '}}' }}</code>), renomme, supprime des champs ; majuscules…</td><td>—</td></tr>
              <tr><td>Écrire un fichier</td><td>Produit un Excel/CSV téléchargeable dans le détail du run.</td><td>—</td></tr>
              <tr class="cat"><td colspan="3">Intégrations</td></tr>
              <tr><td>Requête HTTP</td><td>Appelle une API externe et ajoute sa réponse à l'élément.</td><td>succès / erreur</td></tr>
              <tr><td>Envoyer un e-mail</td><td>Un récapitulatif ou un e-mail par élément (serveur à configurer dans Settings).</td><td>—</td></tr>
              <tr><td>IA locale</td><td>Fait analyser, classer ou extraire une information par le modèle local (Ollama).</td><td>—</td></tr>
            </tbody>
          </table>

          <h3 id="fields">Utiliser les données : {{ '{{' }}Champ{{ '}}' }}</h3>
          <p>Partout où un texte est attendu, <code>{{ '{{' }}NomDuChamp{{ '}}' }}</code> est remplacé par la valeur de l'élément en cours.
            Le petit menu <em>« + champ »</em> liste les champs disponibles (colonnes du fichier, champs calculés plus haut).</p>
          <ul>
            <li><code>{{ '{{' }}Nom{{ '}}' }}</code> → <em>KOUASSI</em> ; <code>Contrat {{ '{{' }}N° Police{{ '}}' }}</code> → <em>Contrat 0042</em></li>
            <li><code>{{ '{{' }}reponse.client.id{{ '}}' }}</code> → un champ imbriqué (réponse d'une requête HTTP)</li>
            <li><code>{{ '{{' }}nombre{{ '}}' }}</code> → nombre d'éléments (e-mail récapitulatif, bloc Fin)</li>
          </ul>
          <p>Dans <strong>Exécuter un processus</strong>, chaque saisie enregistrée peut recevoir une valeur : laissez vide pour taper
            la valeur enregistrée, ou indiquez <code>{{ '{{' }}Login{{ '}}' }}</code> pour taper la colonne <em>Login</em>.</p>

          <h3 id="rules">Règles des conditions</h3>
          <p>Les comparaisons de texte ignorent majuscules et espaces autour ; les nombres acceptent <code>1 000,50</code>.</p>
          <div class="ops">
            <span>est égal à</span><span>est différent de</span><span>contient</span><span>ne contient pas</span>
            <span>commence par</span><span>se termine par</span><span>est vide</span><span>n'est pas vide</span>
            <span>est supérieur à</span><span>est supérieur ou égal à</span><span>est inférieur à</span>
            <span>est inférieur ou égal à</span><span>correspond à (regex)</span>
          </div>
          <p>Plusieurs règles se combinent par <em>toutes</em> (ET) ou <em>au moins une</em> (OU). Aucune formule n'est exécutée : seuls ces opérateurs existent.</p>

          <h3 id="session">Enchaîner des processus : la session</h3>
          <p>Par défaut, un processus rejoue tout, y compris l'ouverture de l'application et la connexion. Pour enchaîner sans tout recommencer,
            cochez dans le bloc <em>Exécuter un processus</em> : <strong>« Continuer dans la session en cours »</strong>.</p>
          <ul>
            <li>Les étapes d'ouverture sont sautées ; le robot travaille dans la fenêtre déjà ouverte.</li>
            <li><strong>Reprendre à l'étape</strong> : choisissez l'étape qui suit la connexion (ex. <em>#7 Clic « ORASS®Suite-SanlamAllianz CI »</em>)
              pour ne pas se reconnecter. Les saisies sautées disparaissent de « Valeurs à taper ».</li>
            <li>Dans une boucle, chaque élément reprend à cette étape.</li>
            <li>Un processus enregistré « dans la session en cours » coche automatiquement cette case.</li>
          </ul>
          <p><strong>Ordre d'exécution</strong> : <em>A → B</em> fait passer <em>toutes</em> les lignes dans A, puis toutes dans B.
            <em>Boucle → A → B → Boucle</em> fait passer chaque ligne par A puis B avant la suivante.</p>

          <h3 id="runs">Lancer et suivre</h3>
          <ul>
            <li>Pendant et après un run, chaque bloc se colore : <span class="c-ok">vert</span> réussi,
              <span class="c-warn">orange</span> avec des éléments en erreur, <span class="c-ko">rouge</span> en échec ; le nombre d'éléments traités s'affiche.</li>
            <li>Cliquez un bloc → onglet <em>Données du run</em> : éléments reçus et produits, et pour un processus chaque exécution avec son lien <em>Détail</em>.</li>
            <li><em>Relancer les éléments en échec</em> : relance uniquement les lignes qui ont échoué, à partir de ce processus.</li>
            <li><em>Rapport CSV</em> et fichiers produits : téléchargeables depuis la barre des exécutions.</li>
            <li><em>Annuler</em> arrête le robot proprement ; les lignes restantes sont marquées non traitées.</li>
          </ul>
        </section>

        <!-- ================================================================ -->
        <section id="triggers">
          <h2>Déclenchement</h2>
          <h3 id="schedule">Planifié (cron)</h3>
          <p>Le planning s'écrit en 5 champs : <code>minute heure jour mois jour-de-semaine</code>, à l'heure d'Abidjan (UTC).
            Cochez <em>Planification active</em> puis enregistrez. Si un run est encore en cours à l'heure prévue, le lancement est ignoré.</p>
          <table>
            <thead><tr><th>Expression</th><th>Signification</th></tr></thead>
            <tbody>
              <tr><td><code>0 8 * * 1-5</code></td><td>Du lundi au vendredi à 8h00</td></tr>
              <tr><td><code>0 7 * * *</code></td><td>Tous les jours à 7h00</td></tr>
              <tr><td><code>*/30 * * * *</code></td><td>Toutes les 30 minutes</td></tr>
              <tr><td><code>0 8-18 * * 1-5</code></td><td>Toutes les heures de 8h à 18h, jours ouvrés</td></tr>
              <tr><td><code>0 6 1 * *</code></td><td>Le 1er de chaque mois à 6h00</td></tr>
            </tbody>
          </table>

          <h3 id="api">Par appel API</h3>
          <p>Ajoutez un bloc <em>Début — appel API</em>, générez la clé (affichée une seule fois), puis :</p>
          <pre>{{ curlExample }}</pre>
          <ul>
            <li><code>&#123;"rows": [...]&#125;</code> : un élément par ligne ; un autre objet JSON : un seul élément ; corps vide : un élément vide.</li>
            <li>La réponse contient l'identifiant du run ; son suivi : <code>GET …/trigger/&lt;run_id&gt;</code> avec la même clé.</li>
          </ul>
        </section>

        <!-- ================================================================ -->
        <section id="integrations">
          <h2>Intégrations</h2>
          <h3 id="email">E-mail</h3>
          <p>Configurez le serveur une fois dans <a routerLink="/settings">Settings → Serveur e-mail</a> (le mot de passe est chiffré et jamais réaffiché),
            puis testez avec <em>Envoyer un test</em>. Le bloc envoie soit un seul e-mail récapitulatif (<code>{{ '{{' }}nombre{{ '}}' }}</code> éléments),
            soit un e-mail par élément.</p>
          <h3 id="http">Requête HTTP</h3>
          <p>Méthode, URL et en-têtes acceptent les champs (<code>https://api.exemple.ci/clients/{{ '{{' }}Code{{ '}}' }}</code>).
            La réponse est ajoutée à l'élément (champ <code>reponse</code> par défaut) ; un code d'erreur envoie l'élément vers la sortie « erreur ».</p>
          <h3 id="ai">IA locale</h3>
          <p>Le modèle tourne sur le serveur (Ollama), aucune donnée ne sort de l'entreprise. Écrivez l'instruction avec des champs
            (« Classe ce sinistre : <code>{{ '{{' }}Description{{ '}}' }}</code> ») ; la réponse est rangée dans le champ choisi.
            Cochez <em>JSON</em> pour extraire plusieurs informations. Sur une machine sans carte graphique, comptez quelques secondes par élément.</p>
        </section>

        <!-- ================================================================ -->
        <section id="example">
          <h2>Exemple complet : contrats Santé par option</h2>
          <p>Objectif : saisir dans ORASS les contrats d'un fichier Excel, avec une saisie différente selon l'option Santé.</p>
          <ol class="steps">
            <li><strong>Enregistrer « Connexion ORASS »</strong> (session normale) : ouverture du portail, identifiant, mot de passe, arrivée sur l'écran d'accueil.</li>
            <li><strong>Enregistrer une variante par option</strong> — ORASS ouvert sur l'écran d'accueil, case <em>« Continuer dans la session en cours »</em> cochée :
              « Santé — Essentiel », « Santé — Confort », « Santé — Premium », chacun revenant à l'écran d'accueil à la fin.</li>
            <li><strong>Créer le workflow</strong> (robot <code>SANLAM_PORTAL</code>) :
              <div class="diagram">DÉBUT → Connexion ORASS → Lire « contrats.xlsx » → Boucle → Aiguillage sur <code>Option</code>
                → [Essentiel | Confort | Premium] → retour à la Boucle ; Boucle « terminé » → Écrire « résultat.xlsx » → FIN (succès) ;
                Aiguillage « autre » → FIN (échec : « Option inconnue : {{ '{{' }}Option{{ '}}' }} »)</div></li>
            <li><strong>Associer les colonnes</strong> dans chaque variante : <code>{{ '{{' }}Nom{{ '}}' }}</code>, <code>{{ '{{' }}Prénom{{ '}}' }}</code>, <code>{{ '{{' }}Prime{{ '}}' }}</code>…</li>
            <li><strong>Lancer</strong>, puis consulter les blocs : les lignes en erreur se relancent d'un clic, le rapport CSV liste chaque contrat.</li>
          </ol>
        </section>

        <!-- ================================================================ -->
        <section id="troubleshooting">
          <h2>Dépannage</h2>
          <table>
            <thead><tr><th>Message / symptôme</th><th>Cause probable et solution</th></tr></thead>
            <tbody>
              <tr><td>Element introuvable à l'écran</td><td>L'écran n'est pas celui attendu (étape précédente ratée, fenêtre différente, application pas encore chargée)
                ou l'image enregistrée était imparfaite. Ouvrez le détail de l'exécution, vérifiez l'étape précédente ; si besoin, réenregistrez
                cette partie en attendant que la fenêtre soit stable.</td></tr>
              <tr><td>Fenêtre introuvable après 30 s</td><td>L'application n'est pas ouverte (bloc en « session en cours » sans connexion avant) ou son titre a changé.</td></tr>
              <tr><td>Texte saisi incomplet ou mélangé</td><td>L'application n'avait pas le focus : vérifiez qu'aucune autre fenêtre ne passe devant pendant le run.</td></tr>
              <tr><td>Un sous-menu ne s'ouvre pas</td><td>Réenregistrez en marquant une pause sur l'élément parent du menu.</td></tr>
              <tr><td>Bouton « Lancer » grisé</td><td>Modifications non enregistrées, problèmes signalés, pas de « Début — manuel », ou un run déjà en cours.</td></tr>
              <tr><td>Le run reste « En attente »</td><td>Un autre run ou une exécution utilise déjà le poste : ils passent un par un.</td></tr>
              <tr><td>Browser agent unreachable</td><td>L'agent n'est pas démarré sur le poste : <code>cd agents/browser &amp;&amp; python run.py</code>.</td></tr>
              <tr><td>Suppression refusée</td><td>Le message indique pourquoi (ex. processus encore utilisé par un workflow : retirez-le d'abord).</td></tr>
            </tbody>
          </table>
        </section>

        <!-- ================================================================ -->
        <section id="security">
          <h2>Sécurité</h2>
          <ul>
            <li>Les valeurs tapées (mots de passe compris) ne sont jamais écrites dans les journaux du robot ; elles sont masquées dans les écrans de configuration.</li>
            <li>Les secrets (mot de passe SMTP…) sont chiffrés en AES-256-GCM.</li>
            <li>Les clés d'appel API ne sont stockées que sous forme d'empreinte et affichées une seule fois.</li>
            <li>Les conditions n'exécutent aucun code : uniquement des opérateurs fixes.</li>
            <li>CAPTCHA et double authentification ne sont jamais contournés : le processus doit s'arrêter pour une intervention humaine.</li>
          </ul>
        </section>
        <div class="end-pad"></div>
      </main>
    </div>
  `,
  styles: [`
    :host { display: block; height: 100vh; }
    .doc { display: flex; height: 100vh; }
    .toc { width: 240px; flex-shrink: 0; border-right: 1px solid var(--border-color); background: var(--bg-primary); padding: 20px 12px; overflow-y: auto; }
    .toc-title { font-weight: 700; font-size: 15px; margin: 0 8px 12px; }
    .search { width: 100%; margin-bottom: 12px; }
    .no-match { font-size: 12px; color: var(--text-muted); margin: 0 8px 8px; }
    .toc-item, .toc-sub { display: block; padding: 6px 8px; border-radius: 6px; font-size: 13px; color: var(--text-secondary); cursor: pointer; text-decoration: none; }
    .toc-sub { padding-left: 20px; font-size: 12px; color: var(--text-muted); }
    .toc-item:hover, .toc-sub:hover { background: var(--bg-hover); color: var(--text-primary); }
    .toc-item.active, .toc-sub.active { color: var(--color-indigo); background: rgba(99,102,241,.1); }
    .dim { opacity: .35; }
    .content { flex: 1; overflow-y: auto; padding: 32px 48px; scroll-behavior: smooth; }
    section { max-width: 860px; margin-bottom: 48px; scroll-margin-top: 16px; }
    h1 { font-size: 26px; margin-bottom: 12px; }
    h2 { font-size: 21px; margin: 0 0 14px; padding-top: 8px; border-top: 1px solid var(--border-color); padding-top: 24px; }
    h3 { font-size: 15px; margin: 24px 0 8px; scroll-margin-top: 16px; }
    p, li, dd { font-size: 14px; line-height: 1.65; color: var(--text-secondary); }
    p { margin: 0 0 12px; }
    strong { color: var(--text-primary); }
    .lead { font-size: 15px; color: var(--text-primary); }
    ul, ol { padding-left: 22px; margin: 0 0 12px; }
    li { margin-bottom: 6px; }
    code { font-family: var(--font-mono); font-size: 12px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; padding: 1px 5px; color: var(--text-primary); }
    pre { font-family: var(--font-mono); font-size: 12px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 14px; white-space: pre-wrap; word-break: break-all; color: var(--text-primary); }
    kbd { font-family: var(--font-mono); font-size: 11px; border: 1px solid var(--border-color); border-bottom-width: 2px; border-radius: 4px; padding: 1px 6px; background: var(--bg-secondary); }
    a { color: var(--color-indigo); cursor: pointer; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 14px; }
    th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); padding: 8px 10px; border-bottom: 1px solid var(--border-color); }
    td { padding: 9px 10px; border-bottom: 1px solid var(--border-color); vertical-align: top; color: var(--text-secondary); line-height: 1.5; }
    td:first-child { color: var(--text-primary); font-weight: 500; white-space: nowrap; }
    table.blocks td:first-child { white-space: normal; min-width: 150px; }
    tr.cat td { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--color-indigo); font-weight: 700; padding-top: 14px; }
    .flow { display: flex; align-items: stretch; gap: 8px; margin: 20px 0; flex-wrap: wrap; }
    .flow-box { flex: 1; min-width: 150px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-muted); position: relative; }
    .flow-box strong { font-size: 14px; }
    .num { position: absolute; top: -10px; left: 12px; background: var(--color-indigo); color: white; width: 20px; height: 20px; border-radius: 50%; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
    .flow-arrow { display: flex; align-items: center; color: var(--text-muted); font-size: 18px; }
    .defs dt { font-weight: 700; color: var(--text-primary); font-size: 14px; margin-top: 10px; }
    .defs dd { margin: 2px 0 0 0; }
    .steps li { margin-bottom: 10px; }
    .callout { border-radius: 8px; padding: 12px 14px; font-size: 13px; line-height: 1.6; margin: 12px 0; }
    .callout.info { background: var(--color-blue-bg); color: var(--color-blue); }
    .callout.warn { background: var(--color-amber-bg); color: var(--color-amber); }
    .callout code { color: inherit; }
    .tips li::marker { color: var(--color-green); }
    .tag { font-size: 10px; font-weight: 800; letter-spacing: .08em; padding: 1px 6px; border-radius: 6px; color: #0b1020; }
    .tag.start { background: #6366f1; }
    .tag.end { background: #34d399; }
    .dot { color: var(--text-muted); }
    .ops { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .ops span { font-size: 12px; padding: 3px 9px; border-radius: 12px; background: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-secondary); }
    .diagram { margin-top: 8px; padding: 10px 12px; border: 1px dashed var(--border-color); border-radius: 8px; font-size: 13px; line-height: 1.7; color: var(--text-primary); }
    .c-ok { color: var(--color-green); font-weight: 600; }
    .c-warn { color: var(--color-amber); font-weight: 600; }
    .c-ko { color: var(--color-red); font-weight: 600; }
    .end-pad { height: 40vh; }
  `]
})
export class DocumentationComponent implements AfterViewInit {
  @ViewChild('content', { static: true }) content!: ElementRef<HTMLElement>;

  toc: TocEntry[] = [
    { id: 'overview', title: 'Comment ça marche' },
    { id: 'quickstart', title: 'Démarrage rapide' },
    { id: 'robots', title: 'Robots' },
    { id: 'recording', title: 'Enregistrer un processus', children: [
      { id: 'recording-session', title: 'Session en cours' },
      { id: 'recording-tips', title: 'Bonnes pratiques' },
    ] },
    { id: 'replay', title: 'Comment le robot rejoue' },
    { id: 'workflows', title: 'Workflows', children: [
      { id: 'editor', title: "L'éditeur" },
      { id: 'start-end', title: 'Début et Fin' },
      { id: 'blocks', title: 'Les blocs' },
      { id: 'fields', title: 'Utiliser les données' },
      { id: 'rules', title: 'Règles des conditions' },
      { id: 'session', title: 'Enchaîner des processus' },
      { id: 'runs', title: 'Lancer et suivre' },
    ] },
    { id: 'triggers', title: 'Déclenchement', children: [
      { id: 'schedule', title: 'Planifié (cron)' },
      { id: 'api', title: 'Par appel API' },
    ] },
    { id: 'integrations', title: 'Intégrations' },
    { id: 'example', title: 'Exemple : Santé par option' },
    { id: 'troubleshooting', title: 'Dépannage' },
    { id: 'security', title: 'Sécurité' },
  ];

  curlExample = `curl -X POST ${window.location.origin}/api/v1/pipelines/<id du workflow>/trigger \\
  -H "X-API-Key: <clé>" -H "Content-Type: application/json" \\
  -d '{"rows": [{"Nom": "KOUASSI", "Option": "Confort"}]}'`;

  active = 'overview';
  query = '';
  hidden = new Set<string>();
  matches = true;

  ngAfterViewInit() { this.onScroll(); }

  go(id: string) {
    const el = this.content.nativeElement.querySelector('#' + id) as HTMLElement | null;
    if (el) {
      this.content.nativeElement.scrollTo({ top: el.offsetTop - 16, behavior: 'smooth' });
      this.active = id;
    }
  }

  /** Highlight the section being read. */
  onScroll() {
    const root = this.content.nativeElement;
    const ids = this.toc.flatMap(s => [s.id, ...(s.children || []).map(c => c.id)]);
    let current = ids[0];
    for (const id of ids) {
      const el = root.querySelector('#' + id) as HTMLElement | null;
      if (el && el.offsetTop - root.scrollTop <= 80) current = id;
    }
    this.active = current;
  }

  /** Dims the sections that don't contain the searched words; jumps to the first match. */
  filter() {
    const words = this.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    this.hidden.clear();
    if (!words.length) { this.matches = true; return; }
    let first: string | null = null;
    for (const s of this.toc) {
      const el = this.content.nativeElement.querySelector('#' + s.id);
      const text = (el?.textContent || '').toLowerCase();
      if (words.every(w => text.includes(w))) { first ??= s.id; } else { this.hidden.add(s.id); }
    }
    this.matches = !!first;
    if (first) this.go(first);
  }
}
