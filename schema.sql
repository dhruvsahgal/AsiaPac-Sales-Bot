-- Run this in Supabase SQL Editor to create tables

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    ooo_until DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    company TEXT NOT NULL,
    next_steps TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'won', 'lost')),
    follow_up_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_user_id ON leads(user_id);
CREATE INDEX idx_leads_follow_up_date ON leads(follow_up_date);
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
