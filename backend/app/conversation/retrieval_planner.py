from typing import List, Dict, Tuple

class RetrievalPlanner:
    """
    Decides what categories of memories are needed to fulfill a conversation intent,
    and calculates the dynamic memory budget policy.
    """
    def __init__(self):
        # Maps query intents to corresponding semantic memory categories
        self.intent_category_map: Dict[str, List[str]] = {
            "IDENTITY_QUERY": ["Identity"],
            "CAREER_QUERY": ["Career", "Identity"],
            "LIFESTYLE_QUERY": ["Lifestyle", "Identity"],
            "PROJECTS_QUERY": ["Project", "Goal"],
            "GOALS_QUERY": ["Goal", "Fact", "Preference"],
            "PREFERENCES_QUERY": ["Preference", "Fact"],
            "PROFILE_QUERY": ["Identity", "Career", "Project", "Goal", "Preference", "Fact"],
            "UNKNOWN_QUERY": ["Fact", "Preference", "Identity", "Career", "Lifestyle", "Project", "Goal"]
        }
        
        # Maps query intents to baseline memory limits (budget policy)
        self.intent_budget_map: Dict[str, int] = {
            "IDENTITY_QUERY": 2,      # Targeted identity lookup
            "LIFESTYLE_QUERY": 6,     # Moderate lookup (contains location details)
            "CAREER_QUERY": 6,        # Structured profile
            "PROJECTS_QUERY": 8,      # Projects context
            "GOALS_QUERY": 8,         # Goals and philosophy
            "PREFERENCES_QUERY": 6,   # User preferences
            "PROFILE_QUERY": 20,      # Comprehensive profile synthesis
            "UNKNOWN_QUERY": 15       # Broad scan (fallback)
        }

    def plan(self, intent: str, context_window_limit: int = 4096) -> Tuple[List[str], int]:
        """
        Calculates the memory category retrieval requirements and dynamic budget.
        Returns a tuple of (categories_list, budget_limit).
        """
        categories = self.intent_category_map.get(intent, self.intent_category_map["UNKNOWN_QUERY"])
        budget = self.intent_budget_map.get(intent, self.intent_budget_map["UNKNOWN_QUERY"])
        
        # Adjust budget based on context limits or environment policies if needed
        if context_window_limit < 2048:
            budget = max(1, budget // 2)
            
        return categories, budget
