"""
Moteur Biomédical FHIR R4B (Monolithe Unifié) — multi-tenant
Empire Digital Colosse — Ma'at Protocol

Architecture : agnostique (aucun framework web), mappage synchrone,
ingestion asynchrone, Pydantic V2.

Principe directeur : FAIL-CLOSED. Une mesure qu'on ne sait pas interpréter avec
certitude lève une erreur ou ressort en REJECTED. Elle ne retombe jamais sur une
valeur par défaut — c'est ce qui rendait le prototype d'origine dangereux : sans
code LOINC, une glycémie en ressortait étiquetée « Heart rate », en status final,
dans le dossier patient.

ISOLATION MULTI-TENANT — trois mécanismes, détaillés section 0 :
  1. le `tenant_id` vient de l'APPELANT, jamais du payload ;
  2. l'espace de nommage des identifiants est dérivé du tenant ;
  3. le sink reçoit le tenant explicitement, il ne peut pas l'ignorer.

DEUX PROPRIÉTÉS QUE CE MODULE NE PEUT PAS TENIR SEUL, et où il tient donc le
contrat plutôt que l'implémentation :
  * l'UNICITÉ des observations est portée par le sink (section 5, `StoreOutcome`) —
    une contrainte de base de données, pas un `if` en Python ;
  * la CLÉ de pseudonymisation vient de l'hôte (section 5, `Pseudonymizer`) — le
    module ne lit aucune configuration de lui-même.

Implémentation R4B : `fhir.resources` ne publie pas de paquet R4 « pur ». R4B est
la révision corrective de R4 et la ressource Observation y est inchangée.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol, runtime_checkable

from fhir.resources.R4B.observation import Observation
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger("biomed.engine")

__all__ = [
    "BIOMED_HMAC_KEY_ENV",
    "DIMENSIONAL_CONVERSIONS",
    "METRICS",
    "BiomarkerReading",
    "BiomedBridgeError",
    "BloodPressureReading",
    "ImplausibleValueError",
    "IngestResult",
    "IngestStatus",
    "MetricDefinition",
    "ObservationSink",
    "PseudonymizationKeyError",
    "Pseudonymizer",
    "StoreOutcome",
    "TenantMismatchError",
    "UnitMismatchError",
    "UnknownMetricError",
    "build_identifier_value",
    "get_metric",
    "ingest_batch",
    "ingest_reading",
    "pseudonymizer_from_env",
    "tenant_identifier_system",
    "to_fhir_blood_pressure",
    "to_fhir_observation",
]

# ============================================================================
# 0. ISOLATION MULTI-TENANT
# ============================================================================
#
# Sur de la donnée de santé, une fuite inter-tenants n'est pas un bug : c'est une
# violation. Trois mécanismes, chacun couvrant une faille distincte.
#
# ── 1. Le tenant vient de l'appelant, jamais du payload ──────────────────────
# Le worker sait quelle file il draine ; le capteur, lui, n'est pas une source de
# vérité — mal configuré ou compromis, il écrirait chez le voisin. Si le payload
# déclare malgré tout un tenant et qu'il diffère, c'est TenantMismatchError : un
# rejet bruyant, journalisé comme incident, jamais une correction silencieuse.
#
# ── 2. L'espace de nommage des identifiants est dérivé du tenant ─────────────
# Sans ça, deux tenants ayant le même `source_event_id` produisent le MÊME
# identifiant métier. Le contrôle de doublon traite alors la mesure du tenant B
# comme un doublon de celle du tenant A et la jette — perte de donnée patient,
# silencieuse. Le tenant est donc injecté à la fois dans le `system` (le
# mécanisme propre, FHIR) ET dans la `value` (ceinture et bretelles : un sink
# qui n'indexerait que sur la valeur reste isolé malgré son erreur).
#
# ── 3. Le sink reçoit le tenant explicitement ────────────────────────────────
# `exists()` et `store()` le prennent en premier argument. Une implémentation ne
# peut pas « oublier » de filtrer : sans le paramètre, elle ne compile même pas
# mentalement. Un sink faisant `SELECT ... WHERE identifier_value = ?` sans
# clause tenant est cross-tenant par construction — on rend cette erreur
# difficile à commettre.
#
# CE QUE CE MODULE NE PEUT PAS FAIRE : `Patient/12345` chez le tenant A et
# `Patient/12345` chez le tenant B sont deux personnes différentes. La résolution
# des références patient appartient au serveur FHIR, pas à cette passerelle. Le
# tag de tenant sur la ressource rend l'appartenance explicite ; il ne remplace
# pas une isolation côté serveur.

#: Format d'un identifiant de tenant. Volontairement restrictif : ni « / », ni
#: « : », ni espace. Un tenant_id contenant « / » permettrait de forger l'espace
#: de nommage d'un autre tenant — « a/tenant/b » se résoudrait en le namespace
#: du tenant « b ». C'est une injection, et elle se referme ici.
_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9._~\-]{1,64}$")

#: Racine des espaces de nommage. À adapter au domaine de l'établissement.
DEFAULT_IDENTIFIER_BASE_SYSTEM: Final = "https://colosse.example/fhir/observation-id"

#: Système du tag d'appartenance porté par chaque ressource produite.
TENANT_TAG_SYSTEM: Final = "https://colosse.example/fhir/tenant"


def ensure_tenant_id(v: str) -> str:
    if not _TENANT_ID_RE.match(v):
        raise ValueError(
            "tenant_id doit correspondre à [A-Za-z0-9._~-]{1,64} — ni '/', ni ':', "
            "ni espace (sinon un tenant peut forger le namespace d'un autre)"
        )
    return v


def tenant_identifier_system(base_system: str, tenant_id: str) -> str:
    """Espace de nommage des identifiants métier, propre à un tenant.

    C'est ce qui empêche deux tenants partageant un `source_event_id` de se
    dédoublonner mutuellement.
    """
    return f"{base_system.rstrip('/')}/tenant/{ensure_tenant_id(tenant_id)}"


def _tenant_tag(tenant_id: str) -> dict:
    """Tag FHIR d'appartenance — rend le tenant lisible sur la ressource elle-même."""
    return {"system": TENANT_TAG_SYSTEM, "code": tenant_id}


# ============================================================================
# 1. EXCEPTIONS MÉDICALES (FAIL-CLOSED)
# ============================================================================


class BiomedBridgeError(Exception):
    """Base de toutes les erreurs de DONNÉE de la passerelle.

    Permet d'attraper la famille entière sans masquer les erreurs de
    programmation (TypeError, AttributeError…).

    Frontière importante : cette famille regroupe les défauts de DONNÉE, ceux qui
    ressortent en REJECTED. Une erreur de CONFIGURATION (clé de pseudonymisation
    absente, par exemple) n'en fait délibérément pas partie — voir
    `PseudonymizationKeyError` section 5.
    """


class UnknownMetricError(BiomedBridgeError):
    """Métrique absente du catalogue.

    Volontairement fatal : sans code LOINC connu, on ne peut pas dire ce que la
    valeur mesure. Ajouter l'entrée au catalogue est la seule réponse correcte —
    jamais un repli sur une métrique « par défaut ».
    """

    def __init__(self, metric_key: str) -> None:
        self.metric_key = metric_key
        super().__init__(
            f"Métrique inconnue rejetée : '{metric_key}'. Aucun repli autorisé. "
            "Ajoutez-la à METRICS (LOINC + unité UCUM + bornes) avant ingestion."
        )


