import io
import json
import os
import socket
import unittest
import urllib.error
from unittest import mock

from experiential_labs import decisions as d


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


MOCK_BODY = {
    "answers": [
        {"name": "safe_to_merge", "type": "predicate", "probability": 0.82},
        {"name": "risk", "type": "score", "score": 1, "label": "medium"},
        {"type": "refusal", "refusal": "declined"},
    ],
    "usage": {"input_tokens": 120, "output_tokens": 9, "total_tokens": 129},
}


@mock.patch.dict(os.environ, {"EXPERIENTIAL_API_KEY": "test-key"}, clear=True)
class DecideTests(unittest.TestCase):
    def test_request_shape(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(json.dumps(MOCK_BODY).encode())) as m:
            resp = d.decide("diff summary", d.review_questions())
        req = m.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.experientiallabs.ai/v1/decisions")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer test-key")
        self.assertIsNone(req.get_header("Idempotency-key"))
        self.assertEqual(m.call_args.kwargs["timeout"], d.DEFAULT_TIMEOUT)
        body = json.loads(req.data)
        self.assertEqual(body["model"], "gpt-6-luna-decisions")
        self.assertEqual(body["input"], "diff summary")
        self.assertEqual(len(body["questions"]), 3)
        self.assertEqual(d.answer_at(resp, d.REVIEW_INDEX)["probability"], 0.82)
        self.assertTrue(d.format_answer(resp["answers"][2]).startswith("refused"))

    def test_missing_key(self):
        os.environ.pop("EXPERIENTIAL_API_KEY")
        with mock.patch("urllib.request.urlopen") as m:
            with self.assertRaises(d.MissingKeyError):
                d.decide("x", d.review_questions())
        m.assert_not_called()

    def test_http_error_no_retry(self):
        err = urllib.error.HTTPError(d.DECISIONS_URL, 429, "Too Many", {}, io.BytesIO(b"slow down"))
        with mock.patch("urllib.request.urlopen", side_effect=err) as m:
            with self.assertRaisesRegex(d.DecisionsError, "HTTP 429.*slow down"):
                d.decide("x", d.review_questions())
        self.assertEqual(m.call_count, 1)

    def test_timeout_no_retry(self):
        with mock.patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")) as m:
            with self.assertRaisesRegex(d.DecisionsError, "outcome unknown"):
                d.decide("x", d.review_questions())
        self.assertEqual(m.call_count, 1)

    def test_image_input(self):
        msgs = d.build_input("look", [("image/png", "QUJD")])
        self.assertEqual(msgs[0]["content"][0], {"type": "input_text", "text": "look"})
        self.assertEqual(msgs[0]["content"][1]["type"], "input_image")
        self.assertTrue(msgs[0]["content"][1]["image_url"].startswith("data:image/png;base64,"))


class ValidationTests(unittest.TestCase):
    def q(self, **kw):
        return {"instructions": "x", "type": "predicate", **kw}

    def test_limits(self):
        with self.assertRaises(ValueError):
            d.validate_questions([self.q()] * 33)
        with self.assertRaises(ValueError):
            d.validate_questions([self.q(type="choice", choices=[{"value": str(i)} for i in range(65)])])
        with self.assertRaises(ValueError):
            d.validate_questions([self.q(type="score", levels=[{"label": "a"}])])
        with self.assertRaises(ValueError):
            d.validate_questions([self.q(type="score", levels=[{"label": str(i)} for i in range(11)])])
        with self.assertRaises(ValueError):
            d.validate_questions([self.q(name="a"), self.q(name="a")])
        with self.assertRaises(ValueError):
            d.validate_questions([{"type": "predicate"}])
        d.validate_questions([self.q()] * 32)


if __name__ == "__main__":
    unittest.main()
