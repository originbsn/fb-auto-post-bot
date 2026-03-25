"""
Facebook Poster - โพสต์บทความและรูปภาพไปยัง Facebook Page
ผ่าน Facebook Graph API
"""

import os
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FB_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookPoster:
    def __init__(self):
        self.page_token = os.getenv("FB_PAGE_ACCESS_TOKEN")
        self.page_id = os.getenv("FB_PAGE_ID")

        if not self.page_token:
            raise ValueError("FB_PAGE_ACCESS_TOKEN is not set in .env")
        if not self.page_id:
            raise ValueError("FB_PAGE_ID is not set in .env")

    async def post(
        self,
        message: str,
        image_path: Optional[str] = None,
    ) -> dict:
        """
        โพสต์ข้อความ (และรูปภาพ) ไปยัง Facebook Page
        คืนค่า dict ที่มี post_id และ post_url
        """
        if image_path and Path(image_path).exists():
            return await self._post_with_photo(message, image_path)
        else:
            return await self._post_text_only(message)

    async def _post_with_photo(self, message: str, image_path: str) -> dict:
        """โพสต์พร้อมรูปภาพ"""
        url = f"{FB_API_BASE}/{self.page_id}/photos"

        async with aiohttp.ClientSession() as session:
            with open(image_path, "rb") as img_file:
                form = aiohttp.FormData()
                form.add_field("message", message)
                form.add_field("access_token", self.page_token)
                form.add_field(
                    "source",
                    img_file,
                    filename=Path(image_path).name,
                    content_type=self._get_content_type(image_path),
                )

                async with session.post(url, data=form) as resp:
                    data = await resp.json()

                    if resp.status != 200 or "error" in data:
                        error_msg = data.get("error", {}).get("message", str(data))
                        raise Exception(f"Facebook API Error: {error_msg}")

                    post_id = data.get("post_id") or data.get("id", "")
                    logger.info(f"Posted with photo. Post ID: {post_id}")

                    return {
                        "post_id": post_id,
                        "post_url": self._build_post_url(post_id),
                        "type": "photo",
                    }

    async def _post_text_only(self, message: str) -> dict:
        """โพสต์ข้อความอย่างเดียว"""
        url = f"{FB_API_BASE}/{self.page_id}/feed"

        payload = {
            "message": message,
            "access_token": self.page_token,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                data = await resp.json()

                if resp.status != 200 or "error" in data:
                    error_msg = data.get("error", {}).get("message", str(data))
                    raise Exception(f"Facebook API Error: {error_msg}")

                post_id = data.get("id", "")
                logger.info(f"Posted text only. Post ID: {post_id}")

                return {
                    "post_id": post_id,
                    "post_url": self._build_post_url(post_id),
                    "type": "text",
                }

    async def verify_token(self) -> bool:
        """ตรวจสอบว่า Token ใช้งานได้"""
        url = f"{FB_API_BASE}/{self.page_id}"
        params = {
            "fields": "id,name",
            "access_token": self.page_token,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"Token verification failed: {data['error']}")
                        return False
                    logger.info(f"Token valid for page: {data.get('name', 'Unknown')}")
                    return True
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False

    def _get_content_type(self, image_path: str) -> str:
        ext = Path(image_path).suffix.lower()
        types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return types.get(ext, "image/jpeg")

    def _build_post_url(self, post_id: str) -> str:
        if not post_id:
            return f"https://www.facebook.com/{self.page_id}"
        # post_id format: pageId_postId
        clean_id = post_id.replace("_", "/posts/") if "_" in post_id else post_id
        return f"https://www.facebook.com/{clean_id}"
