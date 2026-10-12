import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resume_parser import parse_resume, snapshot


class UploadedFixture:
    def __init__(self, path: Path):
        self.name = path.name
        self._raw = path.read_bytes()

    def getvalue(self):
        return self._raw


# N8 回归：纯文本/PDF 简历没有表格分隔符，也要能提取专业；
# 「2028届」这种没有分隔符的写法也要能提取毕业年份。
plain = snapshot(
    "个人简历\n"
    "学校：首都经济贸易大学\n"
    "专业：经济统计学\n"
    "学历：本科\n"
    "毕业时间：2028届\n"
    "技能：Python、SQL、RAG、FineBI"
)
assert plain.school == "首都经济贸易大学", plain
assert plain.major == "经济统计学", plain
assert plain.degree == "本科", plain
assert plain.graduation_year == 2028, plain
assert "RAG" in plain.skills and "FineBI" in plain.skills, plain.skills

# 表格简历的写法不能被这次改动破坏
tabled = snapshot("首都经济贸易大学 | 经济统计学 | 本科\n2028 届\n技能：Python、RAG")
assert tabled.major == "经济统计学", tabled
assert tabled.graduation_year == 2028, tabled


_RESUME_DIR = Path(__file__).resolve().parents[2] / "简历"
_candidates = sorted(_RESUME_DIR.glob("*个人简历*.docx"))
if not _candidates:
    raise SystemExit(f"未在 {_RESUME_DIR} 找到 *个人简历*.docx，请先放入测试简历")
source = _candidates[0]
result = parse_resume(UploadedFixture(source))
assert result.school == "首都经济贸易大学"
assert result.major == "经济统计学"
assert result.degree == "本科"
assert result.graduation_year == 2028
assert "RAG" in result.skills and "FineBI" in result.skills
print({"school": result.school, "major": result.major, "degree": result.degree,
       "graduation_year": result.graduation_year, "skills": result.skills,
       "plain_text_fallback": plain.major, "table_form": tabled.major})
