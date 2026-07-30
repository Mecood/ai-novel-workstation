"""
朱雀真实检测服务 — 通过 Playwright 自动化操作真实朱雀网页。

不走本地模型替代，直接打开 https://matrix.tencent.com/ai-detect/
自动粘贴文本 → 点击检测 → 截取 WebSocket/页面返回的真实检测结果。

返回结构与旧 zhuque_detector 兼容：
{
    "ai_probability": float,       # AI特征占比 0-1
    "human_probability": float,    # 人工特征占比 0-1
    "suspicious_probability": float, # 疑似/混合占比 0-1
    "verdict": str,                # "人工" | "可疑" | "很可能 AI" | "AI 生成"
    "level": str,                  # "safe" | "suspect" | "likely_ai" | "confirmed_ai"
    "source": "zhuque_real",       # 数据来源标记
}
"""

import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

ZHUQUE_URL = "https://matrix.tencent.com/ai-detect/"
DETECT_TIMEOUT = 120_000  # Playwright 用的毫秒

# Playwright 实例缓存（避免每次检测都启动新浏览器）
_pw_instance = None
_pw_lock = asyncio.Lock()


async def detect_ai_generation(text: str) -> dict:
    """用真实朱雀网页检测文本的 AI 概率。

    Args:
        text: 待检测文本（至少 350 字）

    Returns:
        标准化检测结果字典
    """
    if not text or len(text) < 350:
        return {
            "ai_probability": 0.0,
            "human_probability": 1.0,
            "suspicious_probability": 0.0,
            "verdict": "文本过短",
            "level": "safe",
            "source": "zhuque_real",
        }

    try:
        result = await _detect_with_playwright(text)
        return result
    except Exception as e:
        logger.warning(f"朱雀真实检测失败，回退到本地模型: {e}")
        # 回退到本地模型
        try:
            from app.services.zhuque_detector_local import detect_ai_generation as _local_detect
            local_result = await _local_detect(text)
            local_result["source"] = "local_fallback"
            return local_result
        except Exception:
            return {
                "ai_probability": 0.5,
                "human_probability": 0.3,
                "suspicious_probability": 0.2,
                "verdict": "检测失败",
                "level": "suspect",
                "source": "error_fallback",
                "error": str(e),
            }


async def _detect_with_playwright(text: str) -> dict:
    """核心检测逻辑：打开朱雀网页 → 粘贴文本 → 点检测 → 抓结果。"""
    global _pw_instance

    async with _pw_lock:
        if _pw_instance is None:
            _pw_instance = await _create_browser()
        browser = _pw_instance

    page = await browser.new_page()

    try:
        # 拦截 WebSocket 帧，捕获检测结果
        ws_results: list[dict] = []

        page.on("websocket", _create_ws_handler(ws_results))

        # 也拦截 HTTP 响应（朱雀有备用轮询接口）
        page.on("response", _create_response_handler(ws_results))

        # 打开朱雀检测页
        await page.goto(ZHUQUE_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)  # 等页面完全加载

        # 找到文本输入框，粘贴文本
        # 朱雀页面用 textarea 或 contenteditable div
        textarea = await _find_input(page)
        if textarea is None:
            raise RuntimeError("找不到文本输入框")

        await textarea.click()
        await textarea.fill(text[:5000])  # 朱雀限制 5000 字
        await asyncio.sleep(1)

        # 点击检测按钮
        detect_btn = await _find_detect_button(page)
        if detect_btn is None:
            raise RuntimeError("找不到检测按钮")

        await detect_btn.click()

        # 等待结果出现（WebSocket 帧 / 页面结果区域）
        result = await _wait_for_result(ws_results, page, timeout=DETECT_TIMEOUT)

        return result

    finally:
        await page.close()


async def _create_browser():
    """创建 Playwright 浏览器实例。"""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    # 缓存 pw 和 browser，后续复用
    _create_browser._pw = pw
    return browser


def _create_ws_handler(ws_results: list):
    """创建 WebSocket 消息处理器。"""
    def handler(ws):
        def on_message(msg):
            try:
                data = json.loads(msg)
                if isinstance(data, dict) and (
                    data.get("confidence") is not None
                    or data.get("labels_ratio") is not None
                    or data.get("labelsRatio") is not None
                    or data.get("rate") is not None
                ):
                    ws_results.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        ws.on("framereceived", lambda payload: on_message(payload))
    return handler


def _create_response_handler(ws_results: list):
    """创建 HTTP 响应处理器（捕获 /user/detect/result 轮询）。"""
    async def handler(response):
        url = response.url
        if "detect/result" in url or "getClassify" in url:
            try:
                body = await response.json()
                if isinstance(body, dict) and (
                    body.get("confidence") is not None
                    or body.get("labels_ratio") is not None
                    or body.get("labelsRatio") is not None
                ):
                    ws_results.append(body)
            except Exception:
                pass
    return handler


