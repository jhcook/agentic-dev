-- Supabase Schema for Distributed Cache Synchronization

CREATE TABLE IF NOT EXISTS public.artifacts (
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    last_modified TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    state TEXT,
    author TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    owner_id UUID DEFAULT auth.uid(),
    PRIMARY KEY (id, type)
);

CREATE TABLE IF NOT EXISTS public.history (
    change_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    author TEXT,
    description TEXT,
    delta TEXT,
    FOREIGN KEY(artifact_id, artifact_type) REFERENCES public.artifacts(id, type) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.links (
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (source_id, source_type, target_id, target_type),
    FOREIGN KEY(source_id, source_type) REFERENCES public.artifacts(id, type) ON DELETE CASCADE,
    FOREIGN KEY(target_id, target_type) REFERENCES public.artifacts(id, type) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON public.artifacts(type);
CREATE INDEX IF NOT EXISTS idx_history_artifact ON public.history(artifact_id, artifact_type);
CREATE INDEX IF NOT EXISTS idx_links_source ON public.links(source_id, source_type);
CREATE INDEX IF NOT EXISTS idx_links_target ON public.links(target_id, target_type);

-- Row Level Security (RLS)
ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.links ENABLE ROW LEVEL SECURITY;

-- Policies (Basic Authenticated Access)
-- Artifacts
CREATE POLICY "Allow authenticated read access (artifacts)" ON public.artifacts FOR SELECT TO authenticated USING (auth.uid() = owner_id);
CREATE POLICY "Allow authenticated insert access (artifacts)" ON public.artifacts FOR INSERT TO authenticated WITH CHECK (auth.uid() = owner_id);
CREATE POLICY "Allow authenticated update access (artifacts)" ON public.artifacts FOR UPDATE TO authenticated USING (auth.uid() = owner_id);

-- History
CREATE POLICY "Allow authenticated read access (history)" ON public.history FOR SELECT TO authenticated USING (
    exists ( select 1 from public.artifacts a where a.id = history.artifact_id and a.type = history.artifact_type and a.owner_id = auth.uid() )
);
CREATE POLICY "Allow authenticated insert access (history)" ON public.history FOR INSERT TO authenticated WITH CHECK (
    exists ( select 1 from public.artifacts a where a.id = history.artifact_id and a.type = history.artifact_type and a.owner_id = auth.uid() )
);

-- Links
CREATE POLICY "Allow authenticated read access (links)" ON public.links FOR SELECT TO authenticated USING (
    exists ( select 1 from public.artifacts a where a.id = links.source_id and a.type = links.source_type and a.owner_id = auth.uid() )
);
CREATE POLICY "Allow authenticated insert access (links)" ON public.links FOR INSERT TO authenticated WITH CHECK (
    exists ( select 1 from public.artifacts a where a.id = links.source_id and a.type = links.source_type and a.owner_id = auth.uid() )
);
CREATE POLICY "Allow authenticated update access (links)" ON public.links FOR UPDATE TO authenticated USING (
    exists ( select 1 from public.artifacts a where a.id = links.source_id and a.type = links.source_type and a.owner_id = auth.uid() )
);
CREATE POLICY "Allow authenticated delete access (links)" ON public.links FOR DELETE TO authenticated USING (
    exists ( select 1 from public.artifacts a where a.id = links.source_id and a.type = links.source_type and a.owner_id = auth.uid() )
);
