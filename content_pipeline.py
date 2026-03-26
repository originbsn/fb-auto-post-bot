"""
Content Pipeline - อ่าน URL, สรุปเนื้อหา, เขียนบทความด้วย Claude AI
"""

import os
import re
import logging
import asyncio
import aiohttp
from typing import Optional
from bs4 import BeautifulSoup
import anthropic

logger = logging.getLogger(__name__)


class ContentPipeline:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("LLM_MODEL", "claude-sonnet-4-5")

    # ─── Web Scraping ─────────────────────────────────────────────────────────

    async def scrape_url(self, url: str) -> dict:
        """ดึงเนื้อหาจาก URL"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning(f"HTTP {resp.status} for {url}")
                        return {"text": "", "title": "", "images": []}
                    html = await resp.text(errors="replace")
        except Exception as e:
            logger.error(f"Scrape error for {url}: {e}")
            return {"text": "", "title": "", "images": []}

        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "advertisement", "ads", "iframe", "noscript"]):
            tag.decompose()

        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")

        meta_desc = ""
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            meta_desc = og_desc.get("content", "")
        if not meta_desc:
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")

        content_text = self._extract_main_content(soup)
        images = self._extract_images(soup, url)
        full_text = f"{title}\n\n{meta_desc}\n\n{content_text}".strip()

        return {
            "text": full_text,
            "title": title,
            "images": images,
            "meta_description": meta_desc,
        }

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        content_selectors = [
            "article", "main",
            '[class*="content"]', '[class*="article"]', '[class*="post"]',
            '[id*="content"]', '[id*="article"]', "section",
        ]
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                texts = []
                for el in elements[:3]:
                    text = el.get_text(separator="\n", strip=True)
                    if len(text) > 200:
                        texts.append(text)
                if texts:
                    return "\n\n".join(texts)[:8000]

        paragraphs = soup.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50)
        return text[:8000]

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list:
        images = []
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            images.append(og_image["content"])

        for img in soup.find_all("img", src=True)[:10]:
            src = img["src"]
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            elif not src.startswith("http"):
                continue

            width = img.get("width", "")
            height = img.get("height", "")
            try:
                if int(width) < 100 or int(height) < 100:
                    continue
            except (ValueError, TypeError):
                pass

            if src not in images:
                images.append(src)

        return images[:5]

    # ─── Article Generation ───────────────────────────────────────────────────

    async def generate_article(
        self,
        url: Optional[str] = None,
        text: Optional[str] = None,
    ) -> dict:
        scraped_data = {"text": "", "title": "", "images": [], "meta_description": ""}

        if url:
            logger.info(f"Scraping URL: {url}")
            scraped_data = await self.scrape_url(url)

        combined_text = ""
        if scraped_data["text"]:
            combined_text += scraped_data["text"]
        if text:
            combined_text += "\n\n" + text

        combined_text = combined_text.strip()

        if not combined_text:
            raise ValueError("ไม่มีเนื้อหาให้สร้างบทความ กรุณาส่ง link หรือข้อความ")

        logger.info("Generating article with Claude...")
        article = await self._generate_with_claude(combined_text, url)
        article["images"] = scraped_data.get("images", [])

        return article

    async def _generate_with_claude(self, content: str, source_url: Optional[str] = None) -> dict:
        """ใช้ Claude สร้างบทความ"""
        source_note = f"\n\nแหล่งที่มา: {source_url}" if source_url else ""

        system_prompt = """คุณคือนักเขียนคอนเทนต์ระดับท็อปของไทย ที่เขียนบทความ Facebook แล้วคนอยากอ่านจนจบและกดแชร์

หลักการเขียนที่ต้องทำตามเสมอ:

1. ห้ามใช้ Markdown เด็ดขาด
   - ห้ามใช้ ** สำหรับตัวหนา
   - ห้ามใช้ ## สำหรับหัวข้อ  
   - ห้ามใช้ -- หรือ --- สำหรับเส้น
   - ใช้แค่ข้อความธรรมดา + emoji เท่านั้น

