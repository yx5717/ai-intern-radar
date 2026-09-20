export function bodyOnly(record) {
  const markers = ["职位描述", "岗位职责", "工作职责", "工作内容", "一、岗位职责", "【岗位职责】", "岗位简介"];
  const indexes = markers.map((marker) => record.jd_raw.indexOf(marker)).filter((index) => index >= 0);
  return indexes.length ? record.jd_raw.slice(Math.min(...indexes)) : record.jd_raw.replace(record.raw_meta, "");
}

function normalizeNumbers(text) {
  return text
    .replaceAll("一", "1").replaceAll("二", "2").replaceAll("三", "3")
    .replaceAll("四", "4").replaceAll("五", "5").replaceAll("六", "6")
    .replaceAll("七", "7");
}

function scheduleFragments(body, unit) {
  const text = normalizeNumbers(body);
  if (unit === "days") {
    return text.match(/(?:每周|一周)[^。；\n]{0,42}?(?:天|日)[^。；\n]{0,10}/g) ?? [];
  }
  return text.match(/[^。；\n]{0,25}?(?:实习|持续|连续|保证|项目实践)[^。；\n]{0,35}?(?:个?月|半年)[^。；\n]{0,12}/g) ?? [];
}

function parseDayFragment(fragment) {
  const range = fragment.match(/([1-7])\s*[-~～至]\s*([1-7])\s*(?:天|日)/);
  if (range) return { min: Number(range[1]), max: Number(range[2]), kind: "range", fragment };
  const number = fragment.match(/(?:≥\s*)?([1-7])\s*(?:天|日)/);
  if (!number) return null;
  const value = Number(number[1]);
  const isMinimum = /至少|不少于|以上|≥/.test(fragment);
  return { min: value, max: isMinimum ? null : value, kind: isMinimum ? "minimum" : "exact", fragment };
}

function parseMonthFragment(fragment) {
  const halfYear = /半年/.test(fragment);
  const number = halfYear ? 6 : Number(fragment.match(/([2-9])\s*个?月/)?.[1]);
  if (!number) return null;
  return {
    min: number,
    kind: /至少|不少于|以上/.test(fragment) ? "minimum" : "exact",
    preferred: /优先|加分/.test(fragment),
    fragment,
  };
}

export function extractSchedule(record) {
  const summaryDays = Number(record.raw_meta.match(/([1-7])\s*天\s*[/／]\s*周/)?.[1]);
  const summaryMonths = Number(record.raw_meta.match(/([2-9])\s*个?月/)?.[1]);
  const body = bodyOnly(record);
  const bodyDays = scheduleFragments(body, "days").map(parseDayFragment).filter(Boolean);
  const bodyMonths = scheduleFragments(body, "months").map(parseMonthFragment).filter(Boolean);

  const dayDifference = bodyDays.some((item) => item.kind === "range" || item.min !== summaryDays);
  const monthDifference = bodyMonths.some((item) => !item.preferred
    ? item.min !== summaryMonths
    : item.min < summaryMonths);
  const salaryConflict = /\d+\s*[-~～至]\s*\d+\s*元\s*[/／]\s*天/.test(record.jd_raw)
    && /(?:底薪|月薪)[^。；\n]{0,25}\d+/.test(body);

  const flexibleDay = bodyDays.some((item) => item.min <= 4 && (item.max === null || item.max >= 4));
  const ambiguousDayRange = bodyDays.some((item) => item.kind === "range" && item.min <= 4 && item.max > 4);
  const hardDayOver = bodyDays.some((item) => item.kind === "exact" && item.min > 4)
    || bodyDays.some((item) => item.kind === "minimum" && item.min > 4);

  const nonPreferredMonths = bodyMonths.filter((item) => !item.preferred);
  const hardMonthOver = nonPreferredMonths.some((item) => item.min > 4);
  const flexibleMonth = bodyMonths.some((item) => item.min <= 4 && (item.min < summaryMonths || item.preferred));

  let result = "通过";
  if (hardMonthOver || hardDayOver) {
    result = "不通过";
  } else if (summaryMonths > 4) {
    result = flexibleMonth ? "需要核实" : "不通过";
  } else if (summaryDays > 4) {
    result = flexibleDay ? "需要核实" : "不通过";
  } else if (ambiguousDayRange) {
    result = "需要核实";
  }

  const evidence = [record.raw_meta, ...bodyDays.map((item) => item.fragment), ...bodyMonths.map((item) => item.fragment)]
    .filter(Boolean)
    .join("；")
    .replace(/\s+/g, " ")
    .slice(0, 240);

  return {
    days: Number.isFinite(summaryDays) ? summaryDays : null,
    months: Number.isFinite(summaryMonths) ? summaryMonths : null,
    result,
    scheduleConflict: dayDifference || monthDifference,
    salaryConflict,
    evidence,
  };
}

