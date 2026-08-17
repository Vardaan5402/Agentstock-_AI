import os
import unittest
from unittest.mock import patch
from database.database import Database
from models.user import User, UserRole
from models.persistence import AdminAuditEvent
from core.security import (
    hash_password,
    verify_password,
    verify_admin_credentials,
    require_admin,
    generate_secure_otp,
    hash_otp,
    verify_otp,
)


class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.admin_email = "srivastavavardaan05@gmail.com"
        self.plain_admin_pass = "SecureAdminPassword123!"
        self.admin_hash = hash_password(self.plain_admin_pass)

    def test_admin_verification_with_env_hash(self):
        with patch.dict(os.environ, {
            "ADMIN_EMAIL": self.admin_email,
            "ADMIN_PASSWORD_HASH": self.admin_hash,
        }):
            # Correct email and password
            self.assertTrue(verify_admin_credentials(self.admin_email, self.plain_admin_pass))
            # Incorrect password
            self.assertFalse(verify_admin_credentials(self.admin_email, "WrongPassword!"))
            # Incorrect email
            self.assertFalse(verify_admin_credentials("hacker@example.com", self.plain_admin_pass))

    def test_require_admin_authorization(self):
        with patch.dict(os.environ, {
            "ADMIN_EMAIL": self.admin_email,
            "ADMIN_PASSWORD_HASH": self.admin_hash,
        }):
            admin_user = User(
                id="usr_admin_1",
                name="Platform Administrator",
                email=self.admin_email,
                password_hash=self.admin_hash,
                role=UserRole.ADMIN.value,
                is_verified=True,
            )
            ok, msg = require_admin(admin_user)
            self.assertTrue(ok)
            self.assertEqual(msg, "Admin authorized")

            normal_user = User(
                id="usr_normal_1",
                name="Regular Merchant",
                email="merchant@gmail.com",
                password_hash=hash_password("MerchantPass123!"),
                role=UserRole.USER.value,
                is_verified=True,
            )
            ok_norm, msg_norm = require_admin(normal_user)
            self.assertFalse(ok_norm)
            self.assertIn("Access denied", msg_norm)

    def test_immutable_admin_audit_event_creation(self):
        event = AdminAuditEvent(
            id="adm_evt_1",
            user_id="usr_admin_1",
            user_email=self.admin_email,
            event_type="ADMIN_SECURITY_SCAN",
            security_classification="RESTRICTED",
        )
        self.db.create_admin_audit_event(event)

        events = self.db.list_admin_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "ADMIN_SECURITY_SCAN")
    def test_admin_2fa_otp_flow(self):
        otp_val = generate_secure_otp()
        otp_h = hash_otp(otp_val)
        self.db.save_otp(self.admin_email, otp_h, "2099-01-01T00:00:00Z")

        rec = self.db.get_otp_record(self.admin_email)
        self.assertIsNotNone(rec)
        self.assertTrue(verify_otp(otp_val, rec.otp_hash))
        self.assertFalse(verify_otp("999999" if otp_val != "999999" else "000000", rec.otp_hash))


if __name__ == "__main__":
    unittest.main()