class UnitMismatchError(BiomedBridgeError):
    """Unité ni canonique, ni alias, ni convertible POUR CETTE MÉTRIQUE.

    On refuse plutôt que de supposer : une conversion implicite entre mg/dL et
    mmol/L vaut un facteur 18 sur une glycémie — et ce facteur est celui du
    glucose, il ne vaut pour aucun autre analyte (section 2).
    """

    def __init__(self, metric_key: str, received: str, expected: str) -> None:
        self.metric_key = metric_key
        self.received = received
        self.expected = expected
        super().__init__(
            f"Unité incohérente pour '{metric_key}' : reçue '{received}', "
            f"attendue '{expected}' (ou un alias / une conversion déclarée pour "
            "CETTE métrique)."
        )


class ImplausibleValueError(BiomedBridgeError):
    """Valeur hors bornes physiologiques.

    Signale presque toujours un capteur en panne, une unité fausse ou un décalage
    d'octets dans la trame — pas un patient exceptionnel.
    """

    def __init__(
        self,
        metric_key: str,
        value: Decimal,
        min_val: Decimal,
        max_val: Decimal,
        unit: str,
    ) -> None:
        self.metric_key = metric_key
        self.value = value
        self.low = min_val
        self.high = max_val
        self.unit = unit
        super().__init__(
            f"Valeur aberrante pour '{metric_key}' : {value} {unit} "
            f"(bornes physiologiques : {min_val} – {max_val} {unit})."
        )


class TenantMismatchError(BiomedBridgeError):
    """Le payload déclare un tenant différent de celui de l'appelant.

    Incident de sécurité potentiel — capteur mal configuré, file mal routée, ou
    tentative d'écriture inter-tenants. Jamais corrigé en silence.
    """

    def __init__(self, expected: str, declared: Any) -> None:
        self.expected = expected
        self.declared = declared
        super().__init__(
            f"Conflit de tenant : l'appelant traite '{expected}', le payload "
            f"déclare '{declared}'. Mesure rejetée."
        )


# ============================================================================
# 2. CATALOGUE DES MÉTRIQUES (SOURCE DE VÉRITÉ UNIQUE)
# ============================================================================

LOINC_SYSTEM: Final = "http://loinc.org"
UCUM_SYSTEM: Final = "http://unitsofmeasure.org"
OBSERVATION_CATEGORY_SYSTEM: Final = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)

VITAL_SIGNS_PROFILE: Final = "http://hl7.org/fhir/StructureDefinition/vitalsigns"
BLOOD_PRESSURE_PROFILE: Final = "http://hl7.org/fhir/StructureDefinition/bp"
BLOOD_PRESSURE_PANEL_LOINC: Final = "85354-9"
BLOOD_PRESSURE_PANEL_DISPLAY: Final = "Blood pressure panel with all children optional"

#: Clé de routage réservée pour la tension artérielle. Ce n'est PAS une entrée du
#: catalogue : la tension est un panel à deux composants, pas une métrique
#: scalaire. Un garde-fou en fin de section vérifie l'absence de collision.
BLOOD_PRESSURE_KEY: Final = "blood_pressure"

CATEGORY_VITAL_SIGNS: Final = "vital-signs"
CATEGORY_LABORATORY: Final = "laboratory"

_CATEGORY_DISPLAY: Final = {
    CATEGORY_VITAL_SIGNS: "Vital Signs",
    CATEGORY_LABORATORY: "Laboratory",
}


@dataclass(frozen=True)
class MetricDefinition:
    """Définition figée d'une métrique. Le code LOINC détermine tout le reste.

    FHIR distingue deux champs d'unité, et la distinction est porteuse :
      * `ucum_code`    → `Quantity.code` — ce que lisent les machines ;
      * `ucum_display` → `Quantity.unit` — libellé d'affichage seulement.

    Le prototype ne remplissait que le second, avec « beats/minute » — qui n'est
    pas un code UCUM (le bon est `/min`). Sa quantité n'était pas interprétable.
    """

    key: str
    loinc_code: str
    display: str
    ucum_code: str
    ucum_display: str
    category: str
    #: Bornes exprimées dans l'unité canonique. Hors bornes, on suspecte le
    #: capteur avant de suspecter le patient.
    plausible_min: Decimal
    plausible_max: Decimal
    #: Écritures acceptées pour l'unité canonique — pures synonymies, aucun
    #: calcul. Toujours normalisées vers `ucum_code`.
    unit_aliases: frozenset[str] = field(default_factory=frozenset)
    #: Conversions DÉPENDANTES DE L'ANALYTE : `unité reçue` → facteur/formule vers
    #: `ucum_code`. Voir le commentaire de DIMENSIONAL_CONVERSIONS ci-dessous pour
    #: la raison d'être de cette séparation — c'est un correctif de sécurité, pas
    #: un rangement cosmétique.
    #:
    #: `compare=False` : un MappingProxyType n'est pas hachable, et on veut garder
    #: MetricDefinition hachable et comparable sur son identité métier.
    analyte_conversions: Mapping[str, Callable[[Decimal], Decimal]] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # Figer la table : un dataclass frozen protège la référence, pas le dict
        # qu'elle désigne. Sans ça, `metric.analyte_conversions[x] = ...` passerait.
        object.__setattr__(
            self,
            "analyte_conversions",
            MappingProxyType(dict(self.analyte_conversions)),
        )

    @property
    def category_display(self) -> str:
        return _CATEGORY_DISPLAY[self.category]

    @property
    def is_vital_sign(self) -> bool:
        return self.category == CATEGORY_VITAL_SIGNS


def _d(value: str) -> Decimal:
    """Decimal depuis une chaîne — jamais depuis un float (0.1 → 0.1000000000000000055)."""
    return Decimal(value)


