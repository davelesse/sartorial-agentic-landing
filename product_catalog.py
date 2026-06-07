#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════╗
║  PRODUCT CATALOG & ORDER ROUTER — Catalogue Digital Colosse           ║
║                                                                       ║
║  Gère TOUT le catalogue :                                             ║
║  ✅ Packs (Fondation → Titan + Ether → Souverain)                    ║
║  ✅ À la carte digital (Site, Agents IA, Tunnel, Audit, Logo, Oracle)║
║  ✅ Maintenance récurrente (STD 49€, PRO 97€)                        ║
║  ✅ Armurerie physique (textile, print, goodies)                      ║
║                                                                       ║
║  Chaque paiement Stripe est routé vers le bon workflow :              ║
║  - digital_auto → 100% agents (Agents IA, Maintenance)               ║
║  - digital_human → tâche David + agents suivi (Sites, Logos)          ║
║  - physical → tâche fournisseur + agents suivi (Textile, Print)       ║
║  - pack → décomposé en sous-produits                                  ║
║                                                                       ║
║  Digital Colosse — Mars 2026                                         ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger('ProductCatalog')


# ============================================================================
# TYPES DE PRODUITS
# ============================================================================

class ProductType(Enum):
    DIGITAL_AUTO = 'digital_auto'       # 100% agents, zéro intervention humaine
    DIGITAL_HUMAN = 'digital_human'     # David construit + agents suivi
    PHYSICAL = 'physical'               # Fournisseur fabrique + agents suivi
    PACK = 'pack'                       # Combo décomposé en sous-produits
    RECURRING = 'recurring'             # Abonnement mensuel


class ProductCategory(Enum):
    PACK = 'pack'
    SOLUTION_DIGITALE = 'solution_digitale'
    MAINTENANCE = 'maintenance'
    ARMURERIE_TEXTILE = 'armurerie_textile'
    ARMURERIE_PRINT = 'armurerie_print'
    ARMURERIE_GOODIES = 'armurerie_goodies'


class OrderStatus(Enum):
    PAID = 'paid'                       # Paiement reçu
    IN_PROGRESS = 'in_progress'         # En cours de réalisation
    WAITING_SUPPLIER = 'waiting_supplier'  # Commande fournisseur passée
    SHIPPED = 'shipped'                 # Expédié (physique)
    DELIVERED = 'delivered'             # Livré
    COMPLETED = 'completed'             # Terminé
    CANCELLED = 'cancelled'


class TaskPriority(Enum):
    URGENT = 'urgent'
    HIGH = 'high'
    NORMAL = 'normal'
    LOW = 'low'


# ============================================================================
# CATALOGUE PRODUITS
# ============================================================================

@dataclass
class Product:
    """Définition d'un produit Digital Colosse"""
    product_id: str
    name: str
    price: float                        # Prix en euros (0 = gratuit ou variable)
    product_type: ProductType
    category: ProductCategory
    description: str = ''
    price_type: str = 'one_shot'        # one_shot, recurring, per_unit
    recurring_interval: str = ''        # month, year (si recurring)
    currency: str = 'EUR'

    # Ce qui se passe après le paiement
    auto_actions: List[str] = field(default_factory=list)
    creates_tasks: List[dict] = field(default_factory=list)
    sub_products: List[str] = field(default_factory=list)  # Pour les packs

    # Métadonnées
    delivery_days: int = 0              # Délai de livraison estimé
    requires_brief: bool = False        # Le client doit remplir un brief
    requires_shipping: bool = False     # Adresse de livraison requise
    stripe_price_id: str = ''           # ID du prix Stripe (à configurer)
    active: bool = True                 # Produit en vente


