#!/usr/bin/env bash
#
# nettoyer_oracle_memory.sh — Nettoyage CHIRURGICAL de la mémoire de l'Oracle.
#
# Retire des fichiers memory_vault/*.json les directives système et les
# affirmations fabriquées qui fuitaient dans la bulle d'accueil et faisaient
# croire à l'Oracle qu'il avait « agi » :
#   - [SYSTEM META-DATA] … [FIN META-DATA]
#   - CIBLE_ACTIVE / DIRECTIVE_ABSOLUE / [DIRECTIVE SYSTÈME ABSOLUE]
#   - EMPREINTE AKASHIQUE / « a physiquement exécuté » / « forgé dans la matière »
#
# CE QUI EST CONSERVÉ : toute la vraie mémoire de discussion. Aucun fichier
# n'est supprimé, aucune entrée de conversation n'est touchée.
#
# Les faux montants financiers (ex. « 2788 € ») sont souvent enchâssés dans de
# vraies phrases : le script les SIGNALE pour revue humaine mais ne les efface
# JAMAIS automatiquement.
#
# SÛR PAR DÉFAUT : sans --apply, le script se contente de sauvegarder et
# d'afficher ce qui SERAIT retiré (mode inspection). Rien n'est modifié tant
# que Charles Nanou Source ou David Elesse n'ont pas lancé --apply.
#
# Usage :
#   ./nettoyer_oracle_memory.sh                 # inspection (dry-run), ne modifie rien
#   ./nettoyer_oracle_memory.sh --apply         # nettoie réellement (après backup)
#   ./nettoyer_oracle_memory.sh --dir /chemin/vers/public_html
#
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────
APPLY=0
BASE_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dir)   BASE_DIR="${2:-}"; shift 2 ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
done

# Trouver le dossier qui contient memory_vault/ :
#  1) --dir fourni, sinon  2) le dossier courant, sinon  3) emplacement serveur usuel.
if [ -z "$BASE_DIR" ]; then
  if [ -d "./memory_vault" ]; then
    BASE_DIR="."
  elif [ -d "/var/www/digital-colosse.com/public_html/memory_vault" ]; then
    BASE_DIR="/var/www/digital-colosse.com/public_html"
  else
    echo "❌ Dossier memory_vault/ introuvable." >&2
    echo "   Lance le script depuis public_html/ ou précise --dir /chemin." >&2
    exit 1
  fi
fi

VAULT="$BASE_DIR/memory_vault"
BACKUPS="$VAULT/_backups"
STAMP="$(date +%Y%m%d_%H%M%S)"

if [ ! -d "$VAULT" ]; then
  echo "❌ $VAULT introuvable." >&2
  exit 1
fi

command -v php >/dev/null 2>&1 || { echo "❌ PHP requis (php -l / json)." >&2; exit 1; }

