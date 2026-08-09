import os
import glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.config import DATA_DIR

KB_DIR = os.path.join(DATA_DIR, "kb")


class KBIndex:
    def __init__(self, kb_dir: str = KB_DIR):
        self.kb_dir = kb_dir
        self.doc_ids = []
        self.titles = []
        self.categories = []
        self.texts = []
        self.vectorizer = None
        self.matrix = None
        self._build()

    def _build(self):
        # recursive=True + "**/*.md" walks every category subfolder, not just
        # the kb root -- this is the fix for docs nested under billing/,
        # onboarding/, products/, troubleshooting/, etc.
        pattern = os.path.join(self.kb_dir, "**", "*.md")
        paths = sorted(glob.glob(pattern, recursive=True))

        for path in paths:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            rel_path = os.path.relpath(path, self.kb_dir)
            doc_id = rel_path.replace(os.sep, "/")  # stable across OSes

            parts = rel_path.split(os.sep)
            category = parts[0] if len(parts) > 1 else "uncategorized"

            first_line = content.splitlines()[0] if content else os.path.basename(path)
            title = first_line.lstrip("#").strip()

            self.doc_ids.append(doc_id)
            self.titles.append(title)
            self.categories.append(category)
            self.texts.append(content)

        if self.texts:
            self.vectorizer = TfidfVectorizer(stop_words="english")
            self.matrix = self.vectorizer.fit_transform(self.texts)

    def search(self, query: str, top_k: int = 1, min_score: float = 0.05):
        if not self.texts or self.vectorizer is None:
            return []
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            if scores[i] >= min_score:
                results.append({
                    "doc_id": self.doc_ids[i],
                    "title": self.titles[i],
                    "category": self.categories[i],
                    "score": float(scores[i]),
                })
        return results