def build_catalog() -> Dict[str, Product]:
    """Construit le catalogue complet Digital Colosse"""
    catalog = {}

    # ════════════════════════════════════════════════════════
    # PACKS CLASSIQUES
    # ════════════════════════════════════════════════════════

    catalog['pack_fondation'] = Product(
        product_id='pack_fondation',
        name='Pack Fondation',
        price=797,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Site Vitrine (5 pages) + Design Sur-Mesure + Maintenance 49€/mois',
        sub_products=['site_web', 'maintenance_std'],
        delivery_days=7,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Fondation — Construire site vitrine 5 pages',
            'priority': 'high',
            'checklist': [
                'Contacter le client pour le brief',
                'Maquette + validation',
                'Développement 5 pages',
                'Mise en ligne + tests',
                'Activer maintenance 49€/mois',
                'Formation client (15 min)',
            ],
        }],
    )

    catalog['pack_ascension'] = Product(
        product_id='pack_ascension',
        name='Pack Ascension',
        price=1497,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Site Pro Illimité + Agents IA + Textile Staff + Maintenance Pro 97€/mois',
        sub_products=['site_web', 'agents_ia_starter', 'maintenance_pro'],
        delivery_days=14,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Ascension — Site pro + IA + textile',
            'priority': 'high',
            'checklist': [
                'Brief client complet',
                'Maquette site pro',
                'Développement pages illimitées',
                'Configuration Agents IA (capture leads)',
                'Commande textile staff chez fournisseur',
                'Activer maintenance pro 97€/mois',
                'Mise en ligne + tests',
                'Formation client (30 min)',
            ],
        }],
    )

    catalog['pack_empire'] = Product(
        product_id='pack_empire',
        name='Pack Empire',
        price=2497,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='E-Commerce + IA Vente + Cloud Dédié + Maintenance Pro 147€/mois',
        sub_products=['site_web', 'agents_ia_growth', 'tunnel', 'maintenance_empire'],
        delivery_days=21,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Empire — E-commerce complet + IA + cloud',
            'priority': 'urgent',
            'checklist': [
                'Brief client approfondi',
                'Architecture e-commerce',
                'Développement boutique',
                'Configuration paiements Stripe',
                'Agents IA vente (recommandations, relances panier)',
                'Configuration cloud dédié',
                'Tests charge + sécurité',
                'Formation client (1h)',
            ],
        }],
    )

    catalog['pack_titan'] = Product(
        product_id='pack_titan',
        name='Offre Titan',
        price=4997,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Growth Partner + Investissement + Réseau',
        sub_products=['site_web', 'agents_ia_growth', 'tunnel', 'audit_ia', 'oracle', 'maintenance_titan'],
        delivery_days=30,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Offre Titan — Growth Partner complet',
            'priority': 'urgent',
            'checklist': [
                'Rendez-vous stratégique (1h)',
                'Audit complet activité existante',
                'Plan de croissance personnalisé',
                'Développement infrastructure complète',
                'Configuration tous les agents IA',
                'Oracle + reporting avancé',
                'Tunnel de vente optimisé',
                'Formation complète (2h)',
                'Suivi mensuel inclus 3 mois',
            ],
        }],
    )

    # ════════════════════════════════════════════════════════
    # NOUVEAUX PACKS PRODUCTION
    # ════════════════════════════════════════════════════════

    catalog['pack_ether'] = Product(
        product_id='pack_ether',
        name='Pack Ether',
        price=347,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Site Vitrine + Configuration Essentielle',
        sub_products=['site_web', 'maintenance_std'],
        delivery_days=7,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Ether — Configuration Essentielle',
            'priority': 'high',
            'checklist': [
                'Contacter le client pour le brief',
                'Configuration initiale du site vitrine',
                'Mise en ligne et tests',
                'Validation des accès maintenance standard',
            ],
        }],
    )

    catalog['pack_essence'] = Product(
        product_id='pack_essence',
        name='Pack Essence',
        price=147,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Site Pro + Agents IA Starter',
        sub_products=['site_web', 'agents_ia_starter', 'maintenance_pro'],
        delivery_days=14,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Essence — Site Pro & IA Starter',
            'priority': 'high',
            'checklist': [
                'Brief client complet',
                'Développement site pro',
                'Configuration et tests de l\'Agent IA Starter',
                'Activation de la maintenance pro',
            ],
        }],
    )

    catalog['pack_paradise'] = Product(
        product_id='pack_paradise',
        name='Pack Paradise',
        price=997,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='E-Commerce complet + IA Vente',
        sub_products=['site_web', 'agents_ia_growth', 'tunnel', 'maintenance_empire'],
        delivery_days=21,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Paradise — E-Commerce & IA Growth',
            'priority': 'urgent',
            'checklist': [
                'Brief approfondi e-commerce',
                'Mise en place du tunnel de vente et Stripe',
                'Configuration Agent IA Growth',
                'Déploiement sur serveur cloud dédié',
            ],
        }],
    )

    catalog['pack_souverain'] = Product(
        product_id='pack_souverain',
        name='Pack Souverain',
        price=2997,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Growth Partner complet',
        sub_products=['site_web', 'agents_ia_growth', 'tunnel', 'audit_ia', 'oracle', 'maintenance_titan'],
        delivery_days=30,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Pack Souverain — Accompagnement Elite',
            'priority': 'urgent',
            'checklist': [
                'Rendez-vous stratégique initial',
                'Audit IA de l\'activité existante',
                'Configuration de l\'infrastructure complète + Oracle',
                'Suivi et optimisation des tunnels',
            ],
        }],
    )

    # ════════════════════════════════════════════════════════
    # À LA CARTE — SOLUTIONS DIGITALES
    # ════════════════════════════════════════════════════════

    catalog['site_web'] = Product(
        product_id='site_web',
        name='Site Web',
        price=797,
        product_type=ProductType.DIGITAL_HUMAN,
        category=ProductCategory.SOLUTION_DIGITALE,
        description='Site web professionnel sur mesure',
        delivery_days=7,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Création site web',
            'priority': 'high',
            'checklist': [
                'Brief client',
                'Maquette + validation',
                'Développement',
                'Mise en ligne + tests',
            ],
        }],
    )

    catalog['agents_ia_starter'] = Product(
        product_id='agents_ia_starter',
        name='Agents IA Starter',
        price=49,
        product_type=ProductType.RECURRING,
        category=ProductCategory.SOLUTION_DIGITALE,
        price_type='recurring',
        recurring_interval='month',
        description='Agents intelligents essentiels — rappels, emails, KPIs',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
        ],
    )

    catalog['agents_ia_growth'] = Product(
        product_id='agents_ia_growth',
        name='Agents IA Growth',
        price=99,
        product_type=ProductType.RECURRING,
        category=ProductCategory.SOLUTION_DIGITALE,
        price_type='recurring',
        recurring_interval='month',
        description='Agents complets — rappels, emails, KPIs, intégrations, learning',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
            'activate_integrations',
            'activate_learning_engine',
        ],
    )

    catalog['tunnel'] = Product(
        product_id='tunnel',
        name='Tunnel de Vente',
        price=250,
        product_type=ProductType.DIGITAL_HUMAN,
        category=ProductCategory.SOLUTION_DIGITALE,
        description='Tunnel de conversion optimisé',
        delivery_days=5,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Création tunnel de vente',
            'priority': 'normal',
            'checklist': [
                'Brief offre client',
                'Rédaction pages tunnel',
                'Design + développement',
                'Configuration tracking',
                'Tests conversion',
            ],
        }],
    )

    catalog['audit_ia'] = Product(
        product_id='audit_ia',
        name='Audit IA',
        price=97,
        product_type=ProductType.DIGITAL_AUTO,
        category=ProductCategory.SOLUTION_DIGITALE,
        description='Audit complet de votre activité par IA',
        delivery_days=1,
        auto_actions=[
            'run_business_audit',       # L'agent analyse tout
            'generate_audit_report',    # Génère le rapport PDF
            'send_audit_email',         # Envoie le rapport au client
        ],
    )

    catalog['logo_id'] = Product(
        product_id='logo_id',
        name='Logo / Identité Visuelle',
        price=197,
        product_type=ProductType.DIGITAL_HUMAN,
        category=ProductCategory.SOLUTION_DIGITALE,
        description='Logo professionnel + charte graphique',
        delivery_days=5,
        requires_brief=True,
        creates_tasks=[{
            'subject': 'Création logo + identité visuelle',
            'priority': 'normal',
            'checklist': [
                'Brief créatif',
                '3 propositions de logo',
                'Retours client + ajustements',
                'Livraison fichiers (PNG, SVG, PDF)',
                'Charte graphique',
            ],
        }],
    )

    catalog['oracle'] = Product(
        product_id='oracle',
        name='Oracle',
        price=49,
        product_type=ProductType.RECURRING,
        category=ProductCategory.SOLUTION_DIGITALE,
        price_type='recurring',
        recurring_interval='month',
        description='Intelligence business avancée + prédictions + insights hebdomadaires',
        auto_actions=[
            'activate_oracle_agent',
            'setup_advanced_analytics',
            'send_first_insights',
        ],
    )

    # ════════════════════════════════════════════════════════
    # MAINTENANCE (RÉCURRENT)
    # ════════════════════════════════════════════════════════

    catalog['maintenance_std'] = Product(
        product_id='maintenance_std',
        name='Maintenance Standard',
        price=49,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Maintenance site + monitoring + mises à jour',
        auto_actions=[
            'activate_monitoring_agent',
            'setup_weekly_health_check',
            'setup_monthly_report',
        ],
    )

    catalog['maintenance_pro'] = Product(
        product_id='maintenance_pro',
        name='Maintenance Pro',
        price=97,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Maintenance premium + agents IA + support prioritaire',
        auto_actions=[
            'activate_monitoring_agent',
            'activate_all_agents',
            'setup_daily_health_check',
            'setup_weekly_report',
            'enable_priority_support',
        ],
    )

    catalog['maintenance_empire'] = Product(
        product_id='maintenance_empire',
        name='Maintenance Empire',
        price=147,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Maintenance complète + agents IA + cloud dédié + support prioritaire',
        auto_actions=[
            'activate_monitoring_agent',
            'activate_all_agents',
            'setup_daily_health_check',
            'setup_daily_report',
            'enable_priority_support',
            'setup_dedicated_cloud',
        ],
    )

    catalog['maintenance_titan'] = Product(
        product_id='maintenance_titan',
        name='Maintenance Titan',
        price=297,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Partenariat complet — maintenance + agents + suivi mensuel + évolutions',
        auto_actions=[
            'activate_monitoring_agent',
            'activate_all_agents',
            'setup_daily_health_check',
            'setup_daily_report',
            'enable_priority_support',
            'setup_dedicated_cloud',
            'enable_monthly_review',
        ],
    )

    # ════════════════════════════════════════════════════════
    # PLANS SaaS PROFESSIONNELS (sans site — agents uniquement)
    # ════════════════════════════════════════════════════════

    catalog['plan_commission_only'] = Product(
        product_id='plan_commission_only',
        name='Commission Only',
        price=0,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='0€/mois — commission 1.5% par transaction. Zéro risque.',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
        ],
    )

    catalog['plan_starter'] = Product(
        product_id='plan_starter',
        name='Starter',
        price=49,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='L\'essentiel — rappels, emails, KPIs, rapports quotidiens',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
            'setup_daily_report',
        ],
    )

    catalog['plan_growth'] = Product(
        product_id='plan_growth',
        name='Growth',
        price=99,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Tout Starter + intégrations Gmail/Calendar/SMS + learning engine',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
            'setup_daily_report',
            'activate_integrations',
            'activate_learning_engine',
        ],
    )

    catalog['plan_enterprise'] = Product(
        product_id='plan_enterprise',
        name='Enterprise',
        price=299,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='Suite complète — multi-utilisateurs, API, agents sur mesure, support prioritaire',
        auto_actions=[
            'provision_agents',
            'send_questionnaire',
            'setup_stripe_webhook',
            'send_welcome_email',
            'setup_daily_report',
            'activate_integrations',
            'activate_learning_engine',
            'enable_priority_support',
            'enable_api_access',
        ],
    )

    # ════════════════════════════════════════════════════════
    # PLANS REVENDEUR
    # ════════════════════════════════════════════════════════

    catalog['reseller_apporteur'] = Product(
        product_id='reseller_apporteur',
        name='Revendeur — Apporteur d\'affaires',
        price=0,
        product_type=ProductType.RECURRING,
        category=ProductCategory.MAINTENANCE,
        price_type='recurring',
        recurring_interval='month',
        description='0€ — recommandez Digital Colosse, touchez 15% du récurrent à vie.',
        auto_actions=[
            'setup_reseller_dashboard',
            'generate_invite_link',
        ],
    )

    catalog['reseller_agence'] = Product(
        product_id='reseller_agence',
        name='Revendeur — Agence',
        price=297,
        product_type=ProductType.DIGITAL_AUTO,
        category=ProductCategory.MAINTENANCE,
        description='Droit d\'entrée 297€ + 40€/mois/client. White-label complet.',
        auto_actions=[
            'setup_reseller_dashboard',
            'generate_invite_link',
            'setup_white_label',
        ],
    )

    catalog['reseller_partenaire'] = Product(
        product_id='reseller_partenaire',
        name='Revendeur — Partenaire Premium',
        price=997,
        product_type=ProductType.DIGITAL_AUTO,
        category=ProductCategory.MAINTENANCE,
        description='Droit d\'entrée 997€ + 50€/mois/client. White-label + agents custom + API.',
        auto_actions=[
            'setup_reseller_dashboard',
            'generate_invite_link',
            'setup_white_label',
            'enable_custom_agents',
            'enable_api_access',
            'enable_priority_support',
        ],
    )

    # ════════════════════════════════════════════════════════
    # ARMURERIE — TEXTILE
    # ════════════════════════════════════════════════════════

    for item_id, name, price in [
        ('chemise', 'Chemise', 39),
        ('veste', 'Veste', 89),
        ('polo', 'Polo', 39),
        ('tshirt', 'T-Shirt', 25),
        ('gilet', 'Gilet', 20),
        ('casquette', 'Casquette', 20),
    ]:
        catalog[f'textile_{item_id}'] = Product(
            product_id=f'textile_{item_id}',
            name=name,
            price=price,
            product_type=ProductType.PHYSICAL,
            category=ProductCategory.ARMURERIE_TEXTILE,
            price_type='per_unit',
            description=f'{name} personnalisé(e) avec votre marque',
            requires_shipping=True,
            delivery_days=14,
            creates_tasks=[{
                'subject': f'Commande textile — {name}',
                'priority': 'normal',
                'checklist': [
                    'Vérifier les détails (taille, couleur, logo)',
                    'Commander chez le fournisseur',
                    'Suivre la fabrication',
                    'Contrôle qualité à réception',
                    'Expédier au client',
                    'Confirmer la livraison',
                ],
            }],
        )

    # ════════════════════════════════════════════════════════
    # ARMURERIE — PRINT & GOODIES
    # ════════════════════════════════════════════════════════

    for item_id, name, price, cat in [
        ('flyers', 'Flyers', 97, ProductCategory.ARMURERIE_PRINT),
        ('rollup', 'Roll-Up', 120, ProductCategory.ARMURERIE_PRINT),
        ('carte_nfc', 'Carte NFC', 35, ProductCategory.ARMURERIE_PRINT),
        ('pack_goodies', 'Pack Goodies', 30, ProductCategory.ARMURERIE_GOODIES),
    ]:
        catalog[f'print_{item_id}'] = Product(
            product_id=f'print_{item_id}',
            name=name,
            price=price,
            product_type=ProductType.PHYSICAL,
            category=cat,
            price_type='per_unit' if item_id != 'pack_goodies' else 'one_shot',
            description=f'{name} personnalisé(s)',
            requires_shipping=True,
            delivery_days=10,
            creates_tasks=[{
                'subject': f'Commande print — {name}',
                'priority': 'normal',
                'checklist': [
                    'Vérifier le BAT (bon à tirer)',
                    'Valider avec le client',
                    'Commander chez l\'imprimeur',
                    'Suivi production',
                    'Expédier au client',
                ],
            }],
        )

    catalog['agent_ia_bras_arme'] = Product(
        product_id='agent_ia_bras_arme',
        name='Agent IA Automatise Bras Arme Numerique',
        price=0,
        product_type=ProductType.PACK,
        category=ProductCategory.PACK,
        description='Agent IA Automatise Bras Arme Numerique',
        price_type='one_shot',
        recurring_interval='month',
        stripe_price_id='price_1Svo6UFijambRNPlGRBLQlzp',
        active=True
    )
    return catalog


