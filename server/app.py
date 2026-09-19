"""Flask server - previews, checkout, info capture."""
import os
import sqlite3
import stripe
from flask import Flask, render_template_string, send_from_directory, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# Use absolute paths so it works on Windows
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_DIR = os.path.join(BASE_DIR, "preview", "sites")

app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
DB = os.path.join(BASE_DIR, "scanner", "leads.db")
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
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    l = conn.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    conn.close()
    return l


@app.route("/")
def home():
    conn = sqlite3.connect(DB)
    try:
        leads = conn.execute("SELECT id,name,problems FROM leads ORDER BY id DESC LIMIT 50").fetchall()
    except:
        leads = []
    conn.close()
    rows = "".join([f'<li><a href="/preview/{l[0]}">{l[0]}. {l[1]} - {l[2]}</a></li>' for l in leads])
    return f"<h1>Leads</h1><ul>{rows}</ul>"


@app.route("/preview/<int:lid>")
def preview(lid):
    lead = get_lead(lid)
    if not lead:
        return "Not found", 404
    labels = {"has_ssl": "Fixed SSL certificate",
              "has_chatbot": "Added AI chatbot",
              "has_social": "Set up social media",
              "has_video": "Added homepage video"}
    probs = (lead["problems"] or "").split(",")
    fixes = [labels[p] for p in probs if p in labels] or ["Modern design", "Mobile-friendly", "SEO setup"]
    domain = (lead["website"] or "").replace("http://", "").replace("https://", "").rstrip("/") or "yoursite.com"
    return render_template_string(PREVIEW, lead_id=lid, name=lead["name"],
                                    domain=domain, fixes=fixes,
                                    calendly=os.getenv("CALENDLY_URL", "#"))


@app.route("/sites/<int:lid>/")
@app.route("/sites/<int:lid>")
def site(lid):
    folder = os.path.join(SITES_DIR, str(lid))
    if not os.path.exists(os.path.join(folder, "index.html")):
        return f"<h1>Preview not built yet</h1><p>Run: python builder/build.py {lid}</p>", 404
    return send_from_directory(folder, "index.html")


@app.route("/api/create-checkout", methods=["POST"])
def create_checkout():
    d = request.json
    lead = get_lead(d.get("lead_id"))
    if not lead:
        return jsonify({"error": "Not found"}), 404
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
                 (d.get("lead_id"), d.get("email"), d.get("name", ""), d.get("interest")))
    conn.commit()
    conn.close()
    print(f"INFO: {d.get('email')} - {d.get('interest')}")
    return jsonify({"status": "ok"})


@app.route("/thank-you")
def thank_you():
    return "<html><body style='font-family:sans-serif;text-align:center;padding:80px'><h1>You're in!</h1><p>Check your email.</p></body></html>"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
