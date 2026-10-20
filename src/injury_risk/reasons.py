"""Sort an injury-report reason into a class, a body region and an injury type.

Only ``injury`` absences can start an injury. Illness and protocols, planned rest or load management, and
non-medical absences (G League, personal, suspension...) never do.
"""
from __future__ import annotations

import re

ILLNESS = re.compile(r"\b(illness|ill|flu|sick|virus|viral|covid|non-covid|health and safety|gastro|stomach|"
                     r"migraine|headache|dehydrat|food poisoning|strep|tonsil|cold|fever|respiratory|"
                     r"upper respiratory|sinus|bronch|pneumonia|appendic)", re.I)
MANAGEMENT = re.compile(r"(injury management|load management|\brest\b|reconditioning|return to competition)", re.I)
NON_MEDICAL = re.compile(r"(g league|two-way|personal|not with team|suspension|suspended|trade|ineligible|"
                         r"coach'?s decision|bereavement|family|birth of|paternity|league|team decision)", re.I)

REGIONS = [   # first match wins; specific terms before general ones
    ("concussion", r"concussion|head\b"),
    ("achilles", r"achilles"),
    ("hamstring", r"hamstring"),
    ("calf", r"calf|soleus|lower leg|shin|tibia|fibula"),
    ("groin", r"groin|adductor"),
    ("hip", r"hip|glute|pelvi|pointer|sacroiliac"),
    ("thigh", r"quad|thigh"),
    ("knee", r"knee|patell|acl|mcl|lcl|pcl|menisc"),
    ("ankle", r"ankle"),
    ("foot", r"foot|heel|plantar|toe|metatarsal|navicular|arch|sesamoid"),
    ("back", r"back|lumbar|spine|spinal|disc|sacral|tailbone|coccyx"),
    ("trunk", r"abdom|core|oblique|rib|chest|sternum|pectoral|intercostal|thoracic"),
    ("shoulder", r"shoulder|rotator|clavicle|collarbone|labrum|ac joint"),
    ("arm", r"elbow|forearm|bicep|tricep|arm\b"),
    ("hand", r"wrist|hand|finger|thumb|knuckle|pinky|metacarpal"),
    ("head_neck", r"face|facial|nose|nasal|eye|orbital|jaw|mouth|teeth|tooth|lip|ear\b|neck|cervical|cheek"),
    ("leg", r"\bleg\b"),
]

TYPES = [   # injury mechanism by its own word (not the anatomy: "MCL contusion" is an impact)
    ("bone", r"fractur|broken|stress reaction|bone bruise|bone edema"),
    ("impact", r"contusion|bruise|laceration|\bcut\b|dislocat|sublux|hyperextension|pointer"),
    ("muscle_tendon", r"strain|tight|spasm|pull|tendin|tendon|muscle|cramp"),
    ("ligament", r"sprain|ligament|\btear|torn|rupture"),
    ("surgery", r"surgery|procedure|repair|recovery|post-op"),
    ("concussion", r"concussion"),
    ("soreness", r"sore|inflammation|swelling|irritation|impingement|pain|discomfort|effusion|bursitis"),
]
MUSCLE_REGIONS = {"hamstring", "calf", "groin", "thigh", "achilles"}   # a tear here is muscle or tendon


def classify(reason: str | None) -> dict:
    """{'reason_class', 'region', 'injury_type', 'body_part', 'detail'} for one reason string."""
    text = (reason or "").strip()
    out = dict(reason_class="unknown", region=None, injury_type=None, body_part=None, detail=None)
    if not text:
        return out
    low = text.lower()
    if "concussion protocol" in low:
        return dict(out, reason_class="injury", region="concussion", injury_type="concussion")
    if low.startswith("injury/illness"):
        rest = re.sub(r"^injury/illness\s*-?\s*", "", text, flags=re.I)
        body, _, detail = rest.partition(";")
        out.update(body_part=body.strip() or None, detail=detail.strip() or None)
        if MANAGEMENT.search(rest):
            return dict(out, reason_class="management")
        if ILLNESS.search(rest) and not re.search(r"(ankle|knee|foot|back|hip|hamstring|calf|groin|shoulder|wrist|hand)", rest, re.I):
            return dict(out, reason_class="illness")
        out["reason_class"] = "injury"
        region = next((name for name, pattern in REGIONS if re.search(pattern, rest, re.I)), "other")
        kind = next((name for name, pattern in TYPES if re.search(pattern, rest, re.I)), "other")
        if kind == "other" and re.search(r"\b(acl|mcl|lcl|pcl)\b|menisc", rest, re.I):
            kind = "ligament"
        if region in MUSCLE_REGIONS and kind in ("ligament", "other"):
            kind = "muscle_tendon"
        out.update(region=region, injury_type=kind)
        return out
    if ILLNESS.search(low):
        return dict(out, reason_class="illness")
    if MANAGEMENT.search(low):
        return dict(out, reason_class="management")
    if NON_MEDICAL.search(low):
        return dict(out, reason_class="non_medical")
    return dict(out, reason_class="other")