# ────────────────────────────────────────────────────────────────────────────
# Arguments NOMMÉS, délibérément. Neuf champs positionnels dont cinq chaînes
# consécutives, c'est la forme où une transposition passe inaperçue — et toutes
# ne se valent pas :
#
#   * plausible_min <-> plausible_max : rejette TOUTE mesure. Erreur bruyante,
#     détectée en minutes. Peu dangereuse.
#   * ucum_code <-> ucum_display : partiellement silencieuse, et c'est le
#     problème. Si le capteur envoie le code canonique, normalize_to_canonical_
#     unit lève. Mais s'il envoie un alias (« °C », « degC » — le cas courant),
#     la ressource part avec Quantity.code = "°C", qui n'est pas un code UCUM.
#     Elle valide contre FHIR et reste illisible par machine en aval.
#   * pour une métrique où ucum_code == ucum_display (« % »), l'inversion est
#     un no-op — le lecteur s'habitue donc à ne pas regarder ces colonnes.
#
# La verbosité est ici une fonctionnalité. Le test de verrouillage du catalogue
# (test_biomed_engine.py) couvre le cas où elle serait commise malgré tout.
# ────────────────────────────────────────────────────────────────────────────
METRICS: Final[dict[str, MetricDefinition]] = {
    m.key: m
    for m in (
        MetricDefinition(
            key="heart_rate",
            loinc_code="8867-4",
            display="Heart rate",
            ucum_code="/min",
            ucum_display="beats/minute",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("20"),
            plausible_max=_d("300"),
            unit_aliases=frozenset({"bpm", "beats/minute", "beats/min", "1/min"}),
        ),
        MetricDefinition(
            key="respiratory_rate",
            loinc_code="9279-1",
            display="Respiratory rate",
            ucum_code="/min",
            ucum_display="breaths/minute",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("4"),
            plausible_max=_d("80"),
            unit_aliases=frozenset({"breaths/minute", "breaths/min", "rpm", "1/min"}),
        ),
        MetricDefinition(
            key="oxygen_saturation",
            loinc_code="59408-5",
            display="Oxygen saturation in Arterial blood by Pulse oximetry",
            ucum_code="%",
            ucum_display="%",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("50"),
            plausible_max=_d("100"),
            unit_aliases=frozenset({"percent", "pct"}),
            # Aucune conversion : une saturation ne se convertit pas depuis
            # mmol/mol. C'est l'absence d'entrée ici qui protège cette métrique
            # de la formule IFCC déclarée sur hba1c, elle aussi canonique en « % ».
        ),
        MetricDefinition(
            key="body_temperature",
            loinc_code="8310-5",
            display="Body temperature",
            ucum_code="Cel",
            ucum_display="°C",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("25"),
            plausible_max=_d("45"),
            unit_aliases=frozenset({"C", "°C", "degC", "celsius"}),
        ),
        MetricDefinition(
            key="systolic_blood_pressure",
            loinc_code="8480-6",
            display="Systolic blood pressure",
            ucum_code="mm[Hg]",
            ucum_display="mmHg",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("40"),
            plausible_max=_d("300"),
            unit_aliases=frozenset({"mmHg", "mm Hg"}),
        ),
        MetricDefinition(
            key="diastolic_blood_pressure",
            loinc_code="8462-4",
            display="Diastolic blood pressure",
            ucum_code="mm[Hg]",
            ucum_display="mmHg",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("20"),
            plausible_max=_d("200"),
            unit_aliases=frozenset({"mmHg", "mm Hg"}),
        ),
        MetricDefinition(
            key="body_weight",
            loinc_code="29463-7",
            display="Body weight",
            ucum_code="kg",
            ucum_display="kg",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("0.3"),
            plausible_max=_d("650"),
            unit_aliases=frozenset({"kilogram", "kgs"}),
        ),
        MetricDefinition(
            key="body_height",
            loinc_code="8302-2",
            display="Body height",
            ucum_code="cm",
            ucum_display="cm",
            category=CATEGORY_VITAL_SIGNS,
            plausible_min=_d("20"),
            plausible_max=_d("280"),
            unit_aliases=frozenset({"centimeter", "cms"}),
        ),
        MetricDefinition(
            key="blood_glucose",
            loinc_code="2339-0",
            display="Glucose [Mass/volume] in Blood",
            ucum_code="mg/dL",
            ucum_display="mg/dL",
            category=CATEGORY_LABORATORY,
            plausible_min=_d("10"),
            plausible_max=_d("1500"),
            unit_aliases=frozenset({"mg/dl", "mgdl"}),
            #: Facteur molaire DU GLUCOSE (masse molaire 180,156 g/mol). Il ne vaut
            #: que pour le glucose : une créatininémie (113,12 g/mol) se convertit
            #: avec 11,312, pas 18,0182. D'où le scope par métrique.
            analyte_conversions={
                "mmol/L": lambda v: v * Decimal("18.0182"),
                "mmol/l": lambda v: v * Decimal("18.0182"),
            },
        ),
        MetricDefinition(
            key="hba1c",
            loinc_code="4548-4",
            display="Hemoglobin A1c/Hemoglobin.total in Blood",
            ucum_code="%",
            ucum_display="%",
            category=CATEGORY_LABORATORY,
            plausible_min=_d("2"),
            plausible_max=_d("20"),
            unit_aliases=frozenset({"percent", "pct"}),
            #: Équation maîtresse NGSP/IFCC : NGSP(%) = 0,09148 × IFCC(mmol/mol)
            #: + 2,152. Affine, et non un simple facteur — contrôle : 53 mmol/mol
            #: → 7,00 % ; 48 mmol/mol → 6,543 %.
            #:
            #: Cette entrée est la raison d'être du scope par métrique. Dans une
            #: table globale indexée (unité, unité), ("mmol/mol", "%") aurait été
            #: applicable à oxygen_saturation, elle aussi canonique en « % ».
            analyte_conversions={
                "mmol/mol": lambda v: v * Decimal("0.09148") + Decimal("2.152"),
            },
        ),
    )
}

# Garde-fou de routage : si 'blood_pressure' devenait une entrée du catalogue,
# le routage deviendrait ambigu — et silencieusement.
if BLOOD_PRESSURE_KEY in METRICS:  # pragma: no cover
    raise RuntimeError(
        f"'{BLOOD_PRESSURE_KEY}' est une clé de routage réservée et ne peut pas "
        "être une entrée de METRICS (la tension est un panel, pas un scalaire)."
    )

#: Conversions DIMENSIONNELLES : propriétés des unités elles-mêmes, vraies pour
#: n'importe quelle grandeur de cette dimension. Une température en °F fait 37 °C
#: qu'elle mesure un front ou un moteur ; une livre pèse 0,45359237 kg quel que
#: soit l'objet pesé. Ces conversions sont donc légitimement globales.
#:
#: ┌── POURQUOI CETTE TABLE EST SÉPARÉE DES CONVERSIONS D'ANALYTE ──────────────┐
#: │ Une seule table indexée (unité reçue, unité canonique) était un défaut de   │
#: │ conception grave. Le facteur 18,0182 mmol/L → mg/dL est la masse molaire du │
#: │ GLUCOSE ; indexé sans la métrique, il s'appliquait à TOUTE métrique         │
#: │ canonique en mg/dL. Une créatininémie de 1 mmol/L en sortait à              │
#: │ 18,0182 mg/dL au lieu de 11,312 — 59 % d'erreur sur un marqueur rénal,      │
#: │ dans les bornes physiologiques, donc silencieuse.                           │
#: │                                                                             │
#: │ Même mécanisme pour l'HbA1c : ("mmol/mol", "%") dans une table globale      │
#: │ serait devenu applicable à oxygen_saturation, canonique en « % » elle aussi.│
#: │                                                                             │
#: │ RÈGLE : n'ajoutez ici QUE ce qui est une propriété de l'unité. Toute        │
#: │ formule qui dépend de la substance mesurée (masse molaire, équation         │
#: │ clinique de calibration) va dans `analyte_conversions` de SA métrique.      │
#: │ Un test de verrouillage refuse les unités molaires dans cette table.        │
#: └─────────────────────────────────────────────────────────────────────────────┘
DIMENSIONAL_CONVERSIONS: Final[
    dict[tuple[str, str], Callable[[Decimal], Decimal]]
] = {
    # Température
    ("[degF]", "Cel"): lambda v: (v - Decimal("32")) * Decimal("5") / Decimal("9"),
    ("degF", "Cel"): lambda v: (v - Decimal("32")) * Decimal("5") / Decimal("9"),
    ("°F", "Cel"): lambda v: (v - Decimal("32")) * Decimal("5") / Decimal("9"),
    # Masse
    ("g", "kg"): lambda v: v / Decimal("1000"),
    ("[lb_av]", "kg"): lambda v: v * Decimal("0.45359237"),
    ("lb", "kg"): lambda v: v * Decimal("0.45359237"),
    # Longueur
    ("m", "cm"): lambda v: v * Decimal("100"),
    ("[in_i]", "cm"): lambda v: v * Decimal("2.54"),
}


