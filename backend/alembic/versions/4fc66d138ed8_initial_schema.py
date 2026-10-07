"""initial schema - all CRM + lead-gen tables

Revision ID: 4fc66d138ed8
Revises: 
Create Date: 2026-09-25 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4fc66d138ed8"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres enum types must exist before the tables that use them.
    # (CreateTable DDL does not emit CREATE TYPE on its own.)
    op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'SALES_MANAGER', 'SALES_EXECUTIVE', 'VIEWER')")
    op.execute("CREATE TYPE leadstatus AS ENUM ('NEW', 'CONTACTED', 'REPLIED', 'INTERESTED', 'MEETING', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST')")
    op.execute("CREATE TYPE notificationtype AS ENUM ('LEAD_ASSIGNED', 'FOLLOWUP_DUE', 'FOLLOWUP_OVERDUE', 'MEETING_APPROACHING', 'PROPOSAL_ACCEPTED', 'DEAL_WON', 'DEAL_LOST')")
    op.execute("CREATE TYPE activitytype AS ENUM ('LEAD_CREATED', 'AUDIT_COMPLETED', 'PITCH_GENERATED', 'WHATSAPP_SENT', 'WHATSAPP_REPLY', 'CALL', 'EMAIL', 'NOTE', 'MEETING', 'FOLLOW_UP', 'STATUS_CHANGED', 'PROPOSAL_CREATED', 'PROPOSAL_SENT', 'DEAL_CREATED', 'DEAL_WON', 'DEAL_LOST')")
    op.execute("CREATE TYPE dealstage AS ENUM ('NEW', 'CONTACTED', 'REPLIED', 'INTERESTED', 'MEETING', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST')")
    op.execute("CREATE TYPE followuppriority AS ENUM ('LOW', 'MEDIUM', 'HIGH')")
    op.execute("CREATE TYPE followupstatus AS ENUM ('PENDING', 'COMPLETED', 'RESCHEDULED', 'CANCELLED')")
    op.execute("CREATE TYPE pitchchannel AS ENUM ('WHATSAPP', 'EMAIL', 'SMS')")
    op.execute("CREATE TYPE pitchstatus AS ENUM ('DRAFT', 'SENT', 'DELIVERED', 'READ', 'REPLIED', 'FAILED')")
    op.execute("CREATE TYPE proposalstatus AS ENUM ('DRAFT', 'SENT', 'VIEWED', 'ACCEPTED', 'REJECTED', 'EXPIRED')")

    op.execute("""
CREATE TABLE organizations (
	name VARCHAR(255) NOT NULL, 
	slug VARCHAR(255) NOT NULL, 
	plan VARCHAR(50) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);
""")
    op.execute("""
