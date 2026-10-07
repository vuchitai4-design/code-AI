import re
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import feedparser
import requests

# ==========================================
# 1. CÁC HÀM TIỀN XỬ LÝ & CHUẨN HÓA VĂN BẢN
# ==========================================

NUMBER_MAP = {
    "10": "mười",
    "1": "một",
    "2": "hai",
    "3": "ba",
    "4": "bốn",
    "5": "năm",
    "6": "sáu",
    "7": "bảy",
    "8": "tám",
    "9": "chín",
}


def clean_query(query: str) -> str:
  """Làm sạch câu lệnh từ giọng nói người dùng."""
  q = query.lower().strip()
  for num, text in NUMBER_MAP.items():
    q = re.sub(rf"\b{num}\b", text, q)

  stop_words = [
      "đọc",
      "cho em biết",
      "cho tôi biết",
      "cho hỏi",
      "sếp muốn biết",
      "tin tức về",
      "thông tin về",
      "là ai",
      "thế nào",
      "như thế nào",
      "chi tiết",
      "tìm hiểu",
  ]
  for word in stop_words:
    q = q.replace(word, "")

  return re.sub(r"[^\w\s]", " ", q).strip() if q else query


def fix_vietnamese_spacing(text: str) -> str:
  """Tự động sửa lỗi dính chữ, dính số, dính dấu câu giúp TTS đọc chuẩn."""
  if not text:
    return ""
  text = re.sub(r"([,.:;?!])([^\s\d])", r"\1 \2", text)
  text = re.sub(
      r"([a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ])([A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])",
      r"\1 \2",
      text,
  )
  text = re.sub(
      r"([a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ])(\d+)",
      r"\1 \2",
      text,
  )
  text = re.sub(
      r"(\d+)([a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ])",
      r"\1 \2",
      text,
  )
  return re.sub(r"\s+", " ", text).strip()


# ==========================================
# 2. MODULE WIKIPEDIA (Khái niệm/Nhân vật/Điều luật)
# ==========================================


def get_wiki_summary_api(title: str) -> str:
  """Lấy tóm tắt khái niệm/nhân vật từ Wikipedia API."""
  try:
    url = f"https://vi.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles={urllib.parse.quote(title)}&format=json"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=5).json()
    pages = res.get("query", {}).get("pages", {})
    for page_id, page_info in pages.items():
      if page_id != "-1" and "extract" in page_info:
        extract = page_info["extract"].strip()
        if extract:
          return fix_vietnamese_spacing(extract[:1200])
  except Exception:
    pass
  return ""


def get_wikipedia_info(user_query: str) -> str:
  """Tra cứu Wikipedia đa tầng (Cào DOM cho văn bản dài & API cho tóm tắt)."""
  search_term = clean_query(user_query)
  headers = {"User-Agent": "Mozilla/5.0"}

  try:
    search_url = f"https://vi.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(search_term)}&utf8=&format=json"
    s_res = requests.get(search_url, headers=headers, timeout=5).json()
    results = s_res.get("query", {}).get("search", [])

    if not results:
      return ""

    exact_title = results[0]["title"]
    query_lower = user_query.lower()
    content_intent = any(
        kw in query_lower
        for kw in [
            "lời thề",
            "nội dung",
            "đọc",
            "điều",
            "danh sách",
            "mười",
            "10",
            "5",
            "năm",
        ]
    )

    if content_intent:
      wiki_url = (
          f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(exact_title)}"
      )
      soup = BeautifulSoup(
          requests.get(wiki_url, headers=headers, timeout=5).text, "html.parser"
      )
      content_div = soup.find("div", {"class": "mw-parser-output"})

      if content_div:
        for tag in content_div.select(
            "sup, table.infobox, table.navbox, table.sidebar, style, script,"
            " .reflist, .mw-editsection"
        ):
          tag.decompose()

        headings = content_div.find_all(["h2", "h3", "h4"])
        target_heading = None

        for kw in ["hiện tại", "nội dung"]:
          for h in headings:
            if kw in h.get_text().lower():
              target_heading = h
              break
          if target_heading:
            break

        if target_heading:
          curr = target_heading
          if (
              curr.parent
              and curr.parent != content_div
              and "mw-heading" in curr.parent.get("class", [])
          ):
            curr = curr.parent

          extracted_texts = []
          for sib in curr.find_next_siblings():
            if (
                sib.name in ["h2", "h3", "h4"]
                or "mw-heading" in sib.get("class", [])
                or sib.find(["h2", "h3", "h4"])
            ):
              break
            text = sib.get_text(separator=" ", strip=True)
            if text:
              extracted_texts.append(fix_vietnamese_spacing(text))

          final_text = "\n\n".join(extracted_texts).strip()
          if final_text:
            return f"[BÁCH KHOA TOÀN THƯ]: {final_text[:2500]}"

    summary = get_wiki_summary_api(exact_title)
    if summary:
      return f"[BÁCH KHOA TOÀN THƯ]: {summary}"

  except Exception as e:
    print(f"[LỖI WIKI]: {e}")
  return ""


