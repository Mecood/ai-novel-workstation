// @ts-nocheck
import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Spin, Typography, Row, Col, Button, Tag, message, Space, Select, Alert, List, Input } from 'antd';
import {
  ExperimentOutlined, BuildOutlined, ThunderboltOutlined, BulbOutlined,
  CopyOutlined, RedoOutlined, PlusOutlined, BookOutlined,
  RocketOutlined, StarOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi } from '../../services/api';
import type { Project } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

// ---------- 素材池 ----------
const DIMS = ['角色原型', '场景类型', '冲突类型', '主题方向', '结构框架'];
const DIM_COLORS: Record<string, string> = {
  '角色原型': '#722ed1', '场景类型': '#1890ff', '冲突类型': '#ff4d4f',
  '主题方向': '#52c41a', '结构框架': '#fa8c16',
};

const DIM_LABELS: Record<string, string> = {};
DIMS.forEach(d => { DIM_LABELS[d] = d; });

const SEED_POOLS: Record<string, string[]> = {
  '角色原型': [
    '天降异人 — 天生不凡却被世俗所不容，被迫隐姓埋名',
    '破局者 — 在所有人绝望时，一个不合常理的举动改写命运',
    '复仇者 — 为逝去的亲人与信念，独自踏上无人能及的复仇之路',
    '觉醒者 — 普通角色在危机中觉醒，发现自身隐藏的惊世之力',
    '导师型 — 以自身为火，照亮后辈道路，代价是自己走向终点',
    '双面人 — 表面温润如玉，暗藏一腔杀机与不为人知的过去',
    '卧底者 — 游走在正邪之间，身份随时暴露，生死只在一线',
    '逆命者 — 命运给了一手烂牌，偏要把它打到惊天动地',
    '轮回者 — 一次次从死亡归来，只为找到那个能改写结局的真相',
    '失忆者 — 失去记忆却保留本能，在废墟中寻找自己是谁',
  ],
  '场景类型': [
    '末世废墟 — 钢铁丛林中的文明余烬与重生',
    '学府试炼 — 神秘学院里的天才与怪物同台竞技',
    '星际漂流 — 飞船舰队横渡宇宙，寻找回家的坐标',
    '都市暗巷 — 霓虹下的地下世界，金钱与秘密的交易场',
    '深山门派 — 云雾锁门，千百年传承的古老修行之路',
    '海上飞舟 — 岛屿与海城之间的无尽探险',
    '时空夹层 — 两个世界重叠，历史与现实同时发生',
    '古文明秘境 — 被遗忘的遗迹中，藏着改写世界的钥匙',
    '幻境战场 — 意识与现实交锋，赢的人才能醒来',
    '永恒之都 — 时间在这里静止，魔法成为日常',
  ],
  '冲突类型': [
    '天选 vs 宿命 — 主角的使命与血脉里的枷锁',
    '信仰 vs 理性 — 心中的神与手中的尺，谁该让路',
    '复仇 vs 救赎 — 为谁而战，战到最后一刻才懂',
    '秩序 vs 混沌 — 重建世界还是让一切重新燃烧',
    '团结 vs 阴谋 — 队友之中，谁在笑，谁在磨刀',
    '进化 vs 人性 — 力量的代价，是失去人性本身',
    '公开 vs 秘密 — 真相即将曝光，谁在拼命掩盖',
    '传统 vs 革新 — 祖训如山，新一代偏要拆山开路',
    '权力 vs 责任 — 爬到顶端的代价，是再也回不了头',
    '私情 vs 道义 — 爱人与天下，该选哪一边',
  ],
  '主题方向': [
    '秩序与混沌的永恒对抗',
    '超越自身极限的进化之路',
    '被遗忘之物与文明传承',
    '记忆与遗忘的轮回',
    '东西方哲学与修仙道的融合',
    '炎与冰之间的微妙平衡',
    '禁术与瘟疫的生存博弈',
    '梦想与现实之间的那道鸿沟',
    '种族隔阂与历史创伤',
    '生与死的真正定义',
  ],
  '结构框架': [
    '经典 3 幕剧 — 布局 → 冲突 → 解决',
    '双线汇合 — 两个故事线在终局交汇',
    '火焰金字塔 — 步步高升的势力对决',
    '倒叙悬疑 — 从头回溯，层层揭晓真相',
    '群像实验 — 孤岛式分散的团队观察',
    '血脉传承 — 祖训与血脉交织的秘密',
    '双面叙事 — 两条线索并行，终局合一',
    '时空夹层 — 过去与未来层次的碰撞',
    '连续余波 — 一场爆炸后的连锁反应',
    '十字路口 — 多个角色的命运在此交汇',
  ],
};

