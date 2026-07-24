// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, Typography, Row, Col, Button, Tag, message, Space, Collapse, Empty } from 'antd';
import { ExperimentOutlined, BuildOutlined, ThunderboltOutlined, BulbOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi } from '../../services/api';
import type { Project } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

interface CombinationResult {
  combination: {
    genre: string;
    complexity: string;
    combo: Record<string, string>;
    idea_prompt: string;
    dimension_counts: Record<string, number>;
  };
}

interface FrameworkInfo {
  name: string;
  description: string;
  step_count: number;
}

interface FrameworkData {
  frameworks: FrameworkInfo[];
  recommended: string[];
}

interface FrameworkDetail {
  name: string;
  description: string;
  steps: { step: number; name: string; desc: string }[];
}

const COMPLEXITY_OPTIONS = [
  { key: 'low', label: '简洁', desc: '聚焦主线，1个核心伏笔', color: '#52c41a' },
  { key: 'medium', label: '标准', desc: '1条支线，2个伏笔', color: '#1890ff' },
  { key: 'high', label: '复杂', desc: '3层伏笔，2条支线，1个核心隐喻', color: '#722ed1' },
];

const DIM_LABELS: Record<string, string> = {
  '角色原型': '角色原型', '场景类型': '场景类型', '冲突类型': '冲突类型',
  '主题方向': '主题方向', '结构框架': '结构框架',
};
const DIM_COLORS: Record<string, string> = {
  '角色原型': '#722ed1', '场景类型': '#1890ff', '冲突类型': '#ff4d4f',
  '主题方向': '#52c41a', '结构框架': '#fa8c16',
};

export default function CreativePage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  // 创意组合
  const [complexity, setComplexity] = useState('medium');
  const [combLoading, setCombLoading] = useState(false);
  const [combination, setCombination] = useState<CombinationResult | null>(null);

  // 情节框架
  const [frameworks, setFrameworks] = useState<FrameworkInfo[]>([]);
  const [recommended, setRecommended] = useState<string[]>([]);
  const [frameworkDetail, setFrameworkDetail] = useState<FrameworkDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      projectApi.get(id),
      fetch(`/v1/projects/${id}/creative/frameworks`).then(r => r.json()),
    ])
      .then(([proj, fw]) => {
        setProject(proj.data);
        setFrameworks(fw.frameworks || []);
        setRecommended(fw.recommended || []);
      })
      .catch(() => message.error('加载项目失败'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleCombine = async () => {
    if (!id) return;
    setCombLoading(true);
    try {
      const resp = await fetch(`/v1/projects/${id}/creative/combine?complexity=${complexity}`, { method: 'POST' });
      if (!resp.ok) throw new Error('Request failed');
      const data: CombinationResult = await resp.json();
      setCombination(data);
    } catch {
      message.error('创意组合生成失败');
    } finally {
      setCombLoading(false);
    }
  };

  const handleFrameworkClick = async (name: string) => {
    if (!id) return;
    setDetailLoading(true);
    try {
      const resp = await fetch(`/v1/projects/${id}/creative/frameworks?name=${encodeURIComponent(name)}`);
      if (!resp.ok) throw new Error('Request failed');
      const data = await resp.json();
      setFrameworkDetail(data.framework || null);
    } catch {
      message.error('框架详情加载失败');
    } finally {
      setDetailLoading(false);
    }
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
      <Title level={3} style={{ marginBottom: 24 }}>
        <BulbOutlined style={{ marginRight: 8 }} />
        创意工坊
        {project && <Tag style={{ marginLeft: 12 }} color="purple">{project.genre}</Tag>}
      </Title>

      <Row gutter={[16, 16]}>
        {/* 左：创意组合 */}
        <Col xs={24} md={14}>
          <Card
            title={<><ExperimentOutlined style={{ marginRight: 6 }} />创意种子组合器</>}
            extra={
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
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  loading={combLoading}
                  onClick={handleCombine}
                >
                  生成组合
                </Button>
              </Space>
            }
          >
            {!combination ? (
              <div style={{ textAlign: 'center', padding: 60 }}>
                <Text type="secondary">
                  点击"生成组合"随机抽取角色原型×场景×冲突×主题×结构，激发创作灵感
                </Text>
                <div style={{ marginTop: 16 }}>
                  {COMPLEXITY_OPTIONS.find(o => o.key === complexity) && (
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      当前复杂度：{COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.label} —
                      {COMPLEXITY_OPTIONS.find(o => o.key === complexity)?.desc}
                    </Text>
                  )}
                </div>
              </div>
            ) : (
              <div>
                {/* 5维度卡片 */}
                <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
                  {Object.entries(combination.combination.combo).map(([dim, val]) => (
                    <Col xs={24} sm={12} key={dim}>
                      <Card size="small" bordered style={{ borderLeft: `3px solid ${DIM_COLORS[dim] || '#ccc'}` }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>{dim}</Text>
                        <div style={{ marginTop: 4, fontSize: 13 }}>
                          {val.split(' — ').length > 1 ? (
                            <>
                              <Text strong>{val.split(' — ')[0]}</Text>
                              <br />
                              <Text type="secondary" style={{ fontSize: 12 }}>{val.split(' — ').slice(1).join(' — ')}</Text>
                            </>
                          ) : (
                            <Text>{val}</Text>
                          )}
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>

                {/* AI prompt */}
                <Card size="small" title="创意激发 Prompt" style={{ background: '#f6ffed' }}>
                  <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>
                    {combination.combination.idea_prompt}
                  </Paragraph>
                </Card>
              </div>
            )}
          </Card>
        </Col>

        {/* 右：情节框架 */}
        <Col xs={24} md={10}>
          <Card
            title={<><BuildOutlined style={{ marginRight: 6 }} />情节框架库</>}
            size="small"
          >
            {frameworks.length === 0 ? (
              <Empty description="暂无框架" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <>
                {/* 推荐 */}
                {recommended.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>为【{project?.genre || '当前'}】题材推荐：</Text>
                    <div style={{ marginTop: 4 }}>
                      {recommended.map(name => (
                        <Tag key={name} color="purple" style={{ cursor: 'pointer' }}
                          onClick={() => handleFrameworkClick(name)}>{name}</Tag>
                      ))}
                    </div>
                  </div>
                )}

                {/* 框架列表 */}
                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
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

                {/* 框架详情抽屉 */}
                {frameworkDetail && (
                  <Card size="small" title={frameworkDetail.name} style={{ marginTop: 12, background: '#fafafa' }}>
                    <Paragraph type="secondary" style={{ fontSize: 12 }}>
                      {frameworkDetail.description}
                    </Paragraph>
                    {frameworkDetail.steps.map(s => (
                      <div key={s.step} style={{ marginBottom: 6, display: 'flex', gap: 8 }}>
                        <Tag color="blue">{s.step}</Tag>
                        <div>
                          <Text strong style={{ fontSize: 12 }}>{s.name}</Text>
                          <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>{s.desc}</Text>
                        </div>
                      </div>
                    ))}
                  </Card>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>
    </AppLayout>
  );
}