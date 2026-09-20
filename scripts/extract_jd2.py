import json
import re
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "JD2.docx"
OUTPUT = ROOT / "ai-intern-radar" / "data" / "external_jd_v1.jsonl"

COMPANIES = {
    1: "滴滴", 2: "快手", 3: "百度", 4: "滴滴", 5: "美团", 6: "爱奇艺",
    7: "北京量子信息科学研究院", 8: "宝马中国", 9: "慕华信息", 10: "网易有道",
    11: "中国工商银行数据管理部", 12: "中国联通网运事业部", 13: "松下集团",
    14: "智联招聘", 15: "北京淘友天下技术有限公司", 16: "泰康在线", 17: "首佳顾问",
    18: "中核能源科技有限公司", 19: "中创宇峰", 20: "成都森域星河科技",
    21: "微软", 22: "嘉楠科技", 23: "英雄游戏", 24: "脉脉", 25: "八豆智能", 26: "贝壳找房",
}

ROLES = {
    1: "数据开发实习生", 2: "数据研发实习生-数据平台", 3: "数据科学实习生",
    4: "数据运营实习生", 5: "销售策略数据运营实习生-到餐", 6: "数据运营实习生",
    7: "人工智能算法研发实习", 8: "AI Application Development Internship - AI应用开发实习生",
    9: "数据标注/AI训练师", 10: "AI数据标注&大模型评测实习生",
    11: "本部专业实习岗-数据管理部", 12: "大数据实习生", 13: "数据分析实习生",
    14: "AI产品经理实习生", 15: "AI产品经理实习生（C端/招聘业务）",
    16: "产品实习生", 17: "AI应用实习生", 18: "AI应用开发实习生",
    19: "数据分析师", 20: "数据分析（实习）", 21: "数据科学实习生",
    22: "数据分析师（销售运营方向）", 23: "AI工具应用实习生",
    24: "AI产品助理实习生（AI通话方向）", 25: "AI招聘产品运营实习生",
    26: "产品经理（AI效果评测方向）",
}


def source_platform(number: int) -> str:
    if number <= 10:
        return "实习僧"
    if number <= 18:
        return "智联招聘"
    return "牛客网"


def find_starts(paragraphs: list[str]) -> list[int]:
    starts = []
    cursor = 0
    for number in range(1, 27):
        pattern = re.compile(rf"^{number}\s*[.．、]")
        index = next((i for i in range(cursor, len(paragraphs)) if pattern.match(paragraphs[i])), None)
        if index is None:
            raise ValueError(f"Could not find header for JD {number}")
        starts.append(index)
        cursor = index + 1
    return starts


def extract_date(block: list[str]) -> str | None:
    for text in block[:8]:
        match = re.search(r"(20\d{2}-\d{2}-\d{2})(?:\s+\d{2}:\d{2}:\d{2})?\s*(?:刷新|更新)", text)
        if match:
            return match.group(1)
    return None


def raw_meta(block: list[str]) -> str:
    markers = ("职位描述", "岗位职责", "工作职责", "职责描述", "Responsibilities")
    cutoff = next((i for i, text in enumerate(block[1:], start=1) if any(marker in text for marker in markers)), len(block))
    return " | ".join(block[1:cutoff])


def main() -> None:
    document = Document(SOURCE)
    paragraphs = [p.text.strip().replace("\u200b", "") for p in document.paragraphs if p.text.strip()]
    starts = find_starts(paragraphs)
    records = []
    for position, start in enumerate(starts):
        number = position + 1
        end = starts[position + 1] if position + 1 < len(starts) else len(paragraphs)
        block = [text for text in paragraphs[start:end] if not text.startswith("#")]
        records.append({
            "job_id": f"EXT{number:03d}",
            "record_order": number,
            "company": COMPANIES[number],
            "role_title": ROLES[number],
            "raw_heading": block[0],
            "raw_meta": raw_meta(block),
            "jd_raw": "\n".join(block),
            "paragraphs": block,
            "source_platform": source_platform(number),
            "source_url": None,
            "published_at": extract_date(block),
            "collected_at": "2026-09-20",
            "source_file": "JD2.docx",
            "parsing_status": "已结构化，尚未人工标注",
        })

    if len(records) != 26 or len({r["job_id"] for r in records}) != 26:
        raise ValueError("Expected 26 unique external records")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    print(f"Wrote {len(records)} records to {OUTPUT}")


if __name__ == "__main__":
    main()
