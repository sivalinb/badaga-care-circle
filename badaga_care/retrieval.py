from collections import Counter
from datetime import date
from hashlib import sha256
import json
import re
from threading import Lock
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import SearchHit
from .safety import normalise

STOPWORDS = set("a an the of to in is are be can do does did doing how what we i my our with for and or it this that at as on from have has should could would about person people one who everyone".split())
STOPWORDS.update({"எப்படி", "என்ன", "நாம்", "என்", "எனக்கு", "ஒரு", "உள்ள", "மற்றும்", "அல்லது", "செய்ய"})


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+|[\u0b80-\u0bff]+", normalise(text)) if t not in STOPWORDS]


def expand_query(text):
    # Small explicit bilingual topic lexicon; avoids treating Tamil case suffixes as unrelated words.
    aliases = {
        r"பராமரிப்பாள|பொறுப்ப|மன அழுத்த": "caregiver responsibility help",
        r"குடும்ப மாற்று|மாற்று ஏற்பா|ஆவண": "family backup continuity",
        r"தேநீ|சர்க்கரை": "tea sugar",
        r"உப்ப": "salt food",
        r"மாத்திரை|மருந்து": "medicine tablets",
        r"பரிசோதனை|நீரிழி": "screening diabetes",
        r"ரத்த அழுத்த": "blood pressure",
        r"மது|குடிப்ப": "alcohol",
        r"திடீர் மரண|உறவின": "family history sudden death",
    }
    return text + " " + " ".join(alias for pattern, alias in aliases.items() if re.search(pattern, text))


class HybridRetriever:
    """BM25 + Tamil-friendly character TF-IDF; optional OpenAI dense vectors."""
    def __init__(self, knowledge_path, data_dir):
        self.docs = json.loads(knowledge_path.read_text(encoding="utf-8"))
        self.by_id = {d["id"]: d for d in self.docs}
        if len(self.by_id) != len(self.docs):
            raise ValueError("Knowledge IDs must be unique")
        self.corpus = [" ".join([d["title"]["en"], d["title"]["ta"], d["text"]["en"], d["text"]["ta"], *d["tags"]]) for d in self.docs]
        self.counts = [Counter(tokens(c)) for c in self.corpus]
        self.lengths = np.array([sum(c.values()) for c in self.counts], dtype=float)
        self.mean_length = float(np.mean(self.lengths))
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
        self.char_vectors = self.vectorizer.fit_transform(self.corpus)
        self.data_dir = data_dir
        self.cache_lock = Lock()

    def active(self, doc, today, production=False):
        if date.fromisoformat(doc["expires_on"]) < today:
            return False
        if production:
            return doc["review_status"] == "approved" and bool(doc.get("clinical_reviewer") and doc.get("language_reviewer"))
        return True

    def search(self, question, *, today=None, production=False, dense_client=None, embedding_model="text-embedding-3-small", k=3):
        today = today or date.today()
        expanded = expand_query(question)
        query_tokens = tokens(expanded)
        bm25 = np.zeros(len(self.docs))
        n = len(self.docs)
        for token in set(query_tokens):
            df = sum(token in c for c in self.counts)
            if not df:
                continue
            idf = np.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, count in enumerate(self.counts):
                tf = count[token]
                bm25[i] += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * self.lengths[i] / self.mean_length)) if tf else 0
        if bm25.max() > 0:
            bm25 /= bm25.max()
        chars = (self.char_vectors @ self.vectorizer.transform([expanded]).T).toarray().ravel()
        local_scores = 0.65 * bm25 + 0.35 * chars
        semantic = np.zeros(len(self.docs))
        usage = 0
        retrieval_mode = "bm25+char_tfidf"
        if dense_client is not None:
            dense, usage = self._dense_vectors(dense_client, embedding_model)
            response = dense_client.embeddings.create(model=embedding_model, input=[question])
            query = np.array(response.data[0].embedding, dtype=float)
            query /= np.linalg.norm(query) or 1
            semantic = dense @ query
            usage += getattr(response.usage, "total_tokens", 0) or 0
            scores = 0.55 * local_scores + 0.45 * np.maximum(semantic, 0)
            retrieval_mode += "+openai_embeddings"
        else:
            scores = local_scores
        hits = []
        for index in np.argsort(-scores):
            doc = self.docs[index]
            if not self.active(doc, today, production):
                continue
            # With no matched topic term, character overlap alone is not reliable evidence.
            if (bm25[index] == 0 and semantic[index] < 0.4) or scores[index] < 0.15:
                continue
            hits.append(SearchHit(doc, round(float(scores[index]), 4), round(float(local_scores[index]), 4), round(float(semantic[index]), 4)))
            if len(hits) >= k:
                break
        return hits, retrieval_mode, usage

    def _dense_vectors(self, client, model):
        digest = sha256(json.dumps([model, self.corpus], ensure_ascii=False).encode()).hexdigest()
        cache_path = self.data_dir / ("public-embeddings-" + digest[:16] + ".json")
        usage = 0
        with self.cache_lock:
            if cache_path.exists():
                cached = json.loads(cache_path.read_text())
                vectors = np.array(cached["vectors"], dtype=float)
            else:
                response = client.embeddings.create(model=model, input=self.corpus)
                vectors = np.array([d.embedding for d in sorted(response.data, key=lambda item: item.index)], dtype=float)
                usage = getattr(response.usage, "total_tokens", 0) or 0
                cache_path.write_text(json.dumps({"model": model, "corpus_hash": digest, "vectors": vectors.tolist()}))
            if len(vectors) != len(self.docs) or vectors.ndim != 2:
                raise ValueError("Invalid public embedding cache")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms), usage

    def public_register(self, lang):
        return [{"id": d["id"], "title": d["title"][lang], "source": d["source_name"], "version": d["version"], "checked": d["source_checked"], "expires": d["expires_on"], "review": d["review_status"]} for d in self.docs]
