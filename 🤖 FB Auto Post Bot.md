# 🤖 FB Auto Post Bot

ระบบ AI Automation ที่ช่วยให้คุณสร้างคอนเทนต์และโพสต์ลง Facebook Page ได้อย่างง่ายดายผ่าน Telegram Bot เพียงแค่ส่ง Link, ข้อความ, หรือรูปภาพ ระบบจะอ่านเนื้อหา สรุป เขียนบทความที่น่าสนใจ พร้อมจัดการรูปภาพ (ดึงจากเว็บ/ใช้รูปที่คุณส่ง/Generate ใหม่ด้วย AI) และโพสต์ลง Facebook ให้ทันที

## ✨ ฟีเจอร์หลัก

1. **รับข้อมูลหลากหลายรูปแบบ:**
   - **Link (URL):** ระบบจะเข้าไปอ่านเนื้อหาในเว็บ (Scraping) อัตโนมัติ
   - **ข้อความ (Text):** พิมพ์เนื้อหาหรือไอเดียคร่าวๆ ส่งให้บอท
   - **รูปภาพ (Image):** ส่งรูปภาพพร้อม Caption หรือส่งเป็น Reference ให้ AI

2. **AI Content Pipeline:**
   - สรุปเนื้อหาและเขียนบทความใหม่ด้วย LLM (GPT-4)
   - สร้างเนื้อหา 2 รูปแบบ: **Short Post** (โพสต์สั้นกระชับ) และ **Long Post** (บทความยาวอ่านสนุก)
   - เขียนสไตล์น่าติดตาม มี Hook, Storytelling, และ Call-to-Action

3. **Smart Image Handler:**
   - **ดึงรูปจากเว็บ:** หากส่ง Link ระบบจะพยายามดึงรูปภาพประกอบจากเว็บนั้นมาใช้
   - **ใช้รูปที่คุณส่ง:** หากคุณส่งรูปมา ระบบจะใช้ Vision AI ตรวจสอบว่าเข้ากับเนื้อหาหรือไม่ ถ้าเข้ากันจะใช้รูปนั้นเลย
   - **AI Image Generation:** หากไม่มีรูป หรือรูปที่คุณส่งไม่เข้ากับเนื้อหา ระบบจะใช้ DALL-E 3 สร้างรูปภาพใหม่ที่สวยงามและตรงกับบทความ (โดยอ้างอิง Style จากรูปที่คุณส่งมาได้)

4. **Auto Post to Facebook:**
   - โพสต์ข้อความพร้อมรูปภาพลง Facebook Page อัตโนมัติผ่าน Graph API
   - เลือกได้ว่าจะโพสต์แบบ Short, Long หรือทั้งสองแบบ

---

## 🚀 วิธีการติดตั้งและใช้งาน

### 1. สิ่งที่ต้องเตรียม (Prerequisites)

คุณจำเป็นต้องมี API Keys และ Tokens ต่อไปนี้:

1. **Telegram Bot Token:**
   - ไปที่ Telegram ค้นหา `@BotFather`
   - พิมพ์ `/newbot` ทำตามขั้นตอนเพื่อสร้างบอท
   - คัดลอก `HTTP API Token` ที่ได้มา

2. **OpenAI API Key:**
   - ไปที่ [OpenAI Platform](https://platform.openai.com/api-keys)
   - สร้าง Secret Key ใหม่

3. **Facebook Page Access Token & Page ID:**
   - ไปที่ [Facebook Developers](https://developers.facebook.com/)
   - สร้าง App เลือกประเภท Business
   - เพิ่ม Product "Facebook Login for Business"
   - ไปที่ Graph API Explorer
   - เลือก App ของคุณ และเลือก Page ที่ต้องการโพสต์
   - ขอสิทธิ์ (Permissions): `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
   - สร้าง Page Access Token (แนะนำให้ขยายอายุ Token เป็นแบบ Long-lived)
   - คัดลอก `Page ID` และ `Access Token`

### 2. การติดตั้ง (Installation)

1. Clone หรือคัดลอกโฟลเดอร์โปรเจกต์นี้
2. ติดตั้ง Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(หรือติดตั้งแพ็กเกจ: `python-telegram-bot requests beautifulsoup4 openai pillow aiohttp python-dotenv lxml`)*

3. สร้างไฟล์ `.env` จาก `.env.example`:
   ```bash
   cp .env.example .env
   ```

4. แก้ไขไฟล์ `.env` และใส่ Keys/Tokens ที่เตรียมไว้:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   FB_PAGE_ACCESS_TOKEN=your_facebook_page_access_token_here
   FB_PAGE_ID=your_facebook_page_id_here
   ```

### 3. การรันระบบ (Running the Bot)

รันคำสั่งต่อไปนี้ใน Terminal:

```bash
python bot.py
```

เมื่อเห็นข้อความ `🤖 FB Auto Post Bot started!` แสดงว่าบอทพร้อมทำงานแล้ว

---

## 📱 วิธีใช้งานผ่าน Telegram

1. เปิด Telegram และค้นหาบอทของคุณ
2. พิมพ์ `/start` เพื่อเริ่มต้น
3. ส่งข้อมูลที่คุณต้องการให้บอทประมวลผล:
   - **ส่ง Link:** วาง URL ของบทความหรือข่าว
   - **ส่งข้อความ:** พิมพ์เนื้อหาที่ต้องการ
   - **ส่งรูปภาพ:** อัปโหลดรูปภาพ (พร้อมพิมพ์ Caption ได้)
   *(คุณสามารถส่งหลายอย่างรวมกันได้ เช่น ส่ง Link แล้วตามด้วยรูปภาพ)*
4. เมื่อส่งข้อมูลครบแล้ว พิมพ์ `/done`
5. บอทจะเริ่มประมวลผล (อ่านเว็บ -> เขียนบทความ -> จัดการรูปภาพ) ใช้เวลาประมาณ 30-60 วินาที
6. บอทจะส่ง **ตัวอย่างบทความ (Preview)** มาให้คุณตรวจสอบ
7. กดปุ่มเพื่อเลือกโพสต์ลง Facebook:
   - `📤 โพสต์ Short Post`
   - `📰 โพสต์ Long Post`
   - `📤 โพสต์ทั้งคู่`
   - `🔄 สร้างใหม่` (ถ้ายากให้ AI เขียนใหม่)
   - `❌ ยกเลิก`

---

## 🛠 โครงสร้างไฟล์ (Project Structure)

- `bot.py`: ไฟล์หลัก จัดการการเชื่อมต่อและโต้ตอบกับผู้ใช้ผ่าน Telegram
- `content_pipeline.py`: จัดการการดึงข้อมูลจากเว็บ (Scraping) และใช้ LLM เขียนบทความ
- `image_handler.py`: ระบบจัดการรูปภาพอัจฉริยะ (ตรวจสอบความเกี่ยวข้อง, ดึงรูปจากเว็บ, Generate รูปด้วย AI)
- `facebook_poster.py`: จัดการการเชื่อมต่อและโพสต์ข้อมูลผ่าน Facebook Graph API
- `.env.example`: ไฟล์ตัวอย่างสำหรับตั้งค่า Environment Variables

---

## ⚠️ ข้อควรระวัง

- **Facebook Token Expiration:** หากใช้ Short-lived token จะหมดอายุใน 1-2 ชั่วโมง แนะนำให้แปลงเป็น Long-lived token (อยู่ได้ 60 วัน) หรือ Permanent token
- **OpenAI Costs:** การใช้ GPT-4 และ DALL-E 3 มีค่าใช้จ่ายตามการใช้งานจริง (API Usage)
- **Web Scraping:** บางเว็บไซต์อาจบล็อกการดึงข้อมูล (Anti-bot) ทำให้ระบบดึงเนื้อหามาไม่ได้ ในกรณีนี้แนะนำให้ copy เนื้อหามาส่งให้บอทโดยตรง
