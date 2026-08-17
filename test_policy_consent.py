import json
import unittest
from uuid import uuid4
from database.database import Database
from models.user import User, UserRole
from models.security import UserPolicyConsent
from models.persistence import AdminAuditEvent
from core.security import (
    hash_password,
    verify_password,
    generate_secure_otp,
    hash_otp,
    verify_otp,
    require_policy_consent,
    require_authenticated_user,
)


class TestPolicyConsent(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.email = "merchant@gmail.com"
        self.user = User(
            id=f"usr_{uuid4().hex[:12]}",
            name="Sample Merchant",
            email=self.email,
            password_hash=hash_password("SecurePass123!"),
            role=UserRole.USER.value,
        )
        self.db.create_user(self.user)

    def test_new_user_has_not_accepted_current_policies(self):
        self.assertFalse(self.db.has_accepted_current_policies(self.email))
        ok, msg = require_policy_consent(self.email, self.db)
        self.assertFalse(ok)
        self.assertIn("Policy agreement required", msg)

    def test_record_policy_consent_with_exact_versions(self):
        consent = UserPolicyConsent(
            id=f"cons_{uuid4().hex[:14]}",
            user_id=self.user.id,
            email=self.email,
            policy_version="1.0",
            terms_version="1.0",
            privacy_version="1.0",
            acceptable_use_version="1.0",
            subscription_policy_version="1.0",
            communication_policy_version="1.0",
            data_security_policy_version="1.0",
            consent_status="ACCEPTED",
        )
        self.db.record_policy_consent(consent)

        # Verification
        self.assertTrue(self.db.has_accepted_current_policies(self.email))
        ok, msg = require_policy_consent(self.email, self.db)
        self.assertTrue(ok)
        self.assertEqual(msg, "Consent verified")

        retrieved = self.db.get_latest_user_consent(self.email)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.terms_version, "1.0")
        self.assertEqual(retrieved.privacy_version, "1.0")
        self.assertEqual(retrieved.acceptable_use_version, "1.0")
        self.assertEqual(retrieved.subscription_policy_version, "1.0")
        self.assertEqual(retrieved.communication_policy_version, "1.0")
        self.assertEqual(retrieved.data_security_policy_version, "1.0")

    def test_policy_update_requires_reconsent(self):
        # User accepted v1.0
        consent = UserPolicyConsent(
            id=f"cons_{uuid4().hex[:14]}",
            user_id=self.user.id,
            email=self.email,
            policy_version="1.0",
            terms_version="1.0",
            privacy_version="1.0",
            acceptable_use_version="1.0",
            subscription_policy_version="1.0",
            communication_policy_version="1.0",
            data_security_policy_version="1.0",
            consent_status="ACCEPTED",
        )
        self.db.record_policy_consent(consent)
        self.assertTrue(self.db.has_accepted_current_policies(self.email))

        # Platform upgrades Terms of Service to v2.0
        original_terms = self.db.CURRENT_POLICIES["terms_version"]
        try:
            self.db.CURRENT_POLICIES["terms_version"] = "2.0"
            # Now existing consent is outdated
            self.assertFalse(self.db.has_accepted_current_policies(self.email))
            ok, msg = require_policy_consent(self.email, self.db)
            self.assertFalse(ok)
            self.assertIn("Policy agreement required", msg)

            # User accepts updated terms v2.0
            new_consent = UserPolicyConsent(
                id=f"cons_{uuid4().hex[:14]}",
                user_id=self.user.id,
                email=self.email,
                policy_version="2.0",
                terms_version="2.0",
                privacy_version="1.0",
                acceptable_use_version="1.0",
                subscription_policy_version="1.0",
                communication_policy_version="1.0",
                data_security_policy_version="1.0",
                consent_status="ACCEPTED",
            )
            self.db.record_policy_consent(new_consent)
            self.assertTrue(self.db.has_accepted_current_policies(self.email))
        finally:
            self.db.CURRENT_POLICIES["terms_version"] = original_terms

    def test_admin_audit_records_policy_consent_event(self):
        audit_event = AdminAuditEvent(
            id=f"evt_{uuid4().hex[:14]}",
            user_id=self.user.id,
            user_email=self.email,
            event_type="POLICY_CONSENT_ACCEPTED",
            entity_type="POLICY",
            entity_id="cons_12345",
            metadata_json=json.dumps({
                "terms_version": "1.0",
                "privacy_version": "1.0",
                "acceptable_use_version": "1.0",
            }),
            security_classification="STANDARD",
        )
        self.db.create_admin_audit_event(audit_event)

        events = self.db.list_admin_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "POLICY_CONSENT_ACCEPTED")
        meta = json.loads(events[0]["metadata_json"])
        self.assertEqual(meta["terms_version"], "1.0")

    def test_full_login_order_with_otp(self):
        # Step 1 & 2: User enters email + password
        self.assertTrue(verify_password("SecurePass123!", self.user.password_hash))

        # Step 3: Consent check
        self.assertFalse(self.db.has_accepted_current_policies(self.email))

        # Step 4: Explicit consent accepted
        consent = UserPolicyConsent(
            id=f"cons_{uuid4().hex[:14]}",
            user_id=self.user.id,
            email=self.email,
            terms_version="1.0",
            privacy_version="1.0",
            acceptable_use_version="1.0",
            subscription_policy_version="1.0",
            communication_policy_version="1.0",
            data_security_policy_version="1.0",
        )
        self.db.record_policy_consent(consent)
        self.assertTrue(self.db.has_accepted_current_policies(self.email))

        # Step 5: OTP generation & validation
        otp_val = generate_secure_otp()
        otp_h = hash_otp(otp_val)
        self.db.save_otp(self.email, otp_h, "2099-01-01T00:00:00Z")

        # Step 6: OTP verify
        rec = self.db.get_otp_record(self.email)
        self.assertTrue(verify_otp(otp_val, rec.otp_hash))
        self.db.verify_user(self.email)
        self.db.delete_otp(self.email)


if __name__ == "__main__":
    unittest.main()