CREATE TABLE pipeline_stages (
	name VARCHAR(100) NOT NULL, 
	"order" INTEGER NOT NULL, 
	is_won_stage INTEGER, 
	is_lost_stage INTEGER, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE settings (
	key VARCHAR(150) NOT NULL, 
	value JSON NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE users (
	organization_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	role userrole NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	phone VARCHAR(50), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_org_email UNIQUE (organization_id, email), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE audit_logs (
	user_id UUID, 
	action VARCHAR(150) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id UUID, 
	changes JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE leads (
	business_name VARCHAR(255) NOT NULL, 
	category VARCHAR(150), 
	phone VARCHAR(50), 
	email VARCHAR(255), 
	website VARCHAR(500), 
	google_maps_url VARCHAR(1000), 
	google_place_id VARCHAR(255), 
	address TEXT, 
	city VARCHAR(150), 
	state VARCHAR(150), 
	country VARCHAR(150), 
	lead_score INTEGER, 
	website_score INTEGER, 
	opportunity_level VARCHAR(50), 
	estimated_deal_value_min NUMERIC(12, 2), 
	estimated_deal_value_max NUMERIC(12, 2), 
	status leadstatus NOT NULL, 
	assigned_to UUID, 
	next_followup_date DATE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE notifications (
	user_id UUID NOT NULL, 
	type notificationtype NOT NULL, 
	message TEXT NOT NULL, 
	is_read BOOLEAN NOT NULL, 
	link VARCHAR(500), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE activities (
	lead_id UUID NOT NULL, 
	user_id UUID, 
	type activitytype NOT NULL, 
	description TEXT, 
	metadata_json TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE audits (
	lead_id UUID NOT NULL, 
	overall_score INTEGER NOT NULL, 
	performance_score INTEGER, 
	seo_score INTEGER, 
	mobile_score INTEGER, 
	content_score INTEGER, 
	security_score INTEGER, 
	recommendations JSON, 
	raw_report JSON, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE customers (
	source_lead_id UUID NOT NULL, 
	company_name VARCHAR(255) NOT NULL, 
	contact_person VARCHAR(255), 
	phone VARCHAR(50), 
	email VARCHAR(255), 
	address TEXT, 
	website VARCHAR(500), 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_lead_id) REFERENCES leads (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE deals (
	lead_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	amount NUMERIC(12, 2), 
	stage dealstage NOT NULL, 
	probability INTEGER, 
	expected_close_date DATE, 
	sales_owner UUID, 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(sales_owner) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE followups (
	lead_id UUID NOT NULL, 
	assigned_to UUID NOT NULL, 
	due_date DATE NOT NULL, 
	due_time TIME WITHOUT TIME ZONE, 
	priority followuppriority NOT NULL, 
	notes TEXT, 
	status followupstatus NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE pitches (
	lead_id UUID NOT NULL, 
	generated_by UUID, 
	message TEXT NOT NULL, 
	channel pitchchannel NOT NULL, 
	status pitchstatus NOT NULL, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(generated_by) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")
    op.execute("""
CREATE TABLE proposals (
	deal_id UUID NOT NULL, 
	lead_id UUID NOT NULL, 
	proposal_number VARCHAR(50) NOT NULL, 
	line_items JSON NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	grand_total NUMERIC(12, 2) NOT NULL, 
	terms TEXT, 
	validity_days INTEGER, 
	payment_terms VARCHAR(255), 
	status proposalstatus NOT NULL, 
	pdf_path VARCHAR(500), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	organization_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deal_id) REFERENCES deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES leads (id), 
	UNIQUE (proposal_number), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE INDEX ix_organizations_is_deleted ON organizations (is_deleted);
CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug);
CREATE INDEX ix_pipeline_stages_organization_id ON pipeline_stages (organization_id);
CREATE INDEX ix_settings_key ON settings (key);
CREATE INDEX ix_settings_organization_id ON settings (organization_id);
CREATE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_is_deleted ON users (is_deleted);
CREATE INDEX ix_users_organization_id ON users (organization_id);
CREATE INDEX ix_audit_logs_organization_id ON audit_logs (organization_id);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX ix_leads_is_deleted ON leads (is_deleted);
CREATE INDEX ix_leads_phone ON leads (phone);
CREATE INDEX ix_leads_state ON leads (state);
CREATE INDEX ix_leads_business_name ON leads (business_name);
CREATE INDEX ix_leads_next_followup_date ON leads (next_followup_date);
CREATE INDEX ix_leads_organization_id ON leads (organization_id);
CREATE INDEX ix_leads_city ON leads (city);
CREATE INDEX ix_leads_status ON leads (status);
CREATE INDEX ix_leads_google_place_id ON leads (google_place_id);
CREATE INDEX ix_leads_assigned_to ON leads (assigned_to);
CREATE INDEX ix_leads_category ON leads (category);
CREATE INDEX ix_leads_lead_score ON leads (lead_score);
CREATE INDEX ix_notifications_is_read ON notifications (is_read);
CREATE INDEX ix_notifications_organization_id ON notifications (organization_id);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_activities_lead_id ON activities (lead_id);
CREATE INDEX ix_activities_type ON activities (type);
CREATE INDEX ix_activities_created_at ON activities (created_at);
CREATE INDEX ix_activities_organization_id ON activities (organization_id);
CREATE INDEX ix_audits_lead_id ON audits (lead_id);
CREATE INDEX ix_audits_organization_id ON audits (organization_id);
CREATE INDEX ix_customers_source_lead_id ON customers (source_lead_id);
CREATE INDEX ix_customers_organization_id ON customers (organization_id);
CREATE INDEX ix_deals_lead_id ON deals (lead_id);
CREATE INDEX ix_deals_stage ON deals (stage);
CREATE INDEX ix_deals_organization_id ON deals (organization_id);
CREATE INDEX ix_followups_lead_id ON followups (lead_id);
CREATE INDEX ix_followups_assigned_to ON followups (assigned_to);
CREATE INDEX ix_followups_organization_id ON followups (organization_id);
CREATE INDEX ix_followups_status ON followups (status);
CREATE INDEX ix_followups_due_date ON followups (due_date);
CREATE INDEX ix_pitches_lead_id ON pitches (lead_id);
CREATE INDEX ix_pitches_organization_id ON pitches (organization_id);
CREATE INDEX ix_proposals_status ON proposals (status);
CREATE INDEX ix_proposals_deal_id ON proposals (deal_id);
CREATE INDEX ix_proposals_organization_id ON proposals (organization_id);
CREATE INDEX ix_proposals_lead_id ON proposals (lead_id);
""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS proposals CASCADE;")
    op.execute("DROP TABLE IF EXISTS pitches CASCADE;")
    op.execute("DROP TABLE IF EXISTS followups CASCADE;")
    op.execute("DROP TABLE IF EXISTS deals CASCADE;")
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.execute("DROP TABLE IF EXISTS audits CASCADE;")
    op.execute("DROP TABLE IF EXISTS activities CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS leads CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS settings CASCADE;")
    op.execute("DROP TABLE IF EXISTS pipeline_stages CASCADE;")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE;")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS leadstatus")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS activitytype")
    op.execute("DROP TYPE IF EXISTS followupstatus")
    op.execute("DROP TYPE IF EXISTS followuppriority")
    op.execute("DROP TYPE IF EXISTS dealstage")
    op.execute("DROP TYPE IF EXISTS pitchchannel")
    op.execute("DROP TYPE IF EXISTS pitchstatus")
    op.execute("DROP TYPE IF EXISTS proposalstatus")