def get_metric(metric_key: str) -> MetricDefinition:
    """Résout une clé de métrique. Lève si absente — jamais de repli silencieux."""
    try:
        return METRICS[metric_key]
    except KeyError:
        raise UnknownMetricError(metric_key) from None


# ============================================================================
# 3. SCHÉMAS DE VALIDATION (PYDANTIC 2)
# ============================================================================

#: Références FHIR relatives. L'id FHIR est contraint par la spec à
#: [A-Za-z0-9-.]{1,64}.
_PATIENT_REF_RE = re.compile(r"^Patient/[A-Za-z0-9\-.]{1,64}$")
_DEVICE_REF_RE = re.compile(r"^Device/[A-Za-z0-9\-.]{1,64}$")
_PERFORMER_TYPES: Final = (
    "Practitioner",
    "PractitionerRole",
    "Organization",
    "Patient",
    "RelatedPerson",
)
_PERFORMER_REF_RE = re.compile(
    rf"^({'|'.join(_PERFORMER_TYPES)})/[A-Za-z0-9\-.]{{1,64}}$"
)

#: Tolérance d'horloge admise pour un capteur légèrement en avance.
MAX_CLOCK_SKEW = timedelta(minutes=5)


def ensure_finite(v: Decimal) -> Decimal:
    if not v.is_finite():
        raise ValueError("doit être un nombre fini (ni NaN, ni Infinity)")
    return v


def ensure_aware_and_sane(v: datetime) -> datetime:
    if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
        raise ValueError("measured_at doit porter un fuseau horaire (datetime aware)")
    if v > datetime.now(timezone.utc) + MAX_CLOCK_SKEW:
        raise ValueError("measured_at est dans le futur — horloge capteur suspecte")
    return v.astimezone(timezone.utc)


def ensure_patient_ref(v: str) -> str:
    if not _PATIENT_REF_RE.match(v):
        raise ValueError("patient_ref doit être de la forme 'Patient/<id>'")
    return v


def ensure_device_ref(v: str | None) -> str | None:
    if v is not None and not _DEVICE_REF_RE.match(v):
        raise ValueError("device_ref doit être de la forme 'Device/<id>'")
    return v


def ensure_performer_ref(v: str | None) -> str | None:
    if v is not None and not _PERFORMER_REF_RE.match(v):
        raise ValueError(
            "performer_ref doit être de la forme '<Type>/<id>' avec <Type> parmi : "
            + ", ".join(_PERFORMER_TYPES)
        )
    return v


