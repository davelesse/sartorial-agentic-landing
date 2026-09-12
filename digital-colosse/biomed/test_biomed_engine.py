"""Tests du moteur biomédical FHIR — Digital Colosse.

Trois piliers historiques :

* `test_metrique_inconnue_leve_au_lieu_de_retomber_sur_heart_rate` verrouille le
  défaut qui rendait le prototype dangereux ;
* `test_catalogue_verrouille` contrôle les 10 entrées champ par champ — les
  arguments nommés *empêchent* une transposition, ce test la *détecte* si elle
  passait quand même ;
* `test_deux_tenants_meme_source_event_id_ne_se_dedoublonnent_pas` couvre le mode
  de défaillance multi-tenant le plus vicieux : une perte de donnée patient
  silencieuse.

Trois TÉMOINS DE RÉGRESSION ajoutés après revue. Chacun échoue sur le code
d'avant — c'est leur raison d'être, une suite verte qui ne peut pas rougir ne
prouve rien :

* `test_force_brute_sur_identifiants_sequentiels_echoue` — l'empreinte de journal
  était un SHA-256 nu tronqué, donc réversible en 12 345 essais ;
* `test_sink_atomique_ferme_la_course` + `test_le_contrat_detecte_un_sink_non_atomique`
  — `exists()` puis `store()` laissait passer 5 doublons sur 5 requêtes ;
* `test_conversion_du_glucose_ne_contamine_pas_une_autre_metrique_en_mg_dl` — le
  facteur molaire du glucose s'appliquait à toute métrique canonique en mg/dL.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from biomed_engine import (
    BIOMED_HMAC_KEY_ENV,
    BLOOD_PRESSURE_KEY,
    CATEGORY_LABORATORY,
    DIMENSIONAL_CONVERSIONS,
    METRICS,
    TENANT_TAG_SYSTEM,
    BiomarkerReading,
    BiomedBridgeError,
    BloodPressureReading,
    ImplausibleValueError,
    IngestStatus,
    MetricDefinition,
    PseudonymizationKeyError,
    Pseudonymizer,
    StoreOutcome,
    TenantMismatchError,
    UnitMismatchError,
    UnknownMetricError,
    build_identifier_value,
    ingest_batch,
    ingest_reading,
    normalize_to_canonical_unit,
    pseudonymizer_from_env,
    tenant_identifier_system,
    to_fhir_blood_pressure,
    to_fhir_observation,
)

BASE_SYSTEM = "https://colosse.example/fhir/observation-id"
TENANT_A = "clinique-lyon"
TENANT_B = "cabinet-nantes"

#: Clé de test. Fixe et sans valeur en production — ne jamais réutiliser ailleurs.
CLE_TEST = bytes.fromhex("a1" * 32)
CLE_AUTRE = bytes.fromhex("b2" * 32)

PSEUDO = Pseudonymizer(CLE_TEST)


@pytest.fixture
def measured_at() -> datetime:
    """Horodatage passé — un horodatage figé finirait par tomber dans le futur."""
    return datetime.now(timezone.utc) - timedelta(minutes=10)


def make_reading(measured_at: datetime, **overrides) -> BiomarkerReading:
    payload = {
        "tenant_id": TENANT_A,
        "metric_key": "heart_rate",
        "value": Decimal("72"),
        "unit": "bpm",
        "measured_at": measured_at,
        "patient_ref": "Patient/12345",
        "source_event_id": "sensor-7:1739283",
    }
    payload.update(overrides)
    return BiomarkerReading(**payload)


def make_bp(measured_at: datetime, **overrides) -> BloodPressureReading:
    payload = {
        "tenant_id": TENANT_A,
        "systolic": Decimal("128"),
        "diastolic": Decimal("82"),
        "measured_at": measured_at,
        "patient_ref": "Patient/12345",
        "source_event_id": "bp-1",
    }
    payload.update(overrides)
    return BloodPressureReading(**payload)


def obs_of(reading) -> object:
    mapper = (
        to_fhir_blood_pressure
        if isinstance(reading, BloodPressureReading)
        else to_fhir_observation
    )
    return mapper(reading, identifier_base_system=BASE_SYSTEM)


# ── 0. Verrouillage du catalogue ────────────────────────────────────

#: Table de référence indépendante du code. Une transposition dans METRICS ne
#: peut passer qu'en étant commise ici à l'identique — bien moins probable.
CATALOGUE_ATTENDU = {
    "heart_rate": ("8867-4", "/min", "vital-signs"),
    "respiratory_rate": ("9279-1", "/min", "vital-signs"),
    "oxygen_saturation": ("59408-5", "%", "vital-signs"),
    "body_temperature": ("8310-5", "Cel", "vital-signs"),
    "systolic_blood_pressure": ("8480-6", "mm[Hg]", "vital-signs"),
    "diastolic_blood_pressure": ("8462-4", "mm[Hg]", "vital-signs"),
    "body_weight": ("29463-7", "kg", "vital-signs"),
    "body_height": ("8302-2", "cm", "vital-signs"),
    "blood_glucose": ("2339-0", "mg/dL", "laboratory"),
    "hba1c": ("4548-4", "%", "laboratory"),
}

#: Verrou sur le PÉRIMÈTRE des conversions dépendantes de l'analyte. Ajouter une
#: telle conversion à une métrique fait échouer ce test : l'auteur doit venir ici
#: et se demander explicitement si la formule appartient bien à cet analyte.
CONVERSIONS_ANALYTE_ATTENDUES = {
    "blood_glucose": {"mmol/L", "mmol/l"},
    "hba1c": {"mmol/mol"},
}

#: Unités dont la conversion dépend TOUJOURS de la substance mesurée (masse
#: molaire, calibration clinique). Aucune n'a le droit de figurer dans la table
#: dimensionnelle globale — c'est exactement le défaut qu'on a refermé.
UNITES_DEPENDANTES_DE_L_ANALYTE = {
    "mmol/L",
    "mmol/l",
    "mmol/mol",
    "µmol/L",
    "umol/L",
    "mg/dL",
    "mg/dl",
    "mg/L",
    "g/L",
}


def test_catalogue_complet():
    assert set(METRICS) == set(CATALOGUE_ATTENDU)


@pytest.mark.parametrize("key", sorted(CATALOGUE_ATTENDU))
def test_catalogue_verrouille(key):
    """Attrape toute transposition future de champs dans METRICS."""
    loinc, ucum, category = CATALOGUE_ATTENDU[key]
    metric = METRICS[key]

    assert metric.key == key
    assert metric.loinc_code == loinc
    assert metric.ucum_code == ucum
    assert metric.category == category
    # Bornes cohérentes : une inversion min/max rejetterait toute mesure.
    assert metric.plausible_min < metric.plausible_max
    assert metric.ucum_code == metric.ucum_code.strip()


def test_blood_pressure_nest_pas_une_entree_du_catalogue():
    """Sinon le routage de `ingest_reading` deviendrait ambigu, en silence."""
    assert BLOOD_PRESSURE_KEY not in METRICS


def test_perimetre_des_conversions_d_analyte_est_verrouille():
    """Une conversion d'analyte ajoutée ailleurs doit faire échouer un test.

    C'est le garde-fou du défaut de conception : la formule IFCC appartient à
    l'HbA1c, le facteur 18,0182 au glucose. Aucun des deux n'est une propriété
    d'une unité, donc aucun ne peut être global.
    """
    reel = {
        key: set(metric.analyte_conversions)
        for key, metric in METRICS.items()
        if metric.analyte_conversions
    }
    assert reel == CONVERSIONS_ANALYTE_ATTENDUES


@pytest.mark.parametrize("key", sorted(CATALOGUE_ATTENDU))
def test_conversions_d_analyte_sont_bien_scopees(key):
    metric = METRICS[key]
    for recue in metric.analyte_conversions:
        # Une conversion vers sa propre unité canonique (ou un alias) serait du
        # code mort : l'étape 1 de normalize_to_canonical_unit gagne toujours.
        assert recue != metric.ucum_code
        assert recue not in metric.unit_aliases
        # Et un recouvrement avec la table dimensionnelle rendrait la résolution
        # ambiguë pour le lecteur, même si l'ordre la tranche.
        assert (recue, metric.ucum_code) not in DIMENSIONAL_CONVERSIONS


def test_la_table_dimensionnelle_ne_contient_aucune_conversion_d_analyte():
    """LE verrou du défaut de conception.

    Une entrée molaire ici serait applicable à TOUTE métrique partageant l'unité
    canonique — c'est ainsi qu'une créatininémie sortait avec le facteur du
    glucose, et qu'une saturation en oxygène aurait pu sortir avec la formule de
    l'HbA1c.
    """
    for recue, canonique in DIMENSIONAL_CONVERSIONS:
        assert recue not in UNITES_DEPENDANTES_DE_L_ANALYTE, (
            f"'{recue}' dépend de l'analyte : sa conversion appartient à "
            "analyte_conversions d'une métrique, pas à la table globale"
        )
        assert canonique not in UNITES_DEPENDANTES_DE_L_ANALYTE


def test_les_conversions_d_analyte_sont_immuables():
    """`frozen=True` protège la référence, pas le dict qu'elle désigne."""
    with pytest.raises(TypeError):
        METRICS["hba1c"].analyte_conversions["mmol/L"] = lambda v: v


