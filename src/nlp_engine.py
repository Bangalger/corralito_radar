import json
import re
import numpy as np

from src.text_utils import as_text

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    return a_norm @ b_norm.T


def _tokenize(text) -> list[str]:
    return re.findall(r"\b\w{3,}\b", as_text(text).lower())


def _tfidf_matrix(texts: list) -> np.ndarray:
    clean_texts = [as_text(t) for t in texts]
    docs = [_tokenize(t) for t in clean_texts]
    vocab = sorted({w for doc in docs for w in doc})
    if not vocab:
        return np.zeros((len(clean_texts), 1))

    word_idx = {w: i for i, w in enumerate(vocab)}
    n_docs = len(docs)
    df = np.zeros(len(vocab))
    for doc in docs:
        for w in set(doc):
            df[word_idx[w]] += 1

    idf = np.log((1 + n_docs) / (1 + df)) + 1
    matrix = np.zeros((len(clean_texts), len(vocab)))
    for row, doc in enumerate(docs):
        if not doc:
            continue
        counts = {}
        for w in doc:
            counts[w] = counts.get(w, 0) + 1
        for w, tf in counts.items():
            matrix[row, word_idx[w]] = tf * idf[word_idx[w]]
    return matrix


def _parse_news_input(news_items) -> tuple[list[str], np.ndarray]:
    texts: list[str] = []
    weights: list[float] = []
    for item in news_items:
        if isinstance(item, dict):
            w = float(item.get("weight", 1.0))
            if w <= 0:
                continue
            text = as_text(item.get("text", item))
        else:
            text = as_text(item)
            w = 1.0
        if text:
            texts.append(text)
            weights.append(w)
    return texts, np.asarray(weights, dtype=float)


class RiskAnalyzer:
    def __init__(self, historical_file='data/historical_events.json'):
        self.historical_file = historical_file
        self.model = None
        self._use_tfidf = False
        if SentenceTransformer:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                self._use_tfidf = True
        else:
            self._use_tfidf = True
        self.load_historical_data()

    def load_historical_data(self):
        try:
            with open(self.historical_file, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
        except Exception as e:
            print(f"Error cargando historial: {e}")
            self.history = []

        if self.model:
            for period_data in self.history:
                quotes = [as_text(q) for q in period_data['quotes']]
                period_data['embeddings'] = self.model.encode(quotes)

    def analyze_news(self, news_items):
        if not self.history:
            return {"error": "Sin datos históricos o noticias para analizar"}

        news_active, weights_active = _parse_news_input(news_items)
        if len(news_active) == 0:
            return {"error": "Todas las noticias fueron descartadas por filtro de amarillismo"}

        if self.model:
            current_embeddings = self.model.encode(news_active)
            period_slices = [(p['period'], p['embeddings']) for p in self.history]
        else:
            all_quotes = [as_text(q) for p in self.history for q in p['quotes']]
            corpus = all_quotes + news_active
            full_matrix = _tfidf_matrix(corpus)
            current_embeddings = full_matrix[len(all_quotes):]
            offset = 0
            period_slices = []
            for period_data in self.history:
                n = len(period_data['quotes'])
                period_slices.append((period_data['period'], full_matrix[offset:offset + n]))
                offset += n

        results = {}
        for period_name, hist_embeddings in period_slices:
            sim_matrix = _cosine_similarity(current_embeddings, hist_embeddings)
            max_sims = np.max(sim_matrix, axis=1)
            w_sum = float(weights_active.sum())
            avg_sim = float(np.dot(max_sims, weights_active) / w_sum) if w_sum else 0.0
            results[period_name] = min(avg_sim * 150, 100)

        return results

    def calculate_financial_score(self, df):
        if df.empty or len(df) < 30:
            return 0.0

        last_7_dollar = df['Dólar Libre'].iloc[-7:]
        prev_dollar = df['Dólar Libre'].iloc[:-7]

        mean_prev, std_prev = prev_dollar.mean(), prev_dollar.std()
        if std_prev == 0:
            std_prev = 1

        z_score_dollar = (last_7_dollar.mean() - mean_prev) / std_prev
        return min(max(z_score_dollar * 33.3, 0), 100)
