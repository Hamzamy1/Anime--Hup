import re, base64, json, requests, urllib.parse, time

DOMAIN = "https://animeslayer.to"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://animeslayer.to/"}
TIMEOUT = 8

DECRYPT_KEY = "AQWXZSCED@@POIUYTRR159"
TITLE_XOR_KEY = "asxwqa147"

def _clean_title(title):
    for s in ["Anime Slayer", "انمي سلاير", "مشاهدة", "أونلاين", "اونلاين"]:
        title = title.replace(s, "")
    title = title.strip().rstrip(" -–—|").strip()
    return title

def decrypt(data, key=DECRYPT_KEY):
    decoded = base64.b64decode(data)
    return "".join(chr(b ^ ord(key[i % len(key)])) for i, b in enumerate(decoded))

def decrypt_title_href(encrypted_href, key=TITLE_XOR_KEY):
    decoded = base64.b64decode(encrypted_href)
    return "".join(chr(b ^ ord(key[i % len(key)])) for i, b in enumerate(decoded))

def extract(s, start_marker, end_markers, skip=0):
    idx = s.find(start_marker, skip)
    if idx < 0:
        return None, skip
    start = idx + len(start_marker)
    best_end = None
    for em in end_markers:
            ei = s.find(em, start)
            if ei >= 0 and (best_end is None or ei < best_end):
                    best_end = ei
    if best_end is None:
            return None, skip
    return s[start:best_end], best_end + 1