# ── 1. ISOLATION MULTI-TENANT ───────────────────────────────────────


def test_tenant_id_est_obligatoire(measured_at):
    payload = {
        "metric_key": "heart_rate",
        "value": Decimal("72"),
        "unit": "bpm",
        "measured_at": measured_at,
        "patient_ref": "Patient/12345",
        "source_event_id": "e1",
    }
    with pytest.raises(ValidationError):
        BiomarkerReading(**payload)


@pytest.mark.parametrize(
    "bad_tenant",
    ["", "a/tenant/b", "avec espace", "a" * 65, "tenant:1", "../autre", "a\nb"],
    ids=repr,
)
def test_tenant_id_malforme_est_rejete(measured_at, bad_tenant):
    """Un « / » permettrait de forger le namespace d'un autre tenant."""
    with pytest.raises(ValidationError):
        make_reading(measured_at, tenant_id=bad_tenant)


def test_injection_de_namespace_par_le_tenant_id_est_impossible():
    """`a/tenant/b` se résoudrait sinon dans l'espace de nommage du tenant `b`."""
    with pytest.raises(ValueError):
        tenant_identifier_system(BASE_SYSTEM, f"x/tenant/{TENANT_B}")


def test_espace_de_nommage_est_scope_par_tenant():
    a = tenant_identifier_system(BASE_SYSTEM, TENANT_A)
    b = tenant_identifier_system(BASE_SYSTEM, TENANT_B)

    assert a != b
    assert a.endswith(f"/tenant/{TENANT_A}")
    # Idempotent sur une racine avec ou sans slash final.
    assert tenant_identifier_system(BASE_SYSTEM + "/", TENANT_A) == a


def test_deux_tenants_meme_source_event_id_ne_se_dedoublonnent_pas(measured_at):
    """LE test multi-tenant.

    Sans portée tenant, deux établissements ayant le même `source_event_id`
    produisent le MÊME identifiant métier : le contrôle de doublon jette la
    mesure du second. Perte de donnée patient, silencieuse.
    """
    a = obs_of(make_reading(measured_at, tenant_id=TENANT_A, source_event_id="evt-1"))
    b = obs_of(make_reading(measured_at, tenant_id=TENANT_B, source_event_id="evt-1"))

    assert a.identifier[0].value != b.identifier[0].value
    assert a.identifier[0].system != b.identifier[0].system


def test_tenant_present_dans_la_valeur_et_dans_le_systeme(measured_at):
    """Ceinture et bretelles : un sink n'indexant que la valeur reste isolé."""
    obs = obs_of(make_reading(measured_at))

    assert obs.identifier[0].value.startswith(f"{TENANT_A}|")
    assert TENANT_A in obs.identifier[0].system
    assert build_identifier_value(TENANT_A, "heart_rate", "e1") == (
        f"{TENANT_A}|heart_rate|e1"
    )


def test_la_ressource_porte_un_tag_de_tenant(measured_at):
    """Rend l'appartenance lisible sur la ressource elle-même, pour l'audit."""
    obs = obs_of(make_reading(measured_at))
    tags = {(t.system, t.code) for t in obs.meta.tag}

    assert (TENANT_TAG_SYSTEM, TENANT_A) in tags


def test_tag_de_tenant_et_profil_coexistent(measured_at):
    """`meta` porte les deux : un tag ne doit pas écraser le profil revendiqué."""
    vital = obs_of(make_reading(measured_at))
    labo = obs_of(
        make_reading(
            measured_at, metric_key="blood_glucose", value=Decimal("95"), unit="mg/dL"
        )
    )
    bp = obs_of(make_bp(measured_at))

    assert vital.meta.profile == ["http://hl7.org/fhir/StructureDefinition/vitalsigns"]
    assert vital.meta.tag[0].code == TENANT_A
    # Aucun profil de base standard pour le laboratoire en R4 — mais le tag reste.
    assert labo.meta.profile is None
    assert labo.meta.tag[0].code == TENANT_A
    assert bp.meta.profile == ["http://hl7.org/fhir/StructureDefinition/bp"]
    assert bp.meta.tag[0].code == TENANT_A


