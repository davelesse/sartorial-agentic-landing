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

> ℹ️ Reste hors de ce patch : la capsule `[SYSTEM META-DATA]/CIBLE_ACTIVE` est forgée
> dans **`agent108.php`** (`Agent108::forgerCapsule`). Le patch la neutralise à la
> lecture et à l'écriture, mais si tu veux tarir la source, il faudra aussi revoir
> `agent108.php` (non fourni). Idem pour le verrou anti-action (§1B du guide principal).