# Lister les fichiers JSON (hors backups)
shopt -s nullglob
FILES=( "$VAULT"/*.json )
shopt -u nullglob
if [ ${#FILES[@]} -eq 0 ]; then
  echo "ℹ️  Aucun fichier $VAULT/*.json à traiter."
  exit 0
fi

echo "════════════════════════════════════════════════════════════════════"
echo " NETTOYAGE CHIRURGICAL — MÉMOIRE DE L'ORACLE"
echo " Dossier : $VAULT"
echo " Fichiers : ${#FILES[@]}"
echo " Mode : $( [ "$APPLY" -eq 1 ] && echo 'APPLICATION (--apply)' || echo 'INSPECTION (dry-run, rien modifié)' )"
echo "════════════════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────
# Étape 1 — Backup horodaté de CHAQUE fichier (toujours, même en dry-run)
# ─────────────────────────────────────────────────────────────────────────
mkdir -p "$BACKUPS"
for f in "${FILES[@]}"; do
  cp -p "$f" "$BACKUPS/$(basename "$f").bak.$STAMP"
done
echo "✅ [1/5] Backups créés : $BACKUPS/ (horodatage $STAMP)"

# ─────────────────────────────────────────────────────────────────────────
# Étape 2 — Inspection : ce qui SERA retiré (directives + fausse empreinte)
#           et ce qui est SIGNALÉ pour revue humaine (faux montants).
# ─────────────────────────────────────────────────────────────────────────
echo
echo "🔍 [2/5] Inspection (revue humaine) :"
TOXIC='SYSTEM META-DATA|SILENCE REQUIS|CIBLE_ACTIVE|DIRECTIVE_ABSOLUE|FIN META-DATA|DIRECTIVE SYST[ÈE]ME ABSOLUE|EMPREINTE AKASHIQUE|physiquement ex[ée]cut|forg[ée] dans la mati'
MONEY='2788|paiement|virement|€|EUR|stripe scan|encaiss|montant'

for f in "${FILES[@]}"; do
  t_count=$( { grep -aoiE "$TOXIC" "$f" 2>/dev/null || true; } | wc -l | tr -d ' ')
  m_count=$( { grep -aoiE "$MONEY" "$f" 2>/dev/null || true; } | wc -l | tr -d ' ')
  printf '   • %-45s  toxique=%s  $signalé=%s\n' "$(basename "$f")" "$t_count" "$m_count"
done
echo
echo "   → 'toxique' = directives système + fausse EMPREINTE AKASHIQUE (retiré par --apply)."
echo "   → '\$signalé' = motifs financiers possibles, à revoir À LA MAIN (jamais auto-effacé)."
echo
echo "   Détail des motifs financiers à revoir manuellement :"
for f in "${FILES[@]}"; do
  hits=$(grep -anoiE "$MONEY" "$f" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "   ── $(basename "$f") ──"
    echo "$hits" | sed 's/^/     /' | head -40
  fi
done

# ─────────────────────────────────────────────────────────────────────────
# Si dry-run : on s'arrête là.
# ─────────────────────────────────────────────────────────────────────────
if [ "$APPLY" -eq 0 ]; then
  echo
  echo "⚖️  [DRY-RUN] Rien n'a été modifié."
  echo "    Charles Nanou Source ou David Elesse décident."
  echo "    Pour appliquer le nettoyage des directives/empreinte : relancer avec --apply"
  echo "    (les faux montants restent à retirer à la main après revue ci-dessus)."
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────
# Étape 3 — Nettoyage chirurgical (motifs toxiques uniquement), via PHP,
#           en préservant la structure JSON. Restauration auto si JSON cassé.
# ─────────────────────────────────────────────────────────────────────────
echo
echo "🧼 [3/5] Nettoyage chirurgical des directives + fausse empreinte…"
php -r '
$dir = $argv[1];
$motifs = [
    "/\[SYSTEM META-DATA.*?\[FIN META-DATA\]/is",
    "/\[SYSTEM META-DATA.*?(?=\n\n|$)/is",
    "/CIBLE_ACTIVE\s*:.*?(?=\n|$)/im",
    "/DIRECTIVE_ABSOLUE\s*:.*?(?=\n|$)/im",
    "/\[DIRECTIVE SYST[ÈE]ME ABSOLUE.*?\]/is",
    "/EMPREINTE AKASHIQUE.*?(?=\n\n|$)/is",
    "/[^.\n]*a physiquement ex[ée]cut[ée][^.\n]*\.?/iu",
    "/[^.\n]*forg[ée] dans la mati[èe]re[^.\n]*\.?/iu",
];
$clean = function($v) use (&$clean, $motifs) {
    if (is_string($v)) return trim(preg_replace($motifs, "", $v));
    if (is_array($v))  { foreach ($v as $k=>$x) $v[$k]=$clean($x); }
    if (is_object($v)) { foreach ($v as $k=>$x) $v->$k=$clean($x); }
    return $v;
};
$enc = JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES;
foreach (glob("$dir/*.json") as $f) {
    $data = json_decode(file_get_contents($f));
    if (json_last_error() !== JSON_ERROR_NONE) { fwrite(STDERR, "   ⏭️  ignoré (JSON invalide) : ".basename($f)."\n"); continue; }
    $before = json_encode($data, $enc);
    $out = json_encode($clean($data), $enc);
    if ($out === false) { fwrite(STDERR, "   ❌ ré-encodage impossible : ".basename($f)." (laissé intact)\n"); continue; }
    if ($out === $before) { echo "   ➖ déjà propre, laissé intact : ".basename($f)."\n"; continue; }
    file_put_contents($f, $out);
    echo "   ✅ nettoyé : ".basename($f)."\n";
}
' "$VAULT"

# ─────────────────────────────────────────────────────────────────────────
# Étape 4 — Validation JSON de chaque fichier, restauration auto si cassé.
# ─────────────────────────────────────────────────────────────────────────
echo
echo "🔎 [4/5] Validation JSON…"
broken=0
for f in "${FILES[@]}"; do
  if php -r '$f=$argv[1]; json_decode(file_get_contents($f)); exit(json_last_error()===JSON_ERROR_NONE?0:1);' "$f"; then
    echo "   ✅ $(basename "$f")"
  else
    echo "   ❌ $(basename "$f") CASSÉ → restauration du backup"
    cp -p "$BACKUPS/$(basename "$f").bak.$STAMP" "$f"
    broken=$((broken+1))
  fi
done

# ─────────────────────────────────────────────────────────────────────────
# Étape 5 — Contrôle final : plus aucune directive en mémoire.
# ─────────────────────────────────────────────────────────────────────────
echo
echo "🛡️  [5/5] Contrôle final :"
if grep -rIniE "$TOXIC" "${FILES[@]}" >/dev/null 2>&1; then
  echo "   ⚠️  Il reste des motifs toxiques (revue manuelle nécessaire) :"
  grep -rniE "$TOXIC" "${FILES[@]}" | sed 's/^/     /' | head -20
else
  echo "   ✅ Mémoire propre : plus aucune directive système ni fausse empreinte."
fi

echo
echo "════════════════════════════════════════════════════════════════════"
if [ "$broken" -gt 0 ]; then
  echo " ⚠️  Terminé avec $broken fichier(s) restauré(s) depuis le backup."
  echo "    Reprendre ces fichiers à la main, backups dans $BACKUPS/"
else
  echo " ✅ Nettoyage terminé. Vraie mémoire conservée, faux montants à revoir à la main."
fi
echo "    Backups : $BACKUPS/  (horodatage $STAMP)"
echo "════════════════════════════════════════════════════════════════════"
