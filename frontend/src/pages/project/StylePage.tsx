// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, Typography, Row, Col, Button, Tag, message, Space, Descriptions, Select } from 'antd';
import { RocketOutlined, SwapOutlined, SettingOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi, chapterApi } from '../../services/api';
import type { Project, Chapter } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

interface StyleParams {
  genre: string;
  resolved_genre: string;
  params: Record<string, number>;
  style_prompt_section: string;
}

interface VariantOption {
  id: string;
  label: string;
  prompt_addition: string;
}

interface VariantResult {
  genre: string;
  variant_count: number;
  variants: Record<string, { label: string; prompt: string }>;
}

const PARAM_LABELS: Record<string, string> = {
  vocabulary_density: '词汇密度',
  rhythm: '节奏速度',
  sentence_style: '句式复杂度',
  rhetoric_level: '修辞程度',
  emotional_temperature: '情感温度',
  dialogue_ratio: '对话占比',
};

export default function StylePage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);

  // 风格参数
  const [styleParams, setStyleParams] = useState<StyleParams | null>(null);
  const [paramsLoading, setParamsLoading] = useState(false);

  // 变体
  const [variantOptions, setVariantOptions] = useState<VariantOption[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null);
  const [variantResult, setVariantResult] = useState<VariantResult | null>(null);
  const [variantLoading, setVariantLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      projectApi.get(id),
      chapterApi.list(id),
    ])
      .then(([proj, chs]) => {
        setProject(proj.data);
        setChapters(Array.isArray(chs.data) ? chs.data.sort((a, b) => a.chapter_number - b.chapter_number) : []);
      })
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false));
  }, [id]);

  // 取风格参数
  const loadParams = async () => {
    if (!id || !project) return;
    setParamsLoading(true);
    try {
      const resp = await fetch(`/v1/projects/${id}/style/params?genre=${encodeURIComponent(project.genre)}`);
      if (!resp.ok) throw new Error('Request failed');
      setStyleParams(await resp.json());
    } catch {
      message.error('加载风格参数失败');
    } finally {
      setParamsLoading(false);
    }
  };

  // 取变体选项
  const loadVariants = async () => {
    if (!id || !project) return;
    try {
      const resp = await fetch(`/v1/projects/${id}/style/variants/options?genre=${encodeURIComponent(project.genre)}`);
      if (!resp.ok) throw new Error('Request failed');
      const data = await resp.json();
      setVariantOptions(data || []);
    } catch {
      message.error('加载变体选项失败');
    }
  };

  // 生成风格变体
  const generateVariants = async () => {
    if (!id || !selectedChapter) {
      message.warning('请选择章节');
      return;
    }
    setVariantLoading(true);
    try {
      const resp = await fetch(`/v1/projects/${id}/style/variants?chapter_id=${selectedChapter}&genre=${encodeURIComponent(project?.genre || '')}&variant_ids=serious&variant_ids=light&variant_ids=poetic`, { method: 'POST' });
      if (!resp.ok) throw new Error('Request failed');
      setVariantResult(await resp.json());
    } catch {
      message.error('变体生成失败');
    } finally {
      setVariantLoading(false);
    }
  };

  useEffect(() => {
    if (!project) return;
    loadParams();
    loadVariants();
  }, [project]);

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}><Spin size="large" /></div>
      </AppLayout>
    );
  }

  const genreBar = (val: number) => {
    const blocks = '█'.repeat(Math.round(val * 10)) + '░'.repeat(10 - Math.round(val * 10));
    return `${blocks} (${val.toFixed(1)})`;
  };

  return (
    <AppLayout projectId={id!}>
      <Title level={3} style={{ marginBottom: 24 }}>
        <RocketOutlined style={{ marginRight: 8 }} />
        风格工厂
        {project && <Tag style={{ marginLeft: 12 }} color="purple">{project.genre}</Tag>}
      </Title>

      <Row gutter={[16, 16]}>
        {/* 左：风格参数 */}
        <Col xs={24} md={12}>
          <Card
            title={<><SettingOutlined style={{ marginRight: 6 }} />题材风格参数</>}
            loading={paramsLoading}
          >
            {styleParams ? (
              <>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  解析题材：{styleParams.resolved_genre}
                </Text>
                <div style={{ marginTop: 12 }}>
                  {Object.entries(styleParams.params).map(([key, val]) => (
                    <div key={key} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <Text strong style={{ fontSize: 12 }}>{PARAM_LABELS[key] || key}</Text>
                        <Text style={{ fontSize: 12, color: '#888' }}>{genreBar(val)}</Text>
                      </div>
                    </div>
                  ))}
                </div>

                {/* 风格 prompt 段落预览 */}
                <Card size="small" title="注入 Prompt 的风格段落" style={{ marginTop: 16, background: '#fffbe6' }}>
                  <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'monospace' }}>
                    {styleParams.style_prompt_section}
                  </Paragraph>
                </Card>
              </>
            ) : (
              <Text type="secondary">暂无风格参数</Text>
            )}
          </Card>
        </Col>

        {/* 右：风格变体 */}
        <Col xs={24} md={12}>
          <Card
            title={<><SwapOutlined style={{ marginRight: 6 }} />风格变体生成</>}
          >
            {variantOptions.length === 0 ? (
              <Text type="secondary">暂无可用变体风格</Text>
            ) : (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>可用变体风格：</Text>
                  <div style={{ marginTop: 4 }}>
                    {variantOptions.map(v => (
                      <Tag key={v.id} color="blue">{v.label}</Tag>
                    ))}
                  </div>
                </div>

                <Select
                  style={{ width: '100%' }}
                  placeholder="选择章节"
                  value={selectedChapter}
                  onChange={setSelectedChapter}
                  options={chapters.map(ch => ({
                    value: ch.id,
                    label: `第${ch.chapter_number}章 ${ch.title?.replace(/^第\d+章\s*/, '') || ''}`.trim(),
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

                {variantResult && (
                  <div style={{ marginTop: 16 }}>
                    {Object.entries(variantResult.variants).map(([vid, vdata]) => (
                      <Card key={vid} size="small" title={`🎭 ${vdata.label}`} style={{ marginBottom: 8, background: '#f9f9f9' }}>
                        <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'monospace', maxHeight: 300, overflowY: 'auto' }}>
                          {vdata.prompt}
                        </Paragraph>
                      </Card>
                    ))}
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>
    </AppLayout>
  );
}