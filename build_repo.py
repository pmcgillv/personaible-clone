from pathlib import Path
import subprocess

GITHUB_USER = "PMCGILLV"
REPO_NAME = "personaible-clone"
FILES = {}

FILES["README.md"] = """# PersonAIble Clone

Find broken local business websites -> auto-build previews -> sell the fix.

## Quick Start
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in API keys
3. `python scanner/scan.py`
4. `python builder/build.py`
5. `python server/app.py`
6. Open http://localhost:5000
"""

FILES[".gitignore"] = """.env
__pycache__/
*.pyc
scanner/leads.db
preview/sites/*
!preview/sites/.gitkeep
.DS_Store
node_modules/
*.log
"""

FILES[".env.example"] = """OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
RESEND_API_KEY=re_...
FROM_EMAIL=you@yourdomain.com
HEYGEN_API_KEY=...
HEYGEN_AVATAR_ID=...
GOOGLE_PLACES_API_KEY=...
BASE_URL=http://localhost:5000
CALENDLY_URL=https://calendly.com/yourname/10min
YOUR_NAME=Your Name
"""

FILES["requirements.txt"] = """requests
beautifulsoup4
openai
jinja2
stripe
resend
flask
python-dotenv
"""

FILES["scanner/__init__.py"] = ""

FILES["scanner/scan.py"] = r'''"""Lead Scanner."""
import os, sqlite3, requests, time
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
DB = "scanner/leads.db"
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, website TEXT,
        email TEXT, phone TEXT, address TEXT, industry TEXT,
        has_ssl INTEGER, has_chatbot INTEGER, has_social INTEGER,
        has_video INTEGER, problems TEXT, status TEXT DEFAULT 'new',
        preview_url TEXT, scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close()


def find_businesses(query, location, max_results=20):
    if not GOOGLE_API_KEY:
        print("No GOOGLE_PLACES_API_KEY - using sample")
        return [{"name": "Joe's Plumbing", "website": "http://example.com",
                 "phone": "555-0100", "address": "Austin, TX", "industry": "plumber"}]
    r = requests.get("https://maps.googleapis.com/maps/api/place/textsearch/json",
        params={"query": f"{query} in {location}", "key": GOOGLE_API_KEY}, timeout=10).json()
    out = []
    for place in r.get("results", [])[:max_results]:
        d = requests.get("https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place["place_id"],
                    "fields": "name,website,formatted_phone_number,formatted_address",
                    "key": GOOGLE_API_KEY}, timeout=10).json().get("result", {})
        out.append({"name": d.get("name", place.get("name")),
                    "website": d.get("website", ""),
                    "phone": d.get("formatted_phone_number", ""),
                    "address": d.get("formatted_address", ""),
                    "industry": query})
        time.sleep(0.2)
    return out


def check_ssl(url):
    if not url: return False
    try:
        if not url.startswith("https://"): return False
        return requests.get(url, timeout=5).ok
    except: return False


def check_chatbot(s):
    h = str(s).lower()
    return any(x in h for x in ["intercom","drift","tawk","crisp","livechat","tidio","chatbot"])

def check_social(s):
    h = str(s).lower()
    return any(p in h for p in ["facebook.com","instagram.com","twitter.com","linkedin.com"])

def check_video(s):
    h = str(s).lower()
    return any(x in h for x in ["youtube.com/embed","vimeo.com","<video","wistia"])


def scan_site(url):
    if not url: return None
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        return {"has_ssl": check_ssl(url), "has_chatbot": check_chatbot(soup),
                "has_social": check_social(soup), "has_video": check_video(soup)}
    except Exception as e:
        print(f"  Scan failed: {e}"); return None


def save_lead(b):
    p = b["problems"]
    probs = [k for k, v in p.items() if not v]
    conn = sqlite3.connect(DB)
    conn.execute("""INSERT INTO leads (name, website, email, phone, address, industry,
        has_ssl, has_chatbot, has_social, has_video, problems)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (b["name"], b["website"], b.get("email",""), b["phone"], b["address"], b["industry"],
         int(p["has_ssl"]), int(p["has_chatbot"]), int(p["has_social"]), int(p["has_video"]),
         ",".join(probs)))
    conn.commit(); conn.close()
    return probs


def main():
    init_db()
    print("Lead Scanner starting...\n")
    for q, loc in [("plumber","Austin, TX"),("dentist","Austin, TX"),("contractor","Austin, TX")]:
        print(f"Finding {q}s in {loc}...")
        for b in find_businesses(q, loc, 10):
            if not b["website"]:
                print(f"  {b['name']} - no website"); continue
            print(f"  Scanning {b['name']}...")
            pr = scan_site(b["website"])
            if pr:
                b["problems"] = pr
                found = save_lead(b)
                print(f"     Saved - problems: {', '.join(found) or 'none'}")
            time.sleep(1)
    print("\nDone. Leads in scanner/leads.db")


if __name__ == "__main__":
    main()
'''