def test_pseudonymisation_est_scopee_par_tenant():
    """Le même identifiant patient chez deux tenants désigne deux personnes."""
    a = PSEUDO.of_patient(TENANT_A, "Patient/12345")
    b = PSEUDO.of_patient(TENANT_B, "Patient/12345")
    assert a != b


def test_la_tension_est_aussi_scopee(measured_at):
    a = obs_of(make_bp(measured_at, tenant_id=TENANT_A, source_event_id="bp-x"))
    b = obs_of(make_bp(measured_at, tenant_id=TENANT_B, source_event_id="bp-x"))

    assert a.identifier[0].value == f"{TENANT_A}|blood_pressure|bp-x"
    assert b.identifier[0].value == f"{TENANT_B}|blood_pressure|bp-x"


# ── 2. Le chemin nominal produit une ressource conforme ─────────────


def test_mesure_valide_produit_une_observation_complete(measured_at):
    obs = obs_of(make_reading(measured_at, device_ref="Device/oximeter-7"))

    assert obs.get_resource_type() == "Observation"
    assert obs.code.coding[0].code == "8867-4"
    assert obs.code.coding[0].system == "http://loinc.org"

    # Les quatre éléments absents du prototype.
    assert obs.subject.reference == "Patient/12345"
    assert obs.effectiveDateTime is not None
    assert obs.issued is not None
    assert obs.identifier[0].value == f"{TENANT_A}|heart_rate|sensor-7:1739283"

    assert obs.device.reference == "Device/oximeter-7"


def test_quantite_porte_le_code_ucum_et_pas_seulement_le_libelle(measured_at):
    """Le prototype ne remplissait que `unit`, avec une chaîne qui n'est pas de l'UCUM."""
    obs = obs_of(make_reading(measured_at))

    assert obs.valueQuantity.code == "/min"  # lisible par machine
    assert obs.valueQuantity.unit == "beats/minute"  # libellé d'affichage
    assert obs.valueQuantity.system == "http://unitsofmeasure.org"
    assert obs.valueQuantity.value == Decimal("72")


def test_status_preliminary_par_defaut_final_sur_demande(measured_at):
    """Un flux capteur brut n'est pas « final ». Le prototype figeait « final »."""
    assert obs_of(make_reading(measured_at)).status == "preliminary"
    assert obs_of(make_reading(measured_at, final=True)).status == "final"


def test_categorie_decoule_du_code_loinc(measured_at):
    """Le prototype figeait « vital-signs », y compris pour un marqueur de labo."""
    vital = obs_of(make_reading(measured_at))
    labo = obs_of(
        make_reading(
            measured_at, metric_key="blood_glucose", value=Decimal("95"), unit="mg/dL"
        )
    )

    assert vital.category[0].coding[0].code == "vital-signs"
    assert labo.category[0].coding[0].code == "laboratory"
    assert labo.code.coding[0].code == "2339-0"


# ── 3. Métrique inconnue : jamais de repli ──────────────────────────


def test_metrique_inconnue_leve_au_lieu_de_retomber_sur_heart_rate(measured_at):
    """LE test qui compte.

    Le prototype, faute de `loinc_code`, produisait « Heart rate » en
    « beats/minute » : une glycémie ressortait étiquetée fréquence cardiaque,
    en `status: final`, dans le dossier patient.
    """
    reading = make_reading(
        measured_at,
        metric_key="glycemie_capillaire",
        value=Decimal("5.4"),
        unit="mmol/L",
    )

    with pytest.raises(UnknownMetricError) as exc:
        obs_of(reading)

    assert exc.value.metric_key == "glycemie_capillaire"
    assert "Heart rate" not in str(exc.value)


# ── 4. Valeur absente ou invalide ───────────────────────────────────


@pytest.mark.parametrize(
    "bad_value", [None, "", "abcd", float("nan"), float("inf")], ids=repr
)
def test_valeur_absente_ou_non_numerique_est_rejetee(measured_at, bad_value):
    """`payload.get("value")` du prototype produisait `"value": null` en `status: final`."""
    with pytest.raises(ValidationError):
        make_reading(measured_at, value=bad_value)


def test_cle_inconnue_dans_le_payload_est_rejetee(measured_at):
    """`extra="forbid"` : une faute de frappe ne passe plus en silence."""
    with pytest.raises(ValidationError):
        make_reading(measured_at, loinc_code="8867-4")


def test_horodatage_naif_est_rejete(measured_at):
    with pytest.raises(ValidationError):
        make_reading(measured_at.replace(tzinfo=None))


def test_horodatage_dans_le_futur_est_rejete():
    with pytest.raises(ValidationError):
        make_reading(datetime.now(timezone.utc) + timedelta(hours=2))


def test_reference_patient_malformee_est_rejetee(measured_at):
    with pytest.raises(ValidationError):
        make_reading(measured_at, patient_ref="12345")


def test_performer_accepte_les_cinq_types_et_rejette_les_autres(measured_at):
    for ref in (
        "Practitioner/p1",
        "PractitionerRole/pr1",
        "Organization/o1",
        "Patient/12345",
        "RelatedPerson/r1",
    ):
        assert make_reading(measured_at, performer_ref=ref).performer_ref == ref

    with pytest.raises(ValidationError):
        make_reading(measured_at, performer_ref="Device/d1")


# ── 5. Cohérence des unités ─────────────────────────────────────────


def test_unite_incoherente_avec_le_code_loinc_est_rejetee(measured_at):
    """Une fréquence cardiaque en mmHg n'a aucun sens — on refuse."""
    with pytest.raises(UnitMismatchError) as exc:
        obs_of(make_reading(measured_at, unit="mm[Hg]"))
    assert exc.value.expected == "/min"


def test_alias_d_unite_accepte_sans_conversion(measured_at):
    for alias in ("bpm", "/min", "beats/minute"):
        obs = obs_of(make_reading(measured_at, unit=alias))
        assert obs.valueQuantity.value == Decimal("72")
        assert obs.valueQuantity.code == "/min"


def test_conversion_dimensionnelle_est_appliquee(measured_at):
    """98.6 °F → 37 °C. Une conversion non déclarée serait refusée, pas devinée."""
    obs = obs_of(
        make_reading(
            measured_at,
            metric_key="body_temperature",
            value=Decimal("98.6"),
            unit="[degF]",
        )
    )
    assert obs.valueQuantity.value == Decimal("37")
    assert obs.valueQuantity.code == "Cel"


