# Medical Codes Import Script

## Overview

The `import_medical_codes_enhanced.py` script imports medical codes from various sources into the database.

## Features

- **ICD-10 Codes**: Downloads and imports 70,000+ diagnosis codes from CDC/CMS
- **CPT Codes**: Imports procedure codes (requires CSV file)
- **HCPCS Codes**: Imports free alternative to CPT codes
- **Denial Codes**: Imports standard insurance denial codes
- **Payment Codes**: Imports CARC/RARC payment adjustment codes
- **Medical Necessity Rules**: Creates ICD-10 to CPT mapping rules

## Prerequisites

```bash
# Install required packages
pip install httpx tqdm

# Ensure database is running
docker-compose up -d postgres

# Run database migrations
alembic upgrade head
```

## Usage

### Import All Codes

```bash
python scripts/import_medical_codes_enhanced.py --all
```

### Import Specific Code Sets

```bash
# Import ICD-10 codes only
python scripts/import_medical_codes_enhanced.py --icd10 data/icd10_codes.csv

# Import CPT codes only
python scripts/import_medical_codes_enhanced.py --cpt data/cpt_codes.csv

# Import HCPCS codes only
python scripts/import_medical_codes_enhanced.py --hcpcs data/hcpcs_codes.csv

# Download ICD-10 codes from CDC
python scripts/import_medical_codes_enhanced.py --download-icd10 data/
```

## Data Sources

### ICD-10 Codes (Free)
- **Source**: CDC/CMS
- **URL**: https://www.cms.gov/medicare/coding-billing/icd-10-codes
- **Format**: CSV or text file
- **Count**: ~70,000 codes

### CPT Codes (License Required)
- **Source**: American Medical Association (AMA)
- **Cost**: ~$500/year
- **Alternative**: Use HCPCS codes (free)
- **Format**: CSV
- **Count**: ~10,000 codes

### HCPCS Codes (Free Alternative to CPT)
- **Source**: CMS
- **URL**: https://www.cms.gov/medicare/coding-billing/hcpcscodes
- **Format**: CSV
- **Count**: ~7,000 codes

## CSV Format

### ICD-10 CSV Format
```csv
code,description,category,subcategory,billable,valid_for_coding
A00.0,Cholera due to Vibrio cholerae 01 biovar cholerae,Infectious,Intestinal,1,1
A00.1,Cholera due to Vibrio cholerae 01 biovar eltor,Infectious,Intestinal,1,1
```

### CPT CSV Format
```csv
code,description,category,rvu,facility_rvu,non_facility_rvu
99213,Office visit established patient,E/M,1.92,1.92,1.92
99214,Office visit established patient,E/M,2.80,2.80,2.80
```

### HCPCS CSV Format
```csv
code,description,category
G0438,Annual wellness visit,Preventive Care
G0439,Annual wellness visit subsequent,Preventive Care
```

## Sample Data

A sample SQL file with test data is available at `data/sample_medical_codes.sql`:

```bash
# Load sample data
psql -d healthflow -f data/sample_medical_codes.sql
```

## Verification

After import, verify the data:

```bash
# Check counts
psql -d healthflow -c "SELECT 'ICD-10' as type, COUNT(*) as count FROM icd10_codes UNION ALL SELECT 'CPT', COUNT(*) FROM cpt_codes UNION ALL SELECT 'HCPCS', COUNT(*) FROM hcpcs_codes;"

# Test search performance
curl "http://localhost:8000/api/v1/medical-codes/icd10/search?q=diabetes"
```

Expected counts:
- ICD-10: 70,000+ codes
- CPT: 10,000+ codes (or 0 if using HCPCS)
- HCPCS: 7,000+ codes

## Performance

- **Import Speed**: ~1,000 codes/second
- **Search Performance**: <100ms for fuzzy search
- **Database Size**: ~50MB for full dataset

## Troubleshooting

### Error: "Could not connect to database"
```bash
# Check database is running
docker-compose ps

# Check connection string
echo $DATABASE_URL
```

### Error: "Table does not exist"
```bash
# Run migrations
alembic upgrade head
```

### Error: "Permission denied"
```bash
# Make script executable
chmod +x scripts/import_medical_codes_enhanced.py
```

## Next Steps

After importing medical codes:

1. **Test Search API**
   ```bash
   curl "http://localhost:8000/api/v1/medical-codes/icd10/search?q=diabetes"
   ```

2. **Verify Medical Necessity Rules**
   ```bash
   psql -d healthflow -c "SELECT COUNT(*) FROM medical_necessity_rules;"
   ```

3. **Run Tests**
   ```bash
   pytest tests/unit/test_medical_codes_service.py -v
   ```

## Support

For issues or questions:
- Check the main README.md
- Review documentation in `docs/`
- Contact the development team

