import re
import requests
from urllib.parse import quote
from flask import Flask, request, jsonify, send_file
from AnimeSlayerAPI import Anime, DOMAIN, HEADERS, TIMEOUT

app = Flask(__name__)

_eps_cache = {}
_play_cache = {}
_home_cache = None
_MAX_CACHE = 200

def _trim_cache(cache):
    while len(cache) > _MAX_CACHE:
        try:
            cache.pop(next(iter(cache)))
        except StopIteration:
            break

def _number_to_alphabet(number):
    result = ""
    number = int(number)
    while number > 0:
        remainder = (number - 1) % 26
        result = chr(remainder + 97) + result
        number = (number - 1) // 26
    return result

def _make_slug(name, id_):
    slug = (name or "").lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = slug.strip()
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug + "-" + _number_to_alphabet(id_)

def _fetch_browse(params):
    p = {"_api": 1, "order_by": "latest_first", **params}
    r = requests.get(f"{DOMAIN}/browse", params=p, headers=HEADERS, timeout=TIMEOUT)
    data = r.json()
    if data.get("success"):
        for item in data.get("data", []):
            item["slug"] = _make_slug(item["anime_name"], item["anime_id"])
        return data
    return {"success": False, "data": []}

def _fmt_browse_item(item):
    return {
        "title": item["anime_name"],
        "slug": item["slug"],
        "image": item.get("anime_cover_image_url", ""),
        "type": item.get("anime_type", ""),
        "status": item.get("anime_status", ""),
        "year": item.get("anime_release_year", ""),
        "season": item.get("anime_season", ""),
        "rating": item.get("anime_rating"),
        "genres": item.get("anime_genres", "")
    }

@app.route("/")
def index():
    return send_file("index.html", mimetype='text/html')

FALLBACK = [
    {"title":"ون بيس","slug":"one-piece-byw","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-bd6aea763d77a3a6a341a60425f32e5b.jpg","type":"TV","year":"1999"},
    {"title":"هجوم العمالقة","slug":"shingeki-no-kyojin-bzw","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-860185f873a5e284e0c3ba0a4c102f12.jpg","type":"TV","year":"2013"},
    {"title":"جوجوتسو كايسن","slug":"jujutsu-kaisen-cly","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-656701bb048b4df90fbc9d874787014d.jpg","type":"TV","year":"2020"},
    {"title":"كود جياس","slug":"code-geass-hangyaku-no-lelouch-ro","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-b45ba7f1ea5a330750da48e35d9a884b.jpg","type":"TV","year":"2006"},
    {"title":"المسجل الأسود","slug":"the-black-record-fqn","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-7323094cb72aa748f2418a8e273f1b69.jpg","type":"TV","year":"2025"},
    {"title":"دارلينغ إن ذا فرانكس","slug":"darling-in-the-franxx-sl","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-a4b8e29d5eb77c8532202a58a38c3f4c.jpg","type":"TV","year":"2018"},
    {"title":"ناروتو شيبودن","slug":"naruto-shippuuden-byv","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-d6fc57a680a9fb7277ff2c9a7dead6d1.jpg","type":"TV","year":"2007"},
    {"title":"قاتل الشياطين","slug":"kimetsu-no-yaiba-yuukaku-hen-cuu","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-628d1ca5095917f2f21c5caf3d37655a.jpg","type":"TV","year":"2021"},
    {"title":"ون بانش مان","slug":"one-punch-man-bzz","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-e3c7def532f8b3ea38e49616a8b588dc.jpg","type":"TV","year":"2015"},
    {"title":"بليتش","slug":"bleach-sennen-kessen-hen-cuq","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-5e3a0cb2af11c1abdb6ae2e34852ca19.jpg","type":"TV","year":"2022"},
    {"title":"هانتر × هانتر","slug":"hunter-x-hunter-2011-agk","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-baac3c17c15e329e85b2019ab7e9f9af.jpg","type":"TV","year":"2011"},
    {"title":"دراغون بول سوبر","slug":"dragon-ball-super-bxw","image":"https://img.anslayer.com/anime/anime/cover-image/anime-cover-d07a97303a04e13e9a0c3fc096608cfa.jpg","type":"TV","year":"2015"},
]

