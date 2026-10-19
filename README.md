# CodeAlpha_DataRedundancyRemoval

**CodeAlpha Cloud Computing Internship - Task 1: Data Redundancy Removal System**

A cloud-deployable service that classifies incoming data as **unique**, **redundant** or **false positive**,
validates it against existing data, and appends only unique, verified entries to the database.

## How each task requirement is met

| Requirement | Implementation |
|---|---|
| Identify & classify data as redundant or false positive | `dedup.process_record` returns `UNIQUE_VERIFIED`, `REDUNDANT` or `FALSE_POSITIVE` with a reason |
| Validation mechanism against existing data | `validator.py` (format/fake-data checks) + `dedup.find_duplicate` (exact + normalised + fuzzy match against the DB) |
| Prevent duplicates entering the cloud DB | Atomic check-and-insert (`BEGIN IMMEDIATE`) plus DB `UNIQUE` constraints on email, phone and SHA-256 fingerprint |
| Append only unique and verified entries | Only `UNIQUE_VERIFIED` records are inserted; everything else goes to `rejected_log` (audit trail) |
| Database accuracy & efficiency | Indexed unique columns, normalisation (case, spaces, gmail dots/+tags, phone formats), `/cleanup` removes pre-existing duplicates |

## Classification rules
- **FALSE_POSITIVE**: missing name/email, bad email format, placeholder names (`test`, `asdf`, `xxx`...), disposable domains (mailinator...), invalid phone (not 10 digits / all same digit).
- **REDUNDANT**: same normalised email, same phone, or near-duplicate (name similarity >= 0.92 and email username similarity >= 0.85).
- **UNIQUE_VERIFIED**: passes validation and matches nothing existing -> inserted.

## Run locally
```bash
pip install -r requirements.txt
python app.py              # http://localhost:5000
pytest -q                  # 12 tests
```

## API
```bash
# single record
curl -X POST localhost:5000/records -H "Content-Type: application/json" \
  -d '{"name":"Rahul Sharma","email":"rahul@gmail.com","phone":"9876543210"}'

# bulk CSV (sample_data.csv included)
curl -X POST localhost:5000/records/upload-csv -F file=@sample_data.csv

curl localhost:5000/records     # stored unique data
curl localhost:5000/rejected    # rejected + reason
curl localhost:5000/stats
curl -X POST localhost:5000/cleanup
```

## Deploy to the cloud
```bash
docker build -t redundancy-removal .
docker run -p 5000:5000 -v data:/data redundancy-removal
```
Works on AWS (EC2 / Elastic Beanstalk / App Runner), Azure App Service, Google Cloud Run or Render.
Mount a persistent volume for `/data`. For a managed database (e.g. AWS RDS), only `database.py` needs swapping; the `UNIQUE` constraints and logic carry over.

## Structure
```
app.py          REST API
dedup.py        classification + duplicate detection engine
validator.py    validation & normalisation
database.py     schema + constraints
tests/          pytest suite
sample_data.csv demo data (valid, duplicate and fake rows)
```
