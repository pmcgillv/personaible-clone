"""GPT copy rewriting."""
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
