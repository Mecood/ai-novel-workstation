// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Steps, Button, Select, Input, Space, message, Typography,
  Divider, Spin, Alert, Progress, Form, Row, Col, Tag, List, Badge,
} from 'antd';
import {
  RocketOutlined, BookOutlined, ThunderboltOutlined, CheckCircleOutlined,
  PlayCircleOutlined, SearchOutlined, BulbOutlined, LayoutOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { api, projectApi, templateApi } from '../../services/api';
import type { GenreTemplate } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

// 新的步骤定义
const WIZARD_STEPS = [
  { key: 0, title: '项目与题材', icon: <BookOutlined /> },
  { key: 1, title: '选题调研', icon: <SearchOutlined /> },
  { key: 2, title: '创意激发', icon: <BulbOutlined /> },
  { key: 3, title: '风格设定', icon: <RocketOutlined /> },
  { key: 4, title: '开始初始化', icon: <ThunderboltOutlined /> },
  { key: 5, title: '完成', icon: <CheckCircleOutlined /> },
];

const DEFAULT_GENRES = [
  '仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险',
];

// 本地创意种子池（复刻 CreativePage）
const SEED_POOLS: Record<string, string[]> = {
  '角色原型': [
    '天降异人', '破局者', '复仇者', '觉醒者', '导师型', '双面人', '卧底者', '逆命者', '轮回者', '失忆者',
  ],
  '场景类型': [
    '末世废墟', '学府试炼', '星际漂流', '都市暗巷', '深山门派', '海上飞舟', '时空夹层', '古文明秘境', '幻境战场', '永恒之都',
  ],
  '冲突类型': [
    '天选 vs 宿命', '信仰 vs 理性', '复仇 vs 救赎', '秩序 vs 混沌', '团结 vs 阴谋',
    '进化 vs 人性', '公开 vs 秘密', '传统 vs 革新', '权力 vs 责任', '私情 vs 道义',
  ],
  '主题方向': [
    '秩序与混沌', '超越极限', '遗忘与传承', '记忆与轮回', '东西方融合',
    '炎冰平衡', '禁术与生存', '梦想与现实', '隔阂与创伤', '生与死的定义',
  ],
  '结构框架': [
    '经典3幕剧', '双线汇合', '火焰金字塔', '倒叙悬疑', '群像实验',
    '血脉传承', '双面叙事', '时空夹层', '连续余波', '十字路口',
  ],
};

const GENRE_STYLE_PARAMS: Record<string, Record<string, number>> = {
  '仙侠': { vocabulary_density: 0.7, rhythm: 0.6, sentence_style: 0.65, rhetoric_level: 0.85, emotional_temperature: 0.7, dialogue_ratio: 0.45 },
  '武侠': { vocabulary_density: 0.55, rhythm: 0.75, sentence_style: 0.55, rhetoric_level: 0.6, emotional_temperature: 0.55, dialogue_ratio: 0.55 },
  '玄幻': { vocabulary_density: 0.75, rhythm: 0.8, sentence_style: 0.7, rhetoric_level: 0.75, emotional_temperature: 0.8, dialogue_ratio: 0.4 },
  '科幻': { vocabulary_density: 0.7, rhythm: 0.5, sentence_style: 0.6, rhetoric_level: 0.45, emotional_temperature: 0.35, dialogue_ratio: 0.45 },
  '悬疑': { vocabulary_density: 0.5, rhythm: 0.85, sentence_style: 0.65, rhetoric_level: 0.4, emotional_temperature: 0.3, dialogue_ratio: 0.55 },
  '都市': { vocabulary_density: 0.5, rhythm: 0.6, sentence_style: 0.5, rhetoric_level: 0.35, emotional_temperature: 0.55, dialogue_ratio: 0.65 },
  '言情': { vocabulary_density: 0.55, rhythm: 0.5, sentence_style: 0.5, rhetoric_level: 0.7, emotional_temperature: 0.85, dialogue_ratio: 0.7 },
  '历史': { vocabulary_density: 0.65, rhythm: 0.4, sentence_style: 0.75, rhetoric_level: 0.55, emotional_temperature: 0.5, dialogue_ratio: 0.45 },
  '奇幻': { vocabulary_density: 0.7, rhythm: 0.7, sentence_style: 0.65, rhetoric_level: 0.8, emotional_temperature: 0.7, dialogue_ratio: 0.45 },
  '冒险': { vocabulary_density: 0.5, rhythm: 0.85, sentence_style: 0.55, rhetoric_level: 0.45, emotional_temperature: 0.7, dialogue_ratio: 0.55 },
};

function pick<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, Math.min(n, arr.length));
}