class _ReadingBase(BaseModel):
    """Champs et règles communs à toutes les mesures.

    `extra="forbid"` est délibéré : une clé mal orthographiée (`loinc_code` au
    lieu de `metric_key`, `val` au lieu de `value`) devient une erreur bruyante
    au lieu d'être ignorée en silence comme dans le prototype.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    #: Établissement propriétaire de la donnée. Obligatoire : une mesure de santé
    #: sans tenant ne peut être ni isolée, ni auditée, ni purgée sur demande.
    tenant_id: str

    #: **Doit** porter un fuseau : un horodatage naïf sur un flux multi-régions
    #: est une erreur qui ne se voit qu'en aval.
    measured_at: datetime

    #: Sujet de la mesure. Sans lui, l'Observation n'a aucun sens clinique.
    patient_ref: str

    #: Identifiant métier stable de l'événement source : deux livraisons du même
    #: événement produisent le même `Observation.identifier`. Pivot de l'idempotence.
    source_event_id: str = Field(min_length=1, max_length=128)

    #: Capteur ayant produit la mesure — traçabilité.
    device_ref: str | None = None

    #: Auteur de la mesure (soignant, patient lui-même…).
    performer_ref: str | None = None

    #: `status = "final"` uniquement sur demande explicite. Un flux capteur brut
    #: est « preliminary » tant qu'il n'a pas été revu.
    final: bool = False

    _v_tenant = field_validator("tenant_id")(ensure_tenant_id)
    _v_measured_at = field_validator("measured_at")(ensure_aware_and_sane)
    _v_patient = field_validator("patient_ref")(ensure_patient_ref)
    _v_device = field_validator("device_ref")(ensure_device_ref)
    _v_performer = field_validator("performer_ref")(ensure_performer_ref)


class BiomarkerReading(_ReadingBase):
    """Mesure scalaire brute, avant traduction en FHIR."""

    #: Clé du catalogue. Détermine LOINC, unité canonique, catégorie et bornes.
    metric_key: str = Field(min_length=1, max_length=64)

    #: `Decimal` et non `float` : pas de perte de précision sur une glycémie.
    value: Decimal

    #: Unité telle que transmise. Vérifiée contre le catalogue, convertie si — et
    #: seulement si — une conversion est déclarée POUR CETTE MÉTRIQUE.
    unit: str = Field(min_length=1, max_length=32)

    _v_value = field_validator("value")(ensure_finite)


class BloodPressureReading(_ReadingBase):
    """Tension artérielle — mesure à deux composantes.

    Le profil FHIR des signes vitaux attend la pression artérielle comme **une**
    Observation panel (LOINC 85354-9) portant deux `component`, et non deux
    Observations indépendantes : systolique et diastolique séparées perdent le
    lien entre les deux chiffres, et « 80 » isolé ne veut rien dire.
    """

    #: Discriminant de routage explicite. `Literal` : ne peut valoir que cette
    #: clé. On ne renifle jamais la forme du payload pour deviner son type —
    #: c'est précisément le réflexe implicite qui a produit le prototype.
    metric_key: Literal["blood_pressure"] = BLOOD_PRESSURE_KEY

    systolic: Decimal
    diastolic: Decimal
    unit: str = Field(default="mm[Hg]", min_length=1, max_length=32)

    _v_systolic = field_validator("systolic")(ensure_finite)
    _v_diastolic = field_validator("diastolic")(ensure_finite)

    @model_validator(mode="after")
    def _diastolic_below_systolic(self) -> BloodPressureReading:
        """Cohérence entre deux champs — donc au niveau du MODÈLE, pas du champ.

        La version précédente était un `field_validator("diastolic")` lisant
        `info.data["systolic"]` : `info.data` ne contient que les champs déjà
        validés, donc la règle ne s'appliquait que parce que `systolic` est
        déclarée AVANT `diastolic`. Réordonner les deux lignes désactivait le
        contrôle en silence. `mode="after"` voit les deux champs et ne dépend
        plus de l'ordre de déclaration.

        Bénéfice secondaire : si `systolic` échoue sa propre validation, ce
        validateur ne s'exécute pas du tout, au lieu de produire une seconde
        erreur trompeuse.
        """
        if self.diastolic >= self.systolic:
            raise ValueError(
                f"diastolique ({self.diastolic}) doit être strictement inférieure à "
                f"systolique ({self.systolic}) — brassard ou parsing suspect"
            )
        return self


# ============================================================================
# 4. MAPPEUR FHIR (PUR & SYNCHRONE)
# ============================================================================
#
# Aucune E/S ici, juste du calcul : le prototype déclarait `async def` sans un
# seul `await`. L'asynchrone appartient à la section 5.
#
# Les mappeurs prennent le système de nommage RACINE et dérivent eux-mêmes la
# portée tenant depuis `reading.tenant_id`. Un appelant ne peut donc pas fournir
# un namespace incohérent avec la mesure qu'il traduit.

#: Précision retenue après conversion. Au-delà, on propage du bruit de calcul
#: (98.6 °F → 37.000000000000000000000001 °C).
_QUANTUM = Decimal("0.0001")


def _tidy(value: Decimal) -> Decimal:
    """Arrondit et normalise pour une sérialisation FHIR propre.

    FHIR `decimal` n'admet pas la notation exponentielle : `normalize()`
    transforme 100 en `1E+2`, d'où le re-quantize final.
    """
    quantized = value.quantize(_QUANTUM, rounding=ROUND_HALF_UP).normalize()
    if quantized.as_tuple().exponent > 0:
        quantized = quantized.quantize(Decimal(1))
    return quantized


def normalize_to_canonical_unit(
    metric: MetricDefinition, value: Decimal, unit: str
) -> Decimal:
    """Ramène `value` dans l'unité canonique de `metric`.

    Quatre cas, dans cet ordre — et pas de cinquième :

      1. unité canonique ou alias déclaré → inchangée, aucun calcul ;
      2. conversion d'ANALYTE déclarée par cette métrique → appliquée. Passe
         avant le dimensionnel pour qu'une métrique puisse surcharger si besoin ;
      3. conversion DIMENSIONNELLE (propriété de l'unité) → appliquée ;
      4. sinon `UnitMismatchError`.

    L'ordre 2 avant 3 et, surtout, le fait que 2 soit porté par la métrique sont
    ce qui empêche le facteur molaire du glucose de s'appliquer à un autre
    analyte canonique en mg/dL (voir DIMENSIONAL_CONVERSIONS, section 2).
    """
    received = unit.strip()
    if received == metric.ucum_code or received in metric.unit_aliases:
        return value

    convert = metric.analyte_conversions.get(received)
    if convert is None:
        convert = DIMENSIONAL_CONVERSIONS.get((received, metric.ucum_code))
    if convert is None:
        raise UnitMismatchError(metric.key, received, metric.ucum_code)
    return _tidy(convert(value))


def check_plausible(metric: MetricDefinition, value: Decimal) -> None:
    """Bornes physiologiques, appliquées à la valeur CANONIQUE (post-conversion)."""
    if not (metric.plausible_min <= value <= metric.plausible_max):
        raise ImplausibleValueError(
            metric.key,
            value,
            metric.plausible_min,
            metric.plausible_max,
            metric.ucum_code,
        )


def build_identifier_value(
    tenant_id: str, metric_key: str, source_event_id: str
) -> str:
    """Identifiant métier déterministe, porté par le tenant.

    Le tenant figure ici EN PLUS d'être dans le `system` : un sink qui
    n'indexerait que sur la valeur reste isolé malgré son erreur. Le coût est
    nul, le mode de défaillance évité est une perte silencieuse de mesure.
    """
    return f"{tenant_id}|{metric_key}|{source_event_id}"


def _coding(system: str, code: str, display: str) -> dict:
    return {"system": system, "code": code, "display": display}


def _category_block(category: str, display: str) -> list[dict]:
    return [{"coding": [_coding(OBSERVATION_CATEGORY_SYSTEM, category, display)]}]


def _quantity_block(metric: MetricDefinition, value: Decimal) -> dict:
    """`code` + `system` sont ce que lisent les machines ; `unit` est l'affichage."""
    return {
        "value": value,
        "unit": metric.ucum_display,
        "system": UCUM_SYSTEM,
        "code": metric.ucum_code,
    }


def _meta_block(tenant_id: str, profile: str | None = None) -> dict:
    """`meta` porte toujours le tag de tenant, et le profil quand il s'applique.

    Revendiquer un profil n'a de sens que si la ressource s'y conforme : le
    profil vitalsigns exige code, subject, effective et une valeur. Aucun profil
    de base standard ne couvre le laboratoire en R4 — on n'en invente pas.
    """
    meta: dict = {"tag": [_tenant_tag(tenant_id)]}
    if profile is not None:
        meta["profile"] = [profile]
    return meta


def _attach_provenance(payload: dict, reading: _ReadingBase) -> None:
    if reading.device_ref:
        payload["device"] = {"reference": reading.device_ref}
    if reading.performer_ref:
        payload["performer"] = [{"reference": reading.performer_ref}]


def to_fhir_observation(
    reading: BiomarkerReading,
    *,
    identifier_base_system: str = DEFAULT_IDENTIFIER_BASE_SYSTEM,
    issued: datetime | None = None,
) -> Observation:
    """Traduit une mesure scalaire validée en Observation FHIR R4B.

    Args:
        reading: mesure déjà validée, portant son `tenant_id`.
        identifier_base_system: RACINE des espaces de nommage. La portée tenant
            est dérivée ici même — l'appelant ne peut pas la contourner.
        issued: date de publication ; par défaut, maintenant (UTC).

    Raises:
        UnknownMetricError: métrique absente du catalogue.
        UnitMismatchError: unité ni canonique, ni alias, ni convertible.
        ImplausibleValueError: valeur hors bornes physiologiques.
    """
    metric = get_metric(reading.metric_key)
    value = normalize_to_canonical_unit(metric, reading.value, reading.unit)
    check_plausible(metric, value)

    payload: dict = {
        "resourceType": "Observation",
        "meta": _meta_block(
            reading.tenant_id,
            VITAL_SIGNS_PROFILE if metric.is_vital_sign else None,
        ),
        "identifier": [
            {
                "system": tenant_identifier_system(
                    identifier_base_system, reading.tenant_id
                ),
                "value": build_identifier_value(
                    reading.tenant_id, metric.key, reading.source_event_id
                ),
            }
        ],
        "status": "final" if reading.final else "preliminary",
        "category": _category_block(metric.category, metric.category_display),
        "code": {
            "coding": [_coding(LOINC_SYSTEM, metric.loinc_code, metric.display)],
            "text": metric.display,
        },
        "subject": {"reference": reading.patient_ref},
        "effectiveDateTime": reading.measured_at,
        "issued": issued or datetime.now(timezone.utc),
        "valueQuantity": _quantity_block(metric, _tidy(value)),
    }

    _attach_provenance(payload, reading)
    return Observation.model_validate(payload)


def to_fhir_blood_pressure(
    reading: BloodPressureReading,
    *,
    identifier_base_system: str = DEFAULT_IDENTIFIER_BASE_SYSTEM,
    issued: datetime | None = None,
) -> Observation:
    """Traduit une tension en Observation panel FHIR (LOINC 85354-9, profil bp)."""
    systolic_metric = get_metric("systolic_blood_pressure")
    diastolic_metric = get_metric("diastolic_blood_pressure")

    systolic = normalize_to_canonical_unit(
        systolic_metric, reading.systolic, reading.unit
    )
    diastolic = normalize_to_canonical_unit(
        diastolic_metric, reading.diastolic, reading.unit
    )
    check_plausible(systolic_metric, systolic)
    check_plausible(diastolic_metric, diastolic)

    def component(metric: MetricDefinition, value: Decimal) -> dict:
        return {
            "code": {
                "coding": [_coding(LOINC_SYSTEM, metric.loinc_code, metric.display)],
                "text": metric.display,
            },
            "valueQuantity": _quantity_block(metric, _tidy(value)),
        }

    payload: dict = {
        "resourceType": "Observation",
        "meta": _meta_block(reading.tenant_id, BLOOD_PRESSURE_PROFILE),
        "identifier": [
            {
                "system": tenant_identifier_system(
                    identifier_base_system, reading.tenant_id
                ),
                "value": build_identifier_value(
                    reading.tenant_id, reading.metric_key, reading.source_event_id
                ),
            }
        ],
        "status": "final" if reading.final else "preliminary",
        "category": _category_block(CATEGORY_VITAL_SIGNS, "Vital Signs"),
        "code": {
            "coding": [
                _coding(
                    LOINC_SYSTEM,
                    BLOOD_PRESSURE_PANEL_LOINC,
                    BLOOD_PRESSURE_PANEL_DISPLAY,
                )
            ],
            "text": "Blood pressure",
        },
        "subject": {"reference": reading.patient_ref},
        "effectiveDateTime": reading.measured_at,
        "issued": issued or datetime.now(timezone.utc),
        # Pas de valueQuantity au niveau panel : la valeur est dans les composants.
        "component": [
            component(systolic_metric, systolic),
            component(diastolic_metric, diastolic),
        ],
    }

    _attach_provenance(payload, reading)
    return Observation.model_validate(payload)


# ============================================================================
# 5. COUCHE D'INGESTION (ASYNCHRONE)
# ============================================================================
#
# Contrat d'erreurs délibéré :
#   * donnée INVALIDE → ne lève pas, renvoie REJECTED avec le motif. Une trame
#     corrompue ne doit pas tuer le consommateur du flux.
#   * panne d'INFRASTRUCTURE (sink injoignable) → propage. C'est à la file de
#     réessayer ; l'avaler ferait silencieusement perdre la mesure.
#   * erreur de CONFIGURATION (clé de pseudonymisation) → lève au DÉMARRAGE,
#     avant toute ingestion, et n'appartient pas à BiomedBridgeError.


class IngestStatus(str, Enum):
    ACCEPTED = "accepted"
    #: Déjà ingérée — même `source_event_id` pour le MÊME tenant. Pas une erreur.
    DUPLICATE = "duplicate"
    #: Donnée refusée. `reason` dit pourquoi.
    REJECTED = "rejected"


@dataclass(frozen=True)
class IngestResult:
    """Issue explicite d'une ingestion. Jamais `None`, jamais ambigu."""

    status: IngestStatus
    tenant_id: str | None = None
    identifier_value: str | None = None
    observation: Observation | None = None
    reason: str | None = None
    #: Nom de l'exception à l'origine du rejet — utile pour les métriques.
    error_type: str | None = None
    #: Identifiant rendu par le sink (ACCEPTED, et DUPLICATE quand le sink sait
    #: désigner la ligne déjà présente).
    storage_id: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status is IngestStatus.ACCEPTED


@dataclass(frozen=True)
class StoreOutcome:
    """Ce que `store()` a réellement fait — et non ce que l'appelant espérait.

    `created=False` signifie : la mesure était déjà là, la contrainte d'unicité
    a rattrapé l'écriture. C'est le mécanisme qui rend l'idempotence correcte
    sous concurrence, et il ne peut vivre que dans le sink.
    """

    created: bool
    storage_id: str


@runtime_checkable
class ObservationSink(Protocol):
    """Destination des Observations : serveur FHIR, base, file…

    Le `tenant_id` est le PREMIER argument des deux méthodes, délibérément : une
    implémentation ne peut pas l'ignorer par distraction. Un sink qui ferait
    `SELECT ... WHERE identifier_value = ?` sans clause tenant serait
    cross-tenant par construction.

    ┌── L'UNICITÉ EST LA RESPONSABILITÉ DU SINK, PAS DE CE MODULE ──────────────┐
    │ `exists()` puis `store()` est un vérifier-puis-agir : entre les deux, une  │
    │ autre coroutine, un autre worker, un autre processus peut insérer. Ce      │
    │ module ne peut PAS refermer cette course — il n'a pas de transaction. Le   │
    │ séquencement de `ingest_batch` ne protège qu'un lot, jamais plusieurs      │
    │ workers, qui est le cas normal en production.                             │
    │                                                                           │
    │ La garantie doit donc venir de la base. DDL attendu :                     │
    │                                                                           │
    │   CREATE TABLE observations (                                             │
    │       id                BIGSERIAL PRIMARY KEY,                            │
    │       tenant_id         TEXT NOT NULL,                                    │
    │       identifier_system TEXT NOT NULL,                                    │
    │       identifier_value  TEXT NOT NULL,                                    │
    │       resource          JSONB NOT NULL,                                   │
    │       created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),               │
    │       CONSTRAINT observations_identity_uniq                               │
    │           UNIQUE (tenant_id, identifier_system, identifier_value)         │
    │   );                                                                      │
    │                                                                           │
    │ (`tenant_id` est redondant avec `identifier_system`, qui porte déjà le     │
    │  tenant : ceinture et bretelles, cohérent avec la section 0.)              │
    │                                                                           │
    │ Écriture recommandée (PostgreSQL) — aucune exception, donc aucune          │
    │ transaction avortée :                                                     │
    │                                                                           │
    │   INSERT INTO observations (tenant_id, identifier_system,                 │
    │                             identifier_value, resource)                   │
    │   VALUES ($1, $2, $3, $4)                                                 │
    │   ON CONFLICT ON CONSTRAINT observations_identity_uniq DO NOTHING          │
    │   RETURNING id;                                                           │
    │   -- created = (une ligne est revenue)                                    │
    │                                                                           │
    │ Voie portable, par rattrapage d'exception :                               │
    │                                                                           │
    │   try:                                                                    │
    │       async with session.begin_nested():   # SAVEPOINT — indispensable    │
    │           session.add(row)                                                │
    │       return StoreOutcome(created=True, storage_id=str(row.id))           │
    │   except IntegrityError as exc:                                           │
    │       if "observations_identity_uniq" not in str(exc.orig):                │
    │           raise            # ne JAMAIS avaler les autres violations       │
    │       return StoreOutcome(created=False, storage_id=<id existant>)        │
    │                                                                           │
    │ Le SAVEPOINT (`begin_nested`) n'est pas optionnel : en PostgreSQL une      │
    │ IntegrityError avorte la transaction ENTIÈRE, et tout travail en cours     │
    │ serait perdu. C'est le bug de suivi classique de ce motif.                │
    │                                                                           │
    │ `assert_sink_honours_uniqueness()` (test_biomed_engine.py) vérifie qu'une  │
    │ implémentation tient bien ce contrat sous concurrence.                     │
    └───────────────────────────────────────────────────────────────────────────┘
    """

    async def exists(
        self, tenant_id: str, identifier_system: str, identifier_value: str
    ) -> bool:
        """OPTIMISATION seulement — jamais la garantie d'unicité.

        Évite une tentative d'écriture sur la redélivrance courante. Un sink peut
        parfaitement renvoyer `False` en permanence sans rendre l'ingestion
        incorrecte : `store()` reste l'autorité.
        """
        ...

    async def store(self, tenant_id: str, observation: Observation) -> StoreOutcome:
        """Persiste, ATOMIQUEMENT, et dit si la ligne a été créée ou non.

        DOIT s'appuyer sur une contrainte d'unicité
        `(tenant_id, identifier_system, identifier_value)` — voir le DDL
        ci-dessus. Rendre `created=True` sans cette contrainte réintroduit la
        course que ce contrat existe pour refermer.
        """
        ...


# ── Pseudonymisation des journaux ───────────────────────────────────────────
#
# ┌── POURQUOI UN HMAC ET NON UN HASH NU ──────────────────────────────────────┐
# │ La version précédente faisait `sha256(reference)[:12]`. Un hash nu n'est    │
# │ pas une protection quand l'espace des entrées est petit et prévisible : les │
# │ identifiants patients sont souvent séquentiels. `Patient/12345` a été       │
# │ retrouvé depuis son empreinte de journal en 12 345 essais, en 0,01 s —      │
# │ n'importe qui ayant accès aux logs précalcule la table et réidentifie.      │
# │                                                                            │
# │ Préfixer par le tenant n'y changeait rien : le tenant_id est journalisé en  │
# │ clair sur la même ligne, donc l'attaquant le connaît et l'inclut dans son   │
# │ balayage.                                                                   │
# │                                                                            │
# │ Un HMAC-SHA256 à clé serveur conserve la propriété utile — même patient →   │
# │ même empreinte, donc corrélation de deux lignes possible — et retire la     │
# │ réversibilité : sans la clé, il n'y a pas de précalcul.                     │
# └────────────────────────────────────────────────────────────────────────────┘

#: Variable d'environnement portant la clé, en hexadécimal.
BIOMED_HMAC_KEY_ENV: Final = "BIOMED_PSEUDONYM_HMAC_KEY"

#: Longueur minimale de clé. 32 octets = taille de bloc de sortie de SHA-256.
_MIN_KEY_BYTES: Final = 32

#: Longueur de l'empreinte tronquée, en caractères hexadécimaux. 16 → 64 bits.
#: La troncature est sûre sous HMAC (elle ne rend pas la clé), mais 48 bits
#: (l'ancienne valeur) commencent à collisionner vers quelques millions de
#: patients distincts, et une collision fusionnerait deux dossiers dans les logs.
_DIGEST_HEX_LEN: Final = 16

_KEYGEN_HINT: Final = (
    'python -c "import secrets; print(secrets.token_hex(32))"'
)


class PseudonymizationKeyError(Exception):
    """Clé de pseudonymisation absente ou inutilisable.

    N'hérite **délibérément pas** de `BiomedBridgeError`. Cette famille-là est
    attrapée en section 5 et convertie en `REJECTED` : une erreur de
    configuration y tomberait, le système tournerait sans clé, et la seule trace
    serait des mesures rejetées sans raison apparente. C'est exactement le mode
    de défaillance silencieux qu'on referme ici — d'où la séparation, verrouillée
    par un test.
    """


@dataclass(frozen=True, repr=False, eq=False)
class Pseudonymizer:
    """Porteur de la clé HMAC. Produit les empreintes patient des journaux.

    `repr=False` et `eq=False` sont des exigences de sécurité, pas du style :

      * le `__repr__` généré par défaut imprimerait la clé dans toute trace
        d'exception, tout `logger.debug("%r", obj)`, tout dump de contexte — la
        clé fuirait précisément dans les journaux qu'elle protège ;
      * le `__eq__` généré comparerait les clés octet par octet, en court-circuit.

    La clé n'est jamais lue depuis l'environnement par cette classe : elle est
    fournie par l'hôte (voir `pseudonymizer_from_env`). Le moteur reste agnostique
    de la façon dont Digital Colosse gère ses secrets.
    """

    key: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.key, (bytes, bytearray)):
            raise PseudonymizationKeyError(
                "La clé de pseudonymisation doit être des octets (bytes), pas "
                f"{type(self.key).__name__}."
            )
        if len(self.key) < _MIN_KEY_BYTES:
            raise PseudonymizationKeyError(
                f"Clé de pseudonymisation trop courte : {len(self.key)} octets, "
                f"minimum {_MIN_KEY_BYTES}. Générez-en une avec : {_KEYGEN_HINT}"
            )
        object.__setattr__(self, "key", bytes(self.key))

    def of_patient(self, tenant_id: str, patient_ref: str) -> str:
        """Empreinte de journal d'une référence patient, portée par le tenant.

        Le tenant entre dans le message : `Patient/12345` chez deux
        établissements désigne deux personnes, leurs empreintes doivent différer.
        """
        message = f"{tenant_id}|{patient_ref}".encode("utf-8")
        return hmac.new(self.key, message, hashlib.sha256).hexdigest()[
            :_DIGEST_HEX_LEN
        ]

    def __repr__(self) -> str:
        return "Pseudonymizer(key=<redacted>)"

    __str__ = __repr__


