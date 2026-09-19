"""Lead Scanner."""
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
