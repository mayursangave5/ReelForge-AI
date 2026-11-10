from __future__ import annotations

from typing import Any

SYSTEM = """आप एक हिंदी शॉर्ट-वीडियो सोशल मीडिया मैनेजर हैं।
आप Instagram Reels और YouTube Shorts के लिए अलग-अलग मेटाडेटा लिखते हैं।
नियम:
- कैप्शन और टाइटल हिंदी में हों, सरल और आकर्षक।
- कोई झूठा या भ्रामक दावा नहीं। सिर्फ दिए गए विषय और स्क्रिप्ट से जुड़ी बातें।
- हैशटैग विषय से सीधे जुड़े हों, असंबंधित या भ्रामक हैशटैग नहीं।
- Instagram कैप्शन में कम से कम एक उचित इमोजी रखें।
- YouTube शीर्षक 100 अक्षर से कम रखें और Shorts के लिए आकर्षक हो।
- आउटपुट केवल वैध JSON हो, कोई मार्कडाउन नहीं।"""


def metadata_prompt(package: dict[str, Any], topic: str = "") -> str:
    title = package.get("title_hi", "")
    hook = package.get("hook_hi", "")
    narration = "\n".join(
        f"- {scene.get('narration_hi', '')}" for scene in package.get("scenes", [])
    )
    cta = package.get("cta_hi", "")
    return f"""विषय: {topic or title}
स्क्रिप्ट शीर्षक: {title}
हुक: {hook}
मुख्य बातें:
{narration}
कॉल-टू-एक्शन: {cta}

Instagram Reels और YouTube Shorts के लिए अलग मेटाडेटा बनाएं।
हैशटैग में '#' न लगाएं, केवल शब्द दें।

इस JSON ढांचे में लौटाएं:
{{
  "instagram": {{
    "caption": "आकर्षक हिंदी कैप्शन, इमोजी के साथ",
    "hashtags": ["हिंदी", "space", "india", "reels", "factsinhindi"]
  }},
  "youtube": {{
    "title": "100 अक्षर से छोटा आकर्षक हिंदी शीर्षक",
    "caption": "वीडियो का हिंदी विवरण, स्रोत और कॉल-टू-एक्शन के साथ",
    "hashtags": ["Shorts", "हिंदी", "space"],
    "tags": ["हिंदी Facts", "space news", "india space", "science in hindi"]
  }}
}}

Instagram: 5-15 हैशटैग, कैप्शन 2200 अक्षर से कम।
YouTube: 3-8 हैशटैग, 3-15 टैग, शीर्षक 100 अक्षर से कम।"""
