-- PGvector extension 
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS swebench_data;

CREATE TABLE IF NOT EXISTS swebench_data(
id BIGSERIAL PRIMARY KEY, 

-- Properties 
instance_id TEXT NOT NULL UNIQUE, 
repo TEXT NOT NULL, 
base_commit TEXT NOT NULL, 
version TEXT NOT NULL,
environment_setup_commit TEXT NOT NULL,


--problem text
problem_statement TEXT NOT NULL,
hint TEXT,

--patches
patch TEXT NOT NULL,
test_patch TEXT NOT NULL, 

--time
created_at TEXT NOT NULL, 

-- Test cases 
fail_to_pass JSONB NOT NULL, 
pass_to_pass JSONB NOT NULL, 


-- Vector embedding 
embedding vector(1536) -- 200 is a placeholder, will change once embedding code is finished. Changed to 1536. May need to be altered if the table has already been created.
-- ALTER TABLE swebench_data
-- ALTER COLUMN embedding TYPE vector(1536);
-- might need to run these two lines above



);
-- Vector index 
CREATE INDEX IF NOT EXISTS swebench_data_embedding_idx
ON swebench_data
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Helpful filters
CREATE INDEX IF NOT EXISTS swebench_data_repo_idx
ON swebench_data (repo);

CREATE INDEX IF NOT EXISTS swebench_data_base_commit_idx
ON swebench_data (base_commit);