FILES["builder/__init__.py"] = ""

FILES["builder/rewrite.py"] = r'''"""GPT copy rewriting."""
import os, json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def rewrite_content(scraped):
    prompt = f"""You are a website copywriter. Rewrite this business's content.
    Return JSON with keys: headline, subheadline, about, services (list of
    {{name, description}}), cta_text, meta_title, meta_description.
    Business data: {json.dumps(scraped, indent=2)}"""
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}, temperature=0.7)
    return json.loads(r.choices[0].message.content)
'''

FILES["builder/build.py"] = r'''"""Builds preview site for a lead."""
import os, sqlite3
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
load_dotenv()
env = Environment(loader=FileSystemLoader("builder/templates"))
DB = "scanner/leads.db"


def build_site(lead_id):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    if not lead: raise ValueError(f"No lead {lead_id}")
    industry = (lead["industry"] or "plumber").lower()
    tname = industry if industry in ["plumber","dentist","contractor"] else "plumber"
    try:
        from builder.rewrite import rewrite_content
        content = rewrite_content({"name": lead["name"], "industry": lead["industry"],
                                    "address": lead["address"]})
    except Exception as e:
        print(f"  AI rewrite skipped ({e})")
        content = {"headline": f"Trusted {industry.title()} Services",
                   "subheadline": f"Serving {lead['address'] or 'your area'}",
                   "about": f"{lead['name']} is your local {industry} expert.",
                   "services": [{"name": f"Service {i}", "description": "Quality work."} for i in range(1,5)],
                   "cta_text": "Call Now",
                   "meta_title": f"{lead['name']}",
                   "meta_description": f"Professional {industry} services."}
    tpl = env.get_template(f"{tname}.html")
    html = tpl.render(business_name=lead["name"], phone=lead["phone"] or "Call us",
                       address=lead["address"] or "", lead_id=lead_id, **content)
    out = f"preview/sites/{lead_id}"
    os.makedirs(out, exist_ok=True)
    with open(f"{out}/index.html", "w", encoding="utf-8") as f: f.write(html)
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE leads SET preview_url = ? WHERE id = ?", (f"/sites/{lead_id}/", lead_id))
    conn.commit(); conn.close()
    print(f"Built preview for {lead['name']}")
    return f"{out}/index.html"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        build_site(int(sys.argv[1]))
    else:
        conn = sqlite3.connect(DB)
        ids = [r[0] for r in conn.execute("SELECT id FROM leads WHERE preview_url IS NULL").fetchall()]
        conn.close()
        for lid in ids:
            try: build_site(lid)
            except Exception as e: print(f"  Lead {lid} failed: {e}")
'''

TPL = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{meta_title}}</title>
<meta name="description" content="{{meta_description}}">
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="font-sans text-gray-900">
<section class="bg-blue-600 text-white py-20 px-6 text-center">
  <h1 class="text-4xl md:text-5xl font-bold mb-4">{{headline}}</h1>
  <p class="text-xl mb-8 opacity-90">{{subheadline}}</p>
  <a href="tel:{{phone}}" class="inline-block bg-white text-blue-600 px-8 py-4 rounded-lg font-bold text-lg">
    {{cta_text}}: {{phone}}</a></section>
<section class="py-16 px-6 max-w-5xl mx-auto">
  <h2 class="text-3xl font-bold text-center mb-12">Our Services</h2>
  <div class="grid md:grid-cols-2 gap-6">
    {% for s in services %}<div class="border rounded-xl p-6 hover:shadow-lg">
      <h3 class="text-xl font-bold mb-2">{{s.name}}</h3>
      <p class="text-gray-600">{{s.description}}</p></div>{% endfor %}
  </div></section>
