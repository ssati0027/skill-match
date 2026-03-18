from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import sqlite3, bcrypt, uuid, json, os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'skillmatch-ultra-2026'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=14)
CORS(app, origins="*")
jwt = JWTManager(app)
DB = os.path.join(os.path.dirname(__file__), 'skillmatch.db')

# ── DB HELPERS ──────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def rows(cursor_result): return [dict(r) for r in cursor_result]
def row(cursor_result): return dict(cursor_result) if cursor_result else None

def match_score(talent_skills, required_skills):
    if not required_skills: return 0
    have = {s['name'].lower() for s in talent_skills}
    req = [s.lower() for s in required_skills]
    return int(sum(1 for r in req if r in have) / len(req) * 100)

# ── SCHEMA ──────────────────────────────────────────────────────
def init():
    c = db()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, role TEXT NOT NULL,
            name TEXT NOT NULL, title TEXT, country TEXT,
            avatar TEXT, bio TEXT, linkedin TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            name TEXT NOT NULL, score INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0, endorsed INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, recruiter_id TEXT NOT NULL,
            title TEXT NOT NULL, company TEXT NOT NULL,
            description TEXT, required_skills TEXT,
            nice_skills TEXT, location TEXT,
            salary_min INTEGER, salary_max INTEGER,
            job_type TEXT, experience TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(recruiter_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
            talent_id TEXT NOT NULL, status TEXT DEFAULT 'pending',
            match_score INTEGER DEFAULT 0, cover_note TEXT,
            interview_scheduled TEXT, interview_link TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(talent_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY, skill_name TEXT NOT NULL,
            questions TEXT NOT NULL, difficulty TEXT DEFAULT 'medium',
            time_limit INTEGER DEFAULT 10
        );
        CREATE TABLE IF NOT EXISTS assessment_results (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            assessment_id TEXT NOT NULL, score INTEGER,
            answers TEXT, time_taken INTEGER,
            completed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL, content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text', read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS saved_talents (
            recruiter_id TEXT NOT NULL, talent_id TEXT NOT NULL,
            note TEXT, created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(recruiter_id, talent_id)
        );
        CREATE TABLE IF NOT EXISTS endorsements (
            id TEXT PRIMARY KEY, from_user TEXT NOT NULL,
            to_user TEXT NOT NULL, skill_name TEXT NOT NULL,
            note TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            type TEXT, title TEXT, body TEXT,
            read INTEGER DEFAULT 0, link TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    c.commit()
    _seed(c)
    c.close()

def _seed(c):
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0: return
    def hp(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
    def uid(): return str(uuid.uuid4())

    # ── assessments ──
    asm = [
        (uid(),'Java',json.dumps([
            {"q":"Which keyword prevents method overriding?","opts":["static","final","private","abstract"],"a":1},
            {"q":"Default value of int in Java?","opts":["null","0","1","-1"],"a":1},
            {"q":"Which collection maintains insertion order and allows duplicates?","opts":["HashSet","TreeSet","ArrayList","HashMap"],"a":2},
            {"q":"What does JVM stand for?","opts":["Java Virtual Machine","Java Visual Model","Java Variable Manager","Java Verified Module"],"a":0},
            {"q":"Exception thrown on dividing by zero?","opts":["NullPointerException","ArithmeticException","NumberFormatException","RuntimeException"],"a":1},
            {"q":"Which interface is implemented by ArrayList?","opts":["Queue","Deque","List","Set"],"a":2},
            {"q":"What is autoboxing in Java?","opts":["Converting int to Integer automatically","Manual type casting","Array wrapping","None"],"a":0},
        ]),'medium',12),
        (uid(),'Python',json.dumps([
            {"q":"Output of type([])?","opts":["<class 'list'>","<class 'array'>","<class 'tuple'>","list"],"a":0},
            {"q":"Keyword that defines a generator?","opts":["return","yield","generate","async"],"a":1},
            {"q":"What does *args allow?","opts":["keyword args","variable positional args","default args","dict args"],"a":1},
            {"q":"Create virtual environment with?","opts":["python -m venv env","pip venv env","python venv","create env"],"a":0},
            {"q":"What is a decorator?","opts":["A class modifier","A function that wraps another","A type hint","A module"],"a":1},
            {"q":"Which statement is used for list comprehension?","opts":["for x in list","[x for x in list]","map(list)","None"],"a":1},
            {"q":"What does 'pass' do in Python?","opts":["Exits a loop","Does nothing (placeholder)","Returns None","Raises StopIteration"],"a":1},
        ]),'medium',12),
        (uid(),'React',json.dumps([
            {"q":"Hook for local component state?","opts":["useEffect","useContext","useState","useRef"],"a":2},
            {"q":"JSX stands for?","opts":["JavaScript XML","Java Syntax Extension","JSON XML","JavaScript Extension"],"a":0},
            {"q":"What does useEffect with [] dependency do?","opts":["Runs on every render","Runs once on mount","Never runs","Runs on unmount"],"a":1},
            {"q":"Virtual DOM is?","opts":["A browser API","Lightweight copy of real DOM","A database","A CSS framework"],"a":1},
            {"q":"Which hook for side effects?","opts":["useState","useEffect","useCallback","useMemo"],"a":1},
            {"q":"How to pass data down to child components?","opts":["State","Props","Context only","Redux only"],"a":1},
            {"q":"Which method triggers re-render?","opts":["forceUpdate","setState","render","update"],"a":1},
        ]),'medium',12),
        (uid(),'SQL',json.dumps([
            {"q":"Clause filtering rows AFTER grouping?","opts":["WHERE","FILTER","HAVING","GROUP BY"],"a":2},
            {"q":"PRIMARY KEY is?","opts":["A foreign ref","Unique non-null identifier","An index","A constraint"],"a":1},
            {"q":"JOIN returning all rows from both tables?","opts":["INNER JOIN","LEFT JOIN","RIGHT JOIN","FULL OUTER JOIN"],"a":3},
            {"q":"What does DISTINCT do?","opts":["Sorts rows","Removes duplicate rows","Filters nulls","Groups rows"],"a":1},
            {"q":"Function counting non-null values?","opts":["SUM()","COUNT()","AVG()","MAX()"],"a":1},
            {"q":"What does INDEX improve?","opts":["Data insert speed","Query lookup speed","Storage size","Security"],"a":1},
            {"q":"ACID stands for?","opts":["Atomic Consistent Isolated Durable","All Checks In Database","Automatic Consistent Integrated Data","None"],"a":0},
        ]),'easy',10),
        (uid(),'System Design',json.dumps([
            {"q":"Horizontal scaling means?","opts":["Upgrading server hardware","Adding more servers","Increasing RAM","Optimizing code"],"a":1},
            {"q":"CDN is used for?","opts":["Database caching","Delivering static assets near users","Load balancing","API gateway"],"a":1},
            {"q":"CAP theorem stands for?","opts":["Consistency Availability Partition-tolerance","Cache API Performance","Compute Algorithm Process","None"],"a":0},
            {"q":"Message queue is used for?","opts":["SQL queries","Async decoupled communication","File storage","Auth"],"a":1},
            {"q":"Sharding means?","opts":["Replication","Partitioning data across DBs","Backup","Indexing"],"a":1},
            {"q":"What is a load balancer?","opts":["Distributes traffic across servers","A caching layer","A firewall","A database"],"a":0},
            {"q":"What does idempotent mean in APIs?","opts":["Fast response","Same result on repeated calls","No auth needed","Cached"],"a":1},
        ]),'hard',15),
        (uid(),'Spring Boot',json.dumps([
            {"q":"@RestController combines which two annotations?","opts":["@Controller + @RequestBody","@Controller + @ResponseBody","@Service + @Controller","@Bean + @Component"],"a":1},
            {"q":"Default embedded server in Spring Boot?","opts":["Jetty","Undertow","Tomcat","Netty"],"a":2},
            {"q":"@Autowired is used for?","opts":["Creating beans","Dependency injection","Exception handling","Transaction management"],"a":1},
            {"q":"application.properties vs application.yml?","opts":["Same purpose, different format","yml is faster","properties is newer","No difference"],"a":0},
            {"q":"@Transactional annotation?","opts":["Marks REST endpoints","Manages DB transactions","Caches results","Validates input"],"a":1},
            {"q":"Spring Data JPA's save() method?","opts":["Only inserts","Only updates","Insert or update (upsert)","Deletes record"],"a":2},
            {"q":"@Value annotation is used to?","opts":["Inject config properties","Create a new bean","Mark a REST method","Validate input"],"a":0},
        ]),'medium',12),
        (uid(),'AWS',json.dumps([
            {"q":"S3 is used for?","opts":["Compute","Object storage","Database","Networking"],"a":1},
            {"q":"EC2 provides?","opts":["Managed DBs","Virtual compute instances","DNS","CDN"],"a":1},
            {"q":"IAM stands for?","opts":["Internet Access Manager","Identity and Access Management","Internal App Module","None"],"a":1},
            {"q":"Lambda is?","opts":["A container service","Serverless compute","A message queue","A database"],"a":1},
            {"q":"RDS is?","opts":["Object storage","Managed relational database","NoSQL DB","Cache"],"a":1},
            {"q":"CloudFront is?","opts":["A firewall","A CDN","A load balancer","A scheduler"],"a":1},
            {"q":"SQS is?","opts":["A streaming service","A message queue","A cache","An API gateway"],"a":1},
        ]),'medium',12),
    ]
    c.executemany("INSERT INTO assessments VALUES(?,?,?,?,?)", asm)

    # ── talents ──
    talents = [
        (uid(),'sateesh@example.com',hp('pass123'),'talent','Sateesh Patil','Senior Java Backend Engineer','India','☕','4 years building enterprise-scale systems. 10M+ records/day, 99.9% uptime at ITOrizon. Passionate about clean APIs.',''),
        (uid(),'linh@example.com',hp('pass123'),'talent','Linh Tran','Frontend Engineer','Vietnam','🇻🇳','React + TypeScript specialist. Built high-performance dashboards for 500K+ users. Design-minded engineer.',''),
        (uid(),'kofi@example.com',hp('pass123'),'talent','Kofi Asante','Data Engineer','Ghana','🌍','Kafka, Spark, Python, SQL. Turning raw data into business insights for 3 years.',''),
        (uid(),'maria@example.com',hp('pass123'),'talent','Maria Silva','DevOps / Cloud Engineer','Brazil','🚀','Kubernetes, Terraform, AWS. Cut deployment times by 80%. Love automating everything.',''),
        (uid(),'arjun@example.com',hp('pass123'),'talent','Arjun Kumar','Full Stack Developer','India','💻','Node.js + React. Shipped 3 SaaS products from 0→1. 5 years experience.',''),
        (uid(),'nia@example.com',hp('pass123'),'talent','Nia Obi','ML Engineer','Nigeria','🤖','PyTorch, TensorFlow, Python. Building production AI systems that actually work.',''),
        (uid(),'yuki@example.com',hp('pass123'),'talent','Yuki Tanaka','Backend Engineer','Japan','🗾','Go + Rust specialist. Microservices, distributed systems, low-latency APIs.',''),
        (uid(),'emre@example.com',hp('pass123'),'talent','Emre Demir','Mobile Developer','Turkey','📱','React Native + Flutter. 8 published apps with 100K+ downloads combined.',''),
    ]
    recruiters = [
        (uid(),'recruiter1@techcorp.com',hp('pass123'),'recruiter','Alex Chen','Engineering Lead','Germany','🏢','Hiring engineers for TechCorp Berlin. We build infrastructure for 50M users.',''),
        (uid(),'recruiter2@startup.io',hp('pass123'),'recruiter','Sara Kim','Head of Talent','USA','🌟','Growing the team at Startup.io. We move fast and care about skills over pedigree.',''),
    ]
    for u in talents + recruiters:
        c.execute("INSERT INTO users(id,email,password,role,name,title,country,avatar,bio,linkedin) VALUES(?,?,?,?,?,?,?,?,?,?)", u)

    skill_map = [
        [('Java',88),('Spring Boot',85),('SQL',82),('AWS',78),('MarkLogic',90)],
        [('React',91),('TypeScript',89),('Next.js',86),('CSS',84),('Figma',80)],
        [('Python',86),('Apache Kafka',88),('Apache Spark',84),('SQL',90),('Airflow',76)],
        [('Kubernetes',89),('Terraform',91),('AWS',87),('Docker',85),('Linux',92)],
        [('Node.js',84),('React',82),('PostgreSQL',88),('Redis',80),('GraphQL',78)],
        [('Python',93),('PyTorch',90),('TensorFlow',88),('SQL',85),('MLflow',82)],
        [('Go',92),('Rust',88),('Docker',86),('PostgreSQL',84),('gRPC',80)],
        [('React Native',90),('Flutter',87),('Swift',78),('Kotlin',76),('Firebase',82)],
    ]
    for i, (tid_row, skls) in enumerate(zip(talents, skill_map)):
        for sname, score in skls:
            c.execute("INSERT INTO skills VALUES(?,?,?,?,1,0)", (str(uuid.uuid4()), tid_row[0], sname, score))

    # ── jobs ──
    r1 = recruiters[0][0]; r2 = recruiters[1][0]
    jobs = [
        (uid(),r1,'Senior Java Backend Engineer','TechCorp Berlin','Build scalable backend services for our enterprise data platform. You will own core APIs serving 5M+ users.',json.dumps(['Java','Spring Boot','SQL','AWS']),json.dumps(['Docker','Redis']),'Berlin, Germany (Hybrid)',90000,130000,'full-time','4+ years','active'),
        (uid(),r1,'React Frontend Engineer','TechCorp Berlin','Build beautiful, performant UIs for our SaaS product used by Fortune 500 companies.',json.dumps(['React','TypeScript','CSS']),json.dumps(['Next.js','Figma']),'Remote',80000,110000,'full-time','3+ years','active'),
        (uid(),r1,'DevOps / Cloud Engineer','TechCorp Berlin','Own our cloud infrastructure. Lead Kubernetes migration and CI/CD improvements.',json.dumps(['Kubernetes','Terraform','AWS']),json.dumps(['Docker','Linux']),'Berlin, Germany',85000,120000,'full-time','3+ years','active'),
        (uid(),r2,'ML Engineer','Startup.io','Ship AI features in a fast-moving startup. Production ML from day one.',json.dumps(['Python','PyTorch','TensorFlow']),json.dumps(['MLflow','SQL']),'San Francisco / Remote',120000,160000,'full-time','3+ years','active'),
        (uid(),r2,'Data Engineer','Startup.io','Design and maintain our data platform. 10B+ events/day.',json.dumps(['Python','Apache Kafka','SQL']),json.dumps(['Airflow','Spark']),'Remote',95000,130000,'full-time','3+ years','active'),
        (uid(),r2,'Full Stack Developer','Startup.io','Build new product features end-to-end. Own your stack.',json.dumps(['Node.js','React','PostgreSQL']),json.dumps(['GraphQL','Redis']),'Remote',85000,115000,'full-time','2+ years','active'),
        (uid(),r1,'Mobile Developer','TechCorp Berlin','Build our mobile apps for iOS and Android used by 2M+ users.',json.dumps(['React Native','Flutter']),json.dumps(['Firebase','TypeScript']),'Remote',80000,105000,'full-time','2+ years','active'),
    ]
    for j in jobs:
        c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))", j)

    # ── seed some applications ──
    talent_ids = [t[0] for t in talents]
    job_ids = [j[0] for j in jobs]
    for i, (tid, job_i, status) in enumerate([
        (talent_ids[0], 0, 'shortlisted'),
        (talent_ids[0], 3, 'pending'),
        (talent_ids[1], 1, 'pending'),
        (talent_ids[2], 4, 'shortlisted'),
        (talent_ids[3], 2, 'hired'),
    ]):
        talent_skills = [{'name': s[0]} for s in skill_map[talent_ids.index(tid)]]
        req = json.loads(jobs[job_i][5])
        ms = match_score(talent_skills, req)
        c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,NULL,NULL,datetime('now'))",
            (str(uuid.uuid4()), job_ids[job_i], tid, status, ms, 'I am excited about this opportunity.'))

    # ── seed some messages ──
    c.execute("INSERT INTO messages VALUES(?,?,?,?,?,0,datetime('now'))",
        (str(uuid.uuid4()), r1, talent_ids[0], 'Hi Sateesh! Your profile caught my eye. Would love to chat about our Java role.', 'text'))
    c.execute("INSERT INTO messages VALUES(?,?,?,?,?,0,datetime('now'))",
        (str(uuid.uuid4()), talent_ids[0], r1, 'Thanks Alex! Very interested. When are you available?', 'text'))

    # ── notifications ──
    c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,0,?,datetime('now'))",
        (str(uuid.uuid4()), talent_ids[0], 'application', 'Application Update', 'Your application to TechCorp Berlin was shortlisted! 🎉', '/applications'))
    c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,0,?,datetime('now'))",
        (str(uuid.uuid4()), talent_ids[0], 'message', 'New Message', 'Alex Chen sent you a message', '/messages'))

    c.commit()


