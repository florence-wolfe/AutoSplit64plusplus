import threading
import unittest
from unittest import mock

from autosplit64.core import config, livesplit_one
from autosplit64.gui import origin_prompt
from autosplit64.gui.app import App
from autosplit64.gui.origin_prompt import OriginPrompt
from tests.qt import answering, close_window, run_queued
from tests.settings import patch_settings


class OriginPromptTest(unittest.TestCase):
    def setUp(self):
        for patcher in [patch_settings({("connection", "ws_allowed_origins"): ["https://one.livesplit.org"]}),
                        mock.patch.object(config, "save_key")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.prompt = OriginPrompt()
        self.addCleanup(self.prompt.deleteLater)

    def ask(self, origin):
        """ Ask from another thread, as the server does, and answer on this one """
        answers = []
        server = threading.Thread(target=lambda: answers.append(self.prompt(origin)))
        server.start()
        while server.is_alive():
            run_queued()
            server.join(0.01)
        return answers[0]

    def test_allowing_a_page_saves_it(self):
        texts = []
        with answering("Allow", texts):
            self.assertIs(self.ask("https://timer.example"), True)
        self.assertEqual(texts, [{"Allow": True, "Deny": True}])
        config.save_key.assert_called_once_with("connection", "ws_allowed_origins",
                                                ["https://one.livesplit.org", "https://timer.example"])

    def test_denying_a_page(self):
        with answering("Deny"):
            self.assertIs(self.ask("https://timer.example"), False)
        config.save_key.assert_not_called()

    def test_allowed_after_the_page_stopped_waiting(self):
        # The page is refused, and connects the next time it tries
        answers = []
        with mock.patch.object(origin_prompt, "WAIT", 0.05):
            server = threading.Thread(target=lambda: answers.append(self.prompt("https://timer.example")))
            server.start()
            server.join()
        self.assertEqual(answers, [False])
        with answering("Allow"):
            run_queued()
        config.save_key.assert_called_once_with("connection", "ws_allowed_origins",
                                                ["https://one.livesplit.org", "https://timer.example"])


class AppTest(unittest.TestCase):
    def test_the_app_asks_while_it_is_open(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"), mock.patch.object(livesplit_one, "ask", None):
            app = App()
            self.assertIsInstance(livesplit_one.ask, OriginPrompt)
            close_window(app)
            self.assertIsNone(livesplit_one.ask)


if __name__ == "__main__":
    unittest.main()
