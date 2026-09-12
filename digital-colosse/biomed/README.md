# Digital Colosse — Moteur biomédical FHIR R4B

Passerelle d'ingestion multi-tenant : normalise des mesures brutes de capteurs en
ressources FHIR R4B `Observation` validées. Agnostique de tout framework web —
fonctionne sous FastAPI, Django, un worker Celery ou un simple consommateur de file.

Principe directeur : **fail-closed**. Une mesure qu'on ne sait pas interpréter avec
certitude est rejetée. Elle ne retombe jamais sur une valeur par défaut.

## Câblage au démarrage

Deux choses viennent de l'hôte, délibérément : ce module ne lit aucune configuration
de lui-même et ne connaît pas la couche de persistance.

```python
from biomed_engine import ingest_reading, pseudonymizer_from_env

# UNE FOIS au boot. Lève si BIOMED_PSEUDONYM_HMAC_KEY manque → le service ne
# démarre pas. C'est voulu : voir « Pseudonymisation » ci-dessous.
PSEUDONYMIZER = pseudonymizer_from_env()

result = await ingest_reading(
    payload,                      # dict brut du capteur / du courtier
    sink=mon_sink,                # implémentation d'ObservationSink (à fournir)
    tenant_id="clinique-lyon",    # SOURCE DE VÉRITÉ — jamais le payload
    pseudonymizer=PSEUDONYMIZER,
)
```

Clé requise, en hexadécimal (32 octets) :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Voir `.env.example`. `ingest_reading` n'a **pas** de valeur par défaut pour
`pseudonymizer` : on ne peut pas ingérer de la donnée de santé sans savoir comment
la journaliser sans la divulguer.

## Deux propriétés que ce module ne tient pas seul

Il tient le **contrat**, pas l'implémentation. Les deux points à finir côté
Digital Colosse :

### 1. Unicité des observations → contrainte de base de données

`exists()` puis `store()` est un vérifier-puis-agir : entre les deux, un autre
worker peut insérer. Ce module n'a pas de transaction, il ne peut pas refermer
cette course. Le séquencement de `ingest_batch` ne protège qu'un lot, jamais
plusieurs workers — le cas normal en production.

La garantie vient donc de la base. `store()` rend un `StoreOutcome(created=...)`
et **c'est lui qui tranche** : `created=False` → `DUPLICATE`, pas de seconde ligne.

```sql
CREATE TABLE observations (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    identifier_system TEXT NOT NULL,
    identifier_value  TEXT NOT NULL,
    resource          JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT observations_identity_uniq
        UNIQUE (tenant_id, identifier_system, identifier_value)
);
```

```sql
-- Écriture recommandée (PostgreSQL) : aucune exception, donc aucune
-- transaction avortée. created = (une ligne est revenue).
INSERT INTO observations (tenant_id, identifier_system, identifier_value, resource)
VALUES ($1, $2, $3, $4)
ON CONFLICT ON CONSTRAINT observations_identity_uniq DO NOTHING
RETURNING id;
```

