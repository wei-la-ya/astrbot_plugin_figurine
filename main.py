import os
import re
import json
import time
import base64
from typing import Optional, Tuple, Dict

import httpx

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

API_URL = "https://openrouter.ai/api/v1/chat/completions"
QLOGO_AVATAR = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"
FIGURINE_DIR = os.path.join(os.getcwd(), "data", "figurine")
KEYS_FILE = os.path.join(FIGURINE_DIR, "openrouter_keys.json")

DEFAULT_PROMPT = "Please accurately transform the main subject in this photo into a realistic, masterpiece-like 1/7 scale PVC statue. Behind this statue, a packaging box should be placed: the box has a large clear front window on its front side, and is printed with subject artwork, product name, brand logo, barcode, as well as a small specifications or authenticity verification panel. A small price tag sticker must also be attached to one corner of the box. Meanwhile, a computer monitor is placed at the back, and the monitor screen needs to display the ZBrush modeling process of this statue. In front of the packaging box, this statue should be placed on a round plastic base. The statue must have 3D dimensionality and a sense of realism, and the texture of the PVC material needs to be clearly represented. If the background can be set as an indoor scene, the effect will be even better. Below are detailed guidelines to note: When repairing any missing parts, there must be no poorly executed elements. When repairing human figures (if applicable), the body parts must be natural, movements must be coordinated, and the proportions of all parts must be reasonable. If the original photo is not a full-body shot, try to supplement the statue to make it a full-body version. The human figure’s expression and movements must be exactly consistent with those in the photo. The figure’s head should not appear too large, its legs should not appear too short, and the figure should not look stunted—this guideline may be ignored if the statue is a chibi-style design. For animal statues, the realism and level of detail of the fur should be reduced to make it more like a statue rather than the real original creature. No outer outline lines should be present, and the statue must not be flat. Please pay attention to the perspective relationship of near objects appearing larger and far objects smaller."
DEFAULT_PROMPT2 = "Use the nano-banana model to create a 1/7 scale commercialized figure of the character in the illustration, in a realistic style and environment. Place the figure on a computer desk, using a circular transparent acrylic base without any text. On the computer screen, display the ZBrush modeling process of the figure. Next to the computer screen, place a BANDAI-style toy packaging box printed with the original artwork."
DEFAULT_PROMPT3 = "Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging. Crucial First Step: Analyze the image to identify the subject's key attributes (e.g., human male, human female, animal, specific creature) and defining features (hair style, clothing, expression). The generated figurine must strictly adhere to these identified attributes. Top Priority - Character Likeness: The figurine's face MUST maintain a strong likeness to the original character. Your task is to translate the 2D facial features into a 3D sculpt, preserving the identity, expression, and core characteristics. If the source is blurry, interpret the features to create a sharp, well-defined version that is clearly recognizable as the same character. Scene Details: Figurine: The figure version of the photo I gave you, with a clear representation of PVC material, placed on a round plastic base. Packaging: Behind the figure, there should be a partially transparent plastic and paper box, with the character from the photo printed on it. Environment: The entire scene should be in an indoor setting with good lighting."
DEFAULT_PROMPT4 = "Realistic PVC figure based on the game screenshot character, exact pose replication highly detailed textures PVC material with subtle sheen and smooth paint finish, placed on an indoor wooden computer desk (with subtle desk items like a figure box/mouse), illuminated by soft indoor light (mix of desk lamp and natural window light) for realistic shadows and highlights, macro photography style, high resolution, sharp focus on the figure, shallow depth of field (desk background slightly blurred but visible), no stylization, true-to-reference color and design, 1:1 scale."
DEFAULT_PROMPT_Q = "((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)), ((plump cheeks)), ((childlike big eyes)), ((simplified facial features)), ((smooth matte skin, no pores)), ((soft pastel color palette)), ((gentle ambient lighting, natural shadows)), ((same facial expression, same pose, same background scene)), ((seamless integration with original environment, correct perspective and scale)), ((no outline or thin soft outline)), ((high resolution, sharp focus, 8k, ultra-detailed)), avoid: realistic proportions, long limbs, sharp edges, harsh lighting, wrinkles, blemishes, thick black outlines, low resolution, blurry, extra limbs, distorted face"

PROMPT_MAP: Dict[str, str] = {
    "手办化1": DEFAULT_PROMPT,
    "手办化2": DEFAULT_PROMPT2,
    "手办化3": DEFAULT_PROMPT3,
    "手办化4": DEFAULT_PROMPT4,
    "Q版化": DEFAULT_PROMPT_Q,
}

COMMAND_PATTERNS = [
    re.compile(r"^手办化4(?:@(\d+)|\s+(\d+))?\s*$"),
    re.compile(r"^手办化3(?:@(\d+)|\s+(\d+))?\s*$"),
    re.compile(r"^手办化2(?:@(\d+)|\s+(\d+))?\s*$"),
    re.compile(r"^手办化(?:@(\d+)|\s+(\d+))?\s*$"),
    re.compile(r"^Q版化(?:@(\d+)|\s+(\d+))?\s*$"),
]

