<?php
// ═══════════════════════════════════════════
// ⚡ LA PORTE DU COLOSSE (RÉCEPTEUR STRIPE → ESPOCRM)
// Emplacement serveur : /var/www/digital-colosse.com/public_html/webhook_colosse.php
// (sauvegarde reconstruite depuis capture d'écran — vérifier avant redéploiement)
// ═══════════════════════════════════════════

$payload = file_get_contents('php://input');
$sig_header = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

if (!$payload || !$sig_header) { http_response_code(400); exit; }

$tmp_file = '/tmp/stripe_event_' . uniqid() . '.json';
file_put_contents($tmp_file, $payload);

// Appel du Pont Python
$cmd = "python3 /var/www/digital-colosse.com/agents_aurum/bridge_colosse.py "
     . escapeshellarg($tmp_file) . " " . escapeshellarg($sig_header) . " 2>&1";
$out = shell_exec($cmd);

unlink($tmp_file);
http_response_code(200);
echo "Matrice synchronisée. Agent 21 déployé.";
