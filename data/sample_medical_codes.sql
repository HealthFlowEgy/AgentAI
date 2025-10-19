-- Sample ICD-10 Codes (insert after running main import)
-- This provides immediate functional data for testing

INSERT INTO icd10_codes (code, description, category, subcategory, billable, valid_for_coding, effective_date) VALUES
-- Diabetes
('E11.9', 'Type 2 diabetes mellitus without complications', 'Endocrine', 'Diabetes', true, true, CURRENT_DATE),
('E11.65', 'Type 2 diabetes mellitus with hyperglycemia', 'Endocrine', 'Diabetes', true, true, CURRENT_DATE),
('E11.69', 'Type 2 diabetes mellitus with other specified complication', 'Endocrine', 'Diabetes', true, true, CURRENT_DATE),
('E10.9', 'Type 1 diabetes mellitus without complications', 'Endocrine', 'Diabetes', true, true, CURRENT_DATE),

-- Hypertension
('I10', 'Essential (primary) hypertension', 'Circulatory', 'Hypertension', true, true, CURRENT_DATE),
('I11.0', 'Hypertensive heart disease with heart failure', 'Circulatory', 'Hypertension', true, true, CURRENT_DATE),
('I12.9', 'Hypertensive chronic kidney disease', 'Circulatory', 'Hypertension', true, true, CURRENT_DATE),

-- Respiratory
('J45.909', 'Unspecified asthma, uncomplicated', 'Respiratory', 'Asthma', true, true, CURRENT_DATE),
('J45.40', 'Moderate persistent asthma, uncomplicated', 'Respiratory', 'Asthma', true, true, CURRENT_DATE),
('J06.9', 'Acute upper respiratory infection, unspecified', 'Respiratory', 'Infection', true, true, CURRENT_DATE),

-- Pain
('M79.3', 'Panniculitis, unspecified', 'Musculoskeletal', 'Pain', true, true, CURRENT_DATE),
('M79.604', 'Pain in right leg', 'Musculoskeletal', 'Pain', true, true, CURRENT_DATE),
('R10.9', 'Unspecified abdominal pain', 'Symptoms', 'Pain', true, true, CURRENT_DATE),

-- Common conditions
('R50.9', 'Fever, unspecified', 'Symptoms', 'General', true, true, CURRENT_DATE),
('R05', 'Cough', 'Respiratory', 'Symptoms', true, true, CURRENT_DATE),
('R51', 'Headache', 'Symptoms', 'Neurological', true, true, CURRENT_DATE);

-- Sample CPT Codes
INSERT INTO cpt_codes (code, description, category, rvu, facility_rvu, non_facility_rvu, effective_date) VALUES
-- Office Visits (E/M)
('99213', 'Office/outpatient visit, established patient, 20-29 minutes', 'E/M', 1.92, 1.92, 1.92, CURRENT_DATE),
('99214', 'Office/outpatient visit, established patient, 30-39 minutes', 'E/M', 2.80, 2.80, 2.80, CURRENT_DATE),
('99215', 'Office/outpatient visit, established patient, 40-54 minutes', 'E/M', 3.76, 3.76, 3.76, CURRENT_DATE),
('99203', 'Office/outpatient visit, new patient, 30-44 minutes', 'E/M', 2.45, 2.45, 2.45, CURRENT_DATE),
('99204', 'Office/outpatient visit, new patient, 45-59 minutes', 'E/M', 3.56, 3.56, 3.56, CURRENT_DATE),

-- Lab Tests
('82947', 'Glucose; quantitative, blood', 'Laboratory', 0.15, 0.15, 0.15, CURRENT_DATE),
('82950', 'Glucose; post glucose dose', 'Laboratory', 0.15, 0.15, 0.15, CURRENT_DATE),
('85025', 'Complete blood count (CBC) with differential', 'Laboratory', 0.28, 0.28, 0.28, CURRENT_DATE),
('80053', 'Comprehensive metabolic panel', 'Laboratory', 0.35, 0.35, 0.35, CURRENT_DATE),

-- Diagnostics
('93000', 'Electrocardiogram, routine ECG with interpretation', 'Cardiovascular', 0.17, 0.17, 0.17, CURRENT_DATE),
('71045', 'Chest X-ray, single view', 'Radiology', 0.23, 0.23, 0.23, CURRENT_DATE),
('71046', 'Chest X-ray, two views', 'Radiology', 0.32, 0.32, 0.32, CURRENT_DATE),

-- Procedures
('94010', 'Spirometry', 'Pulmonary', 0.27, 0.27, 0.27, CURRENT_DATE),
('94060', 'Bronchodilation responsiveness', 'Pulmonary', 0.42, 0.42, 0.42, CURRENT_DATE);

-- Sample HCPCS Codes (free alternative to CPT)
INSERT INTO hcpcs_codes (code, description, category, effective_date) VALUES
('G0438', 'Annual wellness visit; includes personalized prevention plan', 'Preventive Care', CURRENT_DATE),
('G0439', 'Annual wellness visit; includes personalized prevention plan, subsequent', 'Preventive Care', CURRENT_DATE),
('J1050', 'Injection, medroxyprogesterone acetate, 1 mg', 'Injections', CURRENT_DATE),
('A4253', 'Blood glucose test or reagent strips', 'Supplies', CURRENT_DATE);

-- Create full-text search indexes for performance
CREATE INDEX IF NOT EXISTS idx_icd10_description_fts ON icd10_codes USING gin(to_tsvector('english', description));
CREATE INDEX IF NOT EXISTS idx_cpt_description_fts ON cpt_codes USING gin(to_tsvector('english', description));
CREATE INDEX IF NOT EXISTS idx_icd10_code_trgm ON icd10_codes USING gin(code gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cpt_code_trgm ON cpt_codes USING gin(code gin_trgm_ops);

-- Verify counts
SELECT 'ICD-10 Codes' as table_name, COUNT(*) as count FROM icd10_codes
UNION ALL
SELECT 'CPT Codes', COUNT(*) FROM cpt_codes
UNION ALL
SELECT 'HCPCS Codes', COUNT(*) FROM hcpcs_codes;
