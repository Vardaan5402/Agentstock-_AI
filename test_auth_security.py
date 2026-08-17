"""Test Suite for Authentication, PBKDF2 Password Hashing, OTP Verification, and Rate Limiting."""
import unittest
import time
from core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_secure_otp,
    hash_otp,
    verify_otp,
    RateLimiter,
)


class TestAuthSecurity(unittest.TestCase):
    """Test cryptographic password hashing, OTP handling, and rate limiting."""

    def test_password_hashing_and_verification(self):
        plain = "SecurePassword@1234"
        hashed = hash_password(plain)

        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password(plain, hashed))
        self.assertFalse(verify_password("WrongPassword123", hashed))

    def test_password_strength_validation(self):
        # Too short
        self.assertFalse(validate_password_strength("Ab1!")[0])
        # Missing uppercase
        self.assertFalse(validate_password_strength("password123")[0])
        # Missing digit
        self.assertFalse(validate_password_strength("PasswordNoDigit")[0])
        # Valid strong password
        self.assertTrue(validate_password_strength("ValidP@ssw0rd2026")[0])

    def test_secure_otp_generation_and_hash_verification(self):
        otp = generate_secure_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        # Hash OTP
        otp_h = hash_otp(otp)
        self.assertTrue(verify_otp(otp, otp_h))
        self.assertFalse(verify_otp("000000" if otp != "000000" else "111111", otp_h))

    def test_rate_limiter_sliding_window(self):
        key = "test_rate_client_1"
        RateLimiter._requests.pop(key, None)

        # Allow 3 requests in 10-second window
        self.assertFalse(RateLimiter.is_rate_limited(key, max_requests=3, window_seconds=10))
        self.assertFalse(RateLimiter.is_rate_limited(key, max_requests=3, window_seconds=10))
        self.assertFalse(RateLimiter.is_rate_limited(key, max_requests=3, window_seconds=10))

        # 4th request must be rate limited
        self.assertTrue(RateLimiter.is_rate_limited(key, max_requests=3, window_seconds=10))


if __name__ == "__main__":
    unittest.main()