# ═══════════════════════════════════════════════════════
#   AUTH
# ═══════════════════════════════════════════════════════
@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.json; c = db()
    try:
        if c.execute("SELECT id FROM users WHERE email=?", (d['email'],)).fetchone():
            return jsonify({'error': 'Email already registered'}), 400
        uid = str(uuid.uuid4())
        pw = bcrypt.hashpw(d['password'].encode(), bcrypt.gensalt()).decode()
        c.execute("INSERT INTO users(id,email,password,role,name,title,country,avatar,bio,linkedin) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (uid, d['email'], pw, d['role'], d['name'], d.get('title',''), d.get('country',''), d.get('avatar','👤'), d.get('bio',''), ''))
        c.commit()
        token = create_access_token(identity=uid)
        u = row(c.execute("SELECT id,email,name,role,title,country,avatar,bio FROM users WHERE id=?", (uid,)).fetchone())
        u['skills'] = []
        return jsonify({'token': token, 'user': u}), 201
    finally: c.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.json; c = db()
    try:
        u = c.execute("SELECT * FROM users WHERE email=?", (d['email'],)).fetchone()
        if not u or not bcrypt.checkpw(d['password'].encode(), u['password'].encode()):
            return jsonify({'error': 'Invalid email or password'}), 401
        token = create_access_token(identity=u['id'])
        user = row(c.execute("SELECT id,email,name,role,title,country,avatar,bio FROM users WHERE id=?", (u['id'],)).fetchone())
        user['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (u['id'],)).fetchall())
        return jsonify({'token': token, 'user': user})
    finally: c.close()

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    uid = get_jwt_identity(); c = db()
    try:
        u = row(c.execute("SELECT id,email,name,role,title,country,avatar,bio FROM users WHERE id=?", (uid,)).fetchone())
        if not u: return jsonify({'error': 'Not found'}), 404
        u['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (uid,)).fetchall())
        u['unread_notifications'] = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (uid,)).fetchone()[0]
        return jsonify(u)
    finally: c.close()

@app.route('/api/auth/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        c.execute("UPDATE users SET name=?,title=?,country=?,bio=? WHERE id=?",
            (d.get('name'), d.get('title'), d.get('country'), d.get('bio'), uid))
        c.commit()
        u = row(c.execute("SELECT id,email,name,role,title,country,avatar,bio FROM users WHERE id=?", (uid,)).fetchone())
        return jsonify(u)
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   TALENTS
# ═══════════════════════════════════════════════════════
@app.route('/api/talents', methods=['GET'])
def get_talents():
    c = db()
    try:
        skill_q = request.args.get('skill','').lower()
        country_q = request.args.get('country','').lower()
        search_q = request.args.get('search','').lower()
        ts = rows(c.execute("SELECT id,name,title,country,avatar,bio FROM users WHERE role='talent'").fetchall())
        result = []
        for t in ts:
            t['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (t['id'],)).fetchall())
            t['overall_score'] = int(sum(s['score'] for s in t['skills'])/len(t['skills'])) if t['skills'] else 0
            if skill_q and not any(skill_q in s['name'].lower() for s in t['skills']): continue
            if country_q and country_q not in (t['country'] or '').lower(): continue
            if search_q and search_q not in t['name'].lower() and not any(search_q in s['name'].lower() for s in t['skills']): continue
            result.append(t)
        result.sort(key=lambda x: x['overall_score'], reverse=True)
        return jsonify(result)
    finally: c.close()

@app.route('/api/talents/<tid>', methods=['GET'])
def get_talent(tid):
    c = db()
    try:
        t = row(c.execute("SELECT id,name,title,country,avatar,bio,created_at FROM users WHERE id=? AND role='talent'", (tid,)).fetchone())
        if not t: return jsonify({'error': 'Not found'}), 404
        t['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (tid,)).fetchall())
        t['overall_score'] = int(sum(s['score'] for s in t['skills'])/len(t['skills'])) if t['skills'] else 0
        t['assessment_count'] = c.execute("SELECT COUNT(*) FROM assessment_results WHERE user_id=?", (tid,)).fetchone()[0]
        return jsonify(t)
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   JOBS
# ═══════════════════════════════════════════════════════
@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    c = db()
    try:
        js = rows(c.execute("""SELECT j.*,u.name as recruiter_name,u.avatar as recruiter_avatar
            FROM jobs j JOIN users u ON j.recruiter_id=u.id WHERE j.status='active' ORDER BY j.created_at DESC""").fetchall())
        for j in js:
            j['required_skills'] = json.loads(j['required_skills'] or '[]')
            j['nice_skills'] = json.loads(j['nice_skills'] or '[]')
            j['application_count'] = c.execute("SELECT COUNT(*) FROM applications WHERE job_id=?", (j['id'],)).fetchone()[0]
        return jsonify(js)
    finally: c.close()

@app.route('/api/jobs/<jid>', methods=['GET'])
def get_job(jid):
    c = db()
    try:
        j = row(c.execute("SELECT j.*,u.name as recruiter_name FROM jobs j JOIN users u ON j.recruiter_id=u.id WHERE j.id=?", (jid,)).fetchone())
        if not j: return jsonify({'error': 'Not found'}), 404
        j['required_skills'] = json.loads(j['required_skills'] or '[]')
        j['nice_skills'] = json.loads(j['nice_skills'] or '[]')
        j['application_count'] = c.execute("SELECT COUNT(*) FROM applications WHERE job_id=?", (jid,)).fetchone()[0]
        return jsonify(j)
    finally: c.close()

@app.route('/api/jobs/recruiter/mine', methods=['GET'])
@jwt_required()
def my_jobs():
    uid = get_jwt_identity(); c = db()
    try:
        js = rows(c.execute("SELECT * FROM jobs WHERE recruiter_id=? ORDER BY created_at DESC", (uid,)).fetchall())
        for j in js:
            j['required_skills'] = json.loads(j['required_skills'] or '[]')
            j['nice_skills'] = json.loads(j['nice_skills'] or '[]')
            j['application_count'] = c.execute("SELECT COUNT(*) FROM applications WHERE job_id=?", (j['id'],)).fetchone()[0]
        return jsonify(js)
    finally: c.close()

@app.route('/api/jobs', methods=['POST'])
@jwt_required()
def create_job():
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        jid = str(uuid.uuid4())
        c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (jid, uid, d['title'], d['company'], d.get('description',''),
             json.dumps(d.get('required_skills',[])), json.dumps(d.get('nice_skills',[])),
             d.get('location','Remote'), d.get('salary_min',0), d.get('salary_max',0),
             d.get('job_type','full-time'), d.get('experience','2+ years'), 'active'))
        c.commit()
        return jsonify({'id': jid}), 201
    finally: c.close()

@app.route('/api/jobs/<jid>', methods=['PUT'])
@jwt_required()
def update_job(jid):
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        c.execute("UPDATE jobs SET title=?,description=?,required_skills=?,location=?,salary_min=?,salary_max=?,job_type=?,status=? WHERE id=? AND recruiter_id=?",
            (d.get('title'), d.get('description'), json.dumps(d.get('required_skills',[])), d.get('location'), d.get('salary_min'), d.get('salary_max'), d.get('job_type'), d.get('status','active'), jid, uid))
        c.commit()
        return jsonify({'message': 'Updated'})
    finally: c.close()

@app.route('/api/jobs/<jid>', methods=['DELETE'])
@jwt_required()
def close_job(jid):
    uid = get_jwt_identity(); c = db()
    try:
        c.execute("UPDATE jobs SET status='closed' WHERE id=? AND recruiter_id=?", (jid, uid))
        c.commit()
        return jsonify({'message': 'Closed'})
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   AI MATCHING
# ═══════════════════════════════════════════════════════
@app.route('/api/match/jobs/<talent_id>', methods=['GET'])
@jwt_required()
def match_jobs(talent_id):
    c = db()
    try:
        ts = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (talent_id,)).fetchall())
        js = rows(c.execute("SELECT j.*,u.name as recruiter_name FROM jobs j JOIN users u ON j.recruiter_id=u.id WHERE j.status='active'").fetchall())
        for j in js:
            j['required_skills'] = json.loads(j['required_skills'] or '[]')
            j['nice_skills'] = json.loads(j['nice_skills'] or '[]')
            req_ms = match_score(ts, j['required_skills'])
            nice_ms = match_score(ts, j['nice_skills'])
            j['match_score'] = min(100, req_ms + int(nice_ms * 0.15))
            j['req_match'] = req_ms
            avg_skill = int(sum(s['score'] for s in ts)/len(ts)) if ts else 0
            j['ai_score'] = int(j['match_score'] * 0.6 + avg_skill * 0.4)
        js.sort(key=lambda x: x['ai_score'], reverse=True)
        return jsonify(js)
    finally: c.close()

@app.route('/api/match/talents/<job_id>', methods=['GET'])
@jwt_required()
def match_talents(job_id):
    c = db()
    try:
        j = row(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
        if not j: return jsonify({'error': 'Not found'}), 404
        req = json.loads(j['required_skills'] or '[]')
        ts = rows(c.execute("SELECT id,name,title,country,avatar,bio FROM users WHERE role='talent'").fetchall())
        for t in ts:
            t['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (t['id'],)).fetchall())
            t['overall_score'] = int(sum(s['score'] for s in t['skills'])/len(t['skills'])) if t['skills'] else 0
            t['match_score'] = match_score(t['skills'], req)
            t['ai_score'] = int(t['match_score'] * 0.65 + t['overall_score'] * 0.35)
        ts.sort(key=lambda x: x['ai_score'], reverse=True)
        return jsonify(ts)
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   APPLICATIONS
# ═══════════════════════════════════════════════════════
@app.route('/api/applications', methods=['POST'])
@jwt_required()
def apply():
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        if c.execute("SELECT id FROM applications WHERE job_id=? AND talent_id=?", (d['job_id'], uid)).fetchone():
            return jsonify({'error': 'Already applied to this job'}), 400
        ts = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (uid,)).fetchall())
        j = row(c.execute("SELECT required_skills,recruiter_id,title FROM jobs WHERE id=?", (d['job_id'],)).fetchone())
        req = json.loads(j['required_skills'] or '[]') if j else []
        ms = match_score(ts, req)
        aid = str(uuid.uuid4())
        c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,NULL,NULL,datetime('now'))",
            (aid, d['job_id'], uid, 'pending', ms, d.get('cover_note','')))
        # Notify recruiter
        applicant = row(c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone())
        c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,0,?,datetime('now'))",
            (str(uuid.uuid4()), j['recruiter_id'], 'application', 'New Application',
             f"{applicant['name']} applied to {j['title']}", '/applications'))
        c.commit()
        return jsonify({'id': aid, 'match_score': ms}), 201
    finally: c.close()

