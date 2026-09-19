"""Builds preview site for a lead."""
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