def test_conversion_glycemie_mmol_vers_mg(measured_at):
    """5.4 mmol/L → 97.2983 mg/dL (facteur molaire du glucose, 18.0182)."""
    obs = obs_of(
        make_reading(
            measured_at,
            metric_key="blood_glucose",
            value=Decimal("5.4"),
            unit="mmol/L",
        )
    )
    assert obs.valueQuantity.value == Decimal("97.2983")
    assert obs.valueQuantity.code == "mg/dL"


@pytest.mark.parametrize(
    ("metric_key", "unit"),
    [
        ("blood_glucose", "g/L"),  # plausible, mais non déclarée
        ("oxygen_saturation", "mmol/mol"),  # déclarée, mais sur une AUTRE métrique
        ("heart_rate", "mmol/L"),
        ("body_weight", "[degF]"),  # dimension incompatible
    ],
)
def test_conversion_non_declaree_est_refusee(measured_at, metric_key, unit):
    """Hors table, une conversion ne se devine jamais — elle se déclare."""
    with pytest.raises(UnitMismatchError):
        normalize_to_canonical_unit(METRICS[metric_key], Decimal("1"), unit)


# ── 5bis. Le défaut de conception : conversions scopées par métrique ─
#
# UNIT_CONVERSIONS était indexée (unité reçue, unité canonique), SANS la
# métrique. Le facteur 18,0182 mmol/L → mg/dL est la masse molaire du glucose ;
# indexé ainsi, il s'appliquait à toute métrique canonique en mg/dL.

#: Créatinine sérique — LOCALE AU TEST, délibérément. Le catalogue livré n'est
#: pas élargi : on veut prouver la propriété, pas prendre position sur le
#: périmètre clinique de Digital Colosse.
CREATININE_DE_TEST = MetricDefinition(
    key="serum_creatinine",
    loinc_code="2160-0",
    display="Creatinine [Mass/volume] in Serum or Plasma",
    ucum_code="mg/dL",
    ucum_display="mg/dL",
    category=CATEGORY_LABORATORY,
    plausible_min=Decimal("0.1"),
    plausible_max=Decimal("20"),
    # Aucune analyte_conversions : cette métrique ne DÉCLARE pas savoir convertir
    # depuis mmol/L. Le bon facteur serait 11,312 (masse molaire 113,12 g/mol).
)


def test_conversion_du_glucose_ne_contamine_pas_une_autre_metrique_en_mg_dl():
    """TÉMOIN DE RÉGRESSION — le défaut le plus grave des quatre.

    Avec la table globale, `1 mmol/L` de créatinine ressortait à 18,0182 mg/dL
    au lieu de 11,312 : 59 % d'erreur sur un marqueur rénal, et le résultat
    tombait dans les bornes physiologiques, donc sans aucun signal.

    Le comportement correct est le refus : la métrique ne déclare pas cette
    conversion, donc on ne la devine pas.
    """
    with pytest.raises(UnitMismatchError) as exc:
        normalize_to_canonical_unit(CREATININE_DE_TEST, Decimal("1"), "mmol/L")

    assert exc.value.metric_key == "serum_creatinine"
    assert exc.value.received == "mmol/L"


def test_conversion_hba1c_ifcc():
    """HbA1c en mmol/mol (unité IFCC, courante en Europe).

    Équation maîtresse NGSP : % = 0,09148 × mmol/mol + 2,152. Affine, pas un
    simple facteur. 53 mmol/mol ≈ 7,0 % ; 48 ≈ 6,5 %.
    """
    hba1c = METRICS["hba1c"]
    assert normalize_to_canonical_unit(hba1c, Decimal("53"), "mmol/mol") == Decimal(
        "7.0004"
    )
    assert normalize_to_canonical_unit(hba1c, Decimal("48"), "mmol/mol") == Decimal(
        "6.543"
    )


def test_conversion_hba1c_ne_contamine_pas_la_saturation():
    """L'autre moitié du même défaut.

    `oxygen_saturation` est canonique en « % », comme l'HbA1c. Dans une table
    globale, ajouter ("mmol/mol", "%") pour l'HbA1c aurait rendu la formule IFCC
    applicable à une saturation.

    Sur cette métrique-là, les bornes 50–100 rattraperaient les valeurs
    réalistes (53 mmol/mol ressort à 7 %, hors bornes). Mais s'en remettre aux
    bornes n'est pas une défense : la même contamination sur la créatinine
    produit 18,0182 mg/dL *dans* les bornes, donc sans aucun signal. Ce qu'on
    refuse ici, c'est le mécanisme — pas seulement ses cas visibles.
    """
    # Déclarée sur hba1c : convertit.
    assert normalize_to_canonical_unit(
        METRICS["hba1c"], Decimal("53"), "mmol/mol"
    ) == Decimal("7.0004")

    # Même unité, autre métrique canonique en « % » : refusée.
    with pytest.raises(UnitMismatchError):
        normalize_to_canonical_unit(
            METRICS["oxygen_saturation"], Decimal("53"), "mmol/mol"
        )


def test_les_conversions_dimensionnelles_restent_partagees():
    """La séparation ne doit pas casser ce qui était légitimement global.

    Une livre pèse 0,45359237 kg quel que soit l'objet pesé : cette conversion
    est une propriété de l'unité, elle reste partageable par toute métrique
    canonique en kg.
    """
    assert normalize_to_canonical_unit(
        METRICS["body_weight"], Decimal("100"), "lb"
    ) == Decimal("45.3592")
    assert normalize_to_canonical_unit(
        METRICS["body_height"], Decimal("1.75"), "m"
    ) == Decimal("175")


# ── 6. Bornes physiologiques ────────────────────────────────────────


@pytest.mark.parametrize("value", [Decimal("9000"), Decimal("0"), Decimal("-5")])
def test_valeur_hors_bornes_physiologiques_est_rejetee(measured_at, value):
    """Le prototype émettait une fréquence cardiaque à 9000 en « final »."""
    with pytest.raises(ImplausibleValueError):
        obs_of(make_reading(measured_at, value=value))


def test_bornes_verifiees_apres_conversion(measured_at):
    """200 °F = 93 °C : la borne s'applique à la valeur canonique, pas à la brute."""
    with pytest.raises(ImplausibleValueError):
        obs_of(
            make_reading(
                measured_at,
                metric_key="body_temperature",
                value=Decimal("200"),
                unit="[degF]",
            )
        )


