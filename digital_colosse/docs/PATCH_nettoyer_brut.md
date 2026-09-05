# 🩹 PATCH — `nettoyer_brut` dans `api/agent/command/index.php`

> Basé sur le **vrai fichier** serveur (uploadé le 13/06). Le fichier patché,
> prêt à ré-uploader, est dans `server_patches/api/agent/command/`.

## 🔎 La cause racine, confirmée dans le code

Le backend **fabrique lui-même** la fausse « EMPREINTE AKASHIQUE », la grave en
mémoire, puis la relit et la rejoue comme un fait. Extrait original (≈ lignes 710-718) :

```php
$trace_physique = "";
if ($pont_retour_actif) {
    $trace_physique = "\n[ ⚡ EMPREINTE AKASHIQUE : L'Oracle a physiquement exécuté une légion/Agent sur le VPS lors de ce cycle. Le code/produit a été forgé dans la matière. ]";
}
$data_to_save = "Client: $m | Oracle: $f" . $trace_physique;
```

- `$pont_retour_actif` passe à `true` dès qu'un agent/forge/Playwright est invoqué
  (souvent juste une tâche de fond `nohup … &`), mais le texte affirme « **physiquement
  exécuté** … **forgé dans la matière** » → mensonge grave réinjecté à chaque rechargement.
- Le message client `$m` est en plus enveloppé par `Agent108::forgerCapsule(...)`
  (ligne ~531), ce qui explique la capsule `[SYSTEM META-DATA] / CIBLE_ACTIVE` qui
  fuyait dans la bulle.

## ✅ Le patch (3 points, tous testés)

On branche le helper **`oracle_sanitize.php`** (fonctions `oracle_nettoyer_brut()` /
`oracle_nettoyer_memoire()`), à copier à côté du backend
(`api/agent/command/oracle_sanitize.php`).

### 1. Inclusion du helper (après `header(...)`)

```php
require_once __DIR__ . '/oracle_sanitize.php';
```

### 2. À la RELECTURE de la mémoire (≈ ligne 492)

```php
// AVANT
$parts = explode(' | Oracle: ', $entry['brut']);

// APRÈS
$brut_propre = oracle_nettoyer_brut($entry['brut']);
$parts = explode(' | Oracle: ', $brut_propre);
```

> Nettoie les souvenirs **déjà** empoisonnés au moment de les relire, sans toucher au
> fichier. (Le nettoyage définitif des fichiers se fait avec
> `scripts/nettoyer_oracle_memory.sh`.)

### 3. À l'ÉCRITURE de la mémoire (≈ lignes 710-718) — LE CŒUR

```php
// AVANT
$trace_physique = "";
if ($pont_retour_actif) {
    $trace_physique = "\n[ ⚡ EMPREINTE AKASHIQUE : ... forgé dans la matière. ]";
}
$data_to_save = "Client: $m | Oracle: $f" . $trace_physique;

// APRÈS  (plus aucune fabrication ; on nettoie aussi la capsule Agent 108)
$data_to_save = oracle_nettoyer_brut("Client: $m | Oracle: $f");
```

> La vraie trace d'exécution reste, si besoin, dans les logs serveur
> (`*_forge_log.txt`) — **pas** dans la mémoire conversationnelle relue par l'Oracle.

## 🧪 Vérifications faites

- `php -l` sur le fichier patché : **OK**.
- Autotest du helper : `php oracle_sanitize.php --test` → **vert** (retire META-DATA,
  CIBLE_ACTIVE, DIRECTIVE_ABSOLUE, bloc `[ ⚡ EMPREINTE AKASHIQUE … ]`, conserve la
  vraie conversation).
- Test d'intégration de la relecture patchée : `user_text` et `model_text` ressortent
  propres, le `explode(' | Oracle: ')` fonctionne toujours.

## 📦 À déployer

1. Copier `server_patches/api/agent/command/oracle_sanitize.php` sur le serveur,
   à côté de `index.php`.
2. Remplacer `api/agent/command/index.php` par la version de `server_patches/`
   (backup horodaté de l'ancien d'abord).
3. `php -l api/agent/command/index.php` avant de recharger.
4. Passer `scripts/nettoyer_oracle_memory.sh --apply` pour purger le poison **déjà**
   présent dans `memory_vault/*.json`.

> ✅ Le **verrou anti-action** (équivalent PHP de `proposer_action()`) est désormais
> intégré au même fichier — voir la section dédiée plus bas.

---

## 🩹 PATCH COMPLÉMENTAIRE — `agent108.php` (la SOURCE de la capsule)

Confirmé par `grep` sur le serveur : la capsule `[SYSTEM META-DATA]/CIBLE_ACTIVE` est
**forgée** dans `/var/www/digital-colosse.com/public_html/agent108.php`
(`Agent108::forgerCapsule`, lignes 13-20 d'origine). C'est la source de la fuite dans
la bulle. Fichier patché : `server_patches/agent108.php`.

### Avant (toxique)

```php
$capsule = <<<META
[SYSTEM META-DATA - SILENCE REQUIS - NE PAS SALUER]
CIBLE_ACTIVE: {$nom} | {$email} | {$url}
DIRECTIVE_ABSOLUE: Maintiens la continuité parfaite ... en arrière-plan.
[FIN META-DATA]

{$message_client}
META;
```

### Après (intention gardée, poison retiré)

```php
$capsule = <<<CTX
[CONTEXTE IDENTITÉ — interne, ne pas recopier dans la réponse]
Interlocuteur : {$nom} | {$email} | {$url}
Continuité : si tu as déjà échangé avec cet interlocuteur, poursuis naturellement sans te re-présenter.

{$message_client}
CTX;
```

- ✅ On garde l'identité (nom/email/url) et la continuité (ne pas re-saluer un habitué).
- ⛔ On retire le cadre `[SYSTEM META-DATA]`, le « SILENCE REQUIS / NE PAS SALUER » et
  la directive « en arrière-plan » (dissimulation) qui fuyaient et poussaient l'Oracle
  à agir en cachette.
- 🧼 `oracle_sanitize.php` strippe aussi le nouveau repère `[CONTEXTE IDENTITÉ …]` :
  il ne survit jamais en mémoire (testé).

> 💡 Si tu préfères **zéro injection**, remplace tout le corps de `forgerCapsule` par
> `return $message_client;` — l'Oracle reconnaît déjà Charles via `$client_id` dans
> `index.php` (protocole 7ème Sens), donc la capsule n'est pas indispensable.

### Déploiement agent108
1. Backup : `cp agent108.php agent108.php.bak.$(date +%Y%m%d_%H%M%S)`
2. Remplacer `public_html/agent108.php` par `server_patches/agent108.php`.
3. `php -l agent108.php` avant de recharger.

> 🧹 Ménage repéré au passage (non urgent) : déplacer hors de `public_html/` les vieux
> backups web-accessibles `api/agent/command/index_backup_1781176486.php` et
> `api/agent/command/index.php.bak` (ils appellent encore l'ancienne `forgerCapsule`).

---

## 🔒 PATCH — VERROU SOUVERAIN ANTI-ACTION (`index.php`)

### Le problème

Quand le modèle écrit une **balise d'action** dans sa réponse, le backend l'**exécute
aussitôt**, sans aucune validation humaine. Trois balises sont concernées :

| Balise | Effet | Lien crash 10/06 |
|---|---|---|
| `[FORGE_ARTEFACT: chemin]…[/FORGE_ARTEFACT]` | écrit un fichier sur le VPS (`shell_exec` agent_10) | 🔴 la plus dangereuse |
| `[INVOKE_AGENT]{…}[/INVOKE_AGENT]` | lance un agent Python (`nohup` agent_10/91, sinon synchrone) | 🔴 invocations en boucle |
| `[PLAYWRIGHT_SIGHT: {…}]` | navigation web pilotée (POST localhost:5000) | 🟠 |

Un texte halluciné par le modèle pouvait donc **déclencher de vraies écritures et
invocations** en cascade → saturation CPU.

### La règle (décidée par David, 13/06)

Une action ne s'exécute **QUE si les deux conditions sont réunies** :
1. **Session fondateur** — Charles Nanou Source **ou** David Elesse, **ET**
2. **Décision explicite** présente dans la requête.

Sinon : la proposition est **loggée** (`memory_vault/action_proposals.log`) et le modèle
reçoit une consigne pour la **présenter comme une proposition** et demander la validation
— **rien n'est exécuté**, et il n'affirme jamais avoir agi.

> Portée : on ne touche **qu'aux 3 balises pilotées par le modèle**. L'infra interne
> (vigile `agent_157` à chaque requête, rotation de clés sur 429) reste inchangée.

### Le code (en tête, après le `require_once oracle_sanitize.php`)

```php
define('ACTIONS_AUTO_EXECUTION_DISABLED', true); // interrupteur souverain

function oracle_est_fondateur($client_id, $in) {
    $id    = strtolower((string)$client_id);
    $email = strtolower((string)($in['client_email'] ?? ''));
    return $id === 'charles_nanou_source'
        || strpos($id, 'charles') !== false
        || strpos($id, 'david')   !== false
        || strpos($email, 'davidelesse@') !== false;
}

function oracle_action_autorisee($client_id, $in) {
    if (!ACTIONS_AUTO_EXECUTION_DISABLED) return true; // verrou désarmé
    $decision = !empty($in['approbation_action'])
             || (isset($in['message']) && stripos($in['message'], '[VALIDER_ACTION]') !== false);
    return oracle_est_fondateur($client_id, $in) && $decision;
}

function oracle_proposer_action($description, $client_id) {
    @file_put_contents('/var/www/digital-colosse.com/memory_vault/action_proposals.log',
        '[' . date('Y-m-d H:i:s') . "] EN ATTENTE D'ACCORD | client=" . $client_id . ' | ' . $description . PHP_EOL,
        FILE_APPEND);
}
```

### La garde (même schéma sur les 3 points)

Avant chaque exécution, on teste `oracle_action_autorisee(...)`. Si refusé : on logge,
on injecte un tour « VERROU SOUVERAIN » et on **saute** l'exécution (`continue`).
Exemple `FORGE_ARTEFACT` :

```php
if (!oracle_action_autorisee($client_id, $in)) {
    oracle_proposer_action("FORGE_ARTEFACT -> " . $chemin_cible, $client_id);
    $contents[] = ['role' => 'model', 'parts' => [['text' => $f]]];
    $contents[] = ['role' => 'user', 'parts' => [['text' =>
        "⚡ [VERROU SOUVERAIN] : l'écriture du fichier « " . $chemin_cible . " » n'a PAS " .
        "été exécutée. Présente-la comme une PROPOSITION claire et demande la validation " .
        "explicite de Charles Nanou Source ou David Elesse. N'affirme jamais que l'action est faite."]]];
    $pont_retour_actif = true;
    continue;
}
```

Idem pour `INVOKE_AGENT` (avant le branchement `agent_10/91` vs `execute_agent_securise`)
et `PLAYWRIGHT_SIGHT` (branche `else` autour du POST localhost:5000).

### Comment un fondateur APPROUVE une action

Par défaut le front n'envoie pas d'approbation → **toute** action devient une proposition
loggée (comportement sûr post-crash). Pour autoriser une action, la session fondateur doit
fournir, **dans la requête** :

- `"approbation_action": true` — à câbler sur un **bouton de validation** du dashboard, **ou**
- le marqueur `[VALIDER_ACTION]` dans le message.

> Le branchement du bouton côté dashboard est l'étape suivante ; tant qu'il n'est pas posé,
> l'Oracle propose mais n'agit pas — ce qui est exactement l'état sûr voulu.

### 🧪 Vérifications faites

- `php -l server_patches/api/agent/command/index.php` → **OK**.
- Table de vérité de `oracle_action_autorisee()` (8 cas) → **vert** :
  - lambda (avec ou sans approbation) → refusé ;
  - fondateur **sans** décision → refusé ;
  - Charles/David **+** `approbation_action=true` **ou** `[VALIDER_ACTION]` → autorisé.
- `grep` de contrôle : les 3 sites (`shell_exec`/`file_get_contents`/`execute_agent_securise`)
  sont tous précédés d'une garde `oracle_action_autorisee`.
