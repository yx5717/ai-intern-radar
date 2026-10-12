import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resume_parser import parse_resume


class UploadedFixture:
    def __init__(self, path: Path):
        self.name = path.name
        self._raw = path.read_bytes()

    def getvalue(self):
        return self._raw


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
print({"school": result.school, "major": result.major, "degree": result.degree, "graduation_year": result.graduation_year, "skills": result.skills})
