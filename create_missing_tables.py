import os
from sqlalchemy import create_engine, text

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'

# Create engine
engine = create_engine(os.environ['DATABASE_URL'])

# Create tables
with engine.connect() as conn:
    # Create zeek_http table
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS zeek_http (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid VARCHAR(50),
            source_ip INET NOT NULL,
            dest_ip INET NOT NULL,
            source_port INTEGER,
            dest_port INTEGER,
            method VARCHAR(10),
            uri TEXT,
            referrer TEXT,
            user_agent TEXT,
            status_code INTEGER,
            response_body_size INTEGER,
            raw_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    '''))

    # Create zeek_ssl table
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS zeek_ssl (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid VARCHAR(50),
            source_ip INET NOT NULL,
            dest_ip INET NOT NULL,
            source_port INTEGER,
            dest_port INTEGER,
            server_name TEXT,
            subject TEXT,
            issuer_subject TEXT,
            client_subject TEXT,
            cert_chain_fuids TEXT[],
            client_cert_chain_fuids TEXT[],
            sni TEXT,
            last_alert TEXT,
            next_protocol TEXT,
            established BOOLEAN,
            resumed BOOLEAN,
            version TEXT,
            cipher TEXT,
            curve TEXT,
            server_key_exchange_algorithm TEXT,
            server_signature_algorithm TEXT,
            client_key_exchange_algorithm TEXT,
            client_signature_algorithm TEXT,
            raw_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    '''))

    # Create indexes
    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_http_timestamp ON zeek_http(timestamp);'))
    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_ssl_timestamp ON zeek_ssl(timestamp);'))

    conn.commit()

print('zeek_http and zeek_ssl tables created successfully')