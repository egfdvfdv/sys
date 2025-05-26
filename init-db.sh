#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create database if it doesn't exist
    SELECT 'CREATE DATABASE $POSTGRES_DB'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$POSTGRES_DB')\gexec
    
    -- Connect to the database
    \c $POSTGRES_DB
    
    -- Create tables
    CREATE TABLE IF NOT EXISTS prompts (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(50) NOT NULL,
        requirements TEXT NOT NULL,
        prompt TEXT,
        score INTEGER,
        iterations INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        metadata JSONB
    );
    
    CREATE TABLE IF NOT EXISTS prompt_iterations (
        id SERIAL PRIMARY KEY,
        task_id VARCHAR(255) NOT NULL,
        iteration INTEGER NOT NULL,
        prompt TEXT NOT NULL,
        score INTEGER,
        feedback JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES prompts(task_id) ON DELETE CASCADE,
        UNIQUE(task_id, iteration)
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_prompts_task_id ON prompts(task_id);
    CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(status);
    CREATE INDEX IF NOT EXISTS idx_prompt_iterations_task_id ON prompt_iterations(task_id);
    
    -- Create update trigger for updated_at
    CREATE OR REPLACE FUNCTION update_modified_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    
    DROP TRIGGER IF EXISTS update_prompts_modtime ON prompts;
    CREATE TRIGGER update_prompts_modtime
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();
    
    -- Create user with permissions
    CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $POSTGRES_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $POSTGRES_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $POSTGRES_USER;
EOSQL
