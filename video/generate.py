"""HeyGen AI video."""
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