<section class="bg-gray-100 py-16 px-6">
  <div class="max-w-3xl mx-auto text-center">
    <h2 class="text-3xl font-bold mb-6">About {{business_name}}</h2>
    <p class="text-lg text-gray-700">{{about}}</p>
    {% if address %}<p class="mt-4 text-gray-500">{{address}}</p>{% endif %}
  </div></section>
<section class="bg-blue-600 text-white py-16 px-6 text-center">
  <h2 class="text-3xl font-bold mb-4">Ready to Get Started?</h2>
  <a href="tel:{{phone}}" class="inline-block bg-white text-blue-600 px-8 py-4 rounded-lg font-bold text-lg">
    Call Now: {{phone}}</a></section>
</body></html>'''

FILES["builder/templates/plumber.html"] = TPL
FILES["builder/templates/dentist.html"] = TPL.replace("bg-blue-600","bg-teal-600").replace("text-blue-600","text-teal-600").replace("bg-gray-100","bg-teal-50")
FILES["builder/templates/contractor.html"] = TPL.replace("bg-blue-600","bg-orange-600").replace("text-blue-600","text-orange-600")

FILES["email/__init__.py"] = ""

FILES["email/send.py"] = r'''"""Outreach email sender."""
import os, sqlite3, resend
from dotenv import load_dotenv
load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")
FROM = os.getenv("FROM_EMAIL", "you@yourdomain.com")
BASE = os.getenv("BASE_URL", "http://localhost:5000")


def build_email(lead):
    url = f"{BASE}/preview/{lead['id']}"
    probs = (lead["problems"] or "").split(",")
    labels = {"has_ssl": "your site shows 'Not Secure'",
              "has_chatbot": "no chatbot for after-hours",
              "has_social": "invisible on social media",
              "has_video": "missing video on homepage"}
    issues = [labels[p] for p in probs if p in labels]
    bullets = "\n".join([f"  - {i}" for i in issues])
    subject = f"Quick question about {lead['name']}'s website"
    body = f"""Hi {lead['name']} team,

I built a preview of what your site could look like with a few fixes.

Issues found:
{bullets}

Preview: {url}

(Note: temporary mockup. Final site is custom-designed.)

Book a call: {os.getenv('CALENDLY_URL', '')}

- {os.getenv('YOUR_NAME', 'Your Name')}
"""
    return subject, body


def send_to_lead(lead_id):
    conn = sqlite3.connect("scanner/leads.db"); conn.row_factory = sqlite3.Row
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    if not lead or not lead["email"]:
        print(f"Lead {lead_id} has no email"); return
    subj, body = build_email(lead)
    try:
        resend.Emails.send({"from": FROM, "to": lead["email"], "subject": subj, "text": body})
        conn = sqlite3.connect("scanner/leads.db")
        conn.execute("UPDATE leads SET status='sent' WHERE id=?", (lead_id,))
        conn.commit(); conn.close()
        print(f"Sent to {lead['email']}")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        send_to_lead(int(sys.argv[1]))
    else:
        conn = sqlite3.connect("scanner/leads.db")
        ids = [r[0] for r in conn.execute("SELECT id FROM leads WHERE status='new' AND email!=''").fetchall()]
        conn.close()
        for lid in ids: send_to_lead(lid)
'''

FILES["video/__init__.py"] = ""

FILES["video/generate.py"] = r'''"""HeyGen AI video."""
import os, time, requests
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("HEYGEN_API_KEY")
AVATAR = os.getenv("HEYGEN_AVATAR_ID")


def build_script(lead):
    probs = (lead["problems"] or "").split(",")
    labels = {"has_ssl": "a 'Not Secure' warning",
              "has_chatbot": "no chatbot for after-hours",
              "has_social": "no social media presence",
              "has_video": "no video on homepage"}
    issue = next((labels[p] for p in probs if p in labels), "a few issues")
    return f"Hi {lead['name']} team, I noticed {issue} on your site. Check your inbox for a preview."


def generate_video(lead):
    if not KEY or not AVATAR:
        print("HeyGen not configured"); return None
    r = requests.post("https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": KEY, "Content-Type": "application/json"},
        json={"video_inputs": [{"character": {"type": "avatar", "avatar_id": AVATAR,
            "avatar_style": "normal"}, "voice": {"type": "text",
            "input_text": build_script(lead), "voice_id": "en-US-JennyNeural"}}],
            "dimension": {"width": 1280, "height": 720}}, timeout=30)
    vid = r.json().get("data", {}).get("video_id")
    if not vid: print("Failed"); return None
    for _ in range(60):
        time.sleep(10)
        s = requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid}",
            headers={"X-Api-Key": KEY}, timeout=10).json()
        st = s.get("data", {}).get("status")
        if st == "completed":
            url = s["data"]["video_url"]; print(f"Video: {url}"); return url
        if st == "failed": print("Failed"); return None
    return None


