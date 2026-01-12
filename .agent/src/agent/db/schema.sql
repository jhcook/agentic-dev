CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    state TEXT,
    author TEXT,
    PRIMARY KEY (id, type)
);

CREATE TABLE IF NOT EXISTS history (
    change_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    author TEXT,
    description TEXT,
    delta TEXT,
    FOREIGN KEY(artifact_id, artifact_type) REFERENCES artifacts(id, type)
);

CREATE TABLE IF NOT EXISTS links (
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    rel_type TEXT NOT NULL, -- 'contains', 'implements', 'related'
    PRIMARY KEY (source_id, source_type, target_id, target_type),
    FOREIGN KEY(source_id, source_type) REFERENCES artifacts(id, type),
    FOREIGN KEY(target_id, target_type) REFERENCES artifacts(id, type)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type);
CREATE INDEX IF NOT EXISTS idx_history_artifact ON history(artifact_id, artifact_type);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id, source_type);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id, target_type);
