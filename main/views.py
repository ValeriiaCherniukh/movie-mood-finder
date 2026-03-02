from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.conf import settings
import requests
import math

def landing(request):
    return render(request, "main/landing.html")

def mood(request):
    return render(request, "main/mood.html")

def home(request):
    return render(request, "main/home.html")

# 1) Мапа "настрій -> сигнали"
# genres = ID жанрів TMDB (вони універсальні)
# keywords = слова, які шукаємо в title/overview (приблизно, але працює)
MOOD_SIGNALS = {
    "Happy": {"genres": [35, 12], "keywords": ["fun", "happy", "party", "laugh", "friendship"]},          # Comedy, Adventure
    "Sad": {"genres": [18], "keywords": ["loss", "grief", "sad", "cry", "heart"]},                       # Drama
    "Heartbroken": {"genres": [18, 10749], "keywords": ["breakup", "heart", "love", "tear", "alone"]},  # Drama, Romance
    "Romantic": {"genres": [10749, 35], "keywords": ["love", "date", "relationship", "romance"]},       # Romance, Comedy
    "Cozy evening": {"genres": [35, 10751], "keywords": ["family", "home", "cozy", "warm"]},            # Comedy, Family
    "Lonely": {"genres": [18], "keywords": ["lonely", "alone", "isolation", "quiet"]},                  # Drama
    "Excited": {"genres": [28, 12, 53], "keywords": ["chase", "battle", "mission", "fast"]},            # Action, Adventure, Thriller
    "Anxious": {"genres": [53, 9648, 27], "keywords": ["mystery", "danger", "suspense", "panic"]},      # Thriller, Mystery, Horror
    "Overthinking": {"genres": [9648, 18, 878], "keywords": ["mind", "truth", "reality", "memory"]},    # Mystery, Drama, Sci-Fi
    "Thoughtful": {"genres": [18, 99], "keywords": ["meaning", "life", "choice", "journey"]},           # Drama, Documentary
    "Emotional": {"genres": [18], "keywords": ["family", "touching", "tear", "feel"]},                  # Drama
    "Dark humor": {"genres": [35, 80], "keywords": ["dark", "crime", "twisted", "sarcasm"]},            # Comedy, Crime
    "Wholesome": {"genres": [10751, 35], "keywords": ["kind", "heartwarming", "hope", "together"]},     # Family, Comedy
    "Sick": {"genres": [35, 10751], "keywords": ["comfort", "easy", "warm", "home"]},                   # comfort-watch
    "Tired": {"genres": [10751, 16, 35], "keywords": ["easy", "calm", "simple", "gentle"]},             # Family, Animation, Comedy
    "Inspired": {"genres": [18], "keywords": ["dream", "inspire", "goal", "success"]},
    "Nostalgic": {"genres": [18, 35], "keywords": ["childhood", "old days", "memory", "retro"]},
    "Background watching": {"genres": [35, 10751, 16], "keywords": ["light", "easy", "fun"]},
    "Calm": {"genres": [18], "keywords": ["calm", "quiet", "slow", "peace"]},
    "Escapism": {"genres": [12, 14, 878], "keywords": ["world", "magic", "space", "adventure"]},        # Adventure, Fantasy, Sci-Fi
    "Lost": {"genres": [18], "keywords": ["lost", "search", "purpose", "identity"]},
}


def _normalize_text(s: str) -> str:
    return (s or "").lower()


def _build_signals(selected_moods):
    genres = set()
    keywords = set()
    for mood in selected_moods:
        sig = MOOD_SIGNALS.get(mood, {})
        for g in sig.get("genres", []):
            genres.add(g)
        for k in sig.get("keywords", []):
            keywords.add(k.lower())
    return genres, keywords


def _score_movie(movie, target_genres, target_keywords):
    movie_genres = set(movie.get("genre_ids", []))
    title = _normalize_text(movie.get("title"))
    overview = _normalize_text(movie.get("overview"))
    text = f"{title} {overview}"

    why = []
    score = 0.0

    # жанри (м’яко): за збіг жанрів даємо бали
    common = movie_genres.intersection(target_genres)
    if common:
        score += 2.5 * len(common)
        why.append(f"matches genres: {len(common)}")

    # ключові слова в описі
    kw_hits = 0
    for kw in target_keywords:
        if kw and kw in text:
            kw_hits += 1
    if kw_hits:
        score += 1.2 * kw_hits
        why.append(f"keyword hits: {kw_hits}")

    # якість/популярність (щоб не радити сміття з 2 голосами)
    vote_avg = movie.get("vote_average") or 0
    vote_count = movie.get("vote_count") or 0

    score += (vote_avg / 10.0) * 3.0            # до +3
    score += min(2.0, math.log10(vote_count + 1))  # до +2

    if vote_avg:
        why.append(f"rating: {vote_avg}")
    if vote_count:
        why.append(f"votes: {vote_count}")

    return score, why


def results(request):
    moods_raw = request.GET.get("moods", "")
    moods = [m.strip() for m in moods_raw.split(",") if m.strip()]

    api_key = settings.TMDB_API_KEY
    if not api_key:
        return render(request, "main/results.html", {
            "moods": moods,
            "movies": [],
            "error": "TMDB_API_KEY is missing in .env",
        })

    target_genres, target_keywords = _build_signals(moods)

    # 2) Беремо "широку" вибірку з TMDB і потім скоримо
    base_url = "https://api.themoviedb.org/3/discover/movie"
    candidates = []
    page = 1

    # Базові “анти-сміття” параметри
    params = {
        "api_key": api_key,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "include_video": "false",
        "vote_count.gte": 200,
    }

    from tracker.models import UserTitle

    saved_map = {}
    if request.user.is_authenticated:
        saved_map = {
            ut.title.tmdb_id: ut.status
            for ut in UserTitle.objects.select_related("title")
            .filter(user=request.user, title__tmdb_id__isnull=False)
        }

    # якщо є жанрові сигнали — додамо як “підказку”, але НЕ як жорстку вимогу всіх жанрів
    #if target_genres:
    #    params["with_genres"] = "|".join(str(g) for g in list(target_genres)[:4])  # максимум 4, щоб не душити

    # підвантажимо до ~80 кандидатів (2 сторінки по 20–40 залежно від відповіді)
    while page <= 4 and len(candidates) < 80:
        params["page"] = page
        try:
            r = requests.get(base_url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            results_list = data.get("results", [])
        except Exception as e:
            print("TMDB ERROR:", e)
            results_list = []

        if not results_list:
            break
        candidates.extend(results_list)
        page += 1

    # 3) Скоринг
    scored = []
    for m in candidates:
        s, why = _score_movie(m, target_genres, target_keywords)
        scored.append((s, m, why))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 4) Візьмемо топ-10 унікальних
    movies = []
    seen = set()
    for s, m, why in scored:
        mid = m.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)

        poster_path = m.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        movies.append({
            "title": m.get("title"),
            "overview": m.get("overview"),
            "rating": m.get("vote_average"),
            "poster_url": poster_url,
            "why": ", ".join(why[:2])  # коротко, щоб не засмічувати
        })

        if len(movies) >= 10:
            break

    return render(request, "main/results.html", {
        "moods": moods,
        "movies": movies,
        "tmdb_attribution": True,
        "saved_map": saved_map,
    })
def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})