const GENRES = ['仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险'];

const COMPLEXITY_OPTIONS = [
  { key: 'low', label: '简洁', desc: '1 个维度各取 1 项，聚焦主线', color: '#52c41a' },
  { key: 'medium', label: '标准', desc: '每维度 2 项，1 条支线', color: '#1890ff' },
  { key: 'high', label: '复杂', desc: '每维度 3 项，2 条支线 + 1 个核心隐喻', color: '#722ed1' },
];

// ---------- 内置情节框架 ----------
interface Step { step: number; name: string; desc: string; }
interface FrameworkInfo { name: string; description: string; step_count: number; steps: Step[]; }

const BUILTIN_FRAMEWORKS: FrameworkInfo[] = [
  {
    name: '三幕剧', description: '经典好莱坞叙事结构，最稳妥的开篇路径', step_count: 3,
    steps: [
      { step: 1, name: '前情铺垫', desc: '建立世界观，触发事件打破主角的平静日常' },
      { step: 2, name: '冲突上升', desc: '敌人出现，盟友集结，危机层层加码' },
      { step: 3, name: '高潮与新生', desc: '终极对决 → 回归 → 一个全新的未来' },
    ],
  },
  {
    name: '英雄旅程', description: '12 步英雄之旅的精简版', step_count: 4,
    steps: [
      { step: 1, name: '平凡世界', desc: '主角的日常与潜藏的野心' },
      { step: 2, name: '拒绝召唤', desc: '被事件推着走上不归路' },
      { step: 3, name: '考验与同盟', desc: '绝境探索，结识生死之交' },
      { step: 4, name: '凯旋回归', desc: '拯救世界后，回到一个不同的自己' },
    ],
  },
  {
    name: '七点法', description: '电影编剧经典框架，节奏紧凑', step_count: 7,
    steps: [
      { step: 1, name: '原型阶段', desc: '建立基线、背景与角色常态' },
      { step: 2, name: '激励事件', desc: '打破平衡的关键事件' },
      { step: 3, name: '第一转折', desc: '主角被拖入主冲突' },
      { step: 4, name: '中场', desc: '上下半场的分水岭' },
      { step: 5, name: '第二转折', desc: '最黑暗的时刻' },
      { step: 6, name: '高潮', desc: '终极对决' },
      { step: 7, name: '升华', desc: '尾声与余音' },
    ],
  },
  {
    name: '网文黄金节奏', description: '网文黄金开局，前三章必出钩子', step_count: 4,
    steps: [
      { step: 1, name: '冷开场', desc: '第一章前三句就抛悬念，钩住读者' },
      { step: 2, name: '热高潮', desc: '第二章立即冲突爆发' },
      { step: 3, name: '低谷转折', desc: '主角跌落谷底，获得转机' },
      { step: 4, name: '反击终章', desc: '绝地反击，确立成长方向' },
    ],
  },
  {
    name: '双线曼陀罗', description: '两条线索并行推进，终局合一', step_count: 4,
    steps: [
      { step: 1, name: '双引', desc: '两条线索各自开局' },
      { step: 2, name: '交叉铺垫', desc: '两条线索开始隐约关联' },
      { step: 3, name: '高峰对决', desc: '各自进入高潮' },
      { step: 4, name: '合一', desc: '两条线索交汇，收束终局' },
    ],
  },
  {
    name: '八章轻模板', description: '轻量级网文模板，快速上手', step_count: 8,
    steps: [
      { step: 1, name: '钩子', desc: '第 1 章前三句制造悬念' },
      { step: 2, name: '铺垫', desc: '角色日常与世界规则' },
      { step: 3, name: '首转折', desc: '第一个关键事件' },
      { step: 4, name: '二次冲击', desc: '反转或新危机' },
      { step: 5, name: '身份之谜', desc: '"你到底是谁"的核心揭露' },
      { step: 6, name: '真正的 BOSS', desc: '表面之敌只是幌子' },
      { step: 7, name: '大规模战斗', desc: '终极对决' },
      { step: 8, name: '宁静之后', desc: '终局与余韵' },
    ],
  },
];