def pseudonymizer_from_env(env_var: str = BIOMED_HMAC_KEY_ENV) -> Pseudonymizer:
    """Construit un `Pseudonymizer` depuis l'environnement. ÉCHEC AU DÉMARRAGE.

    À appeler une fois au boot de l'hôte — worker, consommateur de file, API :

        PSEUDONYMIZER = pseudonymizer_from_env()

    Lève si la clé manque, ce qui est le comportement voulu : un service de santé
    qui démarre sans clé journaliserait des empreintes réversibles pendant des
    mois avant que quiconque le remarque. Mieux vaut ne pas démarrer.

    La clé est attendue en hexadécimal (≥ 64 caractères pour 32 octets), format
    unique et sans ambiguïté de padding. Génération :

        python -c "import secrets; print(secrets.token_hex(32))"

    Raises:
        PseudonymizationKeyError: variable absente, vide, non hexadécimale, ou
            clé trop courte.
    """
    raw = os.environ.get(env_var)
    if raw is None or not raw.strip():
        raise PseudonymizationKeyError(
            f"Variable d'environnement {env_var} absente ou vide. Elle porte la "
            "clé HMAC de pseudonymisation des journaux et n'a pas de valeur par "
            f"défaut — un hash sans clé est réversible par force brute. "
            f"Générez-en une avec : {_KEYGEN_HINT}"
        )

    try:
        key = bytes.fromhex(raw.strip())
    except ValueError as exc:
        raise PseudonymizationKeyError(
            f"{env_var} doit contenir une clé en hexadécimal (au moins "
            f"{_MIN_KEY_BYTES * 2} caractères). Générez-en une avec : {_KEYGEN_HINT}"
        ) from exc

    try:
        return Pseudonymizer(key)
    except PseudonymizationKeyError as exc:
        # Le constructeur ignore d'où vient la clé. Ici on le sait : nommer la
        # variable évite à l'exploitant de chercher à l'aveugle au démarrage.
        raise PseudonymizationKeyError(f"{env_var} : {exc}") from exc


