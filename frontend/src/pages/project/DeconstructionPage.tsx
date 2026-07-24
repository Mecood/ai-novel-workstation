// @ts-nocheck
import { useState } from 'react';
import {
  Card, Spin, Button, Typography, Space, Empty, Tabs, Input, Radio, message,
  Tag, Collapse, Row, Col, Statistic, Alert, Divider,
} from 'antd';
import {
  BookOutlined, SearchOutlined, ThunderboltOutlined, WarningOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { api } from '../../services/api';
import ReactEChartsCore from 'echarts-for-react';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const GENRES = ['仙侠', '武侠', '玄幻', '科幻', '悬疑', '都市', '言情', '历史', '奇幻', '冒险'];

interface DeconstructResult {
  source?: { title?: string; input_type?: string };
  analysis_mode?: string;
  reader_promise?: { core_desire?: string; promise_delivery?: string; risk?: string };
  opening_hook_patterns?: any[];
  cool_point_loops?: any[];
  protagonist_patterns?: any[];
  antagonist_pressure_patterns?: any[];
  pacing_notes?: { golden_three?: string; arc_cycle?: string; information_density?: string; chapter_end_strategy?: string };
  borrowable_structures?: any[];
  do_not_copy?: string[];
  differentiation_requirements?: string[];
  init_candidates?: any[];
  quality?: { confidence?: number; coverage?: number; overlap?: number; passed?: boolean; warnings?: string[]; reason?: string };
  canon_contamination_warnings?: string[];
}

export default function DeconstructionPage() {
  const [referenceText, setReferenceText] = useState('');
  const [referenceTitle, setReferenceTitle] = useState('');
  const [mode, setMode] = useState<'quick' | 'deep'>('quick');
  const [targetGenre, setTargetGenre] = useState('仙侠');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DeconstructResult | null>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!referenceText.trim()) {
      message.warning('请输入参考书文本');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const endpoint = mode === 'quick' ? '/deconstruction/quick' : '/deconstruction/deep';
      const { data } = await api.post(endpoint, {
        reference_text: referenceText,
        analysis_mode: mode,
        target_genre: targetGenre,
        reference_title: referenceTitle,
      });
      setResult(data);
      message.success('拆解完成');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '未知错误';
      setError(msg);
      message.error('拆解失败：' + msg);
    } finally {
      setLoading(false);
    }
  };

  // 雷达图配置
  const radarOption = {
    tooltip: {},
    radar: {
      indicator: [
        { name: '开篇钩子', max: 5 },
        { name: '主角塑造', max: 5 },
        { name: '爽点设计', max: 5 },
        { name: '世界观铺设', max: 5 },
        { name: '章尾悬念', max: 5 },
      ],
      radius: 80,
    },
    series: [{
      type: 'radar',
      data: [{
        value: result?.quality ? [
          (result.quality.confidence || 0) * 5,
          (result.quality.coverage || 0) * 5,
          (result.quality.confidence || 0) * 5,
          (result.quality.coverage || 0) * 5,
          (1 - (result.quality.overlap || 0)) * 5,
        ] : [0, 0, 0, 0, 0],
        name: '拆解质量',
        areaStyle: { color: 'rgba(91, 155, 213, 0.3)' },
        lineStyle: { color: '#5B9BD5' },
      }],
    }],
  };

  const q = result?.quality;
  const passed = q?.passed;

  return (
    <AppLayout projectId={(window.location.pathname.match(/\/projects\/([^/]+)/) || ['', ''])[1]}>
      <Card
        title={
          <Space>
            <BookOutlined style={{ color: '#5B9BD5' }} />
            <span>参考书拆解</span>
            <Tag color="purple">Deconstruction Agent</Tag>
          </Space>
        }
      >
        <Row gutter={24}>
          {/* 左侧：输入区 */}
          <Col span={10}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text strong>参考书名</Text>
                <Input
                  placeholder="可选，填写参考书名称"
                  value={referenceTitle}
                  onChange={(e) => setReferenceTitle(e.target.value)}
                  style={{ marginTop: 4 }}
                />
              </div>

              <div>
                <Text strong>分析模式</Text>
                <Radio.Group
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  style={{ marginTop: 4, display: 'block' }}
                >
                  <Radio value="quick">快速模式（黄金三章+拆文报告）</Radio>
                  <Radio value="deep">深度模式（逐章提取+聚合分析）</Radio>
                </Radio.Group>
              </div>

              <div>
                <Text strong>目标题材</Text>
                <Radio.Group
                  value={targetGenre}
                  onChange={(e) => setTargetGenre(e.target.value)}
                  style={{ marginTop: 4 }}
                  size="small"
                >
                  {GENRES.map(g => <Radio.Button key={g} value={g}>{g}</Radio.Button>)}
                </Radio.Group>
              </div>

              <div>
                <Text strong>参考书正文</Text>
                <TextArea
                  rows={12}
                  placeholder="粘贴参考书正文（至少前三章）..."
                  value={referenceText}
                  onChange={(e) => setReferenceText(e.target.value)}
                  style={{ marginTop: 4 }}
                  showCount
                />
              </div>

              <Button
                type="primary"
                size="large"
                icon={<ThunderboltOutlined />}
                onClick={handleAnalyze}
                loading={loading}
                block
              >
                {mode === 'quick' ? '快速拆解' : '深度拆解'}
              </Button>
            </Space>
          </Col>

          {/* 右侧：结果区 */}
          <Col span={14}>
            <Spin spinning={loading} tip="正在拆解参考书...">
              {error && (
                <Alert
                  message="拆解失败"
                  description={error}
                  type="error"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

              {!result && !loading && !error && (
                <Empty
                  description="输入参考书文本后点击拆解按钮"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}

              {result && (
                <Tabs
                  items={[
                    // 质量概览
                    {
                      key: 'quality',
                      label: '拆解质量',
                      children: (
                        <div>
                          <Row gutter={16} style={{ marginBottom: 16 }}>
                            <Col span={6}>
                              <Statistic
                                title="置信度"
                                value={((q?.confidence || 0) * 100).toFixed(0)}
                                suffix="%"
                                valueStyle={{ color: (q?.confidence || 0) >= 0.85 ? '#52c41a' : '#faad14' }}
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="覆盖率"
                                value={((q?.coverage || 0) * 100).toFixed(0)}
                                suffix="%"
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="重叠率"
                                value={((q?.overlap || 0) * 100).toFixed(0)}
                                suffix="%"
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="通过"
                                value={passed ? '✓' : '✗'}
                                valueStyle={{ color: passed ? '#52c41a' : '#ff4d4f' }}
                              />
                            </Col>
                          </Row>

                          {q?.reason && (
                            <Alert message={q.reason} type="info" showIcon style={{ marginBottom: 16 }} />
                          )}

                          {result.canon_contamination_warnings && result.canon_contamination_warnings.length > 0 && (
                            <Alert
                              message="Canon 污染警告"
                              description={
                                <ul style={{ margin: 0, paddingLeft: 20 }}>
                                  {result.canon_contamination_warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                              }
                              type="warning"
                              showIcon
                              style={{ marginBottom: 16 }}
                            />
                          )}

                          <ReactEChartsCore option={radarOption} style={{ height: 250 }} />
                        </div>
                      ),
                    },
                    // 读者承诺
                    {
                      key: 'promise',
                      label: '读者承诺',
                      children: result.reader_promise ? (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <div><Text strong>核心欲望：</Text><Text>{result.reader_promise.core_desire}</Text></div>
                          <div><Text strong>承诺兑现：</Text><Text>{result.reader_promise.promise_delivery}</Text></div>
                          <div><Text strong>风险：</Text><Text type="danger">{result.reader_promise.risk}</Text></div>
                        </Space>
                      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                    // 开篇钩子
                    {
                      key: 'hooks',
                      label: '开篇钩子',
                      children: result.opening_hook_patterns && result.opening_hook_patterns.length > 0 ? (
                        <Collapse items={result.opening_hook_patterns.map((h, i) => ({
                          key: String(i),
                          label: h.pattern || `模式 ${i + 1}`,
                          children: (
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <div><Text strong>为什么有效：</Text>{h.why_it_works}</div>
                              <div><Text strong>迁移规则：</Text>{h.transfer_rule}</div>
                              {h.avoid_copying && (
                                <div>
                                  <Text strong style={{ color: '#ff4d4f' }}>不可复制：</Text>
                                  <Space wrap>
                                    {h.avoid_copying.map((c, j) => <Tag key={j} color="red">{c}</Tag>)}
                                  </Space>
                                </div>
                              )}
                            </Space>
                          ),
                        }))} />
                      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                    // 爽点循环
                    {
                      key: 'loops',
                      label: '爽点循环',
                      children: result.cool_point_loops && result.cool_point_loops.length > 0 ? (
                        <Collapse items={result.cool_point_loops.map((l, i) => ({
                          key: String(i),
                          label: `循环 ${i + 1}`,
                          children: (
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <div><Text strong>铺垫：</Text>{l.setup}</div>
                              <div><Text strong>释放：</Text>{l.release}</div>
                              <div><Text strong>反应层：</Text>{l.reaction_layers}</div>
                              <div><Text strong>衔接：</Text>{l.transition}</div>
                              <div><Text strong>铺放比：</Text>{l.pacing_ratio}</div>
                              <div><Text strong>迁移规则：</Text>{l.transfer_rule}</div>
                            </Space>
                          ),
                        }))} />
                      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                    // 可借结构
                    {
                      key: 'borrowable',
                      label: '可借结构',
                      children: result.borrowable_structures && result.borrowable_structures.length > 0 ? (
                        <Collapse items={result.borrowable_structures.map((b, i) => ({
                          key: String(i),
                          label: b.structure || `结构 ${i + 1}`,
                          children: (
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <div><Text strong>用法：</Text>{b.use_case}</div>
                              <div><Text strong>必要转化：</Text><Text type="warning">{b.required_transformation}</Text></div>
                            </Space>
                          ),
                        }))} />
                      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                    // 候选创意包
                    {
                      key: 'candidates',
                      label: (
                        <Space>
                          <ExperimentOutlined />
                          <span>候选创意包</span>
                          {result.init_candidates && (
                            <Tag color="purple">{result.init_candidates.length}</Tag>
                          )}
                        </Space>
                      ),
                      children: result.init_candidates && result.init_candidates.length > 0 ? (
                        <Row gutter={[12, 12]}>
                          {result.init_candidates.map((c, i) => (
                            <Col span={24} key={i}>
                              <Card size="small" type="inner"
                                title={<Space><Tag color="purple">候选 {i + 1}</Tag><Text strong>{c.one_liner}</Text></Space>}
                              >
                                <Space direction="vertical" style={{ width: '100%' }} size="small">
                                  {c.anti_trope && <div><Text type="secondary">反套路：</Text>{c.anti_trope}</div>}
                                  {c.protagonist_flaw && <div><Text type="secondary">主角缺陷：</Text>{c.protagonist_flaw}</div>}
                                  {c.opening_hook && <div><Text type="secondary">开篇钩子：</Text>{c.opening_hook}</div>}
                                  {c.hard_constraints && c.hard_constraints.length > 0 && (
                                    <div>
                                      <Text type="secondary">硬约束：</Text>
                                      <Space wrap>
                                        {c.hard_constraints.map((hc, j) => <Tag key={j}>{hc}</Tag>)}
                                      </Space>
                                    </div>
                                  )}
                                  {c.transformation_notes && <div><Text type="secondary">转化说明：</Text>{c.transformation_notes}</div>}
                                </Space>
                              </Card>
                            </Col>
                          ))}
                        </Row>
                      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                    // 不可复制
                    {
                      key: 'dont',
                      label: (
                        <Space>
                          <WarningOutlined style={{ color: '#ff4d4f' }} />
                          <span>不可复制</span>
                        </Space>
                      ),
                      children: result.do_not_copy && result.do_not_copy.length > 0 ? (
                        <Alert
                          type="error"
                          message="以下元素不可直接复制到新书"
                          description={
                            <ul style={{ margin: 0, paddingLeft: 20 }}>
                              {result.do_not_copy.map((d, i) => <li key={i}>{d}</li>)}
                            </ul>
                          }
                          showIcon
                        />
                      ) : <Empty description="无不可复制项" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                    },
                  ]}
                />
              )}
            </Spin>

            <Divider />
            <Paragraph type="secondary" style={{ fontSize: 12 }}>
              💡 拆解只提取可迁移的创作模式（钩子/爽点/节奏/结构），不复制原作角色、地名、设定。
              输出的候选创意包需要你进一步加工后才能用于新项目。
            </Paragraph>
          </Col>
        </Row>
      </Card>
    </AppLayout>
  );
}