# ── 7. Idempotence ──────────────────────────────────────────────────


def test_meme_source_event_id_produit_le_meme_identifier(measured_at):
    """Les flux redélivrent : sans identifiant stable, on crée des doublons."""
    first = obs_of(make_reading(measured_at))
    second = obs_of(make_reading(measured_at))

    assert first.identifier[0].value == second.identifier[0].value
    assert first.identifier[0].system == tenant_identifier_system(
        BASE_SYSTEM, TENANT_A
    )


def test_evenements_distincts_produisent_des_identifiers_distincts(measured_at):
    first = obs_of(make_reading(measured_at))
    second = obs_of(make_reading(measured_at, source_event_id="sensor-7:1739284"))
    assert first.identifier[0].value != second.identifier[0].value


# ── 8. Tension artérielle : un panel, pas deux ressources ───────────


def test_tension_produit_un_panel_a_deux_composants(measured_at):
    obs = obs_of(make_bp(measured_at))

    assert obs.code.coding[0].code == "85354-9"
    assert obs.valueQuantity is None  # la valeur est dans les composants
    assert [c.code.coding[0].code for c in obs.component] == ["8480-6", "8462-4"]
    assert [c.valueQuantity.value for c in obs.component] == [
        Decimal("128"),
        Decimal("82"),
    ]
    assert all(c.valueQuantity.code == "mm[Hg]" for c in obs.component)


def test_tension_inversee_est_rejetee(measured_at):
    with pytest.raises(ValidationError):
        make_bp(measured_at, systolic=Decimal("82"), diastolic=Decimal("128"))


def test_tension_egale_est_rejetee(measured_at):
    """Strictement inférieure : 120/120 est un brassard en panne."""
    with pytest.raises(ValidationError):
        make_bp(measured_at, systolic=Decimal("120"), diastolic=Decimal("120"))


def test_le_controle_diastolique_est_un_validateur_de_modele():
    """La règle porte sur DEUX champs — elle appartient donc au modèle.

    En `field_validator("diastolic")` lisant `info.data["systolic"]`, elle ne
    fonctionnait que parce que `systolic` est déclarée avant `diastolic` :
    `info.data` ne contient que les champs déjà validés. Réordonner les deux
    lignes désactivait le contrôle en silence. Ce test verrouille la forme.
    """
    decorateurs = BloodPressureReading.__pydantic_decorators__

    assert "_diastolic_below_systolic" in decorateurs.model_validators
    assert "_diastolic_below_systolic" not in decorateurs.field_validators


def test_systolique_invalide_ne_produit_quune_erreur_claire(measured_at):
    """Avec `mode="after"`, le validateur inter-champs ne tourne pas si un champ
    a déjà échoué — pas de seconde erreur trompeuse par-dessus la vraie."""
    with pytest.raises(ValidationError) as exc:
        make_bp(measured_at, systolic=float("nan"))

    champs = {".".join(str(p) for p in e["loc"]) for e in exc.value.errors()}
    assert champs == {"systolic"}


def test_tension_hors_bornes_est_rejetee(measured_at):
    with pytest.raises(ImplausibleValueError):
        obs_of(make_bp(measured_at, systolic=Decimal("900"), diastolic=Decimal("500")))


def test_metric_key_de_la_tension_est_verrouille(measured_at):
    """`Literal` : la clé de routage ne peut pas être détournée."""
    with pytest.raises(ValidationError):
        make_bp(measured_at, metric_key="heart_rate")


# ── 9. Pseudonymisation des journaux (HMAC à clé serveur) ───────────


def test_force_brute_sur_identifiants_sequentiels_echoue():
    """TÉMOIN DE RÉGRESSION — l'empreinte de journal était réversible.

    Les identifiants patients sont souvent séquentiels. Sur un SHA-256 nu, il
    suffisait de balayer `Patient/1`… pour reconstruire la table de
    correspondance : `Patient/12345` retrouvé en 12 345 essais, quelques
    centièmes de seconde. Préfixer par le tenant n'y changeait rien, le
    tenant_id étant journalisé en clair sur la même ligne.
    """
    cible = "Patient/12345"
    empreinte = PSEUDO.of_patient(TENANT_A, cible)
    candidats = [f"Patient/{i}" for i in range(1, 20_001)]

    # 1. L'ANCIEN schéma cède — c'est la reproduction du défaut.
    def hash_nu(ref: str, longueur: int) -> str:
        return hashlib.sha256(f"{TENANT_A}|{ref}".encode("utf-8")).hexdigest()[
            :longueur
        ]

    table_ancienne = {hash_nu(ref, 12): ref for ref in candidats}
    assert table_ancienne.get(hash_nu(cible, 12)) == cible

    # 2. Le HMAC résiste au MÊME balayage, à troncature égale, parce que
    #    l'attaquant n'a pas la clé.
    assert empreinte not in {hash_nu(ref, 16) for ref in candidats}

    cle_devinee = Pseudonymizer(CLE_AUTRE)
    assert empreinte not in {
        cle_devinee.of_patient(TENANT_A, ref) for ref in candidats
    }


def test_empreinte_est_deterministe_sous_une_meme_cle():
    """Propriété à conserver : corréler deux lignes de journal reste possible."""
    autre_instance = Pseudonymizer(CLE_TEST)
    assert PSEUDO.of_patient(TENANT_A, "Patient/12345") == autre_instance.of_patient(
        TENANT_A, "Patient/12345"
    )
    assert PSEUDO.of_patient(TENANT_A, "Patient/12345") != PSEUDO.of_patient(
        TENANT_A, "Patient/54321"
    )


def test_deux_cles_donnent_deux_empreintes():
    """Corollaire : une rotation de clé rend les anciens journaux non corrélables.

    C'est assumé — les empreintes ne sont pas censées survivre à une rotation.
    """
    assert PSEUDO.of_patient(TENANT_A, "Patient/12345") != Pseudonymizer(
        CLE_AUTRE
    ).of_patient(TENANT_A, "Patient/12345")


def test_les_logs_ne_contiennent_pas_la_reference_patient_en_clair():
    empreinte = PSEUDO.of_patient(TENANT_A, "Patient/12345")

    assert "Patient" not in empreinte
    assert "Patient/12345" not in empreinte
    # Hexadécimal de longueur fixe : rien de la référence ne transparaît, et la
    # longueur ne varie pas avec celle de l'identifiant d'origine.
    assert len(empreinte) == 16
    assert set(empreinte) <= set("0123456789abcdef")
    assert len(PSEUDO.of_patient(TENANT_A, "Patient/1")) == len(
        PSEUDO.of_patient(TENANT_A, "Patient/" + "9" * 60)
    )