Voie portable (rattrapage d'`IntegrityError`) et le détail du `SAVEPOINT`
indispensable : docstring d'`ObservationSink` dans `biomed_engine.py`.

**Pas de dépendance SQLAlchemy ici**, volontairement : elle casserait la propriété
agnostique du module. Quand le sink concret sera écrit, branche-le sur le contrat
de conformité fourni :

```python
from test_biomed_engine import assert_sink_honours_uniqueness
await assert_sink_honours_uniqueness(mon_sink_sqlalchemy, measured_at)
```

S'il ne porte pas la contrainte, l'assert échoue.

### 2. Résolution des références patient → serveur FHIR

`Patient/12345` chez le tenant A et chez le tenant B sont deux personnes. Le tag de
tenant rend l'appartenance explicite sur la ressource ; il ne remplace pas une
isolation côté serveur.

## Pseudonymisation des journaux

Les empreintes patient des journaux sont des **HMAC-SHA256 à clé serveur**, pas des
hash nus. Un hash nu n'est pas une protection quand l'espace des entrées est petit
et prévisible : les identifiants patients sont souvent séquentiels, et
`Patient/12345` se retrouve depuis son empreinte en 12 345 essais — mesuré à
0,008 s. Préfixer par le tenant n'y change rien, le `tenant_id` étant journalisé en
clair sur la même ligne.

Le HMAC conserve la propriété utile — même patient → même empreinte, donc
corrélation de deux lignes possible — et retire la réversibilité.

Absence de clé = **échec au démarrage**. Un service qui démarrerait en mode dégradé
journaliserait des empreintes réversibles pendant des mois sans alerte. Une rotation
de clé rend les anciennes empreintes non corrélables aux nouvelles : c'est attendu,
elles ne sont pas censées y survivre.

## Conversions d'unités — deux mécanismes distincts

La distinction est un correctif de sécurité, pas un rangement.

| | Portée | Exemples |
|---|---|---|
| `DIMENSIONAL_CONVERSIONS` | globale — propriété de l'unité | °F→Cel, lb→kg, m→cm |
| `MetricDefinition.analyte_conversions` | **une seule métrique** | glucose mmol/L→mg/dL, HbA1c mmol/mol→% |

Une table unique indexée `(unité reçue, unité canonique)` était un défaut grave. Le
facteur 18,0182 mmol/L → mg/dL est la masse molaire du **glucose** ; indexé sans la
métrique, il s'appliquait à toute métrique canonique en mg/dL. Une créatininémie de
1 mmol/L en sortait à 18,0182 mg/dL au lieu de 11,312 — **59 % d'erreur sur un
marqueur rénal, dans les bornes physiologiques, donc silencieuse.** Même mécanisme
pour l'HbA1c : `("mmol/mol", "%")` dans une table globale devenait applicable à
`oxygen_saturation`, canonique en `%` elle aussi.

**Règle** : n'ajoute dans `DIMENSIONAL_CONVERSIONS` que ce qui est une propriété de
l'unité. Toute formule dépendant de la substance mesurée (masse molaire, équation
de calibration clinique) va dans `analyte_conversions` de **sa** métrique. Deux
tests verrouillent la règle : `test_la_table_dimensionnelle_ne_contient_aucune_conversion_d_analyte`
et `test_perimetre_des_conversions_d_analyte_est_verrouille`.

HbA1c en mmol/mol suit l'équation maîtresse NGSP : `% = 0,09148 × mmol/mol + 2,152`
(affine, pas un simple facteur).

## Tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-biomed.txt
export BIOMED_PSEUDONYM_HMAC_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
pytest -q          # 119 tests
```

Trois **témoins de régression** — chacun échoue sur le code d'avant, et c'est leur
raison d'être : une suite qui ne peut pas rougir ne prouve rien.

```bash
pytest -q -k "force_brute or course or contamine or contrat_detecte"
```

* `test_force_brute_sur_identifiants_sequentiels_echoue` — reproduit d'abord la
  réversibilité de l'ancien schéma, puis vérifie que le HMAC résiste au même
  balayage à troncature égale ;
* `test_sink_atomique_ferme_la_course` — 5 requêtes concurrentes → 1 `ACCEPTED`,
  4 `DUPLICATE`, 1 ligne. Son miroir `test_le_contrat_detecte_un_sink_non_atomique`
  prouve que le contrat sait échouer (sink sans contrainte → 5 lignes) ;
* `test_conversion_du_glucose_ne_contamine_pas_une_autre_metrique_en_mg_dl` — la
  créatinine (locale au test, le catalogue n'est pas élargi) doit être **refusée**,
  pas convertie avec le facteur du glucose.

## Fichiers

| | |
|---|---|
| `biomed_engine.py` | le moteur — catalogue, schémas, mappeurs FHIR, ingestion |
| `test_biomed_engine.py` | 119 tests, dont le contrat de conformité du sink |
| `requirements-biomed.txt` | `fhir.resources` + `pydantic`. Rien d'autre |
| `.env.example` | la clé HMAC et sa génération |

`bridge_biomed_fhir.py` (présent sur le VPS) est le **prototype d'origine, remplacé
par ce module** — il n'est pas versionné ici. Il produisait un code LOINC `8867-4`
par défaut (« Heart rate »), donc une glycémie sans code ressortait étiquetée
fréquence cardiaque en `status: final` dans le dossier patient ; il figeait
`status: "final"` et la catégorie `vital-signs`, acceptait `"value": null`, et
déclarait `async def` sans un seul `await`. Ne pas le remettre en service à côté de
ce moteur : ce serait réintroduire un chemin d'ingestion dangereux.