# ==========================================
# 3. MODULE RSS (Tin tức / Pháp luật / Chuyên ngành)
# ==========================================

RSS_SOURCES = {
    "tin_nong": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "the_gioi": "https://vnexpress.net/rss/the-gioi.rss",
    "phap_luat": "https://luatvietnam.vn/rss/tin-van-ban-moi.rss",
    "cong_nghe": "https://vnexpress.net/rss/so-hoa.rss",
    "khoa_hoc": "https://vnexpress.net/rss/khoa-hoc.rss",
    "kinh_te": "https://vnexpress.net/rss/kinh-doanh.rss",
}


def get_rss_news(category_or_query: str = "") -> str:
  """Lấy tin tức theo chuyên ngành hoặc từ khóa từ Google News/RSS."""
  q = category_or_query.lower().strip()

  if "pháp luật" in q or "luật" in q:
    rss_url = RSS_SOURCES["phap_luat"]
  elif "công nghệ" in q or "tech" in q:
    rss_url = RSS_SOURCES["cong_nghe"]
  elif any(
      kw in q
      for kw in ["khoa học", "vũ trụ", "vật lý", "đại dương", "thiên văn"]
  ):
    rss_url = RSS_SOURCES["khoa_hoc"]
  elif "thế giới" in q:
    rss_url = RSS_SOURCES["the_gioi"]
  elif any(kw in q for kw in ["kinh tế", "chứng khoán", "giá xăng"]):
    rss_url = RSS_SOURCES["kinh_te"]
  elif q and q not in ["tin mới", "tin nóng", "tin tức", "nổi bật"]:
    encoded_q = urllib.parse.quote(q)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=vi&gl=VN&ceid=VN:vi"
  else:
    rss_url = RSS_SOURCES["tin_nong"]

  try:
    # Gửi Header Giả lập Trình duyệt để Google News không chặn
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(rss_url, headers=headers, timeout=5)
    feed = feedparser.parse(resp.content)

    if not feed.entries:
      return ""

    news_items = []
    for entry in feed.entries[:4]:
      title = entry.title
      if " - " in title:
        title = title.rsplit(" - ", 1)[0]
      news_items.append(f"- {fix_vietnamese_spacing(title)}")

    if news_items:
      return f"[TIN TỨC CẬP NHẬT]:\n" + "\n".join(news_items)
  except Exception as e:
    print(f"[LỖI RSS]: {e}")
  return ""


# ==========================================
# 4. MODULE TIỆN ÍCH (Thời tiết / Giá vàng / Tỷ giá)
# ==========================================

# Bảng ánh xạ từ tiếng Việt có dấu sang tên ASCII chuẩn cho wttr.in
CITY_MAP = {
    "hồ chí minh": "Ho_Chi_Minh",
    "sài gòn": "Ho_Chi_Minh",
    "tp hcm": "Ho_Chi_Minh",
    "hà nội": "Hanoi",
    "đà nẵng": "Danang",
    "cần thơ": "Can_Tho",
    "hải phòng": "Haiphong",
    "nha trang": "Nha_Trang",
    "đà lạt": "Dalat",
    "vũng tàu": "Vung_Tau",
    "huế": "Hue",
}


