"""Regression tests for the Google OIDC-to-AgentStock session bridge."""
import unittest
from unittest.mock import patch

from database.database import Database
from models.security import UserPolicyConsent
from models.user import User, UserRole
import ui.views.auth as auth_view


class _FakeGoogleUser:
    is_logged_in = True

    def __init__(self, claims):
        self.claims = claims

    def get(self, name, default=None):
        return self.claims.get(name, default)


class _FakeStreamlit:
    def __init__(self, claims):
        self.user = _FakeGoogleUser(claims)
        self.session_state = {}
        self.logged_out = False

    def logout(self):
        self.logged_out = True


def _claims(email):
    return {
        "email": email,
        "email_verified": True,
        "iss": "https://accounts.google.com",
        "aud": "google-client-id",
        "exp": 4102444800,
        "name": "Google Merchant",
    }


def _record_consent(database, user):
    database.record_policy_consent(
        UserPolicyConsent(
            id=f"cons_{user.id}",
            user_id=user.id,
            email=user.email,
            policy_version="1.0",
            terms_version="1.0",
            privacy_version="1.0",
            acceptable_use_version="1.0",
            subscription_policy_version="1.0",
            communication_policy_version="1.0",
            data_security_policy_version="1.0",
            consent_status="ACCEPTED",
        )
    )


class TestGoogleOidcAuthentication(unittest.TestCase):
    def setUp(self):
        self.database = Database(":memory:")
        self.st_patch = patch.object(auth_view, "st")
        self.mock_st = self.st_patch.start()
        self.client_id_patch = patch.object(
            auth_view, "get_google_client_id", return_value="google-client-id"
        )
        self.client_id_patch.start()

    def tearDown(self):
        self.client_id_patch.stop()
        self.st_patch.stop()

    def _use_google_identity(self, email):
        fake_st = _FakeStreamlit(_claims(email))
        self.mock_st.user = fake_st.user
        self.mock_st.session_state = fake_st.session_state
        self.mock_st.logout.side_effect = fake_st.logout
        return fake_st

    def test_existing_google_user_keeps_id_and_admin_role(self):
        user = User(
            id="usr_existing_admin",
            name="Existing Admin",
            email="admin@example.com",
            password_hash="existing-password-hash",
            role=UserRole.ADMIN.value,
            is_verified=True,
        )
        self.database.create_user(user)
        _record_consent(self.database, user)
        fake_st = self._use_google_identity(user.email)

        authenticated = auth_view.synchronize_google_oidc_user(self.database)

        self.assertEqual(authenticated.id, user.id)
        self.assertEqual(authenticated.role, UserRole.ADMIN.value)
        self.assertTrue(fake_st.session_state["is_logged_in"])
        self.assertTrue(fake_st.session_state["is_admin"])
        self.assertEqual(self.database.get_user_by_email(user.email).id, user.id)

    def test_new_google_user_is_standard_user_and_must_accept_policy(self):
        email = "new-merchant@example.com"
        fake_st = self._use_google_identity(email)

        authenticated = auth_view.synchronize_google_oidc_user(self.database)

        created_user = self.database.get_user_by_email(email)
        self.assertIsNone(authenticated)
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.role, UserRole.USER.value)
        self.assertEqual(fake_st.session_state["pending_policy_consent_user_id"], created_user.id)
        self.assertEqual(fake_st.session_state["pending_policy_consent_auth_method"], "google")
        self.assertNotIn("pending_otp_email", fake_st.session_state)


if __name__ == "__main__":
    unittest.main()
