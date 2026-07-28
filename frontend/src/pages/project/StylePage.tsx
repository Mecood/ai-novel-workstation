// @ts-nocheck
import { useMemo, useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Spin, Typography, Row, Col, Button, Tag, message, Space, Descriptions,
  Select, Slider, Input, Divider, InputNumber,
} from 'antd';
import {
  RocketOutlined, SwapOutlined, SettingOutlined, CopyOutlined,
  ThunderboltOutlined, EditOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi, chapterApi } from '../../services/api';
import type { Project, Chapter } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

const GENRES = ['仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险'];

// 六维度参数定义
const PARAM_DEFS = [
  { key: 'vocabulary_density', label: '词汇密度', desc: '用词浓稠程度，越高越文雅' },
  { key: 'rhythm', label: '节奏速度', desc: '叙事推进快慢，越高越紧凑' },
  { key: 'sentence_style', label: '句式复杂度', desc: '长短句交织程度' },
  { key: 'rhetoric_level', label: '修辞程度', desc: '比喻、排比等修辞密度' },
  { key: 'emotional_temperature', label: '情感温度', desc: '情感表达的浓烈程度' },
  { key: 'dialogue_ratio', label: '对话占比', desc: '对话与叙述的比例' },
];

const PARAM_LABELS: Record<string, string> = {};
PARAM_DEFS.forEach(d => { PARAM_LABELS[d.key] = d.label; });

