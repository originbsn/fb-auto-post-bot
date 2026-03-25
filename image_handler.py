"""
Image Handler - จัดการรูปภาพอัจฉริยะโดยใช้ fal.ai สำหรับ generate รูป
และ Claude Vision สำหรับตรวจสอบความเกี่ยวข้อง
"""

import os
import logging
import asyncio
import aiohttp
import base64
import time
from pathlib import Path
from typing import Optional
import anthropic
from PIL import Image

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("generated_images")
OUTPUT_DIR.mkdir(exist_ok=True)

FAL_API_KEY = os.getenv("FAL_KEY", "")
FAL_MODEL = os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell")


class ImageHandler:
    def __init__(self):
        self.claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def get_image(
        self,
        url: Optional[str],
        article_content: str,
        article_title: str,
        user_image_path: Optional[str],
        scraped_images: list,
    ) -> Optional[str]:
        # Step 1: ตรวจสอบรูปจากผู้ใช้
        if user_image_path and Path(user_image_path).exists():
            logger.info("User provided image - checking relevance...")
            is_relevant = await self._check_image_relevance(
                user_image_path, article_title, article_content
            )
            if is_relevant:
                logger.info("User image is relevant - using it directly")
                return user_image_path
            else:
                logger.info("User image not relevant - generating new image")

        # Step 2: ลองดึงรูปจาก URL ที่ scrape มา
        if scraped_images:
            logger.info(f"Trying scraped images: {len(scraped_images)} found")
            for img_url in scraped_images[:3]:
                downloaded = await self._download_image(img_url)
                if downloaded:
                    logger.info(f"Using scraped image: {img_url}")
                    return downloaded

        # Step 3: Generate รูปใหม่ด้วย fal.ai
        logger.info("Generating new image with fal.ai...")
        return await self._generate_image_fal(article_title, article_content)

    # ─── Image Relevance Check (Claude Vision) ─────────────────────────────────

    async def _check_image_relevance(
        self, image_path: str, title: str, content: str
    ) -> bool:
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            img = Image.open(image_path)
            fmt = img.format.lower() if img.format else "jpeg"
            media_type = f"image/{fmt}" if fmt != "jpg" else "image/jpeg"

            def call_claude():
                response = self.claude.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=10,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_data,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"ดูรูปภาพนี้และบอกว่ามันเข้ากับบทความนี้หรือไม่\n\n"
                                        f"หัวข้อบทความ: {title}\n"
                                        f"เนื้อหาย่อ: {content[:500]}\n\n"
                                        f"ตอบแค่ YES หรือ NO เท่านั้น"
                                    ),
                                },
                            ],
                        }
                    ],
                )
                return response.content[0].text

            answer = await asyncio.to_thread(call_claude)
            return "YES" in answer.strip().upper()

        except Exception as e:
            logger.error(f"Image relevance check error: {e}")
            return False

    # ─── Generate Image with fal.ai ────────────────────────────────────────────

    async def _generate_image_fal(
        self, article_title: str, article_content: str
    ) -> Optional[str]:
        """Generate รูปภาพด้วย fal.ai"""
        try:
            # สร้าง prompt ด้วย Claude ก่อน
            prompt = await self._create_image_prompt(article_title, article_content)
            logger.info(f"Image prompt: {prompt[:100]}...")

            headers = {
                "Authorization": f"Key {FAL_API_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "prompt": prompt,
                "image_size": "landscape_16_9",
                "num_inference_steps": 4,
                "num_images": 1,
                "enable_safety_checker": True,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://fal.run/{FAL_MODEL}",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"fal.ai error {resp.status}: {error_text}")
                        return None

                    data = await resp.json()
                    images = data.get("images", [])
                    if not images:
                        logger.error("No images returned from fal.ai")
                        return None

                    image_url = images[0].get("url")
                    if not image_url:
                        return None

                    # ดาวน์โหลดรูป
                    filename = str(OUTPUT_DIR / f"generated_{int(time.time())}.png")
                    downloaded = await self._download_image(image_url, filename)
                    return downloaded

        except Exception as e:
            logger.error(f"fal.ai generation error: {e}")
            return None

    async def _create_image_prompt(
        self,
        article_title: str,
        article_content: str,
        style_hint: str = "",
    ) -> str:
        """สร้าง image prompt ที่ดีด้วย Claude"""
        style_instruction = f"\nStyle reference: {style_hint}" if style_hint else ""

        def call_claude():
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Create an image generation prompt for a Facebook post image.\n\n"
                            f"Article title: {article_title}\n"
                            f"Article summary: {article_content[:400]}\n"
                            f"{style_instruction}\n\n"
                            f"Requirements:\n"
                            f"- Eye-catching and professional\n"
                            f"- Suitable for Facebook social media\n"
                            f"- No text or words in the image\n"
                            f"- Landscape orientation (16:9)\n"
                            f"- High quality, photorealistic or modern illustration\n\n"
                            f"Return ONLY the prompt, no explanation."
                        ),
                    }
                ],
            )
            return response.content[0].text.strip()

        return await asyncio.to_thread(call_claude)

    # ─── Download Image ────────────────────────────────────────────────────────

    async def _download_image(
        self, url: str, save_path: Optional[str] = None
    ) -> Optional[str]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; ImageBot/1.0)"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        return None

                    content_type = resp.headers.get("Content-Type", "")
                    if "image" not in content_type and not url.endswith(
                        (".jpg", ".jpeg", ".png", ".webp", ".gif")
                    ):
                        return None

                    data = await resp.read()
                    if len(data) < 5000:
                        return None

                    if not save_path:
                        ext = "jpg"
                        if "png" in content_type or url.endswith(".png"):
                            ext = "png"
                        elif "webp" in content_type or url.endswith(".webp"):
                            ext = "webp"
                        save_path = str(OUTPUT_DIR / f"scraped_{int(time.time())}.{ext}")

                    with open(save_path, "wb") as f:
                        f.write(data)

                    try:
                        img = Image.open(save_path)
                        img.verify()
                        img = Image.open(save_path)
                        if img.width < 200 or img.height < 200:
                            os.remove(save_path)
                            return None
                    except Exception:
                        if os.path.exists(save_path):
                            os.remove(save_path)
                        return None

                    logger.info(f"Downloaded image: {save_path}")
                    return save_path

        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            return None