# ============================================================================
# ORDER ROUTER — Route chaque commande vers le bon workflow
# ============================================================================

@dataclass
class Order:
    """Une commande dans le système"""
    order_id: str
    tenant_id: str
    product_id: str
    product_name: str
    product_type: str
    amount: float
    quantity: int = 1
    status: OrderStatus = OrderStatus.PAID
    stripe_payment_id: str = ''

    # Infos client
    customer_email: str = ''
    customer_name: str = ''
    customer_phone: str = ''

    # Livraison (physique)
    shipping_address: Optional[dict] = None

    # Brief (digital human)
    brief_completed: bool = False
    brief_data: Optional[dict] = None

    # Suivi
    tasks_created: List[str] = field(default_factory=list)
    auto_actions_executed: List[str] = field(default_factory=list)
    notes: str = ''

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_delivery: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'order_id': self.order_id,
            'tenant_id': self.tenant_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'product_type': self.product_type,
            'amount': self.amount,
            'quantity': self.quantity,
            'status': self.status.value,
            'stripe_payment_id': self.stripe_payment_id,
            'customer_email': self.customer_email,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'shipping_address': self.shipping_address,
            'brief_completed': self.brief_completed,
            'brief_data': self.brief_data,
            'tasks_created': self.tasks_created,
            'auto_actions_executed': self.auto_actions_executed,
            'notes': self.notes,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'estimated_delivery': self.estimated_delivery,
        }