// 各题材的默认风格参数
const GENRE_BASE: Record<string, Record<string, number>> = {
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

function computeStyleParams(genre: string): Record<string, number> {
  return GENRE_BASE[genre] || {
    vocabulary_density: 0.55, rhythm: 0.6, sentence_style: 0.55,
    rhetoric_level: 0.55, emotional_temperature: 0.55, dialogue_ratio: 0.55,
  };
}

// 把数值映射到 1-10 分
function toScore(val: number): number {
  return Math.round(val * 10);
}

// 可视化条
function genreBar(val: number): string {
  const filled = Math.round(val * 10);
  return '█'.repeat(filled) + '░'.repeat(10 - filled);
}

// 生成风格指导段落
function buildStylePromptSection(params: Record<string, number>, genre: string): string {
  return [
    `【写作风格注入 — ${genre}】`,
    ``,
    `▼ 整体基调：`,
    `  词汇密度 ${toScore(params.vocabulary_density)}/10 — ${params.vocabulary_density > 0.65 ? '文雅凝练，多用古文词汇与四字短语' : params.vocabulary_density > 0.5 ? '文白夹杂，可读性好' : '口语化，贴近日常'}`,
    `  叙事节奏 ${toScore(params.rhythm)}/10 — ${params.rhythm > 0.75 ? '快节奏，大量短句推进' : params.rhythm > 0.5 ? '节奏适中，张弛有度' : '慢节奏，铺陈细腻'}`,
    `  句式复杂度 ${toScore(params.sentence_style)}/10 — ${params.sentence_style > 0.7 ? '长句为主，层层嵌套' : params.sentence_style > 0.5 ? '长短交错' : '短句为主，利落干脆'}`,
    `  修辞密度 ${toScore(params.rhetoric_level)}/10 — ${params.rhetoric_level > 0.7 ? '比喻、排比密集，意象丰富' : params.rhetoric_level > 0.45 ? '适度修辞，点到为止' : '白描手法，少用修辞'}`,
    `  情感温度 ${toScore(params.emotional_temperature)}/10 — ${params.emotional_temperature > 0.7 ? '情感浓烈，直抒胸臆' : params.emotional_temperature > 0.45 ? '情感内敛，余味悠长' : '冷静克制，物哀之美'}`,
    `  对话占比 ${Math.round(params.dialogue_ratio * 100)}% — ${params.dialogue_ratio > 0.6 ? '对话驱动叙事' : params.dialogue_ratio > 0.45 ? '对话与叙述均衡' : '以叙述为主，对话精炼'}`,
    ``,
    `▼ 写作要点：`,
    `  1. 开篇 ${params.rhythm > 0.6 ? '直接切入冲突' : '先用环境与人物做铺垫'}，`,
    `  2. 人物对话 ${params.dialogue_ratio > 0.5 ? '是推进情节的主力' : '点到为止，以行动替语言'}`,
    `  3. 环境描写 ${params.vocabulary_density > 0.6 ? '用四字短语与古文句式' : '白话铺陈，清晰为主'}。`,
    ``,
    `—— 将上述风格设定注入每章写作指令，保持一致的叙事语调。`,
  ].join('\n');
}

// 风格标签
function generateStyleLabels(params: Record<string, number>): string[] {
  const labels: string[] = [];
  if (params.vocabulary_density > 0.65) labels.push('文雅');
  if (params.vocabulary_density < 0.5) labels.push('口语');
  if (params.rhythm > 0.75) labels.push('快进');
  if (params.rhythm < 0.5) labels.push('慢热');
  if (params.rhetoric_level > 0.7) labels.push('意象浓');
  if (params.emotional_temperature > 0.75) labels.push('浓情');
  if (params.emotional_temperature < 0.4) labels.push('克制');
  if (params.dialogue_ratio > 0.6) labels.push('对话体');
  if (params.sentence_style > 0.7) labels.push('长句派');
  if (labels.length === 0) labels.push('均衡');
  return labels;
}

interface StyleResult {
  genre: string;
  params: Record<string, number>;
  stylePrompt: string;
  styleLabels: string[];
}

export default function StylePage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(!!id);
  const standalone = !id;

  // 独立模式：本地风格
  const [styleGenre, setStyleGenre] = useState('仙侠');
  const [editParams, setEditParams] = useState<Record<string, number>>(() => computeStyleParams('仙侠'));
  const [localResult, setLocalResult] = useState<StyleResult | null>(null);

  // 项目模式：章节相关
  const [paramsLoading, setParamsLoading] = useState(false);
  const [serverStyleResult, setServerStyleResult] = useState<any | null>(null);
  const [variantOptions, setVariantOptions] = useState<any[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null);
  const [variantResult, setVariantResult] = useState<any | null>(null);
  const [variantLoading, setVariantLoading] = useState(false);

  // 独立模式：风格预览实时更新
  const localStylePreview = useMemo(() => {
    const prompt = buildStylePromptSection(editParams, styleGenre);
    const labels = generateStyleLabels(editParams);
    return { genre: styleGenre, params: editParams, stylePrompt: prompt, styleLabels: labels };
  }, [styleGenre, editParams]);

  // 独立模式：生成完整风格指导
  const handleGenerateStyle = useCallback(() => {
    setLocalResult(localStylePreview);
  }, [localStylePreview]);

  // 切换题材时重置参数
  const handleGenreChange = useCallback((g: string) => {
    setStyleGenre(g);
    setEditParams(computeStyleParams(g));
  }, []);

  // 滑块变化
  const handleParamChange = useCallback((key: string, val: number) => {
    setEditParams(prev => ({ ...prev, [key]: val }));
  }, []);

  // 重置为本题材默认值
  const handleResetParams = useCallback(() => {
    setEditParams(computeStyleParams(styleGenre));
  }, [styleGenre]);

  // 项目模式加载
  useEffect(() => {
    if (!id) { setLoading(false); return; }
    Promise.all([
      projectApi.get(id),
      chapterApi.list(id),
    ])
      .then(([proj, chs]) => {
        setProject(proj?.data || null);
        setChapters(Array.isArray(chs?.data) ? chs.data.sort((a: any, b: any) => a.chapter_number - b.chapter_number) : []);
      })
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const loadServerParams = useCallback(async () => {
    if (!id || !project) return;
    setParamsLoading(true);
    try {
      const resp = await fetch(`/v1/projects/${id}/style/params?genre=${encodeURIComponent(project.genre)}`);
      if (!resp.ok) throw new Error('失败');
      setServerStyleResult(await resp.json());
    } catch {
      message.error('加载风格参数失败');
    } finally {
      setParamsLoading(false);
    }
  }, [id, project]);

  const loadVariantOptions = useCallback(async () => {
    if (!id || !project) return;
    try {
      const resp = await fetch(`/v1/projects/${id}/style/variants/options?genre=${encodeURIComponent(project.genre)}`);
      if (!resp.ok) throw new Error('失败');
      const data = await resp.json();
      setVariantOptions(Array.isArray(data) ? data : []);
    } catch {
      message.error('加载变体选项失败');
    }
  }, [id, project]);

  const generateVariants = useCallback(async () => {
    if (!id || !selectedChapter) {
      message.warning('请先选择章节');
      return;
    }
    setVariantLoading(true);
    try {
      const resp = await fetch(
        `/v1/projects/${id}/style/variants?chapter_id=${selectedChapter}&genre=${encodeURIComponent(project?.genre || '')}&variant_ids=serious&variant_ids=light&variant_ids=poetic`,
        { method: 'POST' }
      );
      if (!resp.ok) throw new Error('失败');
      setVariantResult(await resp.json());
    } catch {
      message.error('变体生成失败');
    } finally {
      setVariantLoading(false);
    }
  }, [id, project, selectedChapter]);

  if (loading) {
    return (
      <AppLayout projectId={id}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => message.success('已复制到剪贴板'));
  };

  // ============ 渲染内容 ============
  const content = (
    <>
      <Title level={3} style={{ marginBottom: 24 }}>
        <RocketOutlined style={{ marginRight: 8 }} />
        风格工厂
        {(project || standalone) && (
          <Tag style={{ marginLeft: 12 }} color="purple">
            {project?.genre || styleGenre}
          </Tag>
        )}
      </Title>

      <Row gutter={[16, 16]}>
        {/* 左侧：风格参数 */}
        <Col xs={24} lg={12}>
          <Card
            title={<><SettingOutlined style={{ marginRight: 6 }} />题材风格参数</>}
            extra={standalone ? (
              <Space>
                <Select value={styleGenre} onChange={handleGenreChange} style={{ width: 110 }} size="small">
                  {GENRES.map(g => <Select.Option key={g} value={g}>{g}</Select.Option>)}
                </Select>
                <Button size="small" onClick={handleResetParams}>重置</Button>
              </Space>
            ) : (
              <Button size="small" onClick={loadServerParams} loading={paramsLoading}>加载项目风格</Button>
            )}
          >
            {/* 风格标签 */}
            {standalone && (
              <div style={{ marginBottom: 14 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>题材风格标签：</Text>
                <div style={{ marginTop: 6 }}>
                  {localStylePreview.styleLabels.map(l => (
                    <Tag key={l} color="purple" style={{ margin: 2, fontSize: 12, padding: '3px 8px' }}>{l}</Tag>
                  ))}
                </div>
              </div>
            )}

            {/* 六维度滑块 */}
            {standalone && (
              <div>
                {PARAM_DEFS.map(def => (
                  <div key={def.key} style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text strong style={{ fontSize: 12 }}>{def.label}</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {genreBar(editParams[def.key])} ({toScore(editParams[def.key])}/10)
                      </Text>
                    </div>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{def.desc}</Text>
                    <Slider
                      min={0}
                      max={1}
                      step={0.05}
                      value={editParams[def.key]}
                      onChange={(val: number) => handleParamChange(def.key, val)}
                      style={{ margin: '4px 0 0' }}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* 项目模式：展示服务器参数 */}
            {serverStyleResult && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  解析题材：{serverStyleResult.resolved_genre || serverStyleResult.genre}
                </Text>
                <div style={{ marginTop: 12 }}>
                  {Object.entries(serverStyleResult.params || {}).map(([key, val]: [string, any]) => (
                    <div key={key} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <Text strong style={{ fontSize: 12 }}>{PARAM_LABELS?.[key] || key}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>{genreBar(Number(val))}</Text>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 独立模式：生成按钮 */}
            {standalone && (
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                block
                onClick={handleGenerateStyle}
                style={{ marginTop: 8 }}
              >
                生成风格指导
              </Button>
            )}
          </Card>
        </Col>

        {/* 右侧：风格产出 */}
        <Col xs={24} lg={12}>
          {standalone ? (
            <Card
              title={<><EditOutlined style={{ marginRight: 6 }} />风格指导输出</>}
              extra={
                localResult && (
                  <Space>
                    <Button size="small" onClick={() => handleCopy(localResult.stylePrompt)}>复制 Prompt</Button>
                    <Button size="small" type="primary" onClick={() => navigator.clipboard.writeText(localResult.stylePrompt)}>
                      应用于草稿
                    </Button>
                  </Space>
                )
              }
            >
              {!localResult ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <EditOutlined style={{ fontSize: 36, color: '#5B9BD5', marginBottom: 12 }} />
                  <Paragraph type="secondary">
                    在左侧选择题材、调整六维度参数，点击「生成风格指导」获取写作风格说明。
                    <br />
                    生成的 Prompt 段落可直接粘贴到写作模块中使用。
                  </Paragraph>
                </div>
              ) : (
                <>
                  <Card
                    size="small"
                    title="写作风格注入 Prompt"
                    style={{ background: '#fffbe6' }}
                  >
                    <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'monospace' }}>
                      {localResult.stylePrompt}
                    </Paragraph>
                  </Card>
                </>
              )}
            </Card>
          ) : (
            <Card title={<><SwapOutlined style={{ marginRight: 6 }} />章节风格变体</>}>
              {variantOptions.length === 0 ? (
                <Text type="secondary">暂无可用变体风格。先点击「加载变体选项」。</Text>
              ) : (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>可用变体风格：</Text>
                    <div style={{ marginTop: 4 }}>
                      {variantOptions.map((v: any) => <Tag key={v.id} color="blue">{v.label}</Tag>)}
                    </div>
                  </div>
                  <Select
                    style={{ width: '100%' }}
                    placeholder="选择章节"
                    value={selectedChapter}
                    onChange={setSelectedChapter}
                    options={chapters.map(ch => ({
                      value: ch.id,
                      label: `第${ch.chapter_number}章 ${ch.title || ''}`.trim(),
                    }))}
                  />
                  <Button
                    type="primary"
                    icon={<SwapOutlined />}
                    loading={variantLoading}
                    onClick={generateVariants}
                    style={{ marginTop: 12 }}
                    block
                  >
                    生成风格变体
                  </Button>
                </div>
              )}
              {variantResult && (
                <div style={{ marginTop: 16 }}>
                  {Object.entries(variantResult.variants || {}).map(([vid, vdata]: [string, any]) => (
                    <Card key={vid} size="small" title={`🎭 ${vdata.label || vid}`} style={{ marginBottom: 8, background: '#f9f9f9' }}>
                      <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'monospace', maxHeight: 300, overflowY: 'auto' }}>
                        {vdata.prompt}
                      </Paragraph>
                    </Card>
                  ))}
                </div>
              )}
            </Card>
          )}
        </Col>
      </Row>
    </>
  );

  return <AppLayout projectId={id || undefined}>{content}</AppLayout>;
};