2. สูตรเขียน Hook ที่ดึงคนอ่าน
   - เปิดด้วยประโยคที่ทำให้คนหยุดเลื่อน เช่น คำถามที่โดนใจ, ข้อเท็จจริงที่ตกใจ, หรือเรื่องที่คนไม่รู้
   - ใช้ Before/After ("ก่อนหน้านี้... แต่ตอนนี้..."), Curiosity Gap ("ทำไม... ถึง..."), หรือ Contrast ("คนส่วนใหญ่คิดว่า... แต่ความจริงคือ...")

3. โครงสร้างที่ทำให้คนอ่านจนจบ
   - Hook แรง 1-2 บรรทัด
   - เนื้อหาที่มีคุณค่า ให้ความรู้หรือ insight จริงๆ
   - แบ่งย่อหน้าสั้นๆ อ่านง่ายบนมือถือ
   - ปิดด้วยคำถามหรือ CTA ที่กระตุ้นให้คอมเมนต์หรือแชร์

4. สไตล์ภาษา
   - ภาษาไทยเป็นธรรมชาติ เหมือนเพื่อนคุยกัน ไม่ทางการ
   - ใช้ emoji ที่ช่วยแบ่งเนื้อหา ไม่ใช่แค่ประดับ (ใช้ 3-6 ตัวต่อโพสต์)
   - ย่อหน้าละ 2-3 บรรทัดสูงสุด
   - ใช้การขึ้นบรรทัดเพื่อสร้างจังหวะ"""

        user_prompt = f"""จากเนื้อหาต่อไปนี้ สร้างคอนเทนต์ Facebook ที่คนอยากอ่านและแชร์

ตอบในรูปแบบนี้เท่านั้น (ห้ามเพิ่มอะไรนอกจากนี้):

TITLE: [หัวข้อที่ดึงดูด คนเห็นแล้วต้องคลิก]
---SHORT_POST---
[โพสต์สั้น 150-250 คำ ใช้ภาษาธรรมดา ไม่มี Markdown ไม่มี ** หรือ ## มีแค่ข้อความ + emoji]
---LONG_POST---
[บทความยาว 400-600 คำ ใช้ภาษาธรรมดา ไม่มี Markdown ไม่มี ** หรือ ## มีแค่ข้อความ + emoji แบ่งย่อหน้าสั้นๆ]
---IMAGE_PROMPT---
[Image prompt ภาษาอังกฤษ สำหรับ AI generate รูป ให้เหมาะกับ Facebook landscape 16:9]

เนื้อหา:
{content[:6000]}{source_note}"""

        def call_claude():
            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        raw = await asyncio.to_thread(call_claude)
        return self._parse_llm_response(raw)

    def _parse_llm_response(self, raw: str) -> dict:
        result = {
            "title": "",
            "short_post": "",
            "long_post": "",
            "image_prompt": "",
        }

        title_match = re.search(r"TITLE:\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
        if title_match:
            result["title"] = title_match.group(1).strip()

        short_match = re.search(
            r"---SHORT_POST---\s*(.*?)(?=---LONG_POST---|---IMAGE_PROMPT---|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        if short_match:
            result["short_post"] = short_match.group(1).strip()

        long_match = re.search(
            r"---LONG_POST---\s*(.*?)(?=---IMAGE_PROMPT---|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        if long_match:
            result["long_post"] = long_match.group(1).strip()

        img_match = re.search(
            r"---IMAGE_PROMPT---\s*(.*?)$",
            raw, re.DOTALL | re.IGNORECASE
        )
        if img_match:
            result["image_prompt"] = img_match.group(1).strip()

        if not result["short_post"] and not result["long_post"]:
            result["long_post"] = raw
            result["short_post"] = raw[:500]

        if not result["title"]:
            result["title"] = "บทความใหม่"

        if not result["image_prompt"]:
            result["image_prompt"] = (
                "Professional blog cover image, modern design, "
                "eye-catching colors, suitable for Facebook post"
            )

        return result
