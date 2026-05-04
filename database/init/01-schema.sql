-- ═══════════════════════════════════════════════════════════
-- SARTORIAL AGENTIC — Database Initialization
-- Multi-tenant schema setup
-- ═══════════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── USERS ──
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(50) DEFAULT 'client',  -- client, partner, admin
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── TENANTS ──
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(50) DEFAULT 'atelier',  -- atelier, manufacture, maison
    sectors TEXT[] DEFAULT '{}',          -- array of active sectors
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    subscription_status VARCHAR(50) DEFAULT 'trialing',
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── AGENTS ──
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    sector VARCHAR(50) NOT NULL,          -- transversal, automobile, immobilier, etc.
    category VARCHAR(50) NOT NULL,        -- prospection, catalog, analytics, etc.
    config_schema JSONB DEFAULT '{}',     -- JSON schema for agent configuration
    min_plan VARCHAR(50) DEFAULT 'atelier',
    is_active BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── TENANT AGENTS (junction — which agents are enabled per tenant) ──
CREATE TABLE IF NOT EXISTS tenant_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    is_enabled BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}',            -- tenant-specific agent config
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, agent_id)
);

-- ── TASKS (agent executions) ──
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── PARTNERS (resellers) ──
CREATE TABLE IF NOT EXISTS partners (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(50) DEFAULT 'associe',    -- associe, maison_partenaire
    commission_rate DECIMAL(5,2) DEFAULT 20.00,
    affiliate_code VARCHAR(50) UNIQUE NOT NULL,
    stripe_connect_id VARCHAR(255),
    total_earnings_cents INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── REFERRALS ──
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id UUID NOT NULL REFERENCES partners(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    commission_rate DECIMAL(5,2) NOT NULL,
    total_paid_cents INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(partner_id, tenant_id)
);

-- ── WAITLIST ──
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    source VARCHAR(100) DEFAULT 'landing',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── INDEXES ──
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_tenants_owner ON tenants(owner_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_stripe ON tenants(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_agents_tenant ON tenant_agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_partners_code ON partners(affiliate_code);
CREATE INDEX IF NOT EXISTS idx_referrals_partner ON referrals(partner_id);

-- ── SEED: Default Agents Catalog ──
INSERT INTO agents (name, slug, description, sector, category, min_plan) VALUES
  -- Transversal
  ('Stripe Manager',     'stripe-manager',     'Création, mise à jour et archivage automatique des produits et prix Stripe',       'transversal', 'billing',      'atelier'),
  ('Email Outreach',     'email-outreach',      'Séquences d''emails personnalisés avec relances intelligentes',                    'transversal', 'prospection',  'atelier'),
  ('Analytics Reporter', 'analytics-reporter',  'Tableaux de bord, rapports hebdomadaires, détection d''anomalies',                'transversal', 'analytics',    'atelier'),
  ('Content Creator',    'content-creator',     'Rédaction SEO, fiches produits, posts réseaux sociaux',                            'transversal', 'content',      'manufacture'),
  ('CRM Sync',           'crm-sync',            'Synchronisation bidirectionnelle avec les outils CRM existants',                   'transversal', 'integration',  'manufacture'),
  ('Chatbot White-Label','chatbot-whitelabel',  'Assistant conversationnel intégrable sur le site client',                           'transversal', 'support',      'manufacture'),

  -- Automobile
  ('Catalogue Véhicules','catalogue-vehicules', 'Import/export, mise à jour prix, photos, fiches techniques',                       'automobile',  'catalog',      'manufacture'),
  ('Lead Qualifier Auto','lead-qualifier-auto', 'Scoring des prospects, assignation automatique aux commerciaux',                    'automobile',  'prospection',  'manufacture'),
  ('SAV Prédictif',      'sav-predictif',       'Anticipation des besoins d''entretien, relances automatiques',                      'automobile',  'support',      'maison'),
  ('Comparateur Auto',   'comparateur-auto',    'Génération de comparatifs personnalisés pour le prospect',                          'automobile',  'content',      'maison'),

  -- Immobilier
  ('Matching Acheteur',  'matching-acheteur',   'Algorithme de correspondance acheteur/bien en temps réel',                          'immobilier',  'matching',     'manufacture'),
  ('Visite Virtuelle',   'visite-virtuelle',    'Planification et suivi des visites, feedback automatisé',                           'immobilier',  'planning',     'manufacture'),
  ('Estimation Marché',  'estimation-marche',   'Analyse comparative de marché pour estimation de prix',                             'immobilier',  'analytics',    'maison'),
  ('Agent Mandataire',   'agent-mandataire',    'Génération de mandats, suivi administratif',                                        'immobilier',  'admin',        'maison'),

  -- E-Commerce
  ('Fiche Produit SEO',  'fiche-produit-seo',   'Création automatisée avec SEO, variantes, photos',                                  'ecommerce',   'content',      'manufacture'),
  ('Prix Dynamique',     'prix-dynamique',      'Ajustement de prix selon la concurrence et la demande',                             'ecommerce',   'pricing',      'maison'),
  ('Retours & SAV',      'retours-sav',         'Gestion autonome des retours, génération de bons',                                  'ecommerce',   'support',      'manufacture'),
  ('Panier Abandonné',   'panier-abandonne',    'Relances intelligentes multi-canal',                                                'ecommerce',   'prospection',  'manufacture'),

  -- Beauté / Santé / Restauration
  ('Gestion Agenda',     'gestion-agenda',      'Gestion des RDV, créneaux, confirmations, rappels SMS/email',                       'beaute',      'planning',     'manufacture'),
  ('Fidélisation',       'fidelisation',        'Programmes de points, offres personnalisées, anniversaires',                        'beaute',      'retention',    'manufacture'),
  ('Réputation Online',  'reputation-online',   'Monitoring avis Google/TripAdvisor, réponses automatisées',                         'restauration','analytics',    'manufacture'),
  ('Menu Dynamique',     'menu-dynamique',      'Mise à jour dynamique, suggestions saisonnières',                                   'restauration','content',      'maison'),
  ('Suivi Patient',      'suivi-patient',       'Rappels de soins, suivi post-consultation',                                         'sante',       'support',      'manufacture')
ON CONFLICT DO NOTHING;