@app.route('/api/applications/talent', methods=['GET'])
@jwt_required()
def talent_apps():
    uid = get_jwt_identity(); c = db()
    try:
        apps = rows(c.execute("""SELECT a.*,j.title,j.company,j.location,j.job_type,j.salary_min,j.salary_max,
            u.name as recruiter_name, u.avatar as recruiter_avatar
            FROM applications a JOIN jobs j ON a.job_id=j.id
            JOIN users u ON j.recruiter_id=u.id
            WHERE a.talent_id=? ORDER BY a.created_at DESC""", (uid,)).fetchall())
        return jsonify(apps)
    finally: c.close()

@app.route('/api/applications/recruiter', methods=['GET'])
@jwt_required()
def recruiter_apps():
    uid = get_jwt_identity(); c = db()
    try:
        job_filter = request.args.get('job_id')
        q = """SELECT a.*,j.title,j.company,u.name as talent_name,u.title as talent_title,
            u.country as talent_country,u.avatar as talent_avatar
            FROM applications a JOIN jobs j ON a.job_id=j.id
            JOIN users u ON a.talent_id=u.id
            WHERE j.recruiter_id=?"""
        params = [uid]
        if job_filter: q += " AND a.job_id=?"; params.append(job_filter)
        q += " ORDER BY a.match_score DESC"
        apps = rows(c.execute(q, params).fetchall())
        for a in apps:
            a['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (a['talent_id'],)).fetchall())
        return jsonify(apps)
    finally: c.close()

@app.route('/api/applications/<aid>/status', methods=['PUT'])
@jwt_required()
def update_app_status(aid):
    d = request.json; c = db()
    try:
        app_row = row(c.execute("SELECT a.*,j.title FROM applications a JOIN jobs j ON a.job_id=j.id WHERE a.id=?", (aid,)).fetchone())
        c.execute("UPDATE applications SET status=? WHERE id=?", (d['status'], aid))
        # Notify talent
        msg_map = {'shortlisted': '🎉 Shortlisted', 'hired': '🥳 Hired!', 'rejected': 'Application reviewed'}
        if app_row and d['status'] in msg_map:
            c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,0,?,datetime('now'))",
                (str(uuid.uuid4()), app_row['talent_id'], 'application', 'Application Update',
                 f"{msg_map[d['status']]} for {app_row['title']}", '/applications'))
        if d.get('interview_link'):
            c.execute("UPDATE applications SET interview_link=?,interview_scheduled=? WHERE id=?",
                (d['interview_link'], d.get('interview_scheduled'), aid))
        c.commit()
        return jsonify({'message': 'Updated'})
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   ASSESSMENTS
# ═══════════════════════════════════════════════════════
@app.route('/api/assessments', methods=['GET'])
def get_assessments():
    c = db()
    try:
        return jsonify(rows(c.execute("SELECT id,skill_name,difficulty,time_limit FROM assessments").fetchall()))
    finally: c.close()

