import os
from unittest.mock import patch, MagicMock
from helpers import MockLogger


class TestClashApiInit:
    def test_raises_runtime_error_on_failed_clan_fetch(self):
        import clashApi
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_cm = MagicMock()
        mock_logger = MockLogger()

        with patch('clashApi.requests') as mock_requests:
            mock_session = MagicMock()
            login_resp = MagicMock()
            login_resp.status_code = 200
            token_payload = "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJsaW1pdHMiOiBbeyJjaWRycyI6IFtdfSwgeyJjaWRycyI6IFsiMTI3LjAuMC4xLzMyIl19XX0.testsig"
            login_resp.json.return_value = {"temporaryAPIToken": token_payload}

            list_resp = MagicMock()
            list_resp.json.return_value = {"keys": [{"name": "testkey", "key": "abc123", "cidrRanges": ["127.0.0.1"], "id": "1"}]}

            mock_session.post.side_effect = [login_resp, list_resp]
            mock_requests.Session.return_value = mock_session
            mock_requests.get.return_value = mock_response

            try:
                clashApi.ClashApi(mock_cm, "test@example.com", "pass", "testkey", "CLAN1", mock_logger)
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "500" in str(e) or "Failed to get clan" in str(e)

    def test_invalid_credentials_raises_exception(self):
        import clashApi
        mock_cm = MagicMock()
        mock_logger = MockLogger()

        with patch('clashApi.requests') as mock_requests:
            mock_session = MagicMock()
            login_resp = MagicMock()
            login_resp.status_code = 403
            mock_session.post.return_value = login_resp
            mock_requests.Session.return_value = mock_session

            try:
                clashApi.ClashApi(mock_cm, "bad@example.com", "badpass", "testkey", "CLAN1", mock_logger)
                assert False, "Should have raised InvalidCredentials"
            except clashApi.InvalidCredentials:
                pass


    def test_login_failure_raises_runtime_error(self):
        import clashApi
        mock_cm = MagicMock()
        mock_logger = MockLogger()

        with patch('clashApi.requests') as mock_requests:
            mock_session = MagicMock()
            login_resp = MagicMock()
            login_resp.status_code = 500
            mock_session.post.return_value = login_resp
            mock_requests.Session.return_value = mock_session

            try:
                clashApi.ClashApi(mock_cm, "test@example.com", "pass", "testkey", "CLAN1", mock_logger)
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "Login failed" in str(e)


class TestClashApiTimeouts:
    def test_api_timeout_is_set(self):
        import clashApi
        assert clashApi.ClashApi.API_TIMEOUT == 30