async def _find_input(page):
    """找到朱雀页面的文本输入框。"""
    # 尝试多种选择器
    selectors = [
        "textarea",
        "[contenteditable='true']",
        ".ai-detect-input textarea",
        "#detect-textarea",
        ".detect-input-area",
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue
    return None


async def _find_detect_button(page):
    """找到检测按钮。"""
    selectors = [
        "button:has-text('检测')",
        "button:has-text('Detect')",
        ".detect-btn",
        "[class*='detect'] button",
        "button[type='submit']",
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return el
        except Exception:
            continue
    return None


async def _wait_for_result(ws_results: list, page, timeout: int) -> dict:
    """等待检测结果（WebSocket 或页面 DOM）。"""
    deadline = asyncio.get_event_loop().time() + timeout / 1000

    while asyncio.get_event_loop().time() < deadline:
        # 先看 WebSocket 是否收到结果
        if ws_results:
            raw = ws_results[-1]
            parsed = _parse_zhuque_payload(raw)
            if parsed:
                return parsed

        # 再看页面 DOM 是否渲染了结果
        dom_result = await _extract_dom_result(page)
        if dom_result:
            return dom_result

        await asyncio.sleep(1)

    raise TimeoutError(f"朱雀检测超时 ({timeout // 1000}s)")


def _parse_zhuque_payload(data: dict) -> Optional[dict]:
    """解析朱雀返回的原始数据为标准化结果。"""
    # 朱雀返回的 labels_ratio: {"0": AI, "1": 人工, "2": 疑似}
    # 但旧版可能反过来，用 confidence/rate 校准
    raw_labels = data.get("labels_ratio") or data.get("labelsRatio") or {}
    confidence = data.get("confidence") or data.get("rate")

    if not raw_labels and confidence is not None:
        # 只有总分，没有分标签
        ai_rate = float(confidence) / 100 if float(confidence) > 1 else float(confidence)
        return {
            "ai_probability": round(ai_rate, 4),
            "human_probability": round(1 - ai_rate, 4),
            "suspicious_probability": 0.0,
            "verdict": _classify_verdict(ai_rate),
            "level": _classify_level(ai_rate),
            "source": "zhuque_real",
            "raw_confidence": confidence,
        }

    if not raw_labels:
        return None

    def _coerce(v):
        try:
            f = float(v)
            return f / 100 if f > 1 else f
        except (TypeError, ValueError):
            return 0.0

    raw0 = _coerce(raw_labels.get("0", 0))  # AI
    raw1 = _coerce(raw_labels.get("1", 0))  # 人工
    raw2 = _coerce(raw_labels.get("2", 0))  # 疑似

    # 用 confidence 校验 0/1 是否反了
    if confidence is not None:
        conf = _coerce(confidence)
        if abs(raw1 - conf) < abs(raw0 - conf):
            # raw1 更接近 confidence → raw1 是 AI
            raw0, raw1 = raw1, raw0

    ai_prob = raw0
    human_prob = raw1
    suspicious_prob = raw2

    return {
        "ai_probability": round(ai_prob, 4),
        "human_probability": round(human_prob, 4),
        "suspicious_probability": round(suspicious_prob, 4),
        "verdict": _classify_verdict(ai_prob),
        "level": _classify_level(max(ai_prob, suspicious_prob)),
        "source": "zhuque_real",
        "segment_labels": data.get("segment_labels", []),
    }


async def _extract_dom_result(page) -> Optional[dict]:
    """从页面 DOM 提取检测结果（备用方案）。"""
    try:
        # 朱雀结果区域会显示百分比文字
        # 尝试找 chart/result 区域的文本
        result_text = await page.evaluate("""() => {
            // 找结果图表区域的文本
            const els = document.querySelectorAll(
                '.result-chart, .detect-result, .ai-result, [class*="result"], [class*="chart"]'
            );
            for (const el of els) {
                const text = el.innerText || '';
                // 匹配百分比数字
                const matches = text.match(/(\\d+\\.?\\d*)\\s*%/g);
                if (matches && matches.length >= 2) {
                    return text;
                }
            }
            // 也检查 Vue 组件状态
            const vue = document.querySelector('.ai-detection-result');
            if (vue && vue.__vue__) {
                const v = vue.__vue__;
                if (v.rate !== undefined && v.rate !== null) {
                    return JSON.stringify({
                        confidence: v.rate,
                        labels_ratio: v.labelsRatio || {},
                    });
                }
            }
            return null;
        }""")

        if not result_text:
            return None

        # 如果是 JSON（从 Vue 抓的）
        if result_text.startswith("{"):
            data = json.loads(result_text)
            return _parse_zhuque_payload(data)

        # 从百分比文本中提取
        pcts = re.findall(r"(\d+\.?\d*)\s*%", result_text)
        if len(pcts) >= 2:
            nums = [float(p) for p in pcts]
            # 按朱雀三个标签排序：AI / 疑似 / 人工
            # 页面上 chart 的顺序通常是：AI特征、疑似AI、人工特征
            if len(nums) >= 3:
                ai_prob = nums[0] / 100
                suspicious_prob = nums[1] / 100
                human_prob = nums[2] / 100
            else:
                ai_prob = nums[0] / 100
                human_prob = nums[1] / 100
                suspicious_prob = 0.0

            return {
                "ai_probability": round(ai_prob, 4),
                "human_probability": round(human_prob, 4),
                "suspicious_probability": round(suspicious_prob, 4),
                "verdict": _classify_verdict(ai_prob),
                "level": _classify_level(max(ai_prob, suspicious_prob)),
                "source": "zhuque_real_dom",
            }
    except Exception:
        pass
    return None


def _classify_verdict(ai_prob: float) -> str:
    if ai_prob < 0.30:
        return "人工"
    elif ai_prob < 0.50:
        return "可疑"
    elif ai_prob < 0.80:
        return "很可能 AI"
    else:
        return "AI 生成"


def _classify_level(risk_prob: float) -> str:
    if risk_prob < 0.30:
        return "safe"
    elif risk_prob < 0.50:
        return "suspect"
    elif risk_prob < 0.80:
        return "likely_ai"
    else:
        return "confirmed_ai"
