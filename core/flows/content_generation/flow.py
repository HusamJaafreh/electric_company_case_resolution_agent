#core/flows/content_generation/flow.py
class ContentGenerationFlow:
    def kickoff(self, user_query: str):
        # Stub: return something deterministic for testing
        return [{"text": f"Generated content for: {user_query}", "image": ""}]
