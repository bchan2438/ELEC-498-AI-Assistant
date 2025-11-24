-- PGvector extension 
CREATE EXTENSION IF NOT EXISTS vector;


CREATE TBALE IF NOT EXISTS swebench_data(
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
embedding vector(200), -- 200 is a placeholder, will change once embedding code is finished 




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
