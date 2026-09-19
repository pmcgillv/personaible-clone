"""Outreach email sender."""
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