// ---------- 工具函数 ----------
function pick<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, Math.min(n, arr.length));
}

const COMPLEXITY_N: Record<string, number> = { low: 1, medium: 2, high: 3 };

interface ComboResult {
  genre: string;
  complexity: string;
  combo: Record<string, string>;
  ideaPrompt: string;
  outline: string;
  titles: string[];
}

function buildIdeaPrompt(genre: string, combo: Record<string, string>): string {
  return [
    `题材：${genre}`,
    ``,
    `角色原型：${combo['角色原型']}`,
    `场景：${combo['场景类型']}`,
    `核心冲突：${combo['冲突类型']}`,
    `主题方向：${combo['主题方向']}`,
    `结构框架：${combo['结构框架']}`,
    ``,
    `—— 接下来：从中抽取一个最具体的组合，写一份详细的故事创意大纲或第一章开局剧本。`,
  ].join('\n');
}

// 本地生成故事大纲
function generateOutline(genre: string, combo: Record<string, string>): string {
  const role = combo['角色原型'];
  const scene = combo['场景类型'];
  const conflict = combo['冲突类型'];
  const theme = combo['主题方向'];

  return [
    `【${genre}·故事大纲速写】`,
    ``,
    `【起】主角以「${role.split(' — ')[0]}」的姿态，置身于「${scene.split(' — ')[0]}」。`,
    `  一个突如其来的事件打破了平静的日常——${role.split(' — ')[1] || '命运向他抛来了一根绳索'}。`,
    ``,
    `【承】主线围绕「${conflict.split(' — ')[0]}」展开。`,
    `  主角在 ${scene.split(' — ')[1] || '这个世界的边缘'} 中与盟友集结，与敌人周旋。`,
    `  每一次胜利，都让 ${conflict.split(' — ')[1] || '那个最深的矛盾'} 变得更加尖锐。`,
    ``,
    `【转】危机达到顶峰。`,
    `  主角被迫面对「${theme}」——这不仅是故事的命题，也是他内心的镜子。`,
    `  在所有人都以为故事要结束时，一个反转揭开真相。`,
    ``,
    `【合】决战之后，世界被改写。`,
    `  主角不再是故事开头的那个人。主题「${theme}」在此刻得到了答案。`,
    `  但新的旅程，才刚刚开始。`,
  ].join('\n');
}

function generateTitles(genre: string, combo: Record<string, string>): string[] {
  const role = combo['角色原型'].split(' — ')[0];
  const scene = combo['场景类型'].split(' — ')[0];
  const conflict = combo['冲突类型'].split(' — ')[0];
  return [
    `《${scene}·${role}》`,
    `《${role}录》`,
    `《${conflict}》`,
    `《逆命之${scene}》`,
    `《${genre}·${role}传》`,
    `《${scene}·${conflict}》`,
  ];
}

function generateCombo(genre: string, complexity: string): ComboResult {
  const n = COMPLEXITY_N[complexity] || 2;
  const combo: Record<string, string> = {};
  for (const dim of DIMS) {
    combo[dim] = pick(SEED_POOLS[dim], n).join('；');
  }
  const ideaPrompt = buildIdeaPrompt(genre, combo);
  const outline = generateOutline(genre, combo);
  const titles = generateTitles(genre, combo);
  return { genre, complexity: COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.label || '标准', combo, ideaPrompt, outline, titles };
}

