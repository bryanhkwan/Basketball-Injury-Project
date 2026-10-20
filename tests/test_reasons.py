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

    def test_concussion_protocol_counts(self):
        self.check("Concussion Protocol", "injury", "concussion")

    def test_empty(self):
        self.check("", "unknown")
        self.check(None, "unknown")


if __name__ == "__main__":
    unittest.main()
