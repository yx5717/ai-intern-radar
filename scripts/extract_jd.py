import json
import re
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "JD.docx"
OUTPUT = ROOT / "ai-intern-radar" / "tmp" / "jd_records.json"


COMPANY_AND_ROLE = {
    1: ("字节", "【2728届】AI产品实习生（评测…"),
    2: ("腾讯", "AI策略产品实习生（对话方向）"),
    3: ("至顶科技", "科技助理分析师"),
    4: ("新锶", "AI产品助理"),
    5: ("毕马威", "AQPP TSLD 实习生（AI方向）"),
    6: ("好未来", "学而思招聘运营实习转正"),
    7: ("快看漫画", "AI Agent产品策略实习"),
    8: ("松下集团", "数据分析实习生"),
    9: ("西门子中国", "战略发展部数据岗日常实习"),
    10: ("百度", "数据分析实习生"),
    11: ("元气森林", "商业分析（经营分析与AI应用）"),
    12: ("中国信通院", "人工智能实习生"),
    13: ("值得买科技", "AI产品实习生"),
    14: ("北京焱法科技有限公司", "数据运营实习生"),
    15: ("智源人工智能研究院", "大模型数据实习生"),
    16: ("易思汇", "数据实习生"),
    17: ("圆木智能", "AI产品实习生"),
    18: ("百度", "经营分析实习生（J104037）"),
    19: ("微博", "商业数据实习生（MJ008272）"),
    20: ("阿里巴巴集团", "千问多模态AI产品经理实习生"),
    21: ("枫悦互动", "数据分析实习生"),
    22: ("高途", "数据分析实习生"),
    23: ("海纳数智 VIA", "用户研究-数据分析实习生"),
    24: ("智谱华章", "运营实习生"),
    25: ("美团", "价格分析实习生"),
    26: ("网易", "用户增长运营（AI方向）"),
    27: ("融通供应链", "数据分析实习生"),
    28: ("MiniMax", "AI HR实习生"),
    29: ("联想集团", "AI Agent产品与质量实习生"),
    30: ("洋葱学园", "AI产品实习生"),
}


def is_job_header(text: str) -> bool:
    match = re.match(r"^(\d+)\s*[.．]", text)
    return bool(match and "元" in text and "天" in text and 1 <= int(match.group(1)) <= 30)


def parse_meta(header: str, following: list[str]) -> dict:
    salary = re.search(r"(\d+)\s*-\s*(\d+)\s*元\s*/?\s*天", header)
    header_tail = header[salary.end():].strip() if salary else ""
    meta = header_tail if re.search(r"\d+\s*天\s*/\s*周|\d+\s*个月", header_tail) else (following[0] if following else "")
    days = re.search(r"(\d+)\s*天\s*/\s*周", meta)
    months = re.search(r"(\d+)\s*个月", meta)
    city = re.match(r"^([\u4e00-\u9fff]{2,8})", meta)
    education = next((x for x in ["博士", "硕士", "本科", "大专"] if x in meta), "")
    return {
        "salary_min": int(salary.group(1)) if salary else None,
        "salary_max": int(salary.group(2)) if salary else None,
        "pay_unit": "元/天" if salary else "",
        "city": city.group(1) if city else "",
        "weekly_days_summary": int(days.group(1)) if days else None,
        "duration_months_summary": int(months.group(1)) if months else None,
        "education_summary": education,
        "raw_meta": meta,
    }


def split_sections(paragraphs: list[str]) -> tuple[str, str, str]:
    responsibility_markers = (
        "岗位职责", "工作职责", "工作内容", "职位描述", "Your Responsibility",
        "你将参与但不限于", "你将参与",
    )
    requirement_markers = (
        "任职要求", "职位要求", "岗位要求", "任职资格", "岗位基本要求",
        "We Expect", "我们希望你", "要求：", "要求:",
    )
    resp_idx = next((i for i, text in enumerate(paragraphs) if any(m in text for m in responsibility_markers)), None)
    req_idx = None
    start = (resp_idx + 1) if resp_idx is not None else 0
    for i in range(start, len(paragraphs)):
        if any(m in paragraphs[i] for m in requirement_markers):
            req_idx = i
            break

    if resp_idx is None:
        return "", "", "\n".join(paragraphs)
    responsibilities = paragraphs[resp_idx:req_idx] if req_idx is not None else paragraphs[resp_idx:]
    requirements = paragraphs[req_idx:] if req_idx is not None else []
    other = paragraphs[:resp_idx]
    return "\n".join(responsibilities), "\n".join(requirements), "\n".join(other)


def main() -> None:
    document = Document(SOURCE)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    starts = [i for i, text in enumerate(paragraphs) if is_job_header(text)]
    if len(starts) != 30:
        raise ValueError(f"Expected 30 job headers, found {len(starts)}")

    records = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(paragraphs)
        block = paragraphs[start:end]
        number = int(re.match(r"^(\d+)", block[0]).group(1))
        company, role = COMPANY_AND_ROLE[number]
        responsibilities, requirements, other = split_sections(block[1:])
        record = {
            "job_id": f"J{number:03d}",
            "record_order": number,
            "company": company,
            "role_title": role,
            "raw_heading": block[0],
            **parse_meta(block[0], block[1:]),
            "responsibilities_raw": responsibilities,
            "requirements_raw": requirements,
            "other_raw": other,
            "jd_raw": "\n".join(block),
            "paragraphs": block,
            "source_platform": "BOSS直聘",
            "source_url": None,
            "published_at": None,
            "collected_at": "2026-09-20",
            "source_file": "JD.docx",
            "parsing_status": "已切分，待人工复核",
        }
        records.append(record)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} records to {OUTPUT}")


if __name__ == "__main__":
    main()
