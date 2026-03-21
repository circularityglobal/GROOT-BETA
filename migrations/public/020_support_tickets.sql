-- Support Tickets — XMTP-encrypted customer support desk
-- Linked to messaging conversations for E2E encrypted communication

CREATE TABLE IF NOT EXISTS support_tickets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    conversation_id TEXT REFERENCES conversations(id),
    ticket_number INTEGER UNIQUE,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open',
    assigned_to TEXT REFERENCES users(id),
    resolved_at DATETIME,
    is_encrypted BOOLEAN DEFAULT 0,
    extra_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    message_type TEXT NOT NULL DEFAULT 'reply',
    content TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id);
