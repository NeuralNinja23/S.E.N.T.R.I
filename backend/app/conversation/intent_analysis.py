import re
import math
from typing import Dict, List, Set, Any

class IntentAnalyzer:
    """
    Analyzes user utterances and classifies them into structured cognitive intents.
    Completely local, deterministic, and executes in sub-millisecond time.
    """
    def __init__(self):
        # Category definitions and prototype phrases mapping to intents
        self.prototypes: Dict[str, List[str]] = {
            "IDENTITY_QUERY": [
                "whats my name", "what do you call me", "my name is", 
                "what is my preferred name", "do you know my name", "what is my name",
                "verify my identity", "what name is on record"
            ],
            "CAREER_QUERY": [
                "where do i work", "whos my employer", "what company do i work at", 
                "tell me about my work experience", "what is my job", "my professional background",
                "what company did i found", "what company did i start", "where is my office",
                "my career details", "what experience do i have", "my business background"
            ],
            "LIFESTYLE_QUERY": [
                "where do i live", "who do i live with", "do i live alone", "whos at home with me",
                "am i staying alone", "my apartment roommates", "where am i staying", "who is my roommate",
                "do i live with family", "do i live with friends", "my residential status"
            ],
            "PROJECTS_QUERY": [
                "what projects am i building", "what projects am i working on", "tell me about sentinel",
                "what is genxai studio", "my active software projects", "projects i am developing",
                "what coding projects do i have", "sentinel development"
            ],
            "GOALS_QUERY": [
                "why am i building sentinel", "what is my goal", "what motivates me", "what is my mission",
                "what are my long term goals", "what do i aim to achieve", "what drives me",
                "my goal to build a jarvis assistant"
            ],
            "PREFERENCES_QUERY": [
                "why do i prefer local ai", "what do i dislike", "what do i prefer", "my engineering philosophy",
                "what are my likes and dislikes", "what do i value", "my views on parameter count",
                "my software beliefs", "what are my values", "what is my philosophy", "what motivates me"
            ],
            "PROFILE_QUERY": [
                "who am i", "what kind of engineer am i", "what do you know about me",
                "tell me everything you know about me", "describe me in one paragraph",
                "describe me", "tell me about myself", "my profile", "what is my background",
                "what kind of person am i", "synthesize my profile"
            ]
        }
        
        # Precompute vocabulary and IDF
        self.vocab: Set[str] = set()
        self.docs: List[List[str]] = []
        self.doc_to_intent: List[str] = []
        
        for intent, phrases in self.prototypes.items():
            for phrase in phrases:
                words = self._tokenize(phrase)
                if words:
                    for w in words:
                        self.vocab.add(w)
                    self.docs.append(words)
                    self.doc_to_intent.append(intent)
                    
        self.vocab_list = list(self.vocab)
        self.vocab_idx = {word: i for i, word in enumerate(self.vocab_list)}
        
        # Compute IDF
        self.idf: Dict[str, float] = {}
        n_docs = len(self.docs)
        for word in self.vocab:
            df = sum(1 for doc in self.docs if word in doc)
            self.idf[word] = math.log((1 + n_docs) / (1 + df)) + 1
            
        # Precompute prototype vectors
        self.proto_vectors: List[List[float]] = []
        for doc in self.docs:
            self.proto_vectors.append(self._vectorize(doc))

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        return text.split()

    def _vectorize(self, words: List[str]) -> List[float]:
        vector = [0.0] * len(self.vocab_list)
        if not words:
            return vector
            
        word_counts = {}
        for w in words:
            if w in self.vocab_idx:
                word_counts[w] = word_counts.get(w, 0) + 1
        for w, count in word_counts.items():
            idx = self.vocab_idx[w]
            tf = count / len(words)
            vector[idx] = tf * self.idf[w]
            
        # Normalize vector
        magnitude = math.sqrt(sum(v**2 for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector

    def analyze(self, query: str) -> str:
        """
        Classifies the user query string into one of the structured intents.
        Falls back to 'UNKNOWN_QUERY' if similarity score is below a threshold.
        """
        query_words = self._tokenize(query)
        if not query_words:
            return "UNKNOWN_QUERY"
            
        query_vec = self._vectorize(query_words)
        
        best_score = -1.0
        best_intent = "UNKNOWN_QUERY"
        
        for idx, proto_vec in enumerate(self.proto_vectors):
            # Cosine similarity (dot product of L2-normalized vectors)
            score = sum(q * p for q, p in zip(query_vec, proto_vec))
            if score > best_score:
                best_score = score
                best_intent = self.doc_to_intent[idx]
                
        # Similarity confidence threshold check
        if best_score < 0.15:
            return "UNKNOWN_QUERY"
            
        return best_intent
