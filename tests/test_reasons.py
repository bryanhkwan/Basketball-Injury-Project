import unittest

from injury_risk.reasons import classify


class ClassifyTest(unittest.TestCase):
    def check(self, reason, reason_class, region=None, injury_type=None):
        out = classify(reason)
        self.assertEqual(out["reason_class"], reason_class, reason)
        if region is not None:
            self.assertEqual(out["region"], region, reason)
        if injury_type is not None:
            self.assertEqual(out["injury_type"], injury_type, reason)

    def test_current_layout_injuries(self):
        self.check("Injury/Illness - Left Ankle; Sprain", "injury", "ankle", "ligament")
        self.check("Injury/Illness - Right Calf; Strain", "injury", "calf", "muscle_tendon")
        self.check("Injury/Illness - Left Ankle; Stress Reaction", "injury", "ankle", "bone")
        self.check("Injury/Illness - Right Knee; MCL contusion", "injury", "knee", "impact")
        self.check("Injury/Illness - Left Hamstring; Tightness", "injury", "hamstring", "muscle_tendon")
        self.check("Injury/Illness - Head; Concussion", "injury", "concussion", "concussion")
        self.check("Injury/Illness - Left Great Toe; Surgery Recovery", "injury", "foot", "surgery")
        self.check("Injury/Illness - Right Hip; Pointer", "injury", "hip", "impact")

    def test_a_bones_head_is_not_the_head(self):
        self.check("Injury/Illness - Right Third Metatarsal Head; Stress Reaction Surgery", "injury", "foot", "bone")
        self.check("Injury/Illness - Right Femoral Head Impaction; Injury", "injury", "hip")
        self.check("Injury/Illness - Left Fibular Head; Contusion", "injury", "calf", "impact")
        self.check("Injury/Illness - Left Fibula; Non-displaced head fracture", "injury", "calf", "bone")
        self.check("Injury/Illness - Head; Laceration", "injury", "concussion", "impact")

    def test_a_body_part_inside_another_word(self):
        self.check("Injury/Illness - Neck; Whiplash", "injury", "head_neck")   # not the hip
        self.check("Injury/Illness - Right Elbow; Discomfort", "injury", "arm", "soreness")   # not a disc
        self.check("Injury/Illness - Right Thumb; DIsclocation", "injury", "hand")
        self.check("Injury/Illness - Right Lisfranc Ligament; Tear", "injury", "foot", "ligament")   # not an ear
        self.check("Injury/Illness - Left Facet; Syndrome", "injury", "back")   # not the face
        self.check("Injury/Illness - Right Oribital; Fracture", "injury", "head_neck", "bone")   # not a rib
        self.check("Injury/Illness - Left Zygomatic Arch; Fracture", "injury", "head_neck", "bone")   # not the foot
        self.check("Injury/Illness - Right Gastrocnemius; Strain", "injury", "calf", "muscle_tendon")   # not gastro

    def test_more_body_parts(self):
        self.check("Injury/Illness - Torn right anterior cruciate ligament", "injury", "knee", "ligament")
        self.check("Injury/Illness - Right Medial Femoral Condyle; Fracture", "injury", "knee", "bone")
        self.check("Injury/Illness - Left Tibial Plateau; Non-displaced fracture", "injury", "knee", "bone")
        self.check("Injury/Illness - Left Cuneiform; Fracture", "injury", "foot", "bone")
        self.check("Injury/Illness - Right 1st Mp Joint; Sprain", "injury", "foot", "ligament")
        self.check("Injury/Illness - Right Iliac Wing; Fracture", "injury", "hip", "bone")
        self.check("Injury/Illness - Left SI; Inflammation", "injury", "hip", "soreness")
        self.check("Injury/Illness - Left Scaphoid; Fracture", "injury", "hand", "bone")
        self.check("Injury/Illness - Left Distal Radius; Fracture", "injury", "hand", "bone")
        self.check("Injury/Illness - Left Sciatic Nerve; Irritation", "injury", "back", "soreness")
        self.check("Injury/Illness - Right Acromioclavicular; Sprain", "injury", "shoulder", "ligament")
        self.check("Injury/Illness - Right Lung; Pneumothorax", "injury", "trunk")
        self.check("Injury/Illness - Left Achillies; Tendinopathy", "injury", "achilles", "muscle_tendon")
        self.check("Injury/Illness - Right Sinus; Fracture", "injury", "head_neck", "bone")
        self.check("Injury/Illness - N/a; Sports Hernia Surgery", "injury", "groin", "surgery")
        self.check("Injury/Illness - Left Peroneal; Strain", "injury", "calf", "muscle_tendon")
        self.check("Injury/Illness - Left Ankle; Peroneal Tendinopathy", "injury", "ankle", "muscle_tendon")
        self.check("Injury/Illness - Left Superior Tib/fib; Sprain", "injury", "calf", "ligament")   # a joint, not a muscle

    def test_the_named_body_part_comes_first(self):
        self.check("Injury/Illness - Right Knee; MCL Sprain; Quad Contusion", "injury", "knee")
        self.check("Injury/Illness - Left Foot; Fracture; L Ankle Sprain", "injury", "foot", "bone")
        self.check("Injury/Illness - Right Hand; Metatarsal Fractures", "injury", "hand", "bone")
        self.check("Injury/Illness - Left Foot; Abductor Hallucis Strain", "injury", "foot", "muscle_tendon")
        self.check("Injury/Illness - Left Leg; Popliteus strain", "injury", "knee", "muscle_tendon")   # "Leg" is vague
        self.check("Injury/Illness - Hand; Concussion", "injury", "concussion")

    def test_the_neck_and_the_back(self):
        self.check("Injury/Illness - Neck; Cervical disc herniation", "injury", "head_neck")
        self.check("Injury/Illness - Low Back And Neck; Soreness", "injury", "back", "soreness")
        self.check("Injury/Illness - Thoracic; Spasms", "injury", "back", "muscle_tendon")
        self.check("Injury/Illness - Right Upper Trap; Strain", "injury", "back", "muscle_tendon")
        self.check("Injury/Illness - Thoracic outlet syndrome", "injury", "shoulder")

    def test_injury_recovery_is_not_surgery(self):
        self.check("Injury/Illness - Left Knee; Injury Recovery", "injury", "knee", "other")
        self.check("Injury/Illness - Left Groin; Injury Recovery", "injury", "groin", "other")   # not a strain either
        self.check("Injury/Illness - Left Groin", "injury", "groin", "muscle_tendon")
        self.check("Injury/Illness - Right Knee; ACL Injury Recovery", "injury", "knee", "ligament")
        self.check("Injury/Illness - Left Thumb; UCL Repair", "injury", "hand", "surgery")

    def test_an_injury_beats_an_illness(self):
        self.check("Injury/Illness - Right Shin; Contusion; Viral Illness", "injury", "calf", "impact")
        self.check("Injury/Illness - Head; Post-Traumatic Headache", "injury", "concussion")
        self.check("Injury/Illness - Sinus; Surgery", "illness")
        self.check("Injury/Illness - Left Eye; Infection", "illness")

    def test_2018_19_layout(self):
        self.check("Injury/Illness - Sprained Right Ankle", "injury", "ankle", "ligament")
        self.check("Injury/Illness - Right Knee Bone Bruise", "injury", "knee", "bone")
        self.check("Injury/Illness - Back spasms", "injury", "back", "muscle_tendon")
        self.check("Injury/Illness - Flu-like symptoms", "illness")
        self.check("G League Team", "non_medical")
        self.check("Personal Reasons", "non_medical")

    def test_not_injuries(self):
        self.check("Injury/Illness - N/A; Illness", "illness")
        self.check("Health and Safety Protocols", "illness")
        self.check("Injury/Illness - Right Knee; Injury Management", "management")
        self.check("Return to Competition Reconditioning", "management")
        self.check("Rest", "management")
        self.check("G League - Two-Way", "non_medical")
        self.check("G League - On Assignment", "non_medical")
        self.check("Not With Team", "non_medical")
        self.check("League Suspension", "non_medical")
        self.check("Ineligible To Play", "non_medical")

    def test_not_injuries_under_the_injury_heading(self):
        self.check("Injury/Illness - Personal reasons", "non_medical")
        self.check("Injury/Illness - G League", "non_medical")
        self.check("Injury/Illness - 10 day contract expired", "non_medical")
        self.check("Injury/Illness - Appendectomy", "illness")
        self.check("Injury/Illness - Not Available; Medical Condition", "illness")
        self.check("Injury/Illness - Body; Influenza", "illness")
        self.check('Injury/Illness - " "; Dental Procedure', "illness")
        self.check("Injury/Illness - -; Re-Conditioning", "management")
        self.check("Injury/Illness - Load Managment", "management")
        self.check("Injury/Illness - Dental; Fracture", "injury", "head_neck", "bone")

    def test_concussion_protocol_counts(self):
        self.check("Concussion Protocol", "injury", "concussion")

    def test_empty(self):
        self.check("", "unknown")
        self.check(None, "unknown")


if __name__ == "__main__":
    unittest.main()
