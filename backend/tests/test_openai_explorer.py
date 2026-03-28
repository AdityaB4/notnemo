import unittest

from backend.openai_explorer import SYSTEM_PROMPT, build_initial_input
from backend.models import ExplorerBranchInput, NormalizedQuery, SearchLimits


class OpenAIExplorerPromptTests(unittest.TestCase):
    def test_system_prompt_documents_debug_force_tinyfish(self) -> None:
        self.assertIn("debug_force_tinyfish", SYSTEM_PROMPT)
        self.assertIn("perform web search first", SYSTEM_PROMPT)
        self.assertIn("call tinyfish_scrape", SYSTEM_PROMPT)

    def test_build_initial_input_preserves_profile_debug_hint(self) -> None:
        branch = ExplorerBranchInput(
            job_id="job_123",
            branch_id="root",
            depth=0,
            normalized_query=NormalizedQuery(
                raw_query={
                    "text": "embroidered denim underground brands",
                    "profile": {"debug_force_tinyfish": True},
                },
                query_text="embroidered denim underground brands",
                profile={"debug_force_tinyfish": True},
                keywords=["embroidered", "denim", "underground", "brands"],
            ),
            candidate_urls=["https://www.are.na"],
            limits=SearchLimits(max_results=5),
            stream_tinyfish=True,
        )

        prompt = build_initial_input(branch)[1]["content"][0]["text"]

        self.assertIn('"debug_force_tinyfish": true', prompt)


if __name__ == "__main__":
    unittest.main()
