// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Steps, Button, Select, Input, Space, message, Typography, Divider, Spin, Alert, Progress } from 'antd';
import { RocketOutlined, BookOutlined, ThunderboltOutlined, CheckCircleOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { api, projectApi, templateApi } from '../../services/api';
import type { GenreTemplate } from '../../services/api';
import type { InitStepStatus } from '../../types/init';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const WIZARD_STEPS = [
  { key: 0, title: '选择题材' },
  { key: 1, title: '主题与风格' },
  { key: 2, title: '参考书拆解（可选）' },
  { key: 3, title: '开始初始化' },
  { key: 4, title: '完成' },
];

const DEFAULT_GENRES = [
  '仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险',
];

function statusToStepStatus(status: string): InitStepStatus {
  if (status === 'running') return 'running';
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  return 'waiting';
}

export default function InitWizardPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load seed templates on mount
  useEffect(() => {
    templateApi.seed().catch(() => {});
  }, []);

  // Form state
  const [step, setStep] = useState(0);
  const [genre, setGenre] = useState('');
  const [genreTemplate, setGenreTemplate] = useState<GenreTemplate | null>(null);
  const [genreSearchLoading, setGenreSearchLoading] = useState(false);
  const [theme, setTheme] = useState('');
  const [style, setStyle] = useState('');
  const [referencePatterns, setReferencePatterns] = useState(null);

  // Init progress
  const [running, setRunning] = useState(false);
  const [errors, setErrors] = useState('');
  const [progress, setProgress] = useState({
    step: 'story_core',
    status: 'waiting',
    skipped_steps: [],
    details: {},
  });
  const abortRef = useRef(null);

  // Load project + genre templates
  const loadContext = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [proj, tmpl] = await Promise.all([
        projectApi.get(id),
        templateApi.list().catch(() => ({ data: [] })),
      ]);
      setProject(proj.data);
      setTemplates(Array.isArray(tmpl.data) ? tmpl.data : []);
    } catch {
      message.error('加载项目信息失败');
      navigate('/');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  loadContext();

  // Build steps with status based on init progress
  const wizardSteps = WIZARD_STEPS.map((s, idx) => {
    if (idx > step) return { ...s, status: 'wait' };
    if (idx < step) return { ...s, status: 'finish' };
    return { ...s, status: 'process' };
  });

  const canNext = () => {
    if (step === 0) return !!genre;
    if (step === 1) return theme.trim().length >= 4;
    return true;
  };

  const handleNext = () => {
    if (step === 3) {
      startInit();
      return;
    }
    setStep(step + 1);
  };

  const handleBack = () => {
    if (step === 3 && running) return;
    setStep(step - 1);
  };

  const startInit = async () => {
    if (!id) return;
    setRunning(true);
    setErrors('');
    setProgress({ step: 'preparing', status: 'running', skipped_steps: [], details: {} });

    const params = { genre, theme, style, reference_patterns: referencePatterns };
    const response = await fetch(`/v1/projects/${id}/init`, {
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
      message.error('无法读取初始化响应');
      return;
    }
    const decoder = new TextDecoder();
    let buffer = '';
    const controller = new AbortController();
    abortRef.current = controller;

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
                setProgress({ step: msg.step, status: msg.status, details: { ...progress.details, [msg.step]: msg.details } });
              } else if (msg.type === 'done') {
                setProgress({ step: 'complete', status: 'completed', skipped_steps: msg.skipped_steps, details: progress.details });
              } else if (msg.type === 'error') {
                setErrors(msg.error);
              }
            } catch {
              // ignore raw text
            }
          }
        }
      }
      // Completed
      setStep(4);
      setRunning(false);
      message.success('项目初始化完成！');
    } catch (e) {
      setErrors(`初始化中断：${e?.message || '未知错误'}`);
      setRunning(false);
      message.error('初始化中断');
    } finally {
      await reader.cancel();
    }
  };

  const handleFinish = () => {
    navigate(`/projects/${id}`);
  };

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={id!}>
      <div style={{ maxWidth: 880, margin: '0 auto' }}>
        <Title level={3} style={{ marginBottom: 8 }}>
          初始化项目：{project?.name || '未知项目'}
        </Title>
        <Paragraph type="secondary">
          按引导完成题材、主题和风格设置，AI 将自动为您生成故事核心、世界观、角色和大纲。
        </Paragraph>

        <Steps
          current={step}
          items={wizardSteps}
          style={{ marginBottom: 32 }}
          size="small"
        />

        <Card>
          {step === 0 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>第 1 步：选择题材</Title>
              <Select
                style={{ width: 300 }}
                placeholder="请选择题材"
                value={genre}
                onChange={(v) => {
                  setGenre(v);
                  if (v) {
                    templateApi.search(v).then(r => setGenreTemplate(r.data)).catch(() => setGenreTemplate(null));
                  } else {
                    setGenreTemplate(null);
                  }
                }}
                options={templates.length
                  ? templates.map((t) => ({ label: `${t.name} (${t.category})`, value: t.name }))
                  : DEFAULT_GENRES.map((g) => ({ label: g, value: g }))}
                showSearch
                optionFilterProp="label"
                allowClear
              />
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
              <Text type="secondary">题材决定了故事的世界基底和叙事基调。</Text>
            </Space>
          )}

          {step === 1 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>第 2 步：主题与风格</Title>
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

          {step === 2 && (
            <Space direction="vertical" size={16}>
              <Title level={5}>第 3 步：参考书拆解（可选）</Title>
              <Alert
                message="如有参考书拆解结果，请在此粘贴；AI 将吸收其中的结构/节奏/设定手法。"
                type="info"
              />
              <div>
                <Text>参考书拆解 JSON（可选）</Text>
                <TextArea
                  rows={4}
                  placeholder='粘贴 deconstruction 模块的拆解 JSON，例如：{"structure": "...", "rhythm": "..."}'
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

          {step === 3 && (
            <Space direction="vertical" size={20} style={{ width: '100%' }}>
              <Title level={5}>第 4 步：确认并开始初始化</Title>
              <Card size="small">
                <Space direction="vertical" size={8}>
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
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <Progress
                    percent={
                      progress.status === 'completed' ? 100 :
                      progress.status === 'running' ? 50 : 0
                    }
                    status={progress.status === 'running' ? 'active' : 'normal'}
                    style={{ flex: 1 }}
                  />
                </div>
                {progress.step && progress.step !== 'preparing' && (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {['story_core', 'worldview', 'characters', 'outline'].map((s) => {
                      const st = progress.details?.[s]?.type || (progress.step === s ? 'running' : 'waiting');
                      const statusMap = { generated: 'completed', skipped: 'skipped', running: 'running', waiting: 'waiting' };
                      return (
                        <span key={s}>
                          {s}: {statusMap[st] || st}
                        </span>
                      );
                    })}
                  </div>
                )}
                {errors && (
                  <Alert message="错误" description={errors} type="error" showIcon />
                )}
              </Space>
            </Space>
          )}

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
              onClick={handleBack}
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
                  onClick={handleNext}
                  disabled={!canNext()}
                >
                  {step === 2 ? '下一步：开始初始化' : '下一步'}
                </Button>
              )}
            </Space>
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}