def test_le_pseudonymizer_ne_divulgue_pas_sa_cle():
    """Le `__repr__` généré par défaut imprimerait la clé dans toute trace
    d'exception — donc dans les journaux qu'elle est censée protéger."""
    cle_hex = CLE_TEST.hex()

    for rendu in (repr(PSEUDO), str(PSEUDO), f"{PSEUDO}", f"{PSEUDO!r}"):
        assert cle_hex not in rendu
        assert "a1a1" not in rendu
        assert rendu == "Pseudonymizer(key=<redacted>)"


@pytest.mark.parametrize("octets", [0, 1, 16, 31])
def test_cle_trop_courte_est_refusee(octets):
    with pytest.raises(PseudonymizationKeyError):
        Pseudonymizer(b"\x00" * octets)


def test_cle_de_32_octets_est_acceptee():
    assert Pseudonymizer(b"\x01" * 32).of_patient(TENANT_A, "Patient/1")


def test_clef_non_bytes_est_refusee():
    with pytest.raises(PseudonymizationKeyError):
        Pseudonymizer(CLE_TEST.hex())  # une chaîne hex n'est pas une clé


def test_chargement_depuis_l_environnement(monkeypatch):
    monkeypatch.setenv(BIOMED_HMAC_KEY_ENV, CLE_TEST.hex())
    charge = pseudonymizer_from_env()
    assert charge.of_patient(TENANT_A, "Patient/12345") == PSEUDO.of_patient(
        TENANT_A, "Patient/12345"
    )


