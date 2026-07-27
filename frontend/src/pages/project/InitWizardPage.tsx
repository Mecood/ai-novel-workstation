// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Steps, Button, Select, Input, Space, message, Typography, Divider, Spin, Alert, Progress, Form, Row, Col } from 'antd';
import { RocketOutlined, BookOutlined, ThunderboltOutlined, CheckCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { api, projectApi, templateApi } from '../../services/api';
import type { GenreTemplate } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const WIZARD_STEPS_NEW = [
  { key: 0, title: '项目与题材' },
  { key: 1, title: '主题与风格' },
  { key: 2, title: '参考书拆解（可选）' },
  { key: 3, title: '开始初始化' },
  { key: 4, title: '完成' },
];

const WIZARD_STEPS_EXISTING = [
  { key: 0, title: '选择题材' },
  { key: 1, title: '主题与风格' },
  { key: 2, title: '参考书拆解（可选）' },
  { key: 3, title: '开始初始化' },
  { key: 4, title: '完成' },
];

const DEFAULT_GENRES = [
  '仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险',
];

export default function InitWizardPage() {
  const { id: existingId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // For /projects/new route we create project; for /projects/:id/init-wizard we use existing
  const isCreating = !existingId;

  const [loading, setLoading] = useState(isCreating ? false : true);
  const [project, setProject] = useState(null);
  const [projectId, setProjectId] = useState(existingId || '');
  const [templates, setTemplates] = useState([]);

  // Form state
  const [step, setStep] = useState(0);
  const [projectName, setProjectName] = useState('');
  const [genre, setGenre] = useState('');
  const [genreTemplate, setGenreTemplate] = useState<GenreTemplate | null>(null);
  const [theme, setTheme] = useState('');
  const [style, setStyle] = useState('');
  const [referencePatterns, setReferencePatterns] = useState(null);

  // Init progress
  const [running, setRunning] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [errors, setErrors] = useState('');
  const [progress, setProgress] = useState({
    step: 'preparing', status: 'waiting', skipped_steps: [], details: {},
  });

  const wizardSteps = (isCreating ? WIZARD_STEPS_NEW : WIZARD_STEPS_EXISTING).map((s, idx) => ({
    ...s,
    status: idx > step ? 'wait' : idx < step ? 'finish' : 'process',
  }));

  // Load seed templates + existing project info
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
      }).catch(() => {
        message.error('加载项目信息失败');
        navigate('/');
      }).finally(() => setLoading(false));
    } else {
      templateApi.list().then(t => setTemplates(Array.isArray(t.data) ? t.data : [])).catch(() => {});
    }
  }, [isCreating, existingId, navigate]);

  const canNext = () => {
    if (isCreating && step === 0) return !!genre && projectName.trim().length >= 2;
    if (step === 0) return !!genre;
    if (step === 1) return theme.trim().length >= 4;
    return true;
  };

  const handleNext = () => {
    if (step === 3) { startInit(); return; }
    // If step 0 in create mode and project not yet created, create now
    if (isCreating && step === 0 && canNext() && !projectId) {
      createProject();
      return;
    }
    setStep(step + 1);
  };

  const createProject = async () => {
    setCreatingProject(true);
    try {
      const res = await projectApi.create({ name: projectName, genre, description: '' });
      const pid = res.data.id;
      setProjectId(pid);
      setProject(res.data);
      message.success('项目已创建');
      setStep(1);
    } catch (e) {
      message.error('创建项目失败');
    } finally {
      setCreatingProject(false);
    }
  };

  const startInit = async () => {
    const pid = projectId;
    if (!pid) return;
    setRunning(true);
    setErrors('');
    setProgress({ step: 'preparing', status: 'running', skipped_steps: [], details: {} });

    const params = { genre, theme, style, reference_patterns: referencePatterns };
    const response = await fetch(`/api/v1/projects/${pid}/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      setRunning(false);
      setErrors(`初始化失败：${text}`);
      message.error('初始化失败');
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
    const controller = new AbortController();

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
            } catch { /* ignore */ }
          }
        }
      }
      setStep(4);
      setRunning(false);
      message.success('项目初始化完成！');
    } catch (e) {
      setErrors(`初始化中断：${e?.message || '未知错误'}`);
      setRunning(false);
      message.error('初始化中断');
    } finally {
      await reader.cancel();
      controller.abort();
    }
  };

  const handleFinish = () => {
    const targetId = projectId || existingId;
    navigate(`/projects/${targetId}/workshop`);
  };

  const genreOptions = templates.length
    ? templates.map((t) => ({ label: `${t.name} (${t.category})`, value: t.name }))
    : DEFAULT_GENRES.map((g) => ({ label: g, value: g }));

  const onGenreChange = (v) => {
    setGenre(v);
    if (v) {
      templateApi.search(v).then(r => setGenreTemplate(r.data)).catch(() => setGenreTemplate(null));
    } else {
      setGenreTemplate(null);
    }
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
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 8 }}>
          {isCreating ? '新建项目' : `初始化：${project?.name || '未知项目'}`}
        </Title>
        <Paragraph type="secondary">
          {isCreating
            ? '填写项目信息、选择题材与风格，AI 将自动生成故事核心、世界观、角色和大纲。'
            : '按引导完成题材、主题和风格设置，AI 将自动为您生成故事核心、世界观、角色和大纲。'}
        </Paragraph>

        <Steps current={step} items={wizardSteps} style={{ marginBottom: 32 }} size="small" />

        <Card>
          {/* Step 0: Project name + genre (new project) or genre only (existing) */}
          {step === 0 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>{isCreating ? '项目信息' : '选择题材'}</Title>
              {isCreating && (
                <div>
                  <Text>项目名称</Text>
                  <Input
                    placeholder="例如：《元戒》《星河纪》"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    style={{ width: 360 }}
                    allowClear
                  />
                </div>
              )}
              <div>
                <Text>题材</Text>
                <Select
                  style={{ width: 300 }}
                  placeholder="请选择题材"
                  value={genre}
                  onChange={onGenreChange}
                  options={genreOptions}
                  showSearch
                  optionFilterProp="label"
                  allowClear
                />
              </div>
              {genreTemplate && (
                <Card size="small" style={{ marginTop: 8 }}>
                  <Space direction="vertical" size={8}>
                    <Text><Text strong>类别：</Text>{genreTemplate.category}</Text>
                    {genreTemplate.config && (
                      <>
                        {genreTemplate.config.pacing && (
                          <Text><Text strong>节奏：</Text>每章约 {genreTemplate.config.pacing.typical_chapter_word_count} 字，{genreTemplate.config.pacing.coolpoint_interval_chapters} 章一爽点</Text>
                        )}
                        {genreTemplate.config.style && (
                          <Text><Text strong>风格：</Text>{genreTemplate.config.style.vocabulary}，对话占比 {Math.round(genreTemplate.config.style.dialogue_ratio * 100)}%</Text>
                        )}
                        {genreTemplate.config.tropes && genreTemplate.config.tropes.length > 0 && (
                          <Text><Text strong>经典套路：</Text>{genreTemplate.config.tropes.join('、')}</Text>
                        )}
                      </>
                    )}
                  </Space>
                </Card>
              )}
              <Text type="secondary">{isCreating ? '项目名和题材决定故事的基底。' : '题材决定了故事的世界基底和叙事基调。'}</Text>
            </Space>
          )}

          {/* Step 1: Theme + style */}
          {step === 1 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>主题与风格</Title>
              <div>
                <Text>主题倾向</Text>
                <TextArea
                  rows={3}
                  placeholder="例如：探讨孤独与救赎、热血逆袭、权谋争霸、轻松日常……"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  maxLength={500}
                  showCount
                />
              </div>
              <div>
                <Text>写作风格</Text>
                <TextArea
                  rows={2}
                  placeholder="例如：文风轻松诙谐、节奏紧凑、悬疑感强、诗意抒情……（可选）"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  maxLength={300}
                  showCount
                />
              </div>
            </Space>
          )}

          {/* Step 2: Reference deconstruction */}
          {step === 2 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>参考书拆解（可选）</Title>
              <Alert
                message="如有参考书拆解结果，请在此粘贴；AI 将吸收其中的结构/节奏/设定手法。"
                type="info"
              />
              <div>
                <Text>参考书拆解 JSON（可选）</Text>
                <TextArea
                  rows={4}
                  placeholder='粘贴 deconstruction 模块的拆解 JSON'
                  value={referencePatterns ? JSON.stringify(referencePatterns, null, 2) : ''}
                  onChange={(e) => {
                    try { setReferencePatterns(JSON.parse(e.target.value || '{}')); }
                    catch { setReferencePatterns(e.target.value || null); }
                  }}
                />
              </div>
              <Text type="secondary">此步骤完全可选，跳过不会影响初始化。</Text>
            </Space>
          )}

          {/* Step 3: Start init */}
          {step === 3 && (
            <Space direction="vertical" size={20} style={{ width: '100%' }}>
              <Title level={5}>确认并开始初始化</Title>
              <Card size="small">
                <Space direction="vertical" size={8}>
                  {isCreating && <Text><Text strong>项目名称：</Text>{projectName || '未填写'}</Text>}
                  <Text><Text strong>题材：</Text>{genre || '未选择'}</Text>
                  <Text><Text strong>主题：</Text>{theme || '未填写'}</Text>
                  <Text><Text strong>风格：</Text>{style || '未填写'}</Text>
                  <Text><Text strong>参考拆解：</Text>{referencePatterns ? '已提供' : '无'}</Text>
                </Space>
              </Card>
              <Divider />
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text>初始化进度</Text>
                  <Text type="secondary">{running ? '执行中...' : '待开始'}</Text>
                </div>
                <Progress
                  percent={progress.status === 'completed' ? 100 : progress.status === 'running' ? 50 : 0}
                  status={progress.status === 'running' ? 'active' : 'normal'}
                  style={{ flex: 1 }}
                />
                {progress.step && progress.step !== 'preparing' && (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {['story_core', 'worldview', 'characters', 'outline'].map((s) => {
                      const st = progress.details?.[s]?.type || (progress.step === s ? 'running' : 'waiting');
                      const statusMap = { generated: 'completed', skipped: 'skipped', running: 'running', waiting: 'waiting' };
                      return <span key={s}>{s}: {statusMap[st] || st}</span>;
                    })}
                  </div>
                )}
                {errors && (
                  <Alert message="错误" description={errors} type="error" showIcon />
                )}
              </Space>
            </Space>
          )}

          {/* Step 4: Done */}
          {step === 4 && (
            <Space direction="vertical" size={16} style={{ textAlign: 'center', padding: 20 }}>
              <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a' }} />
              <Title level={4}>初始化完成！</Title>
              <Paragraph type="secondary">
                故事核心、世界观、角色和大纲已生成。
                {progress.skipped_steps?.length > 0 && (
                  <> 已跳过步骤：{progress.skipped_steps.join('、')}</>
                )}
              </Paragraph>
              <Button type="primary" size="large" icon={<RocketOutlined />} onClick={handleFinish}>
                前往项目工坊
              </Button>
            </Space>
          )}

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            <Button
              onClick={() => { if (step === 3 && running) return; setStep(step - 1); }}
              disabled={step === 0 || (step === 3 && running)}
            >
              上一步
            </Button>
            <Space>
              {step === 3 && (
                <Button
                  type="primary"
                  size="large"
                  icon={<ThunderboltOutlined />}
                  loading={running}
                  onClick={startInit}
                  disabled={running}
                >
                  {running ? '初始化中...' : '开始初始化'}
                </Button>
              )}
              {step !== 3 && step !== 4 && (
                <Button
                  type="primary"
                  icon={isCreating && step === 0 ? <PlayCircleOutlined /> : undefined}
                  loading={isCreating && step === 0 ? creatingProject : false}
                  onClick={handleNext}
                  disabled={!canNext() || (isCreating && step === 0 && creatingProject)}
                >
                  {isCreating && step === 0 ? '创建并继续' : step === 2 ? '下一步：开始初始化' : '下一步'}
                </Button>
              )}
            </Space>
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}