@app.route("/api/homepage")
def api_homepage():
    global _home_cache
    if _home_cache:
        return jsonify(_home_cache)
    try:
        real = []
        for pg in range(1, 6):
            data = _fetch_browse({"page": pg})
            for x in data.get("data", []):
                if x.get("just_info", "").lower() != "yes":
                    real.append(_fmt_browse_item(x))
    except:
        real = []
    result = []
    seen = set()
    if len(real) >= 4:
        result.append({"label":"🆕 أحدث الأنمي","items":real[:18]})
        for x in real[:18]: seen.add(x["slug"])
        airing = [x for x in real if x.get("status")=="Currently Airing"][:18]
        if len(airing)>=3:
            result.append({"label":"📺 يعرض الآن","items":airing})
        _home_cache = result
        return jsonify(result)
    result.append({"label":"🆕 أحدث الأنمي","items":FALLBACK[:18]})
    result.append({"label":"🔥 الأكثر مشاهدة","items":FALLBACK[3:9]+FALLBACK[:3]})
    result.append({"label":"⭐ كلاسيكيات","items":FALLBACK[6:12]+FALLBACK[3:6]})
    _home_cache = result
    return jsonify(result)

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"found": 0, "message": "الرجاء إدخال اسم الأنمي"})

    def _search(term):
        try:
            r = requests.get(f"{DOMAIN}/api/search.php?q={quote(term)}", headers=HEADERS, timeout=TIMEOUT)
            return r.json()
        except:
            return []

    def _fmt_s(item):
        return {
            "title": item["title"],
            "slug": item["href"].replace("/title/", ""),
            "image": item.get("image", ""),
            "type": item.get("type", ""),
            "status": item.get("status", ""),
            "season": item.get("season", ""),
            "episodes_count": item.get("episodes")
        }

    try:
        results = _search(title)
        seen = set()
        out = []
        for r in results:
            slug = r["href"].replace("/title/", "")
            if slug not in seen:
                seen.add(slug)
                out.append(_fmt_s(r))

        # Try extra terms if results are few
        if len(results) < 8:
            words = title.split()
            terms = []
            if len(words) > 1:
                terms.extend([words[0], words[-1]])
            for w in words:
                if len(w) > 2:
                    terms.append(w)
            for term in terms:
                extra = _search(term)
                for item in extra:
                    slug = item["href"].replace("/title/", "")
                    if slug not in seen:
                        seen.add(slug)
                        out.append(_fmt_s(item))

        # Also fetch from browse API for full catalog results
        try:
            br = requests.get(f"{DOMAIN}/browse", params={"_api": 1, "page": 1, "keyword": title, "order_by": "latest_first"}, headers=HEADERS, timeout=TIMEOUT)
            bdata = br.json()
            if bdata.get("success"):
                for item in bdata.get("data", []):
                    slug = _make_slug(item["anime_name"], item["anime_id"])
                    if slug not in seen:
                        seen.add(slug)
                        out.append({
                            "title": item["anime_name"],
                            "slug": slug,
                            "image": item.get("anime_cover_image_url", ""),
                            "type": item.get("anime_type", ""),
                            "status": item.get("anime_status", ""),
                            "season": item.get("anime_release_year", ""),
                            "episodes_count": None
                        })
                # Check for more pages
                page = 2
                while bdata.get("has_next"):
                    br = requests.get(f"{DOMAIN}/browse", params={"_api": 1, "page": page, "keyword": title, "order_by": "latest_first"}, headers=HEADERS, timeout=TIMEOUT)
                    bdata = br.json()
                    if bdata.get("success"):
                        for item in bdata.get("data", []):
                            slug = _make_slug(item["anime_name"], item["anime_id"])
                            if slug not in seen:
                                seen.add(slug)
                                out.append({
                                    "title": item["anime_name"],
                                    "slug": slug,
                                    "image": item.get("anime_cover_image_url", ""),
                                    "type": item.get("anime_type", ""),
                                    "status": item.get("anime_status", ""),
                                    "season": item.get("anime_release_year", ""),
                                    "episodes_count": None
                                })
                        page += 1
                    else:
                        break
        except:
            pass

        if not out:
            return jsonify({"found": 0, "message": "لا توجد نتائج", "results": []})
        return jsonify({"found": 1, "results": out})
    except Exception as e:
        return jsonify({"found": 0, "message": str(e), "results": []})

@app.route("/api/episodes", methods=["POST"])
def episodes():
    data = request.get_json()
    slug = data.get("slug", "").strip()
    exp_name = data.get("name", "").strip()
    if not slug:
        return jsonify({"found": 0, "message": "No slug provided"})
    try:
        a = Anime(slug, name=exp_name)
        a.slug = slug
        a.found = 1
        eps = a.get_episodes()
        name = a.name or ""
        # Cache by resolved slug
        resolved_slug = a.slug
        if eps:
            _eps_cache[resolved_slug] = {"eps": eps, "name": name}
            _trim_cache(_eps_cache)
        return jsonify({"found": 1, "episodes": eps, "name": name, "slug": resolved_slug})
    except Exception as e:
        return jsonify({"found": 0, "message": str(e)[:100]})

@app.route("/api/play", methods=["POST"])
def play():
    data = request.get_json()
    slug = data.get("slug", "").strip()
    exp_name = data.get("name", "").strip()
    episode = int(data.get("episode", 1))
    if not slug:
        return jsonify({"found": 0, "message": "No slug provided"})
    cache_key = f"{slug}_{episode}"
    if cache_key in _play_cache:
        return jsonify({"found": 1, "urls": _play_cache[cache_key], "episode": episode})
    try:
        a = Anime(slug, name=exp_name)
        a.slug = slug
        a.found = 1
        a.load_episode_page()
        urls = a.get_all_video_urls(episode)
        if urls:
            _play_cache[cache_key] = urls
            return jsonify({"found": 1, "urls": urls, "episode": episode})
        return jsonify({"found": 0, "message": a.message or "Failed to get video URL"})
    except Exception as e:
        return jsonify({"found": 0, "message": str(e)[:100]})

@app.route("/api/browse", methods=["GET"])
def browse():
    page = request.args.get("page", 1, type=int)
    keyword = request.args.get("keyword", "", type=str)
    order_by = request.args.get("order_by", "latest_first", type=str)
    season = request.args.get("season", "", type=str)
    year = request.args.get("year", "", type=str)
    anime_type = request.args.get("type", "", type=str)
    status = request.args.get("status", "", type=str)
    genre_id = request.args.get("genre_id", "", type=str)

    params = {"_api": 1, "page": page, "order_by": order_by}
    if keyword: params["keyword"] = keyword
    if season: params["season"] = season
    if year: params["year"] = year
    if anime_type: params["type"] = anime_type
    if status: params["status"] = status
    if genre_id: params["genre_id"] = genre_id

    try:
        r = requests.get(f"{DOMAIN}/browse", params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get("success"):
            items = data.get("data", [])
            real = [x for x in items if x.get("just_info", "").lower() != "yes"]
            if len(real) >= 1:
                items = real
            for item in items:
                item["slug"] = _make_slug(item["anime_name"], item["anime_id"])
            data["data"] = items
            return jsonify(data)
        return jsonify({"success": False, "error": data.get("error", "Unknown error")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