@app.route('/api/assessments/<aid>', methods=['GET'])
@jwt_required()
def get_assessment(aid):
    c = db()
    try:
        a = row(c.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone())
        if not a: return jsonify({'error': 'Not found'}), 404
        qs = json.loads(a['questions'])
        for q in qs: q.pop('a', None)
        a['questions'] = qs
        return jsonify(a)
    finally: c.close()

@app.route('/api/assessments/<aid>/submit', methods=['POST'])
@jwt_required()
def submit_assessment(aid):
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        a = row(c.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone())
        if not a: return jsonify({'error': 'Not found'}), 404
        qs = json.loads(a['questions'])
        answers = d.get('answers', [])
        correct = sum(1 for i, q in enumerate(qs) if i < len(answers) and answers[i] == q['a'])
        score = int(correct / len(qs) * 100)
        c.execute("INSERT INTO assessment_results VALUES(?,?,?,?,?,?,datetime('now'))",
            (str(uuid.uuid4()), uid, aid, score, json.dumps(answers), d.get('time_taken', 0)))
        existing = c.execute("SELECT id FROM skills WHERE user_id=? AND name=?", (uid, a['skill_name'])).fetchone()
        if existing:
            c.execute("UPDATE skills SET score=?,verified=1 WHERE user_id=? AND name=?", (score, uid, a['skill_name']))
        else:
            c.execute("INSERT INTO skills VALUES(?,?,?,?,1,0)", (str(uuid.uuid4()), uid, a['skill_name'], score))
        c.commit()
        return jsonify({'score': score, 'correct': correct, 'total': len(qs)})
    finally: c.close()

@app.route('/api/assessments/results/me', methods=['GET'])
@jwt_required()
def my_results():
    uid = get_jwt_identity(); c = db()
    try:
        rs = rows(c.execute("""SELECT ar.*,a.skill_name,a.difficulty FROM assessment_results ar
            JOIN assessments a ON ar.assessment_id=a.id
            WHERE ar.user_id=? ORDER BY ar.completed_at DESC""", (uid,)).fetchall())
        return jsonify(rs)
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   MESSAGES
# ═══════════════════════════════════════════════════════
@app.route('/api/messages/conversations', methods=['GET'])
@jwt_required()
def get_convs():
    uid = get_jwt_identity(); c = db()
    try:
        other_ids = rows(c.execute("""SELECT DISTINCT CASE WHEN sender_id=? THEN receiver_id ELSE sender_id END as oid
            FROM messages WHERE sender_id=? OR receiver_id=?""", (uid, uid, uid)).fetchall())
        convs = []
        for r in other_ids:
            other = row(c.execute("SELECT id,name,avatar,role,title FROM users WHERE id=?", (r['oid'],)).fetchone())
            if not other: continue
            last = row(c.execute("""SELECT content,created_at FROM messages
                WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                ORDER BY created_at DESC LIMIT 1""", (uid, r['oid'], r['oid'], uid)).fetchone())
            unread = c.execute("SELECT COUNT(*) FROM messages WHERE sender_id=? AND receiver_id=? AND read=0", (r['oid'], uid)).fetchone()[0]
            other['last_message'] = last
            other['unread'] = unread
            convs.append(other)
        convs.sort(key=lambda x: x['last_message']['created_at'] if x['last_message'] else '', reverse=True)
        return jsonify(convs)
    finally: c.close()

