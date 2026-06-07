#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRIPE PRICE MAPPING — Généré automatiquement par StripeProductAgent
Dernière mise à jour : 2026-04-07 23:07:42
Produits actifs : 22

NE PAS MODIFIER MANUELLEMENT.
"""


STRIPE_PRICE_MAP = {
    # ── À LA CARTE ──
    'agents_ia_growth': 'price_1TH0qbFijambRNPlGAXkNjoe',    # Agents IA Growth — 99€/month
    'agents_ia_starter': 'price_1TH0qaFijambRNPlRxI6VxAe',    # Agents IA Starter — 49€/month
    'audit_ia': 'price_1TJSDsFijambRNPlpc9QyLBs',    # Audit IA — 88€
    'logo_id': 'price_1TH0qeFijambRNPlpnIquk7B',    # Logo / Identité Visuelle — 197€
    'oracle': 'price_1TH0qfFijambRNPlZoN8F1Iu',    # Oracle — 49€/month
    'site_web': 'price_1TH0qaFijambRNPlKxefJxN5',    # Site Web — 797€
    'tunnel': 'price_1TH0qcFijambRNPlVuH2LpY5',    # Tunnel de Vente — 250€

    # ── MAINTENANCE ──
    'maintenance_empire': 'price_1TH0qhFijambRNPlQBuqVbm7',    # Maintenance Empire — 147€/month
    'maintenance_pro': 'price_1TH0qhFijambRNPl2Ai6wNKr',    # Maintenance Pro — 97€/month
    'maintenance_std': 'price_1TH0qgFijambRNPlUjKuTEcw',    # Maintenance Standard — 49€/month
    'maintenance_titan': 'price_1TH0qiFijambRNPlZ5XruSMf',    # Maintenance Titan — 297€/month

    # ── PACKS ──
    'pack_ascension': 'price_1TH0qXFijambRNPlZ0PugcwA',    # PACK ASCENSION — 1497€
    'pack_empire': 'price_1TJUvkFijambRNPlVgrVs07H',    # PACK EMPIRE — 147€
    'pack_fondation': 'price_1TJJVEFijambRNPlqVB8Ylnd',    # PACK FONDATION — 797€
    'pack_titan': 'price_1TJiigFijambRNPlfX5TdBR0',    # Offre Titan — 297.0€

    # ── PLANS SaaS ──
    'plan_commission_only': 'price_1TH0qjFijambRNPlgq1g7asL',    # Commission Only — 0€/month
    'plan_enterprise': 'price_1TH0qmFijambRNPlufDSojS3',    # Enterprise — 299€/month
    'plan_growth': 'price_1TH0qlFijambRNPlzHZBKS7w',    # Growth — 99€/month
    'plan_starter': 'price_1TH0qkFijambRNPlLJfDvsRG',    # Starter — 49€/month

    # ── REVENDEUR ──
    'reseller_agence': 'price_1TH0qnFijambRNPlh87qsHcH',    # Revendeur — Agence — 297€
    'reseller_apporteur': 'price_1TH0qnFijambRNPlbjUmvlCU',    # Revendeur — Apporteur d'affaires — 0€/month
    'reseller_partenaire': 'price_1TH0qoFijambRNPlhr6vypxb',    # Revendeur — Partenaire Premium — 997€

}


# Mapping inverse
PRICE_TO_PRODUCT = {v: k for k, v in STRIPE_PRICE_MAP.items()}


def get_product_id_from_stripe(stripe_price_id: str) -> str:
    return PRICE_TO_PRODUCT.get(stripe_price_id, '')


def get_stripe_price(product_id: str) -> str:
    return STRIPE_PRICE_MAP.get(product_id, '')