def get_weather(location_vn: str = "Hà Nội") -> str:
  """Lấy thời tiết an toàn qua wttr.in bằng tên ASCII."""
  try:
    loc_key = location_vn.lower().strip()
    # Chuyển tên có dấu thành ASCII (vd: Hồ Chí Minh -> Ho_Chi_Minh)
    loc_ascii = CITY_MAP.get(loc_key, "Ho_Chi_Minh")

    url = f"https://wttr.in/{loc_ascii}"
    params = {"format": "%C, %t, độ ẩm %h, gió %w", "lang": "vi"}
    headers = {"User-Agent": "curl/7.68.0"}

    res = requests.get(url, params=params, headers=headers, timeout=5)
    if res.status_code == 200 and res.text and "Unknown" not in res.text:
      return f"[THỜI TIẾT {location_vn.upper()}]: {res.text.strip()}"
  except Exception as e:
    print(f"[LỖI WEATHER]: {e}")
  return ""


def get_vcb_exchange_rates() -> str:
  """Lấy tỷ giá USD, EUR, JPY từ Ngân hàng Vietcombank."""
  try:
    url = "https://portal.vietcombank.com.vn/Usercontrols/TVWeb.TyGia/pXML.aspx"
    res = requests.get(url, timeout=5)
    root = ET.fromstring(res.content)

    rates = []
    for child in root.findall("Exrate"):
      code = child.attrib.get("CurrencyCode")
      if code in ["USD", "EUR", "JPY"]:
        buy = child.attrib.get("Buy")
        sell = child.attrib.get("Sell")
        rates.append(f"{code}: Mua {buy} - Bán {sell}")

    if rates:
      return "[TỶ GIÁ VIETCOMBANK]: " + " | ".join(rates)
  except Exception:
    pass
  return ""

# ==========================================
# 5. ĐỘNG CƠ ĐIỀU HƯỚNG TỔNG HỢP CHO JARVIS
# ==========================================


def jarvis_knowledge_engine(user_query: str) -> str:
  """Chỉ tìm kiếm khi người dùng nói ĐÚNG TỪ KHÓA YÊU CẦU."""
  q_lower = user_query.lower()

  # 1. Thời tiết (Chỉ chạy khi có từ khóa thời tiết/nhiệt độ)
  if "thời tiết" in q_lower or "nhiệt độ" in q_lower:
    target_city = "Hồ Chí Minh"
    for city_name in CITY_MAP.keys():
      if city_name in q_lower:
        target_city = city_name
        break
    result = get_weather(target_city)
    if result:
      return result
    return f"[THỜI TIẾT]: Hiện không tra cứu được thời tiết tại {target_city}."

  # 2. Tỷ giá / Giá vàng / Xăng dầu
  if any(kw in q_lower for kw in ["tỷ giá", "đô la", "usd", "ngoại tệ"]):
    result = get_vcb_exchange_rates()
    if result:
      return result

  if any(kw in q_lower for kw in ["giá vàng", "giá xăng", "xăng dầu"]):
    result = get_rss_news(user_query)
    if result:
      return result

  # 3. Tin tức (CHỈ chạy khi sếp nói rõ "tin tức", "thời sự", "tin mới")
  if any(
      kw in q_lower
      for kw in ["tin tức", "thời sự", "điểm tin", "tin mới", "tin nóng"]
  ):
    rss_res = get_rss_news(user_query)
    if rss_res:
      return rss_res

  # 4. Wikipedia (CHỈ chạy khi sếp nói rõ "thông tin về", "tìm hiểu về", "wiki")
  wiki_keywords = [
      "thông tin về",
      "cho tôi biết thông tin",
      "cho em biết thông tin",
      "tìm hiểu về",
      "khái niệm",
      "wiki",
  ]
  if any(kw in q_lower for kw in wiki_keywords):
    wiki_res = get_wikipedia_info(user_query)
    if wiki_res:
      return wiki_res

  return "Em chưa tìm thấy thông tin chính xác từ các nguồn dữ liệu sếp ơi."