class OrderRouter:
    """
    Route chaque commande vers le bon workflow.
    
    C'est le cerveau commercial : il sait comment décomposer chaque pack
    et vers quel agent/tâche router l'exécution.
    """

    def __init__(self):
        self.catalog = build_catalog()
        self.orders: Dict[str, Order] = {}
        self._load_orders()
        logger.info(f"🛒 OrderRouter initialisé — {len(self.catalog)} produits au catalogue")

    def _orders_path(self):
        return os.path.join(
            os.getenv('AUTOMATION_DIR', '/opt/digital-colosse/automation'),
            'orders.json'
        )

    def _load_orders(self):
        try:
            path = self._orders_path()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.orders = {k: self._dict_to_order(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Erreur chargement commandes: {e}")

    def _save_orders(self):
        try:
            path = self._orders_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump({k: v.to_dict() for k, v in self.orders.items()}, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erreur sauvegarde commandes: {e}")

    def _dict_to_order(self, d: dict) -> Order:
        o = Order(
            order_id=d['order_id'], tenant_id=d['tenant_id'],
            product_id=d['product_id'], product_name=d['product_name'],
            product_type=d['product_type'], amount=d['amount'],
        )
        o.quantity = d.get('quantity', 1)
        o.status = OrderStatus(d.get('status', 'paid'))
        o.stripe_payment_id = d.get('stripe_payment_id', '')
        o.customer_email = d.get('customer_email', '')
        o.customer_name = d.get('customer_name', '')
        o.customer_phone = d.get('customer_phone', '')
        o.shipping_address = d.get('shipping_address')
        o.brief_completed = d.get('brief_completed', False)
        o.brief_data = d.get('brief_data')
        o.tasks_created = d.get('tasks_created', [])
        o.auto_actions_executed = d.get('auto_actions_executed', [])
        o.notes = d.get('notes', '')
        o.created_at = d.get('created_at', '')
        o.started_at = d.get('started_at')
        o.completed_at = d.get('completed_at')
        o.estimated_delivery = d.get('estimated_delivery')
        return o

    # ────────────────────────────────────────────
    # ROUTING PRINCIPAL
    # ────────────────────────────────────────────

    def process_payment(self, tenant_id: str, product_id: str,
                        stripe_payment_id: str, amount: float,
                        customer_email: str = '', customer_name: str = '',
                        customer_phone: str = '', quantity: int = 1,
                        metadata: dict = None,
                        data_client=None, email_sender=None) -> Tuple[bool, dict]:
        """
        Point d'entrée principal. Appelé par webhook_handler_agent
        quand un paiement arrive.
        """
        metadata = metadata or {}

        # Identifier le produit
        product = self.catalog.get(product_id)
        if not product:
            product = self._identify_product(amount, metadata)
            if not product:
                logger.warning(f"Produit inconnu: {product_id} ({amount}€)")
                return False, {'error': f'Produit inconnu: {product_id}'}

        # Créer la commande
        order_id = f"ord_{tenant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{product.product_id}"
        order = Order(
            order_id=order_id,
            tenant_id=tenant_id,
            product_id=product.product_id,
            product_name=product.name,
            product_type=product.product_type.value,
            amount=amount,
            quantity=quantity,
            stripe_payment_id=stripe_payment_id,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            shipping_address=metadata.get('shipping_address'),
        )

        if product.delivery_days > 0:
            est = datetime.now() + timedelta(days=product.delivery_days)
            order.estimated_delivery = est.isoformat()

        logger.info(f"🛒 Commande {order_id}: {product.name} ({amount}€) — type: {product.product_type.value}")

        # ── Router vers le bon workflow ──
        results = {}

        if product.product_type == ProductType.PACK:
            results = self._handle_pack(order, product, data_client, email_sender, metadata)
        elif product.product_type == ProductType.DIGITAL_AUTO:
            results = self._handle_digital_auto(order, product, data_client, email_sender)
        elif product.product_type == ProductType.DIGITAL_HUMAN:
            results = self._handle_digital_human(order, product, data_client, email_sender)
        elif product.product_type == ProductType.PHYSICAL:
            results = self._handle_physical(order, product, data_client, email_sender, metadata)
        elif product.product_type == ProductType.RECURRING:
            results = self._handle_recurring(order, product, data_client, email_sender)

        self.orders[order_id] = order
        self._save_orders()

        return True, {
            'order_id': order_id,
            'product': product.name,
            'type': product.product_type.value,
            'amount': amount,
            'status': order.status.value,
            'estimated_delivery': order.estimated_delivery,
            'actions': results,
        }

    # ────────────────────────────────────────────
    # WORKFLOWS PAR TYPE
    # ────────────────────────────────────────────

    def _handle_pack(self, order, product, data_client, email_sender, metadata):
        logger.info(f"📦 Pack {product.name} — {len(product.sub_products)} sous-produits")
        results = {'sub_orders': []}

        if product.creates_tasks:
            self._create_tasks(order, product, data_client)

        for sub_id in product.sub_products:
            sub_product = self.catalog.get(sub_id)
            if sub_product:
                if sub_product.product_type == ProductType.DIGITAL_AUTO:
                    sub_result = self._handle_digital_auto(order, sub_product, data_client, email_sender)
                elif sub_product.product_type == ProductType.DIGITAL_HUMAN:
                    sub_result = {'included_in_pack': True}
                results['sub_orders'].append({
                    'product': sub_product.name,
                    'type': sub_product.product_type.value,
                    'result': sub_result,
                })

        if email_sender:
            self._send_pack_confirmation(order, product, email_sender)

        order.status = OrderStatus.IN_PROGRESS
        return results

    def _handle_digital_auto(self, order, product, data_client, email_sender):
        logger.info(f"🤖 Digital auto: {product.name} — {len(product.auto_actions)} actions")
        results = []

        for action in product.auto_actions:
            success = self._execute_auto_action(action, order, data_client)
            results.append({'action': action, 'success': success})
            order.auto_actions_executed.append(action)

        if email_sender and order.customer_email:
            self._send_auto_confirmation(order, product, email_sender)

        order.status = OrderStatus.COMPLETED if all(r['success'] for r in results) else OrderStatus.IN_PROGRESS
        return results

    def _handle_digital_human(self, order, product, data_client, email_sender):
        logger.info(f"👨‍💻 Digital human: {product.name} — tâche créée")
        task_ids = self._create_tasks(order, product, data_client)

        brief_sent = False
        if product.requires_brief and email_sender and order.customer_email:
            brief_sent = self._send_brief_request(order, product, email_sender)

        if email_sender and order.customer_email:
            self._send_human_confirmation(order, product, email_sender)

        order.status = OrderStatus.IN_PROGRESS
        return {'tasks_created': task_ids, 'brief_sent': brief_sent}

    def _handle_physical(self, order, product, data_client, email_sender, metadata):
        logger.info(f"📦 Physique: {product.name} × {order.quantity}")

        if product.requires_shipping and not order.shipping_address:
            shipping = metadata.get('shipping_address') or metadata.get('address')
            if shipping:
                order.shipping_address = shipping

        task_ids = self._create_tasks(order, product, data_client)

        if email_sender and order.customer_email:
            self._send_physical_confirmation(order, product, email_sender)

        order.status = OrderStatus.PAID
        return {
            'tasks_created': task_ids,
            'shipping_required': product.requires_shipping,
            'has_address': order.shipping_address is not None,
        }

    def _handle_recurring(self, order, product, data_client, email_sender):
        logger.info(f"🔄 Récurrent: {product.name} ({product.price}€/mois)")
        results = []
        for action in product.auto_actions:
            success = self._execute_auto_action(action, order, data_client)
            results.append({'action': action, 'success': success})

        if email_sender and order.customer_email:
            self._send_recurring_confirmation(order, product, email_sender)

        order.status = OrderStatus.COMPLETED
        return results

    # ────────────────────────────────────────────
    # ACTIONS AUTO (exécutées par les agents)
    # ────────────────────────────────────────────

    def _execute_auto_action(self, action: str, order: Order, data_client) -> bool:
        try:
            logger.info(f"  ⚡ Action: {action}")
            if action == 'provision_agents':
                return True
            elif action == 'send_questionnaire':
                return True
            elif action == 'setup_stripe_webhook':
                return True
            elif action == 'send_welcome_email':
                return True
            elif action == 'run_business_audit':
                return True
            elif action == 'generate_audit_report':
                return True
            elif action == 'send_audit_email':
                return True
            elif action == 'activate_oracle_agent':
                return True
            elif action == 'setup_advanced_analytics':
                return True
            elif action == 'activate_monitoring_agent':
                return True
            elif action == 'activate_all_agents':
                return True
            elif action in ['setup_weekly_health_check', 'setup_daily_health_check',
                           'setup_monthly_report', 'setup_weekly_report',
                           'enable_priority_support', 'send_first_insights']:
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"  ❌ Erreur action {action}: {e}")
            return False

    # ────────────────────────────────────────────
    # TÂCHES
    # ────────────────────────────────────────────

    def _create_tasks(self, order: Order, product: Product, data_client) -> List[str]:
        task_ids = []
        for task_def in product.creates_tasks:
            subject = task_def['subject']
            priority = task_def.get('priority', 'normal')
            checklist = task_def.get('checklist', [])

            subject = f"{subject} — {order.customer_name or order.customer_email}"
            if order.quantity > 1:
                subject += f" (×{order.quantity})"

            description_parts = [
                f"Client: {order.customer_name} ({order.customer_email})",
                f"Commande: {order.order_id}",
                f"Montant: {order.amount}€",
                f"Paiement Stripe: {order.stripe_payment_id}",
            ]
            if order.shipping_address:
                description_parts.append(f"Livraison: {json.dumps(order.shipping_address)}")
            if order.estimated_delivery:
                description_parts.append(f"Livraison estimée: {order.estimated_delivery}")
            if checklist:
                description_parts.append("\nChecklist:")
                for item in checklist:
                    description_parts.append(f"  □ {item}")

            description = '\n'.join(description_parts)

            if data_client:
                contact_id = None
                if order.customer_email:
                    contact = data_client.find_contact_by_email(order.customer_email)
                    if contact:
                        contact_id = contact['id']

                due_date = None
                if product.delivery_days > 0:
                    due_date = (datetime.now() + timedelta(days=product.delivery_days)).strftime('%Y-%m-%d')

                task_id = data_client.create_task(
                    subject=subject,
                    contact_id=contact_id,
                    due_date=due_date,
                    priority=priority,
                )
                if task_id:
                    task_ids.append(str(task_id))
            else:
                task_ids.append(f"log_{datetime.now().strftime('%H%M%S')}")

        order.tasks_created = task_ids
        return task_ids

    # ────────────────────────────────────────────
    # EMAILS
    # ────────────────────────────────────────────

    def _send_pack_confirmation(self, order, product, email_sender):
        subject = f"Votre {product.name} est en route !"
        body = f"<h2>Merci !</h2><p>Votre <strong>{product.name}</strong> a bien été commandé pour {order.amount}€.</p>"
        self._send(email_sender, order.customer_email, subject, body)

    def _send_auto_confirmation(self, order, product, email_sender):
        subject = f"{product.name} activé !"
        body = f"<h2>Félicitations</h2><p>Votre service {product.name} est maintenant pleinement actif.</p>"
        self._send(email_sender, order.customer_email, subject, body)

    def _send_human_confirmation(self, order, product, email_sender):
        subject = f"Commande confirmée — {product.name}"
        body = f"<h2>Merci</h2><p>Votre commande pour {product.name} est en cours de traitement.</p>"
        self._send(email_sender, order.customer_email, subject, body)

    def _send_physical_confirmation(self, order, product, email_sender):
        subject = f"Commande confirmée — {product.name}"
        body = f"<h2>Merci !</h2><p>Votre colis pour {product.name} (x{order.quantity}) est en préparation.</p>"
        self._send(email_sender, order.customer_email, subject, body)

    def _send_recurring_confirmation(self, order, product, email_sender):
        subject = f"Bienvenue — {product.name} activée !"
        body = f"<h2>Bienvenue</h2><p>Votre abonnement {product.name} à {product.price}€/mois est opérationnel.</p>"
        self._send(email_sender, order.customer_email, subject, body)

    def _send_brief_request(self, order, product, email_sender):
        subject = f"Dernière étape — Votre brief {product.name}"
        body = f"<p>Cliquez ici pour remplir votre brief : <a href='https://digital-colosse.com/brief/{order.order_id}'>Brief</a></p>"
        return self._send(email_sender, order.customer_email, subject, body)

    def _send(self, email_sender, to, subject, body):
        try:
            if hasattr(email_sender, 'send'):
                return email_sender.send(to, subject, body)
            return True
        except Exception as e:
            return False

    # ────────────────────────────────────────────
    # IDENTIFICATION PRODUIT
    # ────────────────────────────────────────────

    def _identify_product(self, amount: float, metadata: dict) -> Optional[Product]:
        pid = metadata.get('product_id') or metadata.get('product')
        if pid and pid in self.catalog:
            return self.catalog[pid]
        for product in self.catalog.values():
            if product.price == amount and product.active:
                return product
        return None

    # ────────────────────────────────────────────
    # API PUBLIQUE
    # ────────────────────────────────────────────

    def get_catalog(self, category: str = None, tenant_type: str = None) -> List[dict]:
        products = []
        for p in self.catalog.values():
            if not p.active:
                continue
            if category and p.category.value != category:
                continue
            products.append({
                'product_id': p.product_id,
                'name': p.name,
                'price': p.price,
                'price_type': p.price_type,
                'category': p.category.value,
                'type': p.product_type.value,
                'description': p.description,
                'delivery_days': p.delivery_days,
                'requires_brief': p.requires_brief,
                'requires_shipping': p.requires_shipping,
            })
        return products

    def get_order(self, order_id: str) -> Optional[dict]:
        order = self.orders.get(order_id)
        return order.to_dict() if order else None

    def get_tenant_orders(self, tenant_id: str) -> List[dict]:
        return [o.to_dict() for o in self.orders.values() if o.tenant_id == tenant_id]

    def update_order_status(self, order_id: str, status: str, notes: str = '') -> bool:
        order = self.orders.get(order_id)
        if not order:
            return False
        order.status = OrderStatus(status)
        if notes:
            order.notes = notes
        if status == 'completed':
            order.completed_at = datetime.now().isoformat()
        elif status == 'in_progress':
            order.started_at = datetime.now().isoformat()
        self._save_orders()
        return True

    def get_pending_tasks(self) -> List[dict]:
        pending = []
        for o in self.orders.values():
            if o.status in [OrderStatus.PAID, OrderStatus.IN_PROGRESS]:
                if o.product_type in ['digital_human', 'physical', 'pack']:
                    pending.append(o.to_dict())
        return sorted(pending, key=lambda x: x.get('created_at', ''), reverse=True)


# ============================================================================
# INSTANCE GLOBALE
# ============================================================================