def ensure_data_dir() -> None:
    if not os.path.exists(FIGURINE_DIR):
        os.makedirs(FIGURINE_DIR, exist_ok=True)

def load_keys_config() -> dict:
    ensure_data_dir()
    if not os.path.exists(KEYS_FILE):
        cfg = {"keys": [], "current": 0}
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return cfg
    with open(KEYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_keys_config(cfg: dict) -> None:
    ensure_data_dir()
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_next_api_key() -> str:
    cfg = load_keys_config()
    keys = cfg.get("keys", [])
    if not keys:
        raise RuntimeError("没有可用的API密钥，请先配置 data/figurine/openrouter_keys.json -> keys[]")
    idx = cfg.get("current", 0) % len(keys)
    cfg["current"] = (idx + 1) % len(keys)
    save_keys_config(cfg)
    return keys[idx]

def build_avatar_url(qq: str) -> str:
    return QLOGO_AVATAR.format(qq=qq)

def parse_command(message_text: str) -> Tuple[str, Optional[str]]:
    message_text = (message_text or "").strip()
    for pattern in COMMAND_PATTERNS:
        m = pattern.match(message_text)
        if m:
            cmd_prefix = message_text.split("@")[0].strip()
            if cmd_prefix.startswith("手办化4"):
                preset = "手办化4"
            elif cmd_prefix.startswith("手办化3"):
                preset = "手办化3"
            elif cmd_prefix.startswith("手办化2"):
                preset = "手办化2"
            elif cmd_prefix.startswith("Q版化"):
                preset = "Q版化"
            else:
                preset = "手办化1"
            qq = m.group(1) or m.group(2)
            return preset, qq
    return "", None

def select_prompt(preset_label: str) -> Tuple[str, str]:
    if preset_label in PROMPT_MAP:
        return PROMPT_MAP[preset_label], preset_label
    if preset_label == "手办化":
        return PROMPT_MAP["手办化1"], "手办化1"
    return PROMPT_MAP["手办化1"], "手办化1"

def build_payload(model: str, prompt: str, image_b64: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }

async def fetch_image_as_b64(url: str, proxies: Optional[Dict[str, str]], timeout: float) -> str:
    if url.startswith("base64://"):
        return url.split("://", 1)[1]
    if url.startswith("file://"):
        local_path = url[len("file://"):]
        with open(local_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(url):
        with open(url, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.get(url)
        res.raise_for_status()
        return base64.b64encode(res.content).decode("utf-8")

def extract_image_url_from_response(data: dict) -> Optional[str]:
    img = data.get("choices", [{}])[0].get("message", {}).get("images", [{}])[0]
    url = img.get("image_url", {}).get("url") or img.get("url")
    if url:
        return url
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    m = re.search(r'https?://[^\s<>"\)\]]+', content)
    if m:
        return m.group(0).rstrip(")]}>'\"")
    return None

def _find_first_at_qq(event: AstrMessageEvent) -> Optional[str]:
    msg = getattr(event, "message_obj", None)
    if not msg:
        return None
    chain = getattr(msg, "message", []) or []
    for comp in chain:
        qq = getattr(comp, "qq", None)
        if qq:
            return str(qq)
    return None

def _find_first_image_url_in_reply(self, event: AstrMessageEvent) -> Optional[str]:
        # 获取引用消息中的图片
        reply_msg = getattr(event, "reply", None)
        if not reply_msg:
            return None
        chain = getattr(reply_msg, "message", []) or []
        for comp in chain:
            url_field = getattr(comp, "url", None)
            file_field = getattr(comp, "file", None)
            candidate = url_field or file_field
            if isinstance(candidate, str) and candidate:
                return candidate
        return None

def _find_first_image_url(event: AstrMessageEvent) -> Optional[str]:
    msg = getattr(event, "message_obj", None)
    if not msg:
        return None
    chain = getattr(msg, "message", []) or []
    for comp in chain:
        url_field = getattr(comp, "url", None)
        file_field = getattr(comp, "file", None)
        candidate = url_field or file_field
        if isinstance(candidate, str) and candidate:
            return candidate
    return None

def _find_first_image_in_reply_chain(event: AstrMessageEvent) -> Optional[str]:
    # 遍历所有消息段，查找 Reply 类型并从 chain 中提取 Image
    if hasattr(event, "get_messages"):
        for _message in event.get_messages():
            # 兼容 Reply 类型消息段
            if hasattr(_message, "chain") and _message.chain:
                for comp in _message.chain:
                    # 兼容 Image 类型消息段
                    url = getattr(comp, "url", None)
                    file = getattr(comp, "file", None)
                    candidate = url or file
                    if isinstance(candidate, str) and candidate:
                        return candidate
    return None

@register("figurine", "auto", "手办化 AstrBot 插件", "0.2.0")
class FigurinePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.model = "google/gemini-2.5-flash-image-preview:free"
        self.max_tokens = 1000
        self.use_proxy = bool(config.get("use_proxy", False))
        self.proxy_url = str(config.get("proxy_url", "")) or None
        self.timeout_sec = float(config.get("request_timeout_sec", 60.0))

    @filter.command("手办化添加key")
    async def cmd_add_keys(self, event: AstrMessageEvent, keys_text: str = ""):
        if not event.is_admin():
            yield event.plain_result("❌ 仅管理员可用")
            return
        msg = event.message_str or ""
        prefix = "手办化添加key"
        pos = msg.find(prefix)
        args = keys_text.strip() if keys_text else (msg[pos + len(prefix):].strip() if pos >= 0 else "")
        if not args:
            yield event.plain_result("❌ 请提供API密钥\n\n📝 用法:\n/手办化添加key <密钥1> [密钥2] ...\n\n支持空格/逗号/分号/换行；格式 sk-or-v1-xxxxxxxx...")
            return
        parts = [p for p in re.split(r"[\s,;，；\n\r]+", args) if p]
        cand = [p for p in parts if p.startswith("sk-or-v1-")]
        if not cand:
            yield event.plain_result("❌ 未检测到有效密钥（须以 sk-or-v1- 开头）")
            return
        cfg = load_keys_config()
        existing = set(cfg.get("keys", []))
        added, dup = [], []
        for k in cand:
            if k in existing:
                dup.append(k[:12] + "***")
            else:
                cfg.setdefault("keys", []).append(k)
                added.append(k[:12] + "***")
        save_keys_config(cfg)
        reply = ["✅ 操作完成:"]
        if added:
            reply.append(f"- 成功添加 {len(added)} 个")
        if dup:
            reply.append(f"- 跳过 {len(dup)} 个重复")
        yield event.plain_result("\n".join(reply))

    @filter.command("手办化key列表")
    async def cmd_list_keys(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("❌ 仅管理员可用")
            return
        cfg = load_keys_config()
        keys = cfg.get("keys", [])
        if not keys:
            yield event.plain_result("📝 当前没有配置任何API密钥\n\n使用 /手办化添加key <密钥> 添加")
            return
        current = cfg.get("current", 0)
        lines = []
        for idx, k in enumerate(keys):
            masked = (k[:12] + "***") if isinstance(k, str) and len(k) >= 12 else "***"
            mark = " (当前)" if idx == current else ""
            lines.append(f"{idx+1}. {masked}{mark}")
        yield event.plain_result("\n".join([f"📝 API密钥列表 ({len(keys)}个)"] + lines))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        message_str = event.message_str or ""
        preset_label, target_qq = parse_command(message_str)
        if not preset_label:
            return
        try:
            yield event.plain_result("🎨 正在生成手办化形象，请稍候…")
        except Exception as send_err:
            logger.error(f"send start msg failed: {send_err}")
        prompt, display_label = select_prompt(preset_label)
        avatar_url: Optional[str] = None
        try:
            # 优先从 Reply chain 获取图片（Image 类型）
            img_url = _find_first_image_in_reply_chain(event)
            if img_url:
                avatar_url = img_url
            else:
                at_qq = _find_first_at_qq(event)
                if at_qq:
                    avatar_url = build_avatar_url(at_qq)
                elif target_qq:
                    avatar_url = build_avatar_url(target_qq)
                else:
                    img_url2 = _find_first_image_url(event)
                    if img_url2:
                        avatar_url = img_url2
                    else:
                        sender_id = event.get_sender_id()
                        if sender_id:
                            avatar_url = build_avatar_url(str(sender_id))
        except Exception as sel_err:
            logger.error(f"select image failed: {sel_err}")
        if not avatar_url:
            yield event.plain_result("❌ 未找到可用图片或头像")
            return
        proxies: Optional[Dict[str, str]] = None
        if self.use_proxy and self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}
        try:
            img_b64 = await fetch_image_as_b64(avatar_url, proxies, self.timeout_sec)
        except Exception as err:
            yield event.plain_result(f"❌ 下载图片失败: {err}")
            return
        payload = build_payload(self.model, prompt, img_b64, self.max_tokens)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {get_next_api_key()}"}
        start = time.time()
        try:
            if proxies:
                os.environ["HTTP_PROXY"] = proxies.get("http", "")
                os.environ["HTTPS_PROXY"] = proxies.get("https", "")
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(API_URL, headers=headers, json=payload)
                data = resp.json()
                if resp.status_code >= 400 or data.get("error"):
                    raise RuntimeError(data.get("error", {}).get("message", f"HTTP {resp.status_code}"))
                image_url = extract_image_url_from_response(data)
                if not image_url:
                    raise RuntimeError("响应中未找到图片数据")
                if image_url.startswith("data:image/"):
                    b64_data = image_url.split(",", 1)[1] if "," in image_url else ""
                    ensure_data_dir()
                    out_path = os.path.join(FIGURINE_DIR, f"generated_{int(time.time())}.png")
                    with open(out_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    img_seg = Comp.Image.fromFileSystem(out_path)
                else:
                    img_seg = Comp.Image.fromURL(image_url)
                elapsed = f"{(time.time() - start):.2f}"
                yield event.chain_result([img_seg, Comp.Plain(f"\n✅ 生成完成（{elapsed}s）｜预设：{display_label}")])
        except Exception as err:
            yield event.plain_result(f"❌ 生成失败: {err}")
