"""Sort an injury-report reason into a class, a body region and an injury type.

Only ``injury`` absences can start an injury. Illness and protocols, planned rest or load management, and
non-medical absences (G League, personal, suspension...) never do.
"""
from __future__ import annotations

import re

ILLNESS = re.compile(r"\b(illness|ilness|ill|flu|influenza|infuenza|sick|virus|viral|covid|non-covid|health and safety|"
                     r"gastro(?!cnem)|stomach|migraine|headache|dehydrat|food poisoning|strep|tonsil|throat|pharyng|cold|fever|"
                     r"respiratory|upper respiratory|sinus|bronch|pneumonia|congestion|asthma|allerg|mononucleosis|"
                     r"infection|appendic|appendectomy|medical condition|medical assessment|under the weather|"
                     r"dental (procedure|work)|dental; (procedure|pain))", re.I)
MANAGEMENT = re.compile(r"(injury management|load manag|\brest\b|conditioning|return to competition|"
                        r"rehabilitation assignment)", re.I)
NON_MEDICAL = re.compile(r"(g league|two-way|personal|not with team|suspension|suspended|trade|ineligible|"
                         r"coach'?s decision|bereavement|family|birth of|paternity|league|team decision|contract)", re.I)
# a listing that names one of these is an injury even when it also names an illness ("Right Shin; Contusion; Viral Illness")
INJURY_WORDS = re.compile(r"(ankle|knee|foot|back|hip|hamstring|calf|groin|shoulder|wrist|hand|lumbar|spine|fractur|"
                          r"sprain|strain|contusion|\btear|torn|lacerat|dislocat|bruise|post.?traumatic)", re.I)

REGIONS = [   # first match wins; specific terms before general ones; a name can come back as a fallback
    # the head, but not a bone's head ("Right Third Metatarsal Head", "Right Femoral Head Impaction", "Left Fibular Head")
    ("concussion", r"concussion|post.?traumatic|(?<!metatarsal )(?<!metacarpal )(?<!radial )(?<!femoral )(?<!humeral )"
                   r"(?<!fibular )(?<!fibula )\bhead\b(?! of )"),
    ("achilles", r"achill"),   # and the "Achillies" misspelling
    ("hamstring", r"hamstring|biceps femoris"),
    ("calf", r"calf|gastroc|soleus|lower leg|\bshins?\b|tibia(?!l plateau)|fibula"),
    ("groin", r"groin|groun\b|adductor|sports hernia|inguinal|pubalgia"),
    ("hip", r"\bhip|glut|pelvi|pointer|sacroiliac|\bsi\b|femoral head|iliac|\bilium|pubic|pubis|ischi"),
    ("thigh", r"quad|thigh|rectus femoris|femur"),
    ("knee", r"knee|patel|acl|mcl|lcl|pcl|menisc|cruciate|condyle|tibial plateau|popliteus"),
    ("ankle", r"ankle|\banke\b|\bangle\b"),
    ("foot", r"foot|heel|\bheal\b|plantar|toe|big tor\b|metatars|navicular|(?<!zygomatic )\barch\b|sesamoid|lisfranc|"
             r"cuneiform|cuboid|calcane|\bmtp\b|1st mp\b"),
    ("calf", r"peroneal|tib/fib|tibiofib"),   # the outside of the lower leg, when no ankle or foot is named
    # the neck, when no part of the back is named ("Neck; Cervical Disc Herniation", but "Low Back and Neck")
    ("head_neck", r"^(?!.*(back|lumbar|thorac|thoratic)).*(neck|cervical)"),
    ("back", r"back|lumbar|lumber|spine|spinal|\bdis[ck]s?\b|sacral|sacrum|tail ?bone|coccyx|facet|sciatic|"
             r"thorac(?!ic outlet)|thoratic|trapezius|\btrap\b"),
    ("trunk", r"abdom|core|oblique|\brib|chest|sternum|sternal|pectoral|costal|lung|pneumothorax|trunk|\bside\b|hernia"),
    ("shoulder", r"shoulder|shoiulder|rotator|clavic|collarbone|labrum|\bac\b|acromio|deltoid|\bsc\b|thoracic outlet|"
                 r"\btos\b"),
    ("arm", r"elbow|forearm|bicep|tricep|arm\b|olecranon|flexor carpi"),
    ("hand", r"wrist|hand|finger|thumb|thunb|knuckle|pink(y|ie)|metacarp|scaph|lunate|styloid|distal radius|carpal|"
             r"\bpip\b|\bdip\b|digit"),
    ("head_neck", r"\bface\b|facial|facemask|nose|nasal|sinus|\beyes?\b|eyelid|orbit|oribital|zygom|jaw|mouth|teeth|tooth|"
                  r"dental|\boral\b|\blips?\b|\bears?\b|neck|cervical|throat|cheek|\bchin\b|retina|cornea|ocular|"
                  r"anterior triangle"),
    ("leg", r"\bleg\b"),
]

TYPES = [   # injury mechanism by its own word (not the anatomy: "MCL contusion" is an impact)
    ("bone", r"fractur|broken|stress reaction|bone bruise|bone edema"),
    ("impact", r"contusion|bruise|laceration|\bcut\b|dislocat|sublux|hyperextension|pointer"),
    ("muscle_tendon", r"strain|tight|spasm|pull|tendin|tendon|muscle|cramp"),
    ("ligament", r"sprain|ligament|\btear|torn|rupture"),
    ("surgery", r"surg|procedure|repair|post-op|reconstruct|scope|ectomy"),   # not "Injury Recovery" alone
    ("concussion", r"concussion"),
    ("soreness", r"sore|inflammation|swelling|irritation|impingement|pain|discomfort|effusion|bursitis"),
]
MUSCLE_REGIONS = {"hamstring", "calf", "groin", "thigh", "achilles"}   # a tear here is muscle or tendon...
JOINTS = r"tib/fib|tibiofib"   # ...but not at the joint between the shin bones
CARE = r"recovery|maintenance"   # "Left Groin; Injury Recovery": care of an injury, which says nothing of its type


def _region(body: str, rest: str) -> str:
    """The body part the team names before the semicolon decides; the rest of the listing decides when that part is
    missing, vague ("N/A", "General") or just "Leg". A concussion anywhere in the listing wins."""
    def first(text):
        return next((name for name, pattern in REGIONS if re.search(pattern, text, re.I)), "other")
    if re.search("concussion", rest, re.I):
        return "concussion"
    region = first(body)
    return first(rest) if region in ("other", "leg") else region


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
        if ILLNESS.search(rest) and not INJURY_WORDS.search(rest):
            return dict(out, reason_class="illness")
        region = _region(body, rest)
        if region == "other" and NON_MEDICAL.search(rest):   # "Injury/Illness - Personal Reasons", "- G League"
            return dict(out, reason_class="non_medical")
        out["reason_class"] = "injury"
        kind = next((name for name, pattern in TYPES if re.search(pattern, rest, re.I)), "other")
        if kind == "other" and re.search(r"\b(acl|mcl|lcl|pcl)\b|menisc", rest, re.I):
            kind = "ligament"
        if region in MUSCLE_REGIONS and not re.search(JOINTS, rest, re.I) and (
                kind == "ligament" or (kind == "other" and not re.search(CARE, rest, re.I))):
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