def _select_handler(
    payload: Mapping[str, Any],
) -> tuple[type[_ReadingBase], Callable[..., Observation]]:
    """Choisit modèle et mappeur d'après le discriminant explicite `metric_key`.

    Aucun reniflage de la forme du payload : deviner le type d'une mesure
    d'après la présence d'une clé, c'est le réflexe implicite qu'on élimine
    partout ailleurs dans ce module.
    """
    if payload.get("metric_key") == BLOOD_PRESSURE_KEY:
        return BloodPressureReading, to_fhir_blood_pressure
    return BiomarkerReading, to_fhir_observation


def _bind_tenant(payload: Mapping[str, Any], tenant_id: str) -> dict:
    """Impose le tenant de l'APPELANT au payload.

    Le worker sait quelle file il draine ; le capteur n'est pas une source de
    vérité. Si le payload déclare un tenant différent, on lève plutôt que de
    corriger en silence : c'est soit un capteur mal configuré, soit une file mal
    routée, soit une tentative d'écriture inter-tenants. Les trois méritent une
    alerte, aucune ne mérite d'être absorbée.
    """
    declared = payload.get("tenant_id")
    if declared is not None and declared != tenant_id:
        raise TenantMismatchError(tenant_id, declared)
    return {**payload, "tenant_id": tenant_id}