@pytest.mark.parametrize(
    "valeur",
    [None, "", "   ", "pas-de-l-hexadecimal", "abc", "a1" * 16],
    ids=["absente", "vide", "espaces", "non-hex", "impaire", "trop-courte"],
)
def test_absence_ou_invalidite_de_cle_echoue_au_demarrage(monkeypatch, valeur):
    """Échec au DÉMARRAGE, jamais de repli sur un hash sans clé.

    Un service de santé qui démarre sans clé journaliserait des empreintes
    réversibles pendant des mois avant que quiconque le remarque.
    """
    if valeur is None:
        monkeypatch.delenv(BIOMED_HMAC_KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(BIOMED_HMAC_KEY_ENV, valeur)

    with pytest.raises(PseudonymizationKeyError) as exc:
        pseudonymizer_from_env()

    # Le message doit nommer la variable — sinon l'exploitant cherche à l'aveugle.
    assert BIOMED_HMAC_KEY_ENV in str(exc.value)


def test_erreur_de_cle_nest_pas_une_erreur_de_donnee():
    """VERROU DE TAXONOMIE, et il compte.

    `ingest_reading` attrape `BiomedBridgeError` et le convertit en REJECTED. Si
    `PseudonymizationKeyError` en héritait, une erreur de configuration y
    tomberait : le système tournerait sans clé et la seule trace serait des
    mesures rejetées sans raison apparente. Exactement le mode de défaillance
    silencieux que ce correctif referme.
    """
    assert not issubclass(PseudonymizationKeyError, BiomedBridgeError)


# ── 10. Couche d'ingestion ──────────────────────────────────────────


class FakeSink:
    """Sink en mémoire conforme au Protocol `ObservationSink`.

    Indexe par (tenant, identifiant) — comme devrait le faire toute
    implémentation réelle.
    """

    def __init__(self) -> None:
        self.stored: dict[tuple[str, str], object] = {}
        self.store_calls = 0
        self.tenants_vus: list[str] = []

    async def exists(
        self, tenant_id: str, identifier_system: str, identifier_value: str
    ) -> bool:
        self.tenants_vus.append(tenant_id)
        return (tenant_id, identifier_value) in self.stored

    async def store(self, tenant_id: str, observation) -> StoreOutcome:
        self.store_calls += 1
        key = (tenant_id, observation.identifier[0].value)
        if key in self.stored:
            return StoreOutcome(created=False, storage_id=f"obs-{self.store_calls}")
        self.stored[key] = observation
        return StoreOutcome(created=True, storage_id=f"obs-{self.store_calls}")


def raw_payload(measured_at: datetime, **overrides) -> dict:
    payload = {
        "metric_key": "heart_rate",
        "value": "72",
        "unit": "bpm",
        "measured_at": measured_at.isoformat(),
        "patient_ref": "Patient/12345",
        "source_event_id": "sensor-7:1739283",
    }
    payload.update(overrides)
    return payload


def raw_bp_payload(measured_at: datetime, **overrides) -> dict:
    payload = {
        "metric_key": "blood_pressure",
        "systolic": "128",
        "diastolic": "82",
        "measured_at": measured_at.isoformat(),
        "patient_ref": "Patient/12345",
        "source_event_id": "bp-9",
    }
    payload.update(overrides)
    return payload


async def ingest(payload, sink, tenant_id=TENANT_A):
    return await ingest_reading(
        payload,
        sink=sink,
        tenant_id=tenant_id,
        pseudonymizer=PSEUDO,
        identifier_base_system=BASE_SYSTEM,
    )


@pytest.mark.asyncio
async def test_ingestion_accepte_puis_dedoublonne(measured_at):
    sink = FakeSink()

    first = await ingest(raw_payload(measured_at), sink)
    second = await ingest(raw_payload(measured_at), sink)

    assert first.status is IngestStatus.ACCEPTED
    assert second.status is IngestStatus.DUPLICATE
    assert sink.store_calls == 1  # la redélivrance n'a rien créé


@pytest.mark.asyncio
async def test_le_sink_rend_un_identifiant_de_stockage(measured_at):
    sink = FakeSink()
    result = await ingest(raw_payload(measured_at), sink)
    assert result.storage_id == "obs-1"


@pytest.mark.asyncio
async def test_ingestion_croisee_entre_tenants_ne_perd_aucune_mesure(measured_at):
    """Même événement, deux établissements : les deux doivent être persistées."""
    sink = FakeSink()
    payload = raw_payload(measured_at, source_event_id="collision")

    a = await ingest(payload, sink, tenant_id=TENANT_A)
    b = await ingest(payload, sink, tenant_id=TENANT_B)

    assert a.status is IngestStatus.ACCEPTED
    assert b.status is IngestStatus.ACCEPTED  # PAS un doublon de A
    assert sink.store_calls == 2
    assert a.identifier_value != b.identifier_value


@pytest.mark.asyncio
async def test_le_sink_recoit_toujours_le_tenant(measured_at):
    sink = FakeSink()
    await ingest(raw_payload(measured_at), sink, tenant_id=TENANT_B)

    assert sink.tenants_vus == [TENANT_B]
    assert list(sink.stored)[0][0] == TENANT_B


@pytest.mark.asyncio
async def test_tenant_du_payload_divergent_est_rejete(measured_at):
    """Capteur mal configuré, file mal routée, ou écriture inter-tenants."""
    sink = FakeSink()

    result = await ingest(
        raw_payload(measured_at, tenant_id=TENANT_B), sink, tenant_id=TENANT_A
    )

    assert result.status is IngestStatus.REJECTED
    assert result.error_type == TenantMismatchError.__name__
    assert result.tenant_id == TENANT_A
    assert sink.store_calls == 0


@pytest.mark.asyncio
async def test_tenant_du_payload_concordant_est_accepte(measured_at):
    sink = FakeSink()
    result = await ingest(
        raw_payload(measured_at, tenant_id=TENANT_A), sink, tenant_id=TENANT_A
    )
    assert result.status is IngestStatus.ACCEPTED


@pytest.mark.asyncio
async def test_payload_sans_tenant_herite_de_celui_de_l_appelant(measured_at):
    """Cas nominal : le capteur ne déclare rien, le worker sait où il est."""
    sink = FakeSink()
    result = await ingest(raw_payload(measured_at), sink, tenant_id=TENANT_B)

    assert result.status is IngestStatus.ACCEPTED
    assert result.observation.meta.tag[0].code == TENANT_B


@pytest.mark.asyncio
async def test_ingestion_de_la_tension_passe_par_le_meme_chemin(measured_at):
    """La tension entre par le flux, avec les mêmes garanties."""
    sink = FakeSink()

    first = await ingest(raw_bp_payload(measured_at), sink)
    second = await ingest(raw_bp_payload(measured_at), sink)

    assert first.status is IngestStatus.ACCEPTED
    assert first.identifier_value == f"{TENANT_A}|blood_pressure|bp-9"
    assert first.observation.code.coding[0].code == "85354-9"
    assert len(first.observation.component) == 2
    assert second.status is IngestStatus.DUPLICATE
    assert sink.store_calls == 1


@pytest.mark.asyncio
async def test_tension_sans_discriminant_est_rejetee_proprement(measured_at):
    """Sans `metric_key`, le payload part vers BiomarkerReading — rejet explicite."""
    sink = FakeSink()
    payload = raw_bp_payload(measured_at)
    del payload["metric_key"]

    result = await ingest(payload, sink)

    assert result.status is IngestStatus.REJECTED
    assert result.error_type == "ValidationError"
    assert "BiomarkerReading" in result.reason
    assert sink.store_calls == 0


@pytest.mark.asyncio
async def test_donnee_invalide_est_rejetee_sans_lever(measured_at):
    """Une trame corrompue ne doit pas tuer le consommateur du flux."""
    sink = FakeSink()

    result = await ingest(raw_payload(measured_at, metric_key="inconnue"), sink)

    assert result.status is IngestStatus.REJECTED
    assert result.error_type == "UnknownMetricError"
    assert sink.store_calls == 0


@pytest.mark.asyncio
async def test_tenant_appelant_malforme_est_rejete(measured_at):
    """Le tenant de l'appelant passe par la même validation que les autres."""
    sink = FakeSink()
    result = await ingest(raw_payload(measured_at), sink, tenant_id="a/tenant/b")

    assert result.status is IngestStatus.REJECTED
    assert sink.store_calls == 0


@pytest.mark.asyncio
async def test_panne_du_sink_remonte(measured_at):
    """Une panne d'infra n'est pas une donnée invalide : la file doit réessayer."""

    class BrokenSink(FakeSink):
        async def store(self, tenant_id: str, observation) -> StoreOutcome:
            raise ConnectionError("serveur FHIR injoignable")

    with pytest.raises(ConnectionError):
        await ingest(raw_payload(measured_at), BrokenSink())


@pytest.mark.asyncio
async def test_un_lot_continue_malgre_une_mesure_refusee(measured_at):
    sink = FakeSink()

    results = await ingest_batch(
        [
            raw_payload(measured_at, source_event_id="a"),
            raw_payload(measured_at, source_event_id="b", value="9000"),
            raw_bp_payload(measured_at, source_event_id="c"),
        ],
        sink=sink,
        tenant_id=TENANT_A,
        pseudonymizer=PSEUDO,
        identifier_base_system=BASE_SYSTEM,
    )

    assert [r.status for r in results] == [
        IngestStatus.ACCEPTED,
        IngestStatus.REJECTED,
        IngestStatus.ACCEPTED,
    ]
    assert sink.store_calls == 2
    assert all(r.tenant_id == TENANT_A for r in results)


def test_l_ingestion_exige_un_pseudonymizer(measured_at):
    """Pas de valeur par défaut : on ne peut pas ingérer de la donnée de santé
    sans savoir comment la journaliser sans la divulguer."""
    with pytest.raises(TypeError):
        asyncio.run(
            ingest_reading(  # type: ignore[call-arg]
                raw_payload(measured_at),
                sink=FakeSink(),
                tenant_id=TENANT_A,
            )
        )


# ── 11. CONCURRENCE — la garantie d'unicité vient du sink ───────────
#
# `exists()` puis `store()` est un vérifier-puis-agir. Ce module ne peut pas le
# rendre atomique : il n'a pas de transaction. La garantie appartient donc au
# sink, et ces tests vérifient le CONTRAT — avec, en miroir, la preuve qu'ils
# savent échouer sur un sink qui ne le tient pas.

#: Latence du `store()` simulé. C'est elle qui ouvre la fenêtre de course : sans
#: elle, les coroutines se sérialisent et le bug reste invisible — c'est pour ça
#: que les 72 tests d'origine ne le voyaient pas.
LATENCE_STORE = 0.01


class _SinkAvecLatence:
    """Base commune : compte les lignes RÉELLEMENT écrites, doublons compris."""

    def __init__(self, latence: float = LATENCE_STORE) -> None:
        self.rows: list[tuple[str, str]] = []
        self.store_attempts = 0
        self._latence = latence

    async def exists(
        self, tenant_id: str, identifier_system: str, identifier_value: str
    ) -> bool:
        return (tenant_id, identifier_value) in self.rows


class SinkAtomique(_SinkAvecLatence):
    """Imite une base portant UNIQUE (tenant_id, identifier_system, identifier_value).

    Le verrou tient le rôle de la contrainte : la section critique est
    indivisible, et une deuxième écriture de la même identité ressort
    `created=False` au lieu d'ajouter une ligne.
    """

    def __init__(self, latence: float = LATENCE_STORE) -> None:
        super().__init__(latence)
        self._lock = asyncio.Lock()

    async def store(self, tenant_id: str, observation) -> StoreOutcome:
        self.store_attempts += 1
        key = (tenant_id, observation.identifier[0].value)
        await asyncio.sleep(self._latence)  # la fenêtre de course, grande ouverte
        async with self._lock:  # = la contrainte UNIQUE
            if key in self.rows:
                return StoreOutcome(
                    created=False, storage_id=f"obs-{self.rows.index(key) + 1}"
                )
            self.rows.append(key)
            return StoreOutcome(created=True, storage_id=f"obs-{len(self.rows)}")


class SinkNonAtomique(_SinkAvecLatence):
    """Sink SANS garantie — tel qu'on l'écrit en croyant qu'`exists()` suffit.

    Présent pour que les tests de concurrence puissent échouer. Un test de
    course qui ne sait pas rougir ne prouve rien.
    """

    async def store(self, tenant_id: str, observation) -> StoreOutcome:
        self.store_attempts += 1
        key = (tenant_id, observation.identifier[0].value)
        deja = key in self.rows
        await asyncio.sleep(self._latence)
        self.rows.append(key)  # insère même si déjà présent → doublon en base
        return StoreOutcome(created=not deja, storage_id=f"obs-{len(self.rows)}")


async def assert_sink_honours_uniqueness(
    sink, measured_at: datetime, *, concurrence: int = 5
) -> None:
    """CONTRAT DE CONFORMITÉ réutilisable pour toute implémentation d'ObservationSink.

    Branche-lui le sink SQLAlchemy quand il sera écrit : s'il ne porte pas la
    contrainte UNIQUE de la section 5, cet assert échoue. C'est la recette sans
    la dépendance — ce module ne connaît toujours pas ta couche de persistance.

    Vérifie les trois propriétés qui comptent sous concurrence :
      * exactement une ingestion ACCEPTED ;
      * toutes les autres DUPLICATE (et non REJECTED, ni une exception) ;
      * exactement une ligne en base.
    """
    payload = raw_payload(measured_at, source_event_id="course-1")

    results = await asyncio.gather(
        *(ingest(payload, sink) for _ in range(concurrence))
    )

    statuts = [r.status for r in results]
    acceptees = statuts.count(IngestStatus.ACCEPTED)
    lignes = [r for r in sink.rows if r[1].endswith("course-1")]

    assert acceptees == 1, (
        f"{acceptees} ingestions « accepted » pour la MÊME mesure — le sink ne "
        "porte pas de contrainte d'unicité"
    )
    assert statuts.count(IngestStatus.DUPLICATE) == concurrence - 1, statuts
    assert len(lignes) == 1, (
        f"{len(lignes)} lignes en base pour la même mesure — doublon de donnée "
        "patient"
    )


@pytest.mark.asyncio
async def test_sink_atomique_ferme_la_course(measured_at):
    """TÉMOIN DE RÉGRESSION — 5 requêtes concurrentes, une seule ligne.

    Avant correction, les 5 passaient `exists()` avant que la première ait fini
    de stocker : 5 « accepted » et 5 doublons en base. Le statut vient maintenant
    de `store()`, donc de la contrainte.
    """
    sink = SinkAtomique()
    await assert_sink_honours_uniqueness(sink, measured_at)

    # Les 5 ont bien TENTÉ d'écrire : la course a réellement eu lieu, ce n'est
    # pas `exists()` qui a filtré.
    assert sink.store_attempts == 5


@pytest.mark.asyncio
async def test_le_contrat_detecte_un_sink_non_atomique(measured_at):
    """Le contrat doit savoir rougir, sinon il ne vaut rien.

    Ce sink-ci reproduit le défaut d'origine : 5 « accepted », 5 lignes.
    """
    sink = SinkNonAtomique()

    with pytest.raises(AssertionError):
        await assert_sink_honours_uniqueness(sink, measured_at)

    # Et on constate le dégât exact que la contrainte évite.
    assert len(sink.rows) == 5


@pytest.mark.asyncio
async def test_le_doublon_rattrape_par_le_sink_est_signale_comme_tel(measured_at):
    """`created=False` → DUPLICATE, jamais ACCEPTED.

    Le sink a déjà la ligne mais `exists()` répond non (cas de la course, ou d'un
    sink qui n'implémente pas d'index de lecture). Le statut doit rester juste.
    """

    class SinkQuiMentSurExists(SinkAtomique):
        async def exists(self, tenant_id, identifier_system, identifier_value) -> bool:
            return False  # pire cas : l'optimisation ne filtre jamais rien

    sink = SinkQuiMentSurExists()
    payload = raw_payload(measured_at, source_event_id="menteur")

    first = await ingest(payload, sink)
    second = await ingest(payload, sink)

    assert first.status is IngestStatus.ACCEPTED
    assert second.status is IngestStatus.DUPLICATE
    assert second.storage_id is not None
    assert len(sink.rows) == 1
    assert sink.store_attempts == 2  # les deux ont tenté, la base a tranché


@pytest.mark.asyncio
async def test_la_concurrence_entre_tenants_ne_se_dedoublonne_pas(measured_at):
    """Même `source_event_id`, deux tenants, en parallèle : deux lignes attendues."""
    sink = SinkAtomique()
    payload = raw_payload(measured_at, source_event_id="parallele")

    results = await asyncio.gather(
        *(ingest(payload, sink, tenant_id=TENANT_A) for _ in range(3)),
        *(ingest(payload, sink, tenant_id=TENANT_B) for _ in range(3)),
    )

    acceptees = [r for r in results if r.status is IngestStatus.ACCEPTED]
    assert len(acceptees) == 2
    assert {r.tenant_id for r in acceptees} == {TENANT_A, TENANT_B}
    assert len(sink.rows) == 2


# ── 12. Conformité FHIR de bout en bout ─────────────────────────────


def test_round_trip_fhir_strict_scalaire_et_panel(measured_at):
    """Sérialiser puis revalider : ce qui part sur le réseau doit être conforme."""
    import json

    from fhir.resources.R4B.observation import Observation

    for obs in (
        obs_of(make_reading(measured_at, device_ref="Device/d1")),
        obs_of(make_bp(measured_at)),
    ):
        raw = json.loads(obs.model_dump_json(exclude_none=True))
        Observation.model_validate(raw)
        # Le tag de tenant survit à la sérialisation.
        assert raw["meta"]["tag"][0]["code"] == TENANT_A
