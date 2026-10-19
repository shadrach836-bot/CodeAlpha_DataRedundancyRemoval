"""REST API - deployable to any cloud (AWS EC2/Elastic Beanstalk, Render, Azure, GCP Cloud Run)."""
import csv
import io

from flask import Flask, jsonify, request

from database import get_conn, init_db
from dedup import cleanup_existing, process_batch, process_record

app = Flask(__name__)
init_db()


@app.get("/")
def home():
    return jsonify(service="Data Redundancy Removal System", status="running",
                   endpoints=["POST /records", "POST /records/bulk", "POST /records/upload-csv",
                              "GET /records", "GET /rejected", "GET /stats", "POST /cleanup"])


@app.post("/records")
def add_record():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="send a JSON object"), 400
    result = process_record(data)
    return jsonify(result), (201 if result["inserted"] else 200)


@app.post("/records/bulk")
def add_bulk():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify(error="send a JSON array of records"), 400
    return jsonify(process_batch(data))


@app.post("/records/upload-csv")
def upload_csv():
    f = request.files.get("file")
    if not f:
        return jsonify(error="attach a CSV as form field 'file'"), 400
    rows = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
    return jsonify(process_batch(rows))


@app.get("/records")
def list_records():
    conn = get_conn()
    rows = conn.execute("SELECT id,name,email,phone,created_at FROM records ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/rejected")
def list_rejected():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM rejected_log ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/stats")
def stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
    rej = {r["classification"]: r["c"] for r in conn.execute(
        "SELECT classification, COUNT(*) c FROM rejected_log GROUP BY classification")}
    conn.close()
    return jsonify(stored_unique_records=total, rejected=rej)


@app.post("/cleanup")
def cleanup():
    return jsonify(removed_redundant_rows=cleanup_existing())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
