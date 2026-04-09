"""
Starship Mission Management System — Backend API
Flask + Oracle Database (via python-oracledb)

SETUP BEFORE RUNNING:
    pip install flask oracledb flask-cors

Edit the DB_CONFIG block below with YOUR Oracle credentials.
"""

import oracledb
from flask import Flask, request, jsonify, g, send_file   # <-- added send_file
from flask_cors import CORS 
from datetime import datetime, date

app = Flask(__name__)
CORS(app)

# Oracle SQL*Plus credentials
DB_CONFIG = {
    "user":     "system",
    "password": "student",
    "dsn":      "localhost/XEPDB1",     # your service name is XEPDB1
}

# ─────────────────────────────────────────────
# Serve the frontend (index.html) from the same origin
# ─────────────────────────────────────────────
@app.route("/")
@app.route("/index.html")
def serve_frontend():
    return send_file("index.html")

# ─────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────

def get_db():
    if "db" not in g:
        conn = oracledb.connect(**DB_CONFIG)
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def query(sql, args=None, one=False):
    cur = get_db().cursor()
    cur.execute(sql, args or [])
    cols = [d[0].upper() for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    # Convert Oracle DATE objects to strings
    for row in rows:
        for k, v in row.items():
            if isinstance(v, (datetime, date)):
                row[k] = str(v)[:10]
    return (rows[0] if rows else None) if one else rows

def execute(sql, args=None):
    db = get_db()
    cur = db.cursor()
    cur.execute(sql, args or [])
    db.commit()
    return cur

def nextval(seq):
    """Get next value from an Oracle sequence."""
    row = query(f"SELECT {seq}.NEXTVAL FROM DUAL", one=True)
    return list(row.values())[0]

# ─────────────────────────────────────────────
# CORS is already handled by flask-cors (CORS(app))
# The manual after_request and OPTIONS routes are optional now
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Oracle Sequences (auto-increment IDs)
# ─────────────────────────────────────────────

SEQ = {
    "mission":   "SEQ_MISSION",
    "crew":      "SEQ_CREW",
    "payload":   "SEQ_PAYLOAD",
    "starship":  "SEQ_STARSHIP",
    "booster":   "SEQ_BOOSTER",
    "site":      "SEQ_SITE",
}

# ─────────────────────────────────────────────
# STARSHIPS
# ─────────────────────────────────────────────

@app.route("/starships", methods=["GET"])
def get_starships():
    return jsonify(query("SELECT * FROM STARSHIP ORDER BY STARSHIPID"))

@app.route("/starships", methods=["POST"])
def add_starship():
    d = request.json
    sid = nextval(SEQ["starship"])
    execute(
        "INSERT INTO STARSHIP(STARSHIPID,SERIALNUMBER,BUILDDATE,STATUS,TOTALFLIGHTS) "
        "VALUES(:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5)",
        [sid, d.get("serialnumber"), d.get("builddate"),
         d.get("status", "ACTIVE"), d.get("totalflights", 0)]
    )
    return jsonify({"id": sid}), 201

@app.route("/starships/<int:sid>/maintenance", methods=["GET"])
def get_maintenance(sid):
    return jsonify(query(
        "SELECT * FROM MAINTENANCE_RECORD WHERE STARSHIPID=:1 ORDER BY MAINT_ID", [sid]
    ))

@app.route("/starships/<int:sid>/maintenance", methods=["POST"])
def add_maintenance(sid):
    d = request.json
    row = query(
        "SELECT NVL(MAX(MAINT_ID),0)+1 AS NID FROM MAINTENANCE_RECORD WHERE STARSHIPID=:1",
        [sid], one=True
    )
    nid = row["NID"]
    execute(
        "INSERT INTO MAINTENANCE_RECORD(STARSHIPID,MAINT_ID,MAINT_DATE,MAINT_DESC,ENGINEERNAME) "
        "VALUES(:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5)",
        [sid, nid, d.get("maint_date", str(datetime.today().date())),
         d.get("maint_desc"), d.get("engineername")]
    )
    return jsonify({"maint_id": nid}), 201

# ─────────────────────────────────────────────
# BOOSTERS
# ─────────────────────────────────────────────

@app.route("/boosters", methods=["GET"])
def get_boosters():
    return jsonify(query("SELECT * FROM BOOSTER ORDER BY BOOSTERID"))

@app.route("/boosters", methods=["POST"])
def add_booster():
    d = request.json
    bid = nextval(SEQ["booster"])
    execute(
        "INSERT INTO BOOSTER(BOOSTERID,SERIALNUMBER,THRUSTCAPACITY,BUILDDATE,STATUS) "
        "VALUES(:1,:2,:3,TO_DATE(:4,'YYYY-MM-DD'),:5)",
        [bid, d.get("serialnumber"), d.get("thrustcapacity"),
         d.get("builddate"), d.get("status", "ACTIVE")]
    )
    return jsonify({"id": bid}), 201

# ─────────────────────────────────────────────
# LAUNCH SITES
# ─────────────────────────────────────────────

@app.route("/launchsites", methods=["GET"])
def get_sites():
    return jsonify(query("SELECT * FROM LAUNCHSITE ORDER BY SITEID"))

@app.route("/launchsites", methods=["POST"])
def add_site():
    d = request.json
    lid = nextval(SEQ["site"])
    execute(
        "INSERT INTO LAUNCHSITE(SITEID,SITENAME,CITY,COUNTRY,CAPACITY) VALUES(:1,:2,:3,:4,:5)",
        [lid, d.get("sitename"), d.get("city"), d.get("country"), d.get("capacity")]
    )
    return jsonify({"id": lid}), 201

# ─────────────────────────────────────────────
# MISSIONS
# ─────────────────────────────────────────────

@app.route("/missions", methods=["GET"])
def get_missions():
    rows = query("""
        SELECT M.MISSIONID, M.MISSIONNAME, M.LAUNCHDATE, M.MISSIONTYPE,
               M.STATUS, M.ORBITTYPE, M.STARSHIPID, M.BOOSTERID, M.SITEID,
               S.SERIALNUMBER  AS STARSHIP_SERIAL,
               B.SERIALNUMBER  AS BOOSTER_SERIAL,
               L.SITENAME      AS SITE_NAME
        FROM MISSION M
        LEFT JOIN STARSHIP   S ON M.STARSHIPID = S.STARSHIPID
        LEFT JOIN BOOSTER    B ON M.BOOSTERID  = B.BOOSTERID
        LEFT JOIN LAUNCHSITE L ON M.SITEID     = L.SITEID
        ORDER BY M.LAUNCHDATE DESC
    """)
    return jsonify(rows)

@app.route("/missions/<int:mid>", methods=["GET"])
def get_mission(mid):
    row = query("""
        SELECT M.MISSIONID, M.MISSIONNAME, M.LAUNCHDATE, M.MISSIONTYPE,
               M.STATUS, M.ORBITTYPE, M.STARSHIPID, M.BOOSTERID, M.SITEID,
               S.SERIALNUMBER  AS STARSHIP_SERIAL,
               B.SERIALNUMBER  AS BOOSTER_SERIAL,
               L.SITENAME AS SITE_NAME, L.CITY, L.COUNTRY
        FROM MISSION M
        LEFT JOIN STARSHIP   S ON M.STARSHIPID = S.STARSHIPID
        LEFT JOIN BOOSTER    B ON M.BOOSTERID  = B.BOOSTERID
        LEFT JOIN LAUNCHSITE L ON M.SITEID     = L.SITEID
        WHERE M.MISSIONID = :1
    """, [mid], one=True)
    if not row:
        return jsonify({"error": "Not found"}), 404
    row["crew"] = query("""
        SELECT C.CREWID, C.FIRSTNAME, C.LASTNAME, C.NATIONALITY, C.ROLE, C.EXPERIENCEYEARS
        FROM CREWMEMBER C
        JOIN MISSION_CREW MC ON C.CREWID = MC.CREWID
        WHERE MC.MISSIONID = :1
    """, [mid])
    row["payloads"] = query("""
        SELECT P.* FROM PAYLOAD P
        JOIN MISSION_PAYLOAD MP ON P.PAYLOADID = MP.PAYLOADID
        WHERE MP.MISSIONID = :1
    """, [mid])
    row["attempts"] = query(
        "SELECT * FROM LAUNCH_ATTEMPT WHERE MISSIONID=:1 ORDER BY ATTEMPTNUMBER", [mid]
    )
    return jsonify(row)

@app.route("/missions", methods=["POST"])
def create_mission():
    d = request.json
    mid = nextval(SEQ["mission"])
    starshipid = d.get("starshipid") or None
    boosterid  = d.get("boosterid")  or None
    siteid     = d.get("siteid")     or None
    execute(
        "INSERT INTO MISSION(MISSIONID,MISSIONNAME,LAUNCHDATE,MISSIONTYPE,STATUS,ORBITTYPE,"
        "STARSHIPID,BOOSTERID,SITEID) "
        "VALUES(:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5,:6,:7,:8,:9)",
        [mid, d.get("missionname"), d.get("launchdate"),
         d.get("missiontype"), d.get("status", "Planned"),
         d.get("orbittype"), starshipid, boosterid, siteid]
    )
    return jsonify({"id": mid}), 201

@app.route("/missions/<int:mid>", methods=["PUT"])
def update_mission(mid):
    d = request.json
    execute("""
        UPDATE MISSION SET
            MISSIONNAME=:1, LAUNCHDATE=TO_DATE(:2,'YYYY-MM-DD'),
            MISSIONTYPE=:3, STATUS=:4, ORBITTYPE=:5,
            STARSHIPID=:6, BOOSTERID=:7, SITEID=:8
        WHERE MISSIONID=:9
    """, [d.get("missionname"), d.get("launchdate"), d.get("missiontype"),
          d.get("status"), d.get("orbittype"),
          d.get("starshipid"), d.get("boosterid"), d.get("siteid"), mid])
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# CREW
# ─────────────────────────────────────────────

@app.route("/crew", methods=["GET"])
def get_crew():
    return jsonify(query("SELECT * FROM CREWMEMBER ORDER BY LASTNAME"))

@app.route("/crew", methods=["POST"])
def add_crew():
    d = request.json
    cid = nextval(SEQ["crew"])
    execute(
        "INSERT INTO CREWMEMBER(CREWID,FIRSTNAME,LASTNAME,NATIONALITY,ROLE,EXPERIENCEYEARS) "
        "VALUES(:1,:2,:3,:4,:5,:6)",
        [cid, d.get("firstname"), d.get("lastname"),
         d.get("nationality"), d.get("role"), d.get("experienceyears", 0)]
    )
    return jsonify({"id": cid}), 201

@app.route("/missions/<int:mid>/crew", methods=["POST"])
def assign_crew(mid):
    d = request.json
    try:
        execute("INSERT INTO MISSION_CREW(MISSIONID,CREWID) VALUES(:1,:2)",
                [mid, d.get("crewid")])
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/missions/<int:mid>/crew/<int:cid>", methods=["DELETE"])
def remove_crew(mid, cid):
    execute("DELETE FROM MISSION_CREW WHERE MISSIONID=:1 AND CREWID=:2", [mid, cid])
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# PAYLOADS
# ─────────────────────────────────────────────

@app.route("/payloads", methods=["GET"])
def get_payloads():
    return jsonify(query("SELECT * FROM PAYLOAD ORDER BY PAYLOADNAME"))

@app.route("/payloads", methods=["POST"])
def add_payload():
    d = request.json
    pid = nextval(SEQ["payload"])
    execute(
        "INSERT INTO PAYLOAD(PAYLOADID,PAYLOADNAME,WEIGHT,TYPE,OWNERORGANIZATION) "
        "VALUES(:1,:2,:3,:4,:5)",
        [pid, d.get("payloadname"), d.get("weight"),
         d.get("type"), d.get("ownerorganization")]
    )
    return jsonify({"id": pid}), 201

@app.route("/missions/<int:mid>/payloads", methods=["POST"])
def assign_payload(mid):
    d = request.json
    try:
        execute("INSERT INTO MISSION_PAYLOAD(MISSIONID,PAYLOADID) VALUES(:1,:2)",
                [mid, d.get("payloadid")])
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/missions/<int:mid>/payloads/<int:pid>", methods=["DELETE"])
def remove_payload(mid, pid):
    execute("DELETE FROM MISSION_PAYLOAD WHERE MISSIONID=:1 AND PAYLOADID=:2", [mid, pid])
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# LAUNCH ATTEMPTS
# ─────────────────────────────────────────────

@app.route("/missions/<int:mid>/attempts", methods=["POST"])
def add_attempt(mid):
    d = request.json
    row = query(
        "SELECT NVL(MAX(ATTEMPTNUMBER),0)+1 AS N FROM LAUNCH_ATTEMPT WHERE MISSIONID=:1",
        [mid], one=True
    )
    n = row["N"]
    execute(
        "INSERT INTO LAUNCH_ATTEMPT(MISSIONID,ATTEMPTNUMBER,ATTEMPTDATE,OUTCOME,WEATHERCONDITION) "
        "VALUES(:1,:2,TO_DATE(:3,'YYYY-MM-DD'),:4,:5)",
        [mid, n, d.get("attemptdate", str(datetime.today().date())),
         d.get("outcome"), d.get("weathercondition")]
    )
    return jsonify({"attemptnumber": n}), 201

# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────

@app.route("/stats", methods=["GET"])
def stats():
    missions  = query("SELECT COUNT(*) AS C FROM MISSION",    one=True)["C"]
    starships = query("SELECT COUNT(*) AS C FROM STARSHIP",   one=True)["C"]
    crew      = query("SELECT COUNT(*) AS C FROM CREWMEMBER", one=True)["C"]
    payloads  = query("SELECT COUNT(*) AS C FROM PAYLOAD",    one=True)["C"]
    att = query("""
        SELECT COUNT(*) AS C,
               SUM(CASE WHEN OUTCOME='SUCCESS' THEN 1 ELSE 0 END) AS S
        FROM LAUNCH_ATTEMPT
    """, one=True)
    by_status = query("SELECT STATUS, COUNT(*) AS C FROM MISSION GROUP BY STATUS")
    return jsonify({
        "missions":  missions,
        "starships": starships,
        "crew":      crew,
        "payloads":  payloads,
        "attempts":  att["C"] or 0,
        "successes": att["S"] or 0,
        "by_status": by_status,
    })

# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Quick connection test on startup
    try:
        conn = oracledb.connect(**DB_CONFIG)
        conn.close()
        print("✅ Oracle connection successful!")
    except Exception as e:
        print(f"❌ Oracle connection FAILED: {e}")
        print("   Check your DB_CONFIG credentials in app.py")
        exit(1)

    print("🚀 Starting Starship API on http://localhost:5000")
    app.run(debug=True, port=5000)