class Anime:
    def __init__(self, title):
        self.title = title
        self.found = 0
        self.slug = None
        self.name = None
        self.eps_data = []
        self.api_name = None
        self.api_san = None
        self.api_mwsem = None
        self.message = ""

    def search(self):
        try:
            r = requests.get(f"{DOMAIN}/api/search.php?q={urllib.parse.quote(self.title)}", headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if not data:
                return False
            main = None
            for item in data:
                if item["title"].lower() == self.title.lower():
                    main = item
                    break
            if not main:
                main = data[0]
            self.name = main["title"]
            self.slug = main["href"].replace("/title/", "")
            self.image = main.get("image", "")
            self.found = 1
            return True
        except Exception as e:
            self.message = str(e)
            return False

    def _load_episodes_from_title_page(self):
        if not self.slug:
            return False
        try:
            r = requests.get(f"{DOMAIN}/title/{self.slug}", headers=HEADERS, timeout=TIMEOUT)
            html = r.text
        except Exception as e:
            self.message = f"Title page failed: {e}"
            return False

        raw, _ = extract(html, "const episodes = [", "];")
        if not raw:
            return False

        entries = re.findall(r'\{([^}]+)\}', raw)
        if not entries:
            return False

        eps = []
        for entry in entries:
            n_match = re.search(r'n:\s*(\d+)', entry)
            title_match = re.search(r'title:\s*"([^"]*)"', entry)
            href_match = re.search(r'href:\s*"([^"]+)"', entry)
            if not n_match or not href_match:
                continue
            ep_n = int(n_match.group(1))
            ep_title = title_match.group(1) if title_match else f"\u062d\u0644\u0642\u0629 {ep_n}"
            try:
                decrypted = decrypt_title_href(href_match.group(1))
                frag = decrypted.split("#")[-1] if "#" in decrypted else ""
            except Exception:
                frag = ""
            eps.append({"n": ep_n, "title": ep_title, "watchUrl": frag})

        if not eps:
            return False
        self.eps_data = eps
        if not self.name:
            try:
                name_match = re.search(r'"name":\s*"([^"]+)"', html)
                if name_match:
                    self.name = _clean_title(name_match.group(1))
            except Exception:
                pass
        return True

    def load_episode_page(self):
        if not self.slug:
            return False
        try:
            r = requests.get(f"{DOMAIN}/e/{self.slug}", headers=HEADERS, timeout=TIMEOUT)
            html = r.text
        except Exception as e:
            self.message = f"Failed to load episode page: {e}"
            return False

        raw, _ = extract(html, "const episodesData = [", "];")

        # Extract anime name from /e/ page
        nm = re.search(r'"name":\s*"([^"]+)"', html)
        if not nm:
            nm = re.search(r'<title>([^<]+)', html)
        if nm:
            self.name = _clean_title(nm.group(1))

        # Always extract name/san/mwsem from /e/ page (needed for video)
        idx = html.find("const name = ")
        if idx >= 0:
            end = html.find(";", idx)
            self.api_name = html[idx:end].split('"')[1] if '"' in html[idx:end] else "Lh8SWGFRVFIl"
        idx = html.find("const san = ")
        if idx >= 0:
            end = html.find(";", idx)
            self.api_san = html[idx:end].split('"')[1] if '"' in html[idx:end] else "Lh8SWGFRVFIl"
        idx = html.find("const mwsem = ")
        if idx >= 0:
            end = html.find(";", idx)
            self.api_mwsem = html[idx:end].split('"')[1] if '"' in html[idx:end] else ""

        if raw:
            ids = re.findall(r'id:\s*"(\d+)"', raw)
            titles = re.findall(r'title:\s*"([^"]+)"', raw)
            watch_urls = re.findall(r'watchUrl:\s*"([^"]+)"', raw)
            if ids:
                self.eps_data = [
                    {"n": int(ids[i]), "title": titles[i] if i < len(titles) else f"\u062d\u0644\u0642\u0629 {ids[i]}", "watchUrl": watch_urls[i] if i < len(watch_urls) else ""}
                    for i in range(len(ids))
                ]
                return True

        # Fallback: /title/ page has const episodes = [XOR-encrypted entries]
        if self._load_episodes_from_title_page():
            return True

        self.message = "No episodes found on /e/ or /title/ pages"
        return False

    def get_episodes(self):
        if not self.eps_data and not self.load_episode_page():
            return []
        return [{"n": e["n"], "title": e["title"]} for e in self.eps_data]

    def get_watch_url(self, episode_n):
        if not self.eps_data and not self.load_episode_page():
            return None
        for e in self.eps_data:
            if e["n"] == episode_n:
                return f"{DOMAIN}/e/{self.slug}#{e['watchUrl']}"
        return None

    def _get_video_data(self, episode_n):
        """Shared logic: returns (video_data, ep_code, frag) or None"""
        if not self.eps_data and not self.load_episode_page():
            return None
        ep_info = next((e for e in self.eps_data if e["n"] == episode_n), None)
        if not ep_info:
            return None
        frag = ep_info["watchUrl"]
        if not isinstance(frag, str):
            frag = str(frag) if frag else ""
        parts = self.slug.split("-")
        ep_code = parts[-1] if len(parts) > 1 else self.slug
        name = self.api_name or "Lh8SWGFRVFIl"
        san = self.api_san or "Lh8SWGFRVFIl"
        mwsem = self.api_mwsem or base64.b64encode(f"OP,{self.name}".encode()).decode()
        try:
            r = requests.get("https://patrimoines-en-mouvement.org/lib/flare/v3.php", headers=HEADERS, timeout=TIMEOUT)
            flare = r.json()
            first, sec = flare["first"], flare["sec"]
        except Exception as e:
            self.message = f"Flare API: {e}"
            return None
        try:
            r2 = requests.post(first, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                               data=f"pe={ep_code}&hash={frag}", timeout=TIMEOUT)
            auth = r2.json()
            if not all(k in auth for k in ("a", "b", "c", "d")):
                self.message = "Auth API failed"
                return None
        except Exception as e:
            self.message = f"Auth API: {e}"
            return None
        params = urllib.parse.urlencode({
            "keyn": auth["d"], "name": name, "pe": auth["c"], "bool": "no",
            "id": auth["a"], "info": auth["b"], "san": san, "mwsem": mwsem
        })
        for _ in range(6):
            try:
                r3 = requests.post(sec, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                                   data=params, timeout=TIMEOUT)
                video_data = r3.json()
                # Check if data decrypts to a valid (non-vfail) URL
                if isinstance(video_data, dict):
                    raw = video_data.get("data")
                    if raw and isinstance(raw, str):
                        p = decrypt(raw)
                        if p and "vfail" not in p and "vdeleted" not in p and "verror" not in p:
                            return video_data
                # Retry on vfail
                time.sleep(0.3)
            except Exception as e:
                self.message = f"Video API: {e}"
                return None
        return video_data if isinstance(video_data, dict) else None

    def _extract_php_url(self, php_url):
        try:
            if not isinstance(php_url, str) or not php_url:
                return None
            # Skip known-failure pages
            if "vfail" in php_url or "vdeleted" in php_url or "verror" in php_url:
                return None
            r4 = requests.get(php_url, headers=HEADERS, timeout=TIMEOUT)
            text = r4.text
            # Check for deleted/removed indicators in the page (specific only)
            deleted_keywords = ["\u062A\u0645 \u062D\u0630\u0641", "\u0645\u062D\u0630\u0648\u0641",
                                "\u062A\u0645 \u0625\u0632\u0627\u0644\u0629", "video has been deleted",
                                "video removed", "this video is no longer", "content removed"]
            for kw in deleted_keywords:
                if kw in text.lower():
                    return None
            for pat in [r"src:\s*'([^']+\.mp4)'", r"src:\s*'([^']+\.m3u8)'"]:
                m = re.search(pat, text)
                if m:
                    url = m.group(1)
                    # Skip placeholder videos
                    if "vid.mp4" in url or "placeholder" in url or "deleted" in url:
                        return None
                    if not url.startswith("http"):
                        url = urllib.parse.urljoin(php_url.rsplit("/", 1)[0] + "/", url)
                    return url
            any_src = re.findall(r"src:\s*'([^']+)'", text)
            for s in any_src:
                if isinstance(s, str) and "http" in s and not any(x in s for x in [".js", ".css"]):
                    if s.endswith((".mp4", ".m3u8")) or "/video/" in s or "/d/" in s or "mediafire" in s or "gamescdn" in s:
                        if "vid.mp4" not in s and "placeholder" not in s and "deleted" not in s:
                            return s
        except:
            pass
        return None

    def _try_decrypt_url(self, encrypted_url):
        if not isinstance(encrypted_url, str):
            return None
        php_url = decrypt(encrypted_url)
        if not php_url:
            return None
        if "mega.nz/embed" in php_url:
            return php_url  # treated as success by caller
        return self._extract_php_url(php_url)

    def _iter_servers(self, video_data):
        """Yield (name, encrypted_url) from video_data safely."""
        # Primary data
        data_val = video_data.get("data") if isinstance(video_data, dict) else None
        if data_val and isinstance(data_val, str):
            yield ("auto", data_val)
        # Servers
        srv = video_data.get("servers") if isinstance(video_data, dict) else None
        if isinstance(srv, dict):
            for k, v in srv.items():
                if isinstance(v, str):
                    yield (k, v)
        elif isinstance(srv, list):
            for i, v in enumerate(srv):
                if isinstance(v, str):
                    yield (f"server_{i+1}", v)
                elif isinstance(v, dict):
                    # list of dicts like [{"name":"s1","url":"..."}]
                    inner = v.get("url") or v.get("data") or v.get("src") or ""
                    if isinstance(inner, str):
                        yield (v.get("name", f"server_{i+1}"), inner)

    def get_video_url(self, episode_n):
        vd = self._get_video_data(episode_n)
        if not vd or not isinstance(vd, dict):
            return None
        for _, enc_url in self._iter_servers(vd):
            result = self._try_decrypt_url(enc_url)
            if result:
                return result
        self.message = "No working video source found"
        return None

    def get_all_video_urls(self, episode_n):
        vd = self._get_video_data(episode_n)
        if not vd or not isinstance(vd, dict):
            return []
        results = []
        seen = set()
        for srv_name, enc_url in self._iter_servers(vd):
            url = self._try_decrypt_url(enc_url)
            if url and url not in seen:
                seen.add(url)
                results.append({"server": srv_name, "url": url})
        return results