export function classifyRole(record) {
  const title = record.role_title;
  const body = bodyOnly(record);
  const text = `${title}\n${body}`;
  let family;
  let direction;
  let boundary = false;

  if (/HR|hr|招聘/.test(title)) {
    family = "职能支持/边界岗位";
    direction = /招聘/.test(text) ? "AI招聘" : "职能支持";
  } else if (/大模型数据|评测|Agent产品与质量|Agent.*质量/.test(title)) {
    family = "大模型评测、训练与数据质量";
    direction = /大模型数据/.test(title) ? "大模型数据与Benchmark"
      : /Agent.*质量/.test(title) ? "Agent质量与知识管理" : "模型评测";
    boundary = /产品/.test(title) || /产品优化|产品方案|原型/.test(body);
  } else if (/数据运营/.test(title)) {
    family = "数据分析与商业/经营分析";
    direction = "增长数据分析";
  } else if (/数据|商业分析|经营分析|价格分析|用户研究/.test(title)) {
    family = "数据分析与商业/经营分析";
    direction = /经营/.test(title) ? "经营分析"
      : /商业/.test(title) ? "商业数据分析"
      : /价格/.test(title) ? "价格分析"
      : /用户研究/.test(title) ? "用户研究与数据分析"
      : /治理|规范|质量/.test(body) ? "数据治理"
      : /用户行为|埋点/.test(body) ? "用户行为分析" : "业务数据分析";
  } else if (/产品/.test(title)) {
    family = "AI产品与Agent产品";
    direction = /对话/.test(title) ? "对话策略产品"
      : /多模态/.test(title) ? "多模态AI产品"
      : /策略/.test(title) ? "Agent产品策略"
      : /工业|ToB|客户场景/.test(text) ? "ToB AI产品"
      : /UAT|交付/.test(text) ? "AI Agent产品与交付"
      : /自动化流程|搭建Demo/.test(text) ? "AI产品与自动化" : "AI产品助理";
    boundary = /评测方案|训练数据生产策略|质量分析|评估标准/.test(body);
  } else if (/运营/.test(title)) {
    family = "AI运营、知识库与增长运营";
    direction = /增长/.test(title) ? "用户增长运营" : "垂直场景AI运营";
  } else if (/行业报告|研究报告|行业研究|最新发展|技术趋势/.test(text)) {
    family = "AI行业研究与战略分析";
    direction = /项目|技术文档/.test(body) ? "AI研究与项目支持" : "AI产业研究";
  } else {
    family = "职能支持/边界岗位";
    direction = "其他";
    boundary = true;
  }

  return { family, direction, boundary };
}

export function predict(record) {
  const schedule = extractSchedule(record);
  const role = classifyRole(record);
  const badCase = schedule.scheduleConflict || schedule.salaryConflict
    ? "摘要正文冲突"
    : role.boundary ? "边界分类" : "无";
  return {
    job_id: record.job_id,
    split: record.split,
    role_family: role.family,
    sub_direction: role.direction,
    weekly_days: schedule.days,
    minimum_months: schedule.months,
    constraint_result: schedule.result,
    bad_case_type: badCase,
    evidence: schedule.evidence,
  };
}