if __name__ == "__main__":
    import sys, sqlite3
    conn = sqlite3.connect("scanner/leads.db"); conn.row_factory = sqlite3.Row
    lead = conn.execute("SELECT * FROM leads WHERE id=?", (int(sys.argv[1]),)).fetchone()
    conn.close()
    if lead: generate_video(lead)
'''

FILES["server/__init__.py"] = ""

FILES["server/app.py"] = r'''"""Flask server - previews, checkout, info capture."""
import os, sqlite3, stripe
from flask import Flask, render_template_string, send_from_directory, request, jsonify
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
DB = "scanner/leads.db"
BASE = os.getenv("BASE_URL", "http://localhost:5000")

PREVIEW = """
<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preview</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 font-sans">
<div class="sticky top-0 z-50 bg-yellow-400 text-black px-4 py-3 text-center text-sm font-medium border-b-2 border-black">
  TEMPORARY PREVIEW ONLY - AI mockup. Final site may look different.
  <a href="#get-started" class="ml-3 underline font-bold">Get Started</a></div>
<div class="bg-gray-300 px-4 py-2 flex items-center gap-3 border-b border-gray-400">
  <div class="flex gap-1.5"><span class="w-3 h-3 rounded-full bg-gray-500"></span>
  <span class="w-3 h-3 rounded-full bg-gray-500"></span>
  <span class="w-3 h-3 rounded-full bg-gray-500"></span></div>
  <div class="flex-1 bg-white rounded-full px-3 py-1 text-xs text-gray-500">{{domain}}</div></div>
<iframe src="/sites/{{lead_id}}/" class="w-full h-[600px] bg-white border-0 block"></iframe>
<section class="max-w-2xl mx-auto my-10 bg-white rounded-2xl shadow-lg p-8" id="get-started">
  <h1 class="text-3xl font-bold mb-6">Here's what we fixed for {{name}}</h1>
  <ul class="space-y-2 mb-6">{% for f in fixes %}<li class="text-lg">{{f}}</li>{% endfor %}</ul>
  <div class="text-center my-6">
    <span class="block line-through text-gray-400">$2,000 - $5,000</span>
    <span class="block text-3xl font-bold mt-1">Your price today: $397</span></div>
  <button id="checkout-btn" class="w-full bg-green-500 hover:bg-green-600 text-white py-4 rounded-xl text-lg font-bold mt-5">
    Reserve My Site - $397</button>
  <p class="text-center text-green-600 mt-3">60-day money-back guarantee</p>
  <div class="text-center my-6 text-gray-400">- or -</div>
  <a href="{{calendly}}" class="block text-center bg-black text-white py-4 rounded-xl font-semibold">
    Book a 10-Min Call</a>
  <div class="text-center my-6 text-gray-400">- or -</div>
  <form id="info-form" class="space-y-3">
    <h3 class="text-lg font-bold">Not ready yet?</h3>
    <select name="interest" required class="w-full p-3 border rounded-lg">
      <option value="">What do you want to know?</option>
      <option value="pricing">Pricing</option>
      <option value="examples">Examples</option>
      <option value="call">Book a call</option>
      <option value="later">Not ready yet</option></select>
    <input type="email" name="email" placeholder="Your email" required class="w-full p-3 border rounded-lg">
    <input type="text" name="name" placeholder="Your name (optional)" class="w-full p-3 border rounded-lg">
    <button type="submit" class="w-full bg-black text-white py-3 rounded-lg font-semibold">
      Send Me Info</button></form></section>
<footer class="text-center py-10 text-xs text-gray-400">
  Temporary AI preview for illustration only.</footer>
<script>
const LEAD_ID = {{lead_id}};
document.getElementById('checkout-btn').addEventListener('click', async () => {
  const res = await fetch('/api/create-checkout', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({lead_id:LEAD_ID})});
  const d = await res.json();
  if (d.url) window.location.href = d.url;
  else alert('Error: ' + (d.error||'unknown'));
});
document.getElementById('info-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  d.lead_id = LEAD_ID;
  await fetch('/api/capture-info', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(d)});
  e.target.innerHTML = '<p class="text-center py-4">Thanks!</p>';
});
</script></body></html>
"""


