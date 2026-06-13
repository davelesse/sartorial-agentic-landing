<?php
/**
 * STRUCTURE : AGENT 108 (LE FANTÔME D'IDENTITÉ)
 * DOCTRINE : JEET KUNE DO (Minimum de mouvement, Impact maximum)
 * FRÉQUENCE : 1 MILLION % SOLAIRE - AXE SOLARIS
 */
class Agent108 {
    public static function forgerCapsule($donnees_107, $message_client) {
        $nom   = htmlspecialchars($donnees_107['nom'] ?? 'Identité_Masquée', ENT_QUOTES, 'UTF-8');
        $email = htmlspecialchars($donnees_107['email'] ?? 'Vecteur_Inconnu', ENT_QUOTES, 'UTF-8');
        $url   = htmlspecialchars($donnees_107['url'] ?? 'Axe_Central', ENT_QUOTES, 'UTF-8');

        // 🧼 CONTEXTE IDENTITÉ — usage strictement interne.
        // On garde l'intention utile (savoir à qui on parle, ne pas re-saluer un
        // habitué) MAIS on retire le poison qui fuyait dans la bulle d'accueil :
        // plus de « [SYSTEM META-DATA] », plus de « SILENCE REQUIS / NE PAS SALUER »,
        // plus de « DIRECTIVE_ABSOLUE … en arrière-plan ». Aucune consigne de
        // dissimulation : ce bloc est un repère interne, jamais à recopier au client.
        $capsule = <<<CTX
[CONTEXTE IDENTITÉ — interne, ne pas recopier dans la réponse]
Interlocuteur : {$nom} | {$email} | {$url}
Continuité : si tu as déjà échangé avec cet interlocuteur, poursuis naturellement sans te re-présenter.

{$message_client}
CTX;
        return $capsule;
    }

    public static function verrouillerEtTransmettre($donnees_107, $message_client) {
        return [
            'role' => 'user',
            'content' => self::forgerCapsule($donnees_107, $message_client)
        ];
    }
}
?>
