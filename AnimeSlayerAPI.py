import re, base64, json, requests, urllib.parse

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
        if not self.name:
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

    def get_video_url(self, episode_n):
        if not self.eps_data and not self.load_episode_page():
            return None

        ep_info = None
        for e in self.eps_data:
            if e["n"] == episode_n:
                ep_info = e
                break
        if not ep_info:
            return None

        frag = ep_info["watchUrl"]
        parts = self.slug.split("-")
        ep_code = parts[-1] if len(parts) > 1 else self.slug

        name = self.api_name or "Lh8SWGFRVFIl"
        san = self.api_san or "Lh8SWGFRVFIl"
        mwsem = self.api_mwsem or base64.b64encode(f"OP,{self.name}".encode()).decode()

        try:
            r = requests.get("https://patrimoines-en-mouvement.org/lib/flare/v3.php", headers=HEADERS, timeout=TIMEOUT)
            flare = r.json()
            first = flare["first"]
            sec = flare["sec"]
        except Exception as e:
            self.message = f"Flare API failed: {e}"
            return None

        try:
            r2 = requests.post(first, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                               data=f"pe={ep_code}&hash={frag}", timeout=TIMEOUT)
            auth = r2.json()
            if "a" not in auth or "d" not in auth:
                self.message = "Auth API failed"
                return None
        except Exception as e:
            self.message = f"Auth API failed: {e}"
            return None

        params = urllib.parse.urlencode({
            "keyn": auth["d"], "name": name,
            "pe": auth["c"], "bool": "no",
            "id": auth["a"], "info": auth["b"],
            "san": san, "mwsem": mwsem
        })
        try:
            r3 = requests.post(sec, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                               data=params, timeout=TIMEOUT)
            video_data = r3.json()
            if "data" not in video_data:
                self.message = "Video API failed"
                return None
        except Exception as e:
            self.message = f"Video API failed: {e}"
            return None

        def extract_video_from_php(php_url):
            try:
                r4 = requests.get(php_url, headers=HEADERS, timeout=TIMEOUT)
                mp4 = re.search(r"src:\s*'([^']+\.mp4)'", r4.text)
                if mp4:
                    url = mp4.group(1)
                    if not url.startswith("http"):
                        base = php_url.rsplit("/", 1)[0] + "/"
                        url = urllib.parse.urljoin(base, url)
                    return url
                m3u8 = re.search(r"src:\s*'([^']+\.m3u8)'", r4.text)
                if m3u8:
                    url = m3u8.group(1)
                    if not url.startswith("http"):
                        base = php_url.rsplit("/", 1)[0] + "/"
                        url = urllib.parse.urljoin(base, url)
                    return url
                any_src = re.findall(r"src:\s*'([^']+)'", r4.text)
                for s in any_src:
                    if "http" in s and not any(x in s for x in [".js", ".css", "bkvideo.online"]):
                        if s.endswith(".mp4") or s.endswith(".m3u8") or "/video/" in s or "/d/" in s or "mediafire" in s or "gamescdn" in s:
                            return s
            except Exception:
                pass
            return None

        def try_server(encrypted_url):
            php_url = decrypt(encrypted_url)
            if php_url:
                if "mega.nz/embed" in php_url:
                    self.message = "Mega.nz embed (requires extension)"
                    return php_url
                return extract_video_from_php(php_url)
            return None

        result = try_server(video_data["data"])
        if result:
            return result

        for srv_name, srv_enc in video_data.get("servers", {}).items():
            result = try_server(srv_enc)
            if result:
                return result

        self.message = "No working video source found"
        return None

    def get_all_video_urls(self, episode_n):
        if not self.eps_data and not self.load_episode_page():
            return []

        ep_info = None
        for e in self.eps_data:
            if e["n"] == episode_n:
                ep_info = e
                break
        if not ep_info:
            return []

        frag = ep_info["watchUrl"]
        parts = self.slug.split("-")
        ep_code = parts[-1] if len(parts) > 1 else self.slug
        name = self.api_name or "Lh8SWGFRVFIl"
        san = self.api_san or "Lh8SWGFRVFIl"
        mwsem = self.api_mwsem or base64.b64encode(f"OP,{self.name}".encode()).decode()

        try:
            r = requests.get("https://patrimoines-en-mouvement.org/lib/flare/v3.php", headers=HEADERS, timeout=TIMEOUT)
            flare = r.json()
            first = flare["first"]
            sec = flare["sec"]
        except:
            return []

        try:
            r2 = requests.post(first, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                               data=f"pe={ep_code}&hash={frag}", timeout=TIMEOUT)
            auth = r2.json()
            if "a" not in auth or "d" not in auth:
                return []
        except:
            return []

        params = urllib.parse.urlencode({
            "keyn": auth["d"], "name": name, "pe": auth["c"], "bool": "no",
            "id": auth["a"], "info": auth["b"], "san": san, "mwsem": mwsem
        })
        try:
            r3 = requests.post(sec, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                               data=params, timeout=TIMEOUT)
            video_data = r3.json()
        except:
            return []

        def extract_video(encrypted_url):
            php_url = decrypt(encrypted_url)
            if not php_url:
                return None
            if "mega.nz/embed" in php_url:
                return php_url
            try:
                r4 = requests.get(php_url, headers=HEADERS, timeout=TIMEOUT)
                for pat in [r"src:\s*'([^']+\.mp4)'", r"src:\s*'([^']+\.m3u8)'"]:
                    m = re.search(pat, r4.text)
                    if m:
                        url = m.group(1)
                        if not url.startswith("http"):
                            url = urllib.parse.urljoin(php_url.rsplit("/", 1)[0] + "/", url)
                        return url
                any_src = re.findall(r"src:\s*'([^']+)'", r4.text)
                for s in any_src:
                    if "http" in s and not any(x in s for x in [".js", ".css", "bkvideo.online"]):
                        if s.endswith(".mp4") or s.endswith(".m3u8") or "/video/" in s or "/d/" in s or "mediafire" in s or "gamescdn" in s:
                            return s
            except:
                pass
            return None

        servers_list = [("auto", video_data.get("data", ""))]
        servers_list.extend(video_data.get("servers", {}).items())

        results = []
        seen = set()
        for srv_name, srv_enc in servers_list:
            url = extract_video(srv_enc)
            if url and url not in seen:
                seen.add(url)
                results.append({"server": srv_name, "url": url})
        return results