export default function InitWizardPage() {
  const { id: existingId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const isCreating = !existingId;

  const [loading, setLoading] = useState(isCreating ? false : true);
  const [project, setProject] = useState<any>(null);
  const [projectId, setProjectId] = useState(existingId || '');
  const [templates, setTemplates] = useState<any[]>([]);

  // 步骤
  const [step, setStep] = useState(0);
  const [projectName, setProjectName] = useState('');
  const [genre, setGenre] = useState('');
  const [genreTemplate, setGenreTemplate] = useState<GenreTemplate | null>(null);
  const [theme, setTheme] = useState('');
  const [style, setStyle] = useState('');

  // 步骤 1: 选题调研
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchResult, setResearchResult] = useState<any>(null);
  const [selectedRecommendation, setSelectedRecommendation] = useState<number | null>(null);

  // 步骤 2: 创意激发
  const [comboResult, setComboResult] = useState<Record<string, string> | null>(null);
  const [comboLoading, setComboLoading] = useState(false);

  // 步骤 3: 风格设定
  const [styleParams, setStyleParams] = useState<Record<string, number> | null>(null);
  const [customStylePrompt, setCustomStylePrompt] = useState('');

  // 初始化
  const [running, setRunning] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [errors, setErrors] = useState('');
  const [progress, setProgress] = useState({
    step: 'preparing', status: 'waiting', skipped_steps: [], details: {},
  });

  const wizardSteps = WIZARD_STEPS.map((s, idx) => ({
    ...s,
    status: idx > step ? 'wait' : idx < step ? 'finish' : 'process',
  }));

  // 加载模板
  useEffect(() => {
    templateApi.seed().catch(() => {});
    if (!isCreating) {
      setLoading(true);
      Promise.all([
        projectApi.get(existingId!),
        templateApi.list().catch(() => ({ data: [] })),
      ]).then(([proj, tmpl]) => {
        setProject(proj.data);
        setTemplates(Array.isArray(tmpl.data) ? tmpl.data : []);
        setProjectId(existingId!);
        setGenre(proj.data.genre || '');
      }).catch(() => {
        message.error('加载项目信息失败');
        navigate('/');
      }).finally(() => setLoading(false));
    } else {
      templateApi.list().then(t => setTemplates(Array.isArray(t.data) ? t.data : [])).catch(() => {});
    }
  }, [isCreating, existingId, navigate]);

  // 步骤 0 → 1: 创建项目 + 直接去调研
  const handleCreateProject = async () => {
    if (!canNext()) return;
    setCreatingProject(true);
    try {
      const res = await projectApi.create({ name: projectName, genre, description: '' });
      setProjectId(res.data.id);
      setProject(res.data);
      message.success('项目已创建');
      setStep(1); // 直接进入选题调研
    } catch {
      message.error('创建项目失败');
    } finally {
      setCreatingProject(false);
    }
  };

  // 选题调研
  const handleResearch = async () => {
    if (!genre) return;
    setResearchLoading(true);
    setResearchResult(null);
    try {
      const resp = await fetch(`/api/v1/projects/topic/research?genre=${encodeURIComponent(genre)}&project_name=${encodeURIComponent(projectName)}`);
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt);
      }
      const data = await resp.json();
      setResearchResult(data);
    } catch (e: any) {
      message.error('选题调研失败：' + (e.message || '未知错误'));
    } finally {
      setResearchLoading(false);
    }
  };

  // 步骤 2: 创意组合生成
  const handleGenerateCombo = () => {
    setComboLoading(true);
    setTimeout(() => {
      const combo: Record<string, string> = {};
      for (const dim of ['角色原型', '场景类型', '冲突类型', '主题方向', '结构框架']) {
        combo[dim] = pick(SEED_POOLS[dim], 2).join('，');
      }
      setComboResult(combo);
      setComboLoading(false);
    }, 400);
  };

  // 步骤 3: 风格参数
  const handleComputeStyle = () => {
    if (!genre) return;
    const params = GENRE_STYLE_PARAMS[genre] || {
      vocabulary_density: 0.55, rhythm: 0.6, sentence_style: 0.55,
      rhetoric_level: 0.55, emotional_temperature: 0.55, dialogue_ratio: 0.55,
    };
    setStyleParams(params);
    const prompt = [
      `【写作风格注入 — ${genre}】`,
      `词汇密度 ${Math.round(params.vocabulary_density * 10)}/10`,
      `叙事节奏 ${Math.round(params.rhythm * 10)}/10`,
      `句式复杂度 ${Math.round(params.sentence_style * 10)}/10`,
      `修辞密度 ${Math.round(params.rhetoric_level * 10)}/10`,
      `情感温度 ${Math.round(params.emotional_temperature * 10)}/10`,
      `对话占比 ${Math.round(params.dialogue_ratio * 100)}%`,
    ].join('\n');
    setCustomStylePrompt(prompt);
  };

  // 步骤 4: 初始化
  const startInit = async () => {
    let pid = projectId;
    if (!pid) {
      const res = await projectApi.create({ name: projectName, genre, description: '' });
      pid = res.data.id;
      setProjectId(pid);
      setProject(res.data);
    }
    setRunning(true);
    setErrors('');
    setProgress({ step: 'preparing', status: 'running', skipped_steps: [], details: {} });

    // 拼接创意思维和风格 prompt 到主题/style
    const comboText = comboResult
      ? Object.entries(comboResult).map(([k, v]) => `${k}: ${v}`).join('; ')
      : '';
    const finalTheme = `${theme || genre + '题材'}，${comboText || ''}`;
    const finalStyle = customStylePrompt || style || '';

    const params = {
      genre,
      theme: selectedRecommendation !== null && researchResult
        ? `${researchResult.recommendations[selectedRecommendation]?.angle || ''} - ${finalTheme}`
        : finalTheme,
      style: finalStyle,
    };

    const response = await fetch(`/api/v1/projects/${pid}/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      setRunning(false);
      setErrors(`初始化失败：${text}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      setRunning(false);
      message.error('无法读取响应');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const raw = line.slice(6);
            if (raw === '[DONE]') continue;
            try {
              const msg = JSON.parse(raw);
              if (msg.type === 'step') {
                setProgress(prev => ({ ...prev, step: msg.step, status: msg.status, details: { ...prev.details, [msg.step]: msg.details } }));
              } else if (msg.type === 'done') {
                setProgress({ step: 'complete', status: 'completed', skipped_steps: msg.skipped_steps, details: progress.details });
              } else if (msg.type === 'error') {
                setErrors(msg.error);
              }
            } catch {}
          }
        }
      }
      setStep(5);
      setRunning(false);
      message.success('项目初始化完成！');
    } catch (e: any) {
      setErrors(`初始化中断：${e?.message || '未知错误'}`);
      setRunning(false);
    } finally {
      await reader.cancel();
    }
  };

  const handleNext = () => {
    if (step === 4) { startInit(); return; }
    setStep(step + 1);
  };

  const handleFinish = () => {
    navigate(`/projects/${projectId}/workshop`);
  };

  const genreOptions = templates.length
    ? templates.map(t => ({ label: `${t.name} (${t.category})`, value: t.name }))
    : DEFAULT_GENRES.map(g => ({ label: g, value: g }));

  const handleGenreChange = (v: string) => {
    setGenre(v);
    if (v) {
      templateApi.search(v).then(r => setGenreTemplate(r.data)).catch(() => setGenreTemplate(null));
    } else {
      setGenreTemplate(null);
    }
  };

  const canNext = (): boolean => {
    if (step === 0) return !!genre && projectName.trim().length >= 2;
    if (step === 1) return !!researchResult;
    if (step === 2) return !!comboResult;
    if (step === 3) return !!styleParams;
    return true;
  };

  if (loading) {
    return (
      <AppLayout projectId={projectId || undefined}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={projectId || undefined}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 8 }}>
          {isCreating ? '新建项目' : `初始化：${project?.name || '未知项目'}`}
        </Title>
        <Paragraph type="secondary">
          从题材调研到风格设定，逐步搭建你的小说蓝图。
        </Paragraph>

        <Steps current={step} items={wizardSteps} style={{ marginBottom: 24 }} size="small" />

        <Card>
          {/* ====================== 步骤 0: 项目信息 ====================== */}
          {step === 0 && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Title level={5}>项目信息</Title>
              <Row gutter={16}>
                <Col span={12}>
                  <Text strong>项目名称</Text>
                  <Input
                    placeholder="例如：《元戒》《星河纪》"
                    value={projectName}
                    onChange={e => setProjectName(e.target.value)}
                    allowClear
                  />
                </Col>
                <Col span={12}>
                  <Text strong>题材</Text>
                  <Select
                    style={{ width: '100%' }}
                    placeholder="请选择题材"
                    value={genre}
                    onChange={handleGenreChange}
                    options={genreOptions}
                    showSearch
                    optionFilterProp="label"
                    allowClear
                  />
                </Col>
              </Row>
              {genreTemplate && (
                <Card size="small">
                  <Space direction="vertical" size={4}>
                    <Text><Text strong>类别：</Text>{genreTemplate.category}</Text>
                    {genreTemplate.config?.pacing && (
                      <Text><Text strong>节奏：</Text>每章约 {genreTemplate.config.pacing.typical_chapter_word_count} 字</Text>
                    )}
                  </Space>
                </Card>
              )}
            </Space>
          )}

          {/* ====================== STEP 1：选题调研 ====================== */}
          {step === 1 && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Title level={5}>AI 选题调研</Title>
              <Text type="secondary">
                基于当前网文市场趋势，AI 分析「{genre}」题材的竞争环境、读者偏好，并推荐 3 个差异化切入点方案。
              </Text>
              {!researchResult ? (
                <div style={{ textAlign: 'center', padding: 30 }}>
                  <Button
                    type="primary"
                    size="large"
                    icon={<SearchOutlined />}
                    loading={researchLoading}
                    onClick={handleResearch}
                  >
                    开始调研
                  </Button>
                </div>
              ) : (
                <div>
                  <Card size="small" title="市场概况" style={{ marginBottom: 12, background: '#fafafa' }}>
                    <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>
                      {researchResult.market_summary}
                    </Paragraph>
                  </Card>
                  {researchResult.hot_trends?.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <Text strong style={{ fontSize: 12 }}>热点趋势：</Text>
                      <div style={{ marginTop: 4 }}>
                        {researchResult.hot_trends.map((t: string, i: number) => (
                          <Tag key={i} color="blue" style={{ margin: 2, padding: '4px 8px', fontSize: 12 }}>
                            {t}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
                  <Divider style={{ margin: '12px 0' }} />
                  <Text strong>推荐切入点（请选择一个）</Text>
                  <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
                    {researchResult.recommendations?.map((rec: any, i: number) => (
                      <Col xs={24} key={i}>
                        <Card
                          hoverable
                          size="small"
                          style={{
                            borderLeft: selectedRecommendation === i ? '4px solid #5B9BD5' : '4px solid #e8e8e8',
                            background: selectedRecommendation === i ? '#f0f5ff' : 'white',
                          }}
                          onClick={() => setSelectedRecommendation(i)}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                              <Text strong style={{ fontSize: 14 }}>{rec.angle}</Text>
                            </div>
                            <Tag color={selectedRecommendation === i ? 'blue' : 'default'}>
                              {rec.score != null ? `匹配度 ${(rec.score * 100).toFixed(0)}%` : '—'}
                            </Tag>
                          </div>
                          <Typography.Paragraph
                            type="secondary"
                            style={{ fontSize: 13, marginTop: 8, marginBottom: 4 }}
                          >
                            {rec.description}
                          </Typography.Paragraph>
                          <Text type="secondary" italic style={{ fontSize: 12}}>
                            📌 {rec.entry_point}
                          </Text>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </div>
              )}
            </Space>
          )}

          {/* ====================== 步骤 2：创意激发 ====================== */}
          {step === 2 && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Title level={5}>创意激发 + 主题填充</Title>
              {!comboResult ? (
                <div style={{ textAlign: 'center', padding: 30 }}>
                  <Button
                    type="primary"
                    icon={<BulbOutlined />}
                    loading={comboLoading}
                    onClick={handleGenerateCombo}
                  >
                    生成创意组合
                  </Button>
                </div>
              ) : (
                <>
                  <Row gutter={8}>
                    {Object.entries(comboResult).map(([dim, val]) => (
                      <Col xs={24} sm={12} key={dim}>
                        <Card size="small" bordered style={{ borderLeft: `4px solid ${({ '角色原型': '#906dd6', '场景类型': '#1890ff' })[dim] || '#ccc'}` }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>{dim}</Text>
                          <div><Text strong>{val}</Text></div>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                  <div>
                    <Text strong>主题倾向（可修改）</Text>
                    <TextArea
                      rows={3}
                      placeholder="例如：孤独与救赎 / 热血逆袭 / 权谋争霸……"
                      value={theme}
                      onChange={e => setTheme(e.target.value)}
                      maxLength={500}
                    />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      填入你的故事想表达的核心主题，AI 将围绕这个主题生成故事核心。
                    </Text>
                  </div>
                </>
              )}
            </Space>
          )}

          {/* ====================== 步骤 3：风格设定 ====================== */}
          {step === 3 && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Title level={5}>风格参数 + 写作指导</Title>
              {!styleParams ? (
                <Button type="primary" onClick={handleComputeStyle}>{`为《genre》生成风格参数`}</Button>
              ) : (
                <div>
                  <Card size="small" title="风格写作注入 Prompt" style={{ background: '#fffbe6', marginBottom: 12 }}>
                    <Typography.Paragraph
                      style={{ whiteSpace: 'pre-wrap', fontSize: 13, fontFamily: 'monospace', margin: 0 }}
                    >
                      {customStylePrompt}
                    </Typography.Paragraph>
                  </Card>
                  <Text type="secondary">
                    此风格设定会与上面的选词和主题一起被注入项目初始化，且可后续在「写作模块」手动修改。
                  </Text>
                </div>
              )}
            </Space>
          )}

          {/* ====================== 步骤 4：确认 + 初始化 ====================== */}
          {step === 4 && (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Title level={5}>确认所有设置，开始初始化</Title>
              <Card size="small">
                <Space direction="vertical" size={4}>
                  <Text><Text strong>项目名称：</Text>{projectName}</Text>
                  <Text><Text strong>题材：</Text>{genre}</Text>
                  {researchResult && selectedRecommendation !== null && (
                    <Text><Text strong>切入点：</Text>{researchResult.recommendations[selectedRecommendation]?.angle}</Text>
                  )}
                  <Text><Text strong>主题：</Text>{theme || '未填写'}</Text>
                  <Text><Text strong>风格 Prompt：</Text>{customStylePrompt ? '已设定' : '未设定'}</Text>
                </Space>
              </Card>
              <Progress
                              percent={progress.status === 'completed' ? 100 : progress.status === 'running' ? 50 : 0}
                              active={progress.status === 'running' ? 'active' : 'normal'}
                              format={() => <Text type="secondary">{progress.step}</Text>}
                            />
              {errors && <Alert message="错误" error={errors} type="error" showIcon />}
            </Space>
          )}

          {/* ====================== 步骤 5：完成 ====================== */}
          {step === 5 && (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a' }} />
              <Title level={4} style={{ marginTop: 12 }}>初始化完成！</Title>
              <Paragraph>
                              故事核心、世界观、人物和大纲已生成。
                              {progress.skipped_steps?.length > 0 && (
                                <Text type="secondary">其余步骤已跳过。</Text>
                              )}
                            </Paragraph>
            </div>
          )}

          {/* ====================== 底部导航 ====================== */}
          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            <Button
              onClick={() => setStep(step - 1)}
              disabled={step === 0 || (step === 4 && running)}
            >
              上一步
            </Button>
            <Space>
              {step === 4 && (
                <Button
                  type="primary"
                  size="large"
                  icon={<ThunderboltOutlined />}
                  loading={running}
                  onClick={startInit}
                  disabled={!!errors}
                />
              )}
              {step !== 4 && step !== 5 && (
                <Button
                  type="primary"
                  icon={step === 0 ? <PlayCircleOutlined /> : undefined}
                  loading={step === 0 ? creatingProject : false}
                  onClick={step === 0 ? handleCreateProject : handleNext}
                  disabled={!canNext()}
                >
                  {step === 0 ? '创建并继续' : step === 3 ? '开始初始化' : '下一步'}
                </Button>
              )}
            </Space>
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}