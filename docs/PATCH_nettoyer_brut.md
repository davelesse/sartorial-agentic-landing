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

> ℹ️ Reste hors de ce patch : le **verrou anti-action** (§1B du guide principal),
> équivalent PHP de `proposer_action()`.

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