async def ingest_reading(
    payload: Mapping[str, Any],
    *,
    sink: ObservationSink,
    tenant_id: str,
    pseudonymizer: Pseudonymizer,
    identifier_base_system: str = DEFAULT_IDENTIFIER_BASE_SYSTEM,
) -> IngestResult:
    """Valide, traduit, dédoublonne et persiste une mesure, dans un tenant donné.

    Accepte les deux formes : mesure scalaire, et tension artérielle (payload
    portant `metric_key = "blood_pressure"`).

    Args:
        payload: dict brut issu du capteur ou du courtier de messages.
        sink: destination des Observations. C'est lui qui porte la garantie
            d'unicité — voir `ObservationSink`.
        tenant_id: établissement traité — **source de vérité**. S'il est aussi
            déclaré dans le payload et qu'il diffère, la mesure est rejetée.
        pseudonymizer: porteur de la clé HMAC des empreintes de journal.
            **Obligatoire et sans valeur par défaut** : on ne peut pas ingérer de
            la donnée de santé sans savoir comment la journaliser sans la
            divulguer. Construisez-le une fois au démarrage avec
            `pseudonymizer_from_env()`.
        identifier_base_system: racine des espaces de nommage.

    Returns:
        `IngestResult` — toujours, y compris en cas de donnée refusée.

    Raises:
        Toute exception levée par `sink` : une panne d'infrastructure doit
        remonter pour que la file réessaie.
    """
    # ── 0. Portée tenant, imposée par l'appelant ────────────────────
    try:
        scoped_payload = _bind_tenant(payload, tenant_id)
    except TenantMismatchError as exc:
        logger.warning(
            "biomed.ingest.rejected.tenant_mismatch",
            extra={"tenant": tenant_id, "declared_tenant": str(exc.declared)},
        )
        return IngestResult(
            status=IngestStatus.REJECTED,
            tenant_id=tenant_id,
            reason=str(exc),
            error_type=type(exc).__name__,
        )

    model, to_fhir = _select_handler(scoped_payload)

    # ── 1. Validation du contrat d'entrée ───────────────────────────
    try:
        reading = model.model_validate(scoped_payload)
    except ValidationError as exc:
        # On journalise l'emplacement des erreurs, pas les valeurs : le payload
        # peut contenir de la donnée de santé.
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        logger.warning(
            "biomed.ingest.rejected.schema",
            extra={
                "tenant": tenant_id,
                "model": model.__name__,
                "invalid_fields": fields,
            },
        )
        return IngestResult(
            status=IngestStatus.REJECTED,
            tenant_id=tenant_id,
            reason=f"payload invalide ({model.__name__}) sur : {', '.join(fields)}",
            error_type="ValidationError",
        )

    identifier_system = tenant_identifier_system(identifier_base_system, tenant_id)
    identifier_value = build_identifier_value(
        tenant_id, reading.metric_key, reading.source_event_id
    )
    patient_hash = pseudonymizer.of_patient(tenant_id, reading.patient_ref)

    # ── 2. Traduction FHIR (fail-closed) ────────────────────────────
    try:
        observation = to_fhir(
            reading, identifier_base_system=identifier_base_system
        )
    except BiomedBridgeError as exc:
        logger.warning(
            "biomed.ingest.rejected.mapping",
            extra={
                "tenant": tenant_id,
                "metric_key": reading.metric_key,
                "identifier_value": identifier_value,
                "patient": patient_hash,
                "error_type": type(exc).__name__,
            },
        )
        return IngestResult(
            status=IngestStatus.REJECTED,
            tenant_id=tenant_id,
            identifier_value=identifier_value,
            reason=str(exc),
            error_type=type(exc).__name__,
        )

    # ── 3. Chemin rapide sur la redélivrance ────────────────────────
    #
    # ATTENTION — ce `exists()` est une OPTIMISATION, pas la garantie. Entre ce
    # test et le `store()` ci-dessous, un autre worker peut insérer : c'est un
    # vérifier-puis-agir, et il est irréparable ici (aucune transaction à ce
    # niveau). Il économise une écriture inutile sur le cas courant — la
    # redélivrance d'un événement déjà ingéré — et rien de plus.
    #
    # La correction est à l'étape 4 : c'est `store()` qui tranche.
    if await sink.exists(tenant_id, identifier_system, identifier_value):
        logger.info(
            "biomed.ingest.duplicate",
            extra={
                "tenant": tenant_id,
                "identifier_value": identifier_value,
                "patient": patient_hash,
                "detected_at": "exists",
            },
        )
        return IngestResult(
            status=IngestStatus.DUPLICATE,
            tenant_id=tenant_id,
            identifier_value=identifier_value,
            observation=observation,
        )

    # ── 4. Persistance — le sink tranche, et ses pannes remontent ───
    #
    # `created=False` signifie que la contrainte d'unicité a rattrapé un doublon
    # arrivé entre-temps. C'est le cas qui refermait la course : deux appelants
    # concurrents passent tous deux l'étape 3, appellent tous deux `store()`, la
    # base n'en laisse entrer qu'un, et l'autre ressort DUPLICATE au lieu de
    # créer une seconde ligne.
    outcome = await sink.store(tenant_id, observation)

    if not outcome.created:
        logger.info(
            "biomed.ingest.duplicate",
            extra={
                "tenant": tenant_id,
                "identifier_value": identifier_value,
                "patient": patient_hash,
                # Distinguer les deux détections rend la course OBSERVABLE en
                # production : un taux non nul de `store` signifie que des
                # écritures concurrentes arrivent réellement, et que c'est bien
                # la contrainte de base qui tient l'unicité.
                "detected_at": "store",
            },
        )
        return IngestResult(
            status=IngestStatus.DUPLICATE,
            tenant_id=tenant_id,
            identifier_value=identifier_value,
            observation=observation,
            storage_id=outcome.storage_id,
        )

    logger.info(
        "biomed.ingest.accepted",
        extra={
            "tenant": tenant_id,
            "metric_key": reading.metric_key,
            "identifier_value": identifier_value,
            "patient": patient_hash,
            "observation_status": observation.status,
        },
    )
    return IngestResult(
        status=IngestStatus.ACCEPTED,
        tenant_id=tenant_id,
        identifier_value=identifier_value,
        observation=observation,
        storage_id=outcome.storage_id,
    )


async def ingest_batch(
    payloads: Iterable[Mapping[str, Any]],
    *,
    sink: ObservationSink,
    tenant_id: str,
    pseudonymizer: Pseudonymizer,
    identifier_base_system: str = DEFAULT_IDENTIFIER_BASE_SYSTEM,
) -> list[IngestResult]:
    """Ingère un lot pour UN tenant, séquentiellement.

    Un lot appartient à un seul tenant : mélanger des tenants dans un même appel
    obligerait à porter la portée mesure par mesure, et la première distraction
    la perdrait. Draine une file par tenant.

    Une mesure refusée n'interrompt pas le lot : chaque entrée a son résultat.

    Séquentiel, mais **pas** pour garantir l'unicité : ce séquencement ne protège
    que d'un lot, jamais de plusieurs workers concurrents, qui est le cas normal
    en production. L'unicité vient de la contrainte de base portée par le sink
    (voir `ObservationSink`). Le séquencement ne fait que borner la charge et
    rendre l'ordre des résultats prévisible.
    """
    return [
        await ingest_reading(
            payload,
            sink=sink,
            tenant_id=tenant_id,
            pseudonymizer=pseudonymizer,
            identifier_base_system=identifier_base_system,
        )
        for payload in payloads
    ]