// ---------- 主组件 ----------
export default function CreativePage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(!!id);
  const standaloneMode = !id;

  const [genre, setGenre] = useState('仙侠');
  const [complexity, setComplexity] = useState('medium');
  const [comboLoading, setComboLoading] = useState(false);
  const [combination, setCombination] = useState<ComboResult | null>(null);

  const [frameworks] = useState<FrameworkInfo[]>(BUILTIN_FRAMEWORKS);
  const [recommended] = useState<string[]>(['三幕剧', '七点法', '网文黄金节奏']);
  const [frameworkDetail, setFrameworkDetail] = useState<FrameworkInfo | null>(null);

  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  useEffect(() => {
    if (!id) { setLoading(false); return; }
    Promise.all([
      projectApi.get(id),
      fetch(`/v1/projects/${id}/creative/frameworks`).then(r => r.json()).catch(() => null),
    ])
      .then(([proj, fw]) => {
        setProject(proj?.data || null);
        if (fw?.frameworks) setFrameworks(fw.frameworks);
        if (fw?.recommended) setRecommended(fw.recommended);
      })
      .catch(() => message.error('加载项目失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleCombine = useCallback(async () => {
    if (id) {
      setComboLoading(true);
      try {
        const resp = await fetch(`/v1/projects/${id}/creative/combine?complexity=${complexity}`, { method: 'POST' });
        if (!resp.ok) throw new Error('请求失败');
        const data = await resp.json();
        // 适配后端返回结构
        const c = data.combination || data;
        setCombination({
          genre: project?.genre || genre,
          complexity: COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.label || '标准',
          combo: c.combo || {},
          ideaPrompt: c.idea_prompt || JSON.stringify(c),
          outline: '（请结合项目信息生成）',
          titles: [],
        });
      } catch {
        message.error('创意组合生成失败，已切换至本地生成');
        setCombination(generateCombo(genre, complexity));
      } finally {
        setComboLoading(false);
      }
    } else {
      setComboLoading(true);
      setTimeout(() => {
        setCombination(generateCombo(genre, complexity));
        setComboLoading(false);
      }, 400);
    }
  }, [id, complexity, genre, project]);

  const handleFrameworkClick = useCallback((name: string) => {
    const fw = frameworks.find(f => f.name === name);
    setFrameworkDetail(fw || null);
  }, [frameworks]);

  if (loading) {
    return (
      <AppLayout projectId={id}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  const handleCopy = (text: string, idx: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    });
    message.success('已复制到剪贴板');
  };

  const content = (
    <>
      <Title level={3} style={{ marginBottom: 24 }}>
        <BulbOutlined style={{ marginRight: 8 }} />
        创意工坊
        {(project || standaloneMode) && (
          <Tag style={{ marginLeft: 12 }} color="purple">
            {project?.genre || genre}
          </Tag>
        )}
      </Title>

      {standaloneMode && (
        <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
          <Space>
            <Text strong>题材：</Text>
            <Select value={genre} onChange={setGenre} style={{ width: 120 }}>
              {GENRES.map(g => <Select.Option key={g} value={g}>{g}</Select.Option>)}
            </Select>
            <Text type="secondary">复杂度：</Text>
            <Space>
              {COMPLEXITY_OPTIONS.map(opt => (
                <Button
                  key={opt.key}
                  size="small"
                  type={complexity === opt.key ? 'primary' : 'default'}
                  style={complexity === opt.key ? { background: opt.color, borderColor: opt.color } : undefined}
                  onClick={() => setComplexity(opt.key)}
                >
                  {opt.label}
                </Button>
              ))}
            </Space>
            <Button type="primary" icon={<ThunderboltOutlined />} loading={comboLoading} onClick={handleCombine}>
              生成组合
            </Button>
          </Space>
        </Card>
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title={<><ExperimentOutlined style={{ marginRight: 6 }} />创意种子组合器</>}
            extra={!standaloneMode ? (
              <Space>
                {COMPLEXITY_OPTIONS.map(opt => (
                  <Button
                    key={opt.key}
                    size="small"
                    type={complexity === opt.key ? 'primary' : 'default'}
                    style={complexity === opt.key ? { background: opt.color, borderColor: opt.color } : undefined}
                    onClick={() => setComplexity(opt.key)}
                  >
                    {opt.label}
                  </Button>
                ))}
                <Button type="primary" icon={<ThunderboltOutlined />} loading={comboLoading} onClick={handleCombine}>
                  生成组合
                </Button>
              </Space>
            ) : undefined}
          >
            {!combination ? (
              <div style={{ textAlign: 'center', padding: 50 }}>
                <Text type="secondary">
                  点击「生成组合」，随机抽取角色原型 × 场景 × 冲突 × 主题 × 结构，激发创作灵感
                </Text>
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    当前复杂度：{COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.label} —
                    {COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.desc}
                  </Text>
                </div>
              </div>
            ) : (
              <div>
                {/* 五维度卡片 */}
                <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
                  {Object.entries(combination.combo).map(([dim, val]) => (
                    <Col xs={24} sm={12} key={dim}>
                      <Card size="small" bordered style={{ borderLeft: `4px solid ${DIM_COLORS[dim] || '#ccc'}` }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {DIM_LABELS[dim] || dim}
                        </Text>
                        <div style={{ marginTop: 4, fontSize: 13 }}>
                          <Text>{val}</Text>
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>

                {/* 创意激发 Prompt */}
                <Card
                  size="small"
                  title={<><CopyOutlined style={{ marginRight: 4 }} />创意激发 Prompt</>}
                  extra={<Button size="small" onClick={() => handleCopy(combination.ideaPrompt, 0)}>复制</Button>}
                  style={{ background: '#f6ffed', marginBottom: 16 }}
                >
                  <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>
                    {combination.ideaPrompt}
                  </Paragraph>
                </Card>

                {/* 故事大纲速写 */}
                <Card
                  size="small"
                  title={<><BookOutlined style={{ marginRight: 4 }} />故事大纲速写</>}
                  extra={<Button size="small" onClick={() => handleCopy(combination.outline, 1)}>复制</Button>}
                  style={{ background: '#f0f5ff', marginBottom: 16 }}
                >
                  <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>
                    {combination.outline}
                  </Paragraph>
                </Card>

                {/* 标题候选 */}
                <Card
                  size="small"
                  title={<><StarOutlined style={{ marginRight: 4 }} />书名候选</>}
                  style={{ background: '#fff7e6' }}
                >
                  <Row gutter={[8, 8]}>
                    {combination.titles.map((t, i) => (
                      <Col xs={24} sm={8} md={6} key={i}>
                        <Tag
                          color="orange"
                          style={{
                            fontSize: 13,
                            padding: '6px 10px',
                            cursor: 'pointer',
                            display: 'inline-block',
                            margin: 2,
                          }}
                          onClick={() => handleCopy(t, 100 + i)}
                        >
                          {t}
                        </Tag>
                      </Col>
                    ))}
                  </Row>
                </Card>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title={<><BuildOutlined style={{ marginRight: 6 }} />情节框架库</>} size="small">
            {frameworks.length === 0 ? (
              <Text type="secondary">暂无框架</Text>
            ) : (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    为【{project?.genre || genre}】题材推荐：
                  </Text>
                  <div style={{ marginTop: 4 }}>
                    {recommended.map(name => (
                      <Tag
                        key={name}
                        color="purple"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleFrameworkClick(name)}
                      >
                        {name}
                      </Tag>
                    ))}
                  </div>
                </div>

                <div style={{ maxHeight: 360, overflowY: 'auto' }}>
                  {frameworks.map(fw => (
                    <Card
                      key={fw.name}
                      size="small"
                      hoverable
                      style={{ marginBottom: 6 }}
                      onClick={() => handleFrameworkClick(fw.name)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text strong style={{ fontSize: 13 }}>{fw.name}</Text>
                        <Tag>{fw.step_count}步</Tag>
                      </div>
                      <Paragraph ellipsis={{ rows: 2 }} style={{ fontSize: 12, color: '#888', margin: '4px 0 0' }}>
                        {fw.description}
                      </Paragraph>
                    </Card>
                  ))}
                </div>

                {frameworkDetail && (
                  <Card size="small" title={frameworkDetail.name} style={{ marginTop: 12, background: '#fafafa' }}>
                    <Paragraph type="secondary" style={{ fontSize: 12 }}>
                      {frameworkDetail.description}
                    </Paragraph>
                    <div style={{ marginTop: 8 }}>
                      {frameworkDetail.steps.map(s => (
                        <div key={s.step} style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                          <Tag color="blue">{s.step}</Tag>
                          <div>
                            <Text strong style={{ fontSize: 12 }}>{s.name}</Text>
                            <br />
                            <Text type="secondary" style={{ fontSize: 11 }}>{s.desc}</Text>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );

  return <AppLayout projectId={id || undefined}>{content}</AppLayout>;
};
