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
        self.model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

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

        system_prompt = """คุณคือนักเขียนบทความมืออาชีพที่เชี่ยวชาญการเขียนเนื้อหาสำหรับ Facebook 
โดยเน้นให้ผู้อ่านอ่านสนุก ติดตาม และอยากแชร์ต่อ

สไตล์การเขียน:
- ใช้ภาษาไทยที่เป็นธรรมชาติ อ่านง่าย ไม่เป็นทางการเกินไป
- เปิดด้วยประโยคที่ดึงดูดความสนใจ (Hook)
- ใช้ storytelling และตัวอย่างที่เข้าใจง่าย
- แบ่งเนื้อหาเป็นส่วนๆ อ่านง่าย
- ปิดด้วย call-to-action หรือคำถามกระตุ้นความคิด
- ใช้ emoji อย่างเหมาะสม (ไม่มากเกินไป)"""

        user_prompt = f"""จากเนื้อหาต่อไปนี้ กรุณาสร้าง:

1. **TITLE** - หัวข้อบทความที่น่าสนใจ ดึงดูดคนคลิก (1 บรรทัด)

2. **SHORT_POST** - โพสต์สั้นสำหรับ Facebook (150-300 คำ)
   - เปิดด้วย hook ที่แรง
   - สรุปประเด็นสำคัญ 2-3 ข้อ
   - ปิดด้วย call-to-action
   - ใช้ emoji เหมาะสม

3. **LONG_POST** - บทความยาวสำหรับ Facebook (500-800 คำ)
   - เปิดด้วย hook และเรื่องราวที่น่าสนใจ
   - เนื้อหาครบถ้วน ลึกซึ้ง
   - แบ่งเป็น section ชัดเจน
   - ใช้ตัวอย่าง/เปรียบเทียบที่เข้าใจง่าย
   - ปิดด้วย insight สำคัญและ call-to-action

4. **IMAGE_PROMPT** - คำอธิบายรูปภาพสำหรับ AI image generation (ภาษาอังกฤษ)
   - อธิบายรูปที่เหมาะกับบทความ
   - สไตล์: professional, eye-catching, suitable for Facebook
   - ระบุ style เช่น photorealistic, illustration, etc.

ตอบในรูปแบบ:
TITLE: [หัวข้อ]
---SHORT_POST---
[เนื้อหา short post]
---LONG_POST---
[เนื้อหา long post]
---IMAGE_PROMPT---
[image prompt ภาษาอังกฤษ]

เนื้อหาที่ต้องการ:
{content[:6000]}{source_note}"""

        # Claude API เป็น sync ใช้ asyncio.to_thread
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