@app.route('/api/messages/<other_id>', methods=['GET'])
@jwt_required()
def get_messages(other_id):
    uid = get_jwt_identity(); c = db()
    try:
        msgs = rows(c.execute("""SELECT m.*,u.name as sender_name,u.avatar as sender_avatar
            FROM messages m JOIN users u ON m.sender_id=u.id
            WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
            ORDER BY m.created_at ASC""", (uid, other_id, other_id, uid)).fetchall())
        c.execute("UPDATE messages SET read=1 WHERE sender_id=? AND receiver_id=?", (other_id, uid))
        c.commit()
        return jsonify(msgs)
    finally: c.close()

@app.route('/api/messages', methods=['POST'])
@jwt_required()
def send_message():
    uid = get_jwt_identity(); d = request.json; c = db()
    try:
        mid = str(uuid.uuid4())
        c.execute("INSERT INTO messages VALUES(?,?,?,?,?,0,datetime('now'))",
            (mid, uid, d['receiver_id'], d['content'], d.get('msg_type','text')))
        sender = row(c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone())
        c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,0,?,datetime('now'))",
            (str(uuid.uuid4()), d['receiver_id'], 'message', 'New Message',
             f"{sender['name']}: {d['content'][:60]}", '/messages'))
        c.commit()
        return jsonify({'id': mid}), 201
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   ANALYTICS
# ═══════════════════════════════════════════════════════
@app.route('/api/analytics/recruiter', methods=['GET'])
@jwt_required()
def recruiter_analytics():
    uid = get_jwt_identity(); c = db()
    try:
        def q1(sql, *p): return c.execute(sql, p).fetchone()[0]
        total_jobs = q1("SELECT COUNT(*) FROM jobs WHERE recruiter_id=?", uid)
        active_jobs = q1("SELECT COUNT(*) FROM jobs WHERE recruiter_id=? AND status='active'", uid)
        total_apps = q1("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=?", uid)
        shortlisted = q1("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=? AND a.status='shortlisted'", uid)
        hired = q1("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=? AND a.status='hired'", uid)
        avg_match = c.execute("SELECT AVG(a.match_score) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=?", (uid,)).fetchone()[0] or 0
        top_skills = rows(c.execute("SELECT name,COUNT(*) as cnt FROM skills JOIN users ON skills.user_id=users.id WHERE users.role='talent' GROUP BY name ORDER BY cnt DESC LIMIT 8").fetchall())
        jobs_pipeline = rows(c.execute("""SELECT j.title,j.id,
            COUNT(CASE WHEN a.status='pending' THEN 1 END) as pending,
            COUNT(CASE WHEN a.status='shortlisted' THEN 1 END) as shortlisted,
            COUNT(CASE WHEN a.status='hired' THEN 1 END) as hired
            FROM jobs j LEFT JOIN applications a ON j.id=a.job_id
            WHERE j.recruiter_id=? GROUP BY j.id ORDER BY pending DESC LIMIT 6""", (uid,)).fetchall())
        weekly = rows(c.execute("""SELECT date(created_at) as day, COUNT(*) as count
            FROM applications a JOIN jobs j ON a.job_id=j.id
            WHERE j.recruiter_id=? AND created_at >= date('now','-7 days')
            GROUP BY date(created_at) ORDER BY day""", (uid,)).fetchall())
        return jsonify({'total_jobs':total_jobs,'active_jobs':active_jobs,'total_applications':total_apps,
            'shortlisted':shortlisted,'hired':hired,'avg_match_score':round(avg_match,1),
            'top_skills':top_skills,'jobs_pipeline':jobs_pipeline,'weekly_applications':weekly})
    finally: c.close()

@app.route('/api/analytics/talent', methods=['GET'])
@jwt_required()
def talent_analytics():
    uid = get_jwt_identity(); c = db()
    try:
        skills = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (uid,)).fetchall())
        total_apps = c.execute("SELECT COUNT(*) FROM applications WHERE talent_id=?", (uid,)).fetchone()[0]
        shortlisted = c.execute("SELECT COUNT(*) FROM applications WHERE talent_id=? AND status='shortlisted'", (uid,)).fetchone()[0]
        hired = c.execute("SELECT COUNT(*) FROM applications WHERE talent_id=? AND status='hired'", (uid,)).fetchone()[0]
        results = rows(c.execute("""SELECT ar.*,a.skill_name FROM assessment_results ar
            JOIN assessments a ON ar.assessment_id=a.id WHERE ar.user_id=? ORDER BY completed_at DESC LIMIT 8""", (uid,)).fetchall())
        market_avg = rows(c.execute("""SELECT name, AVG(score) as avg_score FROM skills
            GROUP BY name ORDER BY avg_score DESC""").fetchall())
        return jsonify({'skills':skills,'overall_score':int(sum(s['score'] for s in skills)/len(skills)) if skills else 0,
            'total_applications':total_apps,'shortlisted':shortlisted,'hired':hired,
            'assessment_history':results,'market_averages':market_avg})
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   SAVED TALENTS
# ═══════════════════════════════════════════════════════
@app.route('/api/saved-talents', methods=['GET'])
@jwt_required()
def get_saved():
    uid = get_jwt_identity(); c = db()
    try:
        saved = rows(c.execute("""SELECT u.id,u.name,u.title,u.country,u.avatar,u.bio,st.note,st.created_at as saved_at
            FROM saved_talents st JOIN users u ON st.talent_id=u.id WHERE st.recruiter_id=?""", (uid,)).fetchall())
        for s in saved:
            s['skills'] = rows(c.execute("SELECT * FROM skills WHERE user_id=?", (s['id'],)).fetchall())
            s['overall_score'] = int(sum(sk['score'] for sk in s['skills'])/len(s['skills'])) if s['skills'] else 0
        return jsonify(saved)
    finally: c.close()

@app.route('/api/saved-talents/<tid>', methods=['POST'])
@jwt_required()
def save_talent(tid):
    uid = get_jwt_identity(); d = request.json or {}; c = db()
    try:
        c.execute("INSERT OR REPLACE INTO saved_talents VALUES(?,?,?,datetime('now'))", (uid, tid, d.get('note','')))
        c.commit()
        return jsonify({'saved': True})
    finally: c.close()

@app.route('/api/saved-talents/<tid>', methods=['DELETE'])
@jwt_required()
def unsave_talent(tid):
    uid = get_jwt_identity(); c = db()
    try:
        c.execute("DELETE FROM saved_talents WHERE recruiter_id=? AND talent_id=?", (uid, tid))
        c.commit()
        return jsonify({'saved': False})
    finally: c.close()


# ═══════════════════════════════════════════════════════
#   NOTIFICATIONS
# ═══════════════════════════════════════════════════════
@app.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    uid = get_jwt_identity(); c = db()
    try:
        ns = rows(c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (uid,)).fetchall())
        return jsonify(ns)
    finally: c.close()

@app.route('/api/notifications/read-all', methods=['PUT'])
@jwt_required()
def read_all_notifications():
    uid = get_jwt_identity(); c = db()
    try:
        c.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
        c.commit()
        return jsonify({'message': 'OK'})
    finally: c.close()


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0'})

if __name__ == '__main__':
    init()
    print("✅ SkillMatch Backend v2 running on http://localhost:5001")
    app.run(debug=False, port=5001)
