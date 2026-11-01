-- GENERATED from work/database/models.py by scripts/gen_schema_sql.py. Do not edit by hand.
-- The DB owner's models are the source of truth; re-run the script after they change.
-- All statements are IF NOT EXISTS, so running init_db against a DB created by
-- work/database/create_tables.py is a no-op.

CREATE TABLE IF NOT EXISTS alumni (
	id UUID NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	phone VARCHAR(30), 
	city VARCHAR(100), 
	cohort VARCHAR(100), 
	graduation_year INTEGER, 
	is_demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_alumni_email ON alumni (email);

CREATE TABLE IF NOT EXISTS jobs (
	id UUID NOT NULL, 
	board_token VARCHAR(100) NOT NULL, 
	greenhouse_job_id VARCHAR(100) NOT NULL, 
	company VARCHAR(255) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	location VARCHAR(255), 
	absolute_url TEXT NOT NULL, 
	description TEXT, 
	salary_min NUMERIC(12, 2), 
	salary_max NUMERIC(12, 2), 
	is_remote BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_greenhouse_job UNIQUE (board_token, greenhouse_job_id)
);

CREATE TABLE IF NOT EXISTS salary_benchmarks (
	id UUID NOT NULL, 
	title_family VARCHAR(100) NOT NULL, 
	city VARCHAR(100) NOT NULL, 
	experience_band VARCHAR(50) NOT NULL, 
	salary_min NUMERIC(12, 2) NOT NULL, 
	salary_max NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_salary_benchmark UNIQUE (title_family, city, experience_band)
);

CREATE TABLE IF NOT EXISTS certifications (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	issuer VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id)
);

CREATE INDEX IF NOT EXISTS ix_certifications_alumni_id ON certifications (alumni_id);

CREATE TABLE IF NOT EXISTS education (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	school VARCHAR(255) NOT NULL, 
	degree VARCHAR(150), 
	field_of_study VARCHAR(150), 
	start_year INTEGER, 
	graduation_year INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id)
);

CREATE INDEX IF NOT EXISTS ix_education_alumni_id ON education (alumni_id);

CREATE TABLE IF NOT EXISTS resume_uploads (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	parsed_data JSON, 
	confirmed BOOLEAN NOT NULL, 
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id)
);

CREATE INDEX IF NOT EXISTS ix_resume_uploads_alumni_id ON resume_uploads (alumni_id);

CREATE TABLE IF NOT EXISTS salary_records (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	salary_min NUMERIC(12, 2), 
	salary_max NUMERIC(12, 2), 
	source VARCHAR(30) NOT NULL, 
	effective_date DATE, 
	work_experience_id UUID, 
	PRIMARY KEY (id), 
	CONSTRAINT valid_salary_source CHECK (source IN ('self_reported', 'estimated')), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id), 
	FOREIGN KEY(work_experience_id) REFERENCES work_experience (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_salary_records_alumni_id ON salary_records (alumni_id);

CREATE TABLE IF NOT EXISTS skills (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_alumni_skill UNIQUE (alumni_id, name), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id)
);

CREATE INDEX IF NOT EXISTS ix_skills_alumni_id ON skills (alumni_id);

CREATE TABLE IF NOT EXISTS work_experience (
	id UUID NOT NULL, 
	alumni_id UUID NOT NULL, 
	employer VARCHAR(255) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	location VARCHAR(150), 
	start_date DATE, 
	end_date DATE, 
	is_current BOOLEAN NOT NULL, 
	description TEXT, 
	source VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alumni_id) REFERENCES alumni (id)
);

CREATE INDEX IF NOT EXISTS ix_work_experience_alumni_id ON work_experience (alumni_id);