def get_lead(lid):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    l = conn.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    conn.close()
    return l


@app.route("/")
def home():
    conn = sqlite3.connect(DB)
    try: leads = conn.execute("SELECT id,name,problems FROM leads ORDER BY id DESC LIMIT 50").fetchall()
    except: leads = []
    conn.close()
    rows = "".join([f'<li><a href="/preview/{l[0]}">{l[0]}. {l[1]} - {l[2]}</a></li>' for l in leads])
    return f"<h1>Leads</h1><ul>{rows}</ul>"


@app.route("/preview/<int:lid>")
def preview(lid):
    lead = get_lead(lid)
    if not lead: return "Not found", 404
    labels = {"has_ssl": "Fixed SSL certificate",
              "has_chatbot": "Added AI chatbot",
              "has_social": "Set up social media",
              "has_video": "Added homepage video"}
    probs = (lead["problems"] or "").split(",")
    fixes = [labels[p] for p in probs if p in labels] or ["Modern design","Mobile-friendly","SEO setup"]
    domain = (lead["website"] or "").replace("http://","").replace("https://","").rstrip("/") or "yoursite.com"
    return render_template_string(PREVIEW, lead_id=lid, name=lead["name"],
                                    domain=domain, fixes=fixes,
                                    calendly=os.getenv("CALENDLY_URL","#"))


@app.route("/sites/<int:lid>/")
def site(lid):
    return send_from_directory(f"preview/sites/{lid}", "index.html")


@app.route("/api/create-checkout", methods=["POST"])
def create_checkout():
    d = request.json
    lead = get_lead(d.get("lead_id"))
    if not lead: return jsonify({"error": "Not found"}), 404
    try:
        s = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "usd",
                "product_data": {"name": f"Website Build - {lead['name']}"},
                "unit_amount": 39700}, "quantity": 1}],
            mode="payment",
            success_url=f"{BASE}/thank-you?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE}/preview/{lead['id']}",
            metadata={"lead_id": lead["id"]})
        return jsonify({"url": s.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/capture-info", methods=["POST"])
def capture_info():
    d = request.json
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS info_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, email TEXT,
        name TEXT, interest TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("INSERT INTO info_requests (lead_id,email,name,interest) VALUES (?,?,?,?)",
                 (d.get("lead_id"), d.get("email"), d.get("name",""), d.get("interest")))
    conn.commit(); conn.close()
    print(f"INFO: {d.get('email')} - {d.get('interest')}")
    return jsonify({"status": "ok"})


@app.route("/thank-you")
def thank_you():
    return "<html><body style='font-family:sans-serif;text-align:center;padding:80px'><h1>You're in!</h1><p>Check your email.</p></body></html>"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
'''

FILES["docs/BUILD_PLAN.md"] = """# Build Plan

## Week 1 - Foundation
- [x] Repo + folders
- [x] Lead scanner
- [x] Preview page
- [x] Stripe checkout

## Week 2 - Real Leads
- [ ] Google Places API key
- [ ] Scan 50 businesses
- [ ] Build 3 preview sites
- [ ] Send 5 emails

## Week 3 - Automation
- [ ] Wire everything together
- [ ] LLM rewriting
- [ ] Resend email
- [ ] Stripe webhook

## Week 4 - Video
- [ ] HeyGen integration
- [ ] Nurture sequence
- [ ] Tracking
- [ ] First paying client
"""

FILES["preview/sites/.gitkeep"] = ""


def main():
    print("Writing files...")
    for p, c in FILES.items():
        path = Path(p)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(c, encoding="utf-8")
        print(f"  + {p}")
    print(f"\nWrote {len(FILES)} files.\n")

    def run(cmd):
        print(f"$ {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.stdout: print(r.stdout)
        if r.stderr: print(r.stderr)

    print("Git push...\n")
    run(["git", "add", "."])
    run(["git", "commit", "-m", "Initial build"])
    run(["git", "push", "-u", "origin", "master"])

    print("\nDONE. Check github.com/PMCGILLV/personaible-clone")


if __name__ == "__main__":
    main()
