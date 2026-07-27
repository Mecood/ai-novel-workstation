// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import {
  Card, Spin, message, Button, Typography, Tag, List, Empty, Alert, Space, Statistic, Row, Col, Divider, Collapse, Tabs, Progress
} from 'antd';
import {
  ExperimentOutlined, ReloadOutlined, WarningFilled, CheckCircleFilled,
  CloseCircleFilled, InfoCircleFilled, FileTextOutlined, ThunderboltOutlined,
  StopOutlined, ToolOutlined
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import {
  reviewApi, ReviewReport, ReviewIssue, ReviewTrend, DimensionTrend,
  TieredResults, TierL1Result, TierL1Check, TierL2Result, TierL3Result, AntiHallucinationCheck
} from '../../services/api';

const { Title, Text, Paragraph } = Typography;

// ── Color palette ──────────────────────────────────────────────────────
const DIMENSION_COLORS: Record<string, string> = {
  '设定一致性': '#5B9BD5',
  '时间线': '#ED7D31',
  '叙事连贯': '#70AD47',
  '角色一致性': '#9B59B6',
  '逻辑': '#E74C3C',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#cf1322',
  high: '#fa8c16',
  medium: '#fadb14',
  low: '#8c8c8c',
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: '阻断',
  high: '严重',
  medium: '一般',
  low: '轻微',
};

const SCORE_COLORS = (score: number) => {
  if (score >= 90) return '#3f8600';
  if (score >= 70) return '#5B9BD5';
  if (score >= 50) return '#fa8c16';
  return '#cf1322';
};

const VERDICT_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  PASS: { color: '#3f8600', icon: <CheckCircleFilled style={{ color: '#3f8600' }} />, label: '通过' },
  REVISE: { color: '#faad14', icon: <InfoCircleFilled style={{ color: '#faad14' }} />, label: '需修改' },
  REJECT: { color: '#cf1322', icon: <CloseCircleFilled style={{ color: '#cf1322' }} />, label: '拒绝' },
};

// ── Trend chart ────────────────────────────────────────────────────────
function TrendChart({
  chapters,
  seriesData,
}: {
  chapters: number[];
  seriesData: { name: string; data: (number | null)[]; color: string }[];
}) {
  const option: any = {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: chapters.map((c) => `第${c}章`),
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } },
    },
    series: seriesData.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: s.color },
      itemStyle: { color: s.color },
      connectNulls: true,
    })),
  };
  return <ReactEChartsCore option={option} style={{ height: 260 }} notMerge />;
}

// ── Issue item (shared) ────────────────────────────────────────────────
function IssueItem({ issue, idx }: { issue: ReviewIssue; idx: number }) {
  return (
    <List.Item
      style={{
        background: issue.blocking ? '#fff2f0' : 'transparent',
        borderRadius: 6,
        padding: '10px 14px',
        marginBottom: 4,
        border: issue.blocking ? '1px solid #ffccc7' : '1px solid #f0f0f0',
      }}
    >
      <div style={{ width: '100%' }}>
        <Row gutter={12} align="middle" style={{ marginBottom: 4 }}>
          <Col>
            <Tag color={issue.blocking ? 'red' : SEVERITY_COLORS[issue.severity]}>
              {issue.blocking ? '🔴 阻断' : SEVERITY_LABELS[issue.severity]}
            </Tag>
          </Col>
          <Col>
            <Tag
              style={{
                color: DIMENSION_COLORS[issue.dimension] || '#5B9BD5',
                borderColor: DIMENSION_COLORS[issue.dimension] || '#5B9BD5',
              }}
            >
              {issue.dimension}
            </Tag>
          </Col>
          {issue.location && (
            <Col>
              <Text type="secondary" style={{ fontSize: 12 }}>📍 {issue.location}</Text>
            </Col>
          )}
        </Row>
        <Paragraph style={{ margin: 0, fontSize: 12 }}>{issue.description}</Paragraph>
        <Collapse ghost size="small" style={{ marginTop: 4 }}
          items={[
            ...(issue.evidence ? [{
              key: `ev-${idx}`,
              label: <Text type="secondary" style={{ fontSize: 11 }}>原文证据</Text>,
              children: <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'pre-wrap', fontStyle: 'italic' }}>"{issue.evidence}"</Text>,
            }] : []),
            ...(issue.fix_hint ? [{
              key: `fx-${idx}`,
              label: <Text style={{ fontSize: 11, color: '#5B9BD5' }}>修复建议</Text>,
              children: <Text style={{ fontSize: 11, whiteSpace: 'pre-wrap' }}>{issue.fix_hint}</Text>,
            }] : []),
          ]}
        />
      </div>
    </List.Item>
  );
}

// ── L1 Tab ─────────────────────────────────────────────────────────────
function L1Tab({ l1 }: { l1: TierL1Result }) {
  const L1_LABELS: Record<string, string> = {
    word_count: '字数范围',
    title_not_empty: '章节标题',
    skeleton_present: '骨架定义',
    character_event_new: '新增角色/事件',
    skeleton_coverage: '骨架覆盖率',
  };

  const L1_THRESHOLDS: Record<string, string> = {
    word_count: '2000-5000字',
    title_not_empty: '非空',
    skeleton_present: '有骨架定义',
    character_event_new: '有新增',
    skeleton_coverage: '≥60%',
  };

  return (
    <div>
      <Alert
        type={l1.status === 'PASS' ? 'success' : 'error'}
        message={l1.status === 'PASS' ? '✅ L1 硬指标：全部通过' : '❌ L1 硬指标：存在未通过项'}
        description={l1.status === 'FAIL' ? '以下硬指标未通过，建议先修复再进入 L2 审查。' : ''}
        showIcon
        style={{ marginBottom: 16 }}
      />
      <Row gutter={[12, 12]}>
        {l1.checks.map((check, idx) => (
          <Col xs={24} sm={12} md={8} key={idx}>
            <Card
              size="small"
              style={{
                borderLeft: `4px solid ${check.passed ? '#3f8600' : '#cf1322'}`,
                margin: 0,
              }}
            >
              <Row gutter={8} align="middle" style={{ marginBottom: 6 }}>
                <Col>
                  {check.passed ? (
                    <CheckCircleFilled style={{ color: '#3f8600', fontSize: 14 }} />
                  ) : (
                    <CloseCircleFilled style={{ color: '#cf1322', fontSize: 14 }} />
                  )}
                </Col>
                <Col>
                  <Text strong>{L1_LABELS[check.name] || check.label || check.name}</Text>
                </Col>
              </Row>
              <Text type="secondary" style={{ fontSize: 12 }}>
                要求：{L1_THRESHOLDS[check.name] || check.threshold || check.detail}
              </Text>
              <div style={{ marginTop: 4 }}>
                {check.passed ? (
                  <Tag color="green">通过</Tag>
                ) : (
                  <Tag color="red">未通过 — {check.detail}</Tag>
                )}
              </div>
              {/* Skeleton coverage progress bar */}
              {check.name === 'skeleton_coverage' && check.total && (
                <Progress
                  percent={Math.round((check.covered || 0) / (check.total || 1) * 100)}
                  size="small"
                  strokeColor={check.passed ? '#3f8600' : '#cf1322'}
                  showInfo={true}
                  style={{ marginTop: 6 }}
                />
              )}
              {/* Invented items */}
              {check.invented && check.invented.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    🔬 检测到新增元素：{check.invented.map((i: string) => (
                      <Tag key={i} color="blue" style={{ marginRight: 4 }}>{i}</Tag>
                    ))}
                  </Text>
                </div>
              )}
              {/* Missed skeleton nodes */}
              {check.missed && check.missed.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    ⚠️ 未覆盖骨架节点：{check.missed.map((m: string) => (
                      <Tag key={m} color="orange" style={{ marginRight: 4 }}>{m}</Tag>
                    ))}
                  </Text>
                </div>
              )}
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

// ── L2 Tab (existing 5-dimension review) ───────────────────────────────
function L2Tab({
  l2,
  report,
}: {
  l2: TierL2Result | null;
  report: ReviewReport | null;
}) {
  if (!l2 && !report) return <Empty description="无 L2 审查数据" />;

  const dimensionScores = l2?.dimension_scores || report?.dimension_scores || {};
  const overallScore = l2?.overall_score ?? report?.overall_score ?? 0;
  const issues = l2?.issues ?? report?.issues ?? [];
  const severityCounts = l2 ? _countSeverities(l2.issues) : report?.severity_counts || {};
  const blockingIssues = issues.filter((i) => i.blocking);
  const nonBlockingIssues = issues.filter((i) => !i.blocking);
  const sortedIssues = [...blockingIssues, ...nonBlockingIssues];

  return (
    <div>
      {/* Overall score */}
      <Card style={{ marginBottom: 16, borderLeft: `4px solid ${SCORE_COLORS(overallScore)}` }}>
        <Row gutter={16} align="middle">
          <Col>
            <Statistic
              title="综合评分"
              value={overallScore}
              suffix="/ 100"
              valueStyle={{ color: SCORE_COLORS(overallScore), fontSize: 32, fontWeight: 600 }}
            />
          </Col>
          <Col>
            <Statistic
              title="阻断问题"
              value={l2?.blocking_count ?? report?.blocking_count ?? 0}
              valueStyle={{ color: (l2?.blocking_count ?? report?.blocking_count ?? 0) > 0 ? '#cf1322' : '#3f8600' }}
              prefix={(l2?.blocking_count ?? report?.blocking_count ?? 0) > 0 ? <CloseCircleFilled /> : <CheckCircleFilled />}
            />
          </Col>
          <Col>
            <Statistic title="严重" value={severityCounts.high || 0} valueStyle={{ color: '#fa8c16' }} />
          </Col>
          <Col>
            <Statistic title="一般" value={severityCounts.medium || 0} valueStyle={{ color: '#fadb14' }} />
          </Col>
          <Col>
            <Statistic title="轻微" value={severityCounts.low || 0} valueStyle={{ color: '#8c8c8c' }} />
          </Col>
        </Row>
        {(l2?.summary || report?.summary) && (
          <div style={{ marginTop: 10, padding: 10, background: '#fafafa', borderRadius: 6 }}>
            <Text type="secondary">{l2?.summary || report?.summary}</Text>
          </div>
        )}
      </Card>

      {/* 5 Dimension cards */}
      <Title level={5} style={{ marginBottom: 10 }}>5 维度评分</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        {Object.entries(dimensionScores).map(([dim, score]) => (
          <Col xs={12} sm={8} md={4} key={dim}>
            <Card
              size="small"
              style={{ borderTop: `3px solid ${DIMENSION_COLORS[dim] || '#5B9BD5'}`, textAlign: 'center' }}
            >
              <Statistic
                title={dim}
                value={Number(score).toFixed(1)}
                suffix="分"
                valueStyle={{ color: SCORE_COLORS(Number(score)), fontSize: 22, fontWeight: 600 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* Issues */}
      <Divider />
      <Row justify="space-between" align="middle" style={{ marginBottom: 10 }}>
        <Col>
          <Title level={5} style={{ margin: 0 }}>
            问题清单
            {issues.length > 0 && <Text style={{ fontSize: 13, marginLeft: 8, color: '#8c8c8c' }}>(共 {issues.length} 项)</Text>}
          </Title>
        </Col>
      </Row>
      {sortedIssues.length === 0 ? (
        <Card>
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={
            <Space><CheckCircleFilled style={{ color: '#3f8600', fontSize: 18 }} />
            <Text strong>未发现任何问题</Text></Space>
          } />
        </Card>
      ) : (
        <List dataSource={sortedIssues} renderItem={(issue, idx) => <IssueItem issue={issue} idx={idx} />} />
      )}
    </div>
  );
}

function _countSeverities(issues: ReviewIssue[]) {
  const counts: Record<string, number> = { high: 0, medium: 0, low: 0 };
  issues.forEach((i) => { if (counts[i.severity] !== undefined) counts[i.severity]++; });
  return counts;
}

// ── L3 Tab ─────────────────────────────────────────────────────────────
function L3Tab({ l3 }: { l3: TierL3Result | null }) {
  if (!l3) return <Empty description="无 L3 终审数据" />;

  const verdictConfig = VERDICT_CONFIG[l3.verdict] || VERDICT_CONFIG.REVISE;
  const blockingIssues = l3.anti_hallucination.filter((a) => a.blocking);

  return (
    <div>
      {/* Verdict card */}
      <Card
        style={{
          marginBottom: 16,
          borderLeft: `4px solid ${verdictConfig.color}`,
        }}
      >
        <Row gutter={24} align="middle">
          <Col>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 28 }}>{verdictConfig.icon}</div>
              <div>
                <Text strong style={{ fontSize: 16 }}>{verdictConfig.label}</Text>
              </div>
            </div>
          </Col>
          <Col flex="1" style={{ marginTop: 4 }}>
            <Text>{l3.summary}</Text>
          </Col>
        </Row>
        <Collapse ghost size="small" style={{ marginTop: 10 }}
          items={[
            ...(l3.l1_summary ? [{
              key: 'l1s',
              label: <Text style={{ fontSize: 12 }}>L1 硬指标摘要</Text>,
              children: <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{l3.l1_summary}</Text>,
            }] : []),
            ...(l3.l2_summary ? [{
              key: 'l2s',
              label: <Text style={{ fontSize: 12 }}>L2 软指标摘要</Text>,
              children: <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{l3.l2_summary}</Text>,
            }] : []),
            ...(l3.l3_reasoning ? [{
              key: 'reasoning',
              label: <Text style={{ fontSize: 12, color: '#5B9BD5' }}>AI 推理过程</Text>,
              children: <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{l3.l3_reasoning}</Text>,
            }] : []),
          ]}
        />
      </Card>

      {/* Anti-hallucination 3 laws */}
      <Divider />
      <Title level={5} style={{ marginBottom: 10 }}>
        <ThunderboltOutlined style={{ color: '#5B9BD5', marginRight: 6 }} />
        反幻觉 3 定律
      </Title>

      {l3.anti_hallucination.map((check, idx) => {
        const icon = check.passed
          ? <CheckCircleFilled style={{ color: '#3f8600', fontSize: 14 }} />
          : <StopOutlined style={{ color: '#cf1322', fontSize: 14 }} />;

        return (
          <Card
            key={idx}
            size="small"
            style={{
              marginBottom: 8,
              borderLeft: `4px solid ${check.blocking ? '#cf1322' : check.passed ? '#3f8600' : '#faad14'}`,
            }}
          >
            <Row gutter={8} align="middle" style={{ marginBottom: 4 }}>
              <Col>{icon}</Col>
              <Col>
                <Text strong>{check.label}</Text>
              </Col>
              {check.blocking && <Tag color="red">🔴 阻断</Tag>}
              {!check.passed && !check.blocking && <Tag color="orange">⚠️ 警告</Tag>}
              {check.passed && <Tag color="green">通过</Tag>}
            </Row>
            <Text type="secondary" style={{ fontSize: 12 }}>{check.detail}</Text>

            {/* Deviation check */}
            {check.deviation && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>📏 偏离度：{check.deviation}</Text>
              </div>
            )}

            {/* Violations */}
            {check.violations && check.violations.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {check.violations.map((v, vi) => (
                  <div key={vi} style={{ marginTop: 4, padding: 6, background: '#fffbe6', borderRadius: 4 }}>
                    <Text style={{ fontSize: 11 }}><strong>违反规则：</strong>{v.rule}</Text>
                    <div style={{ marginTop: 2 }}>
                      <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'pre-wrap' }}>"{v.evidence}"</Text>
                    </div>
                    <div style={{ marginTop: 2 }}>
                      <Text style={{ fontSize: 11, color: '#5B9BD5' }}>💡 修复：{v.fix_hint}</Text>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Invented items */}
            {check.invented_items && check.invented_items.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  🔬 AI 新增元素（未标记为"发明"）：{check.invented_items.map((i: string) => (
                    <Tag key={i} color="blue" style={{ marginRight: 4 }}>{i}</Tag>
                  ))}
                </Text>
              </div>
            )}
            {check.unflagged && check.unflagged.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  ⚠️ 未标记为"发明"的元素：{check.unflagged.map((i: string) => (
                    <Tag key={i} color="orange" style={{ marginRight: 4 }}>{i}</Tag>
                  ))}
                </Text>
              </div>
            )}
          </Card>
        );
      })}

      {/* Blocking issues */}
      {blockingIssues.length > 0 && (
        <>
          <Divider />
          <Title level={5} style={{ marginBottom: 10, color: '#cf1322' }}>
            🔴 阻断问题
          </Title>
          {blockingIssues.map((issue: ReviewIssue, idx: number) => <IssueItem key={idx} issue={issue} idx={idx} />)}
        </>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────
export default function ConsistencyPage() {
  const { id } = useParams<{ id: string }>();
  const [reviewing, setReviewing] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [trend, setTrend] = useState<ReviewTrend | null>(null);
  const [dimensionTrend, setDimensionTrend] = useState<DimensionTrend | null>(null);
  const [selectedChapter, setSelectedChapter] = useState<number>(1);
  const [loadingReport, setLoadingReport] = useState(false);
  const [progressMsg, setProgressMsg] = useState('');

  const tieredResults = report?.tiered_results;

  const loadReport = useCallback(async (chapterNumber: number) => {
    if (!id) return;
    setLoadingReport(true);
    try {
      const res = await reviewApi.getReport(id, chapterNumber);
      setReport(res.data);
    } catch {
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  }, [id]);

  const loadTrend = useCallback(async () => {
    if (!id) return;
    try {
      const [trendRes, dimRes] = await Promise.all([
        reviewApi.getTrend(id),
        reviewApi.getDimensionTrend(id),
      ]);
      setTrend(trendRes.data);
      setDimensionTrend(dimRes.data);
    } catch {}
  }, [id]);

  useEffect(() => {
    loadReport(selectedChapter);
    loadTrend();
  }, [selectedChapter, loadReport, loadTrend]);

  const handleReview = async () => {
    if (!id) return;
    setReviewing(true);
    setProgressMsg('正在准备审查...');
    setReport(null);
    try {
      await reviewApi.trigger(id, selectedChapter, (data) => {
        if (data.type === 'progress') {
          setProgressMsg(data.message || '审查中...');
        } else if (data.type === 'complete') {
          setReport((data.report || data.tiered_results) as ReviewReport);
          setProgressMsg('');
          message.success('审查完成');
        } else if (data.type === 'error') {
          message.error(data.message || '审查失败');
          setProgressMsg('');
        }
      });
      await loadTrend();
    } catch (e: any) {
      message.error(e?.message || '审查请求失败');
      setProgressMsg('');
    } finally {
      setReviewing(false);
    }
  };

  const handlePolish = async () => {
    if (!id || !report) return;
    const blocking = report.blocking_count || 0;
    if (blocking === 0) {
      message.info('当前章节无阻断问题，无需修复');
      return;
    }
    setPolishing(true);
    try {
      const result = await reviewApi.polish(id, selectedChapter);
      message.success(
        `修复完成！${result.data.total_changes} 处修改（${result.data.original_word_count}字→${result.data.polished_word_count}字）`
      );
      await loadReport(selectedChapter);
    } catch (e: any) {
      message.error(e?.message || '修复失败');
    } finally {
      setPolishing(false);
    }
  };

  const hasTiered = !!tieredResults;

  return (
    <AppLayout projectId={id!}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <FileTextOutlined style={{ color: '#5B9BD5', marginRight: 8 }} />
            三层评审
          </Title>
          <Text type="secondary">L1 硬指标 / L2 软指标 / L3 终审 — 阻断问题在 L3 裁决</Text>
        </Col>
        <Col>
          <Space>
            <Button
              type="primary"
              icon={<ExperimentOutlined />}
              loading={reviewing}
              onClick={handleReview}
            >
              开始审查第{selectedChapter}章
            </Button>
            {report && (report.blocking_count ?? 0) > 0 && (
              <Button
                icon={<ToolOutlined />}
                loading={polishing}
                onClick={handlePolish}
                style={{ background: '#fff2f0', borderColor: '#ff4d4f', color: '#cf1322' }}
              >
                一键修复 {report.blocking_count} 个阻断问题
              </Button>
            )}
          </Space>
        </Col>
      </Row>

      {/* Chapter selector */}
      <Card size="small" style={{ marginBottom: 14 }}>
        <Space>
          <Text strong>选择章节：</Text>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
            <Button
              key={n}
              size="small"
              type={selectedChapter === n ? 'primary' : 'default'}
              onClick={() => setSelectedChapter(n)}
            >
              第{n}章
            </Button>
          ))}
        </Space>
      </Card>

      {/* Reviewing progress */}
      {reviewing && (
        <Card style={{ marginBottom: 14 }}>
          <Spin tip={progressMsg} style={{ display: 'block', textAlign: 'center', padding: 36 }} />
        </Card>
      )}
      {loadingReport && !reviewing && (
        <Card style={{ marginBottom: 14 }}>
          <Spin tip="加载审查报告..." style={{ display: 'block', textAlign: 'center', padding: 36 }} />
        </Card>
      )}
      {polishing && (
        <Card style={{ marginBottom: 14 }}>
          <Spin tip="正在修复阻断问题（定点修复→风格适配→排版→AI味检测）..." style={{ display: 'block', textAlign: 'center', padding: 36 }} />
        </Card>
      )}

      {/* Report content */}
      {!reviewing && !loadingReport && report && (
        <div>
          {/* Tiered tabs if available */}
          {hasTiered ? (
            <Tabs
              defaultActiveKey="l2"
              items={[
                {
                  key: 'l1',
                  label: (
                    <span>
                      L1 硬指标
                      {tieredResults.l1.status === 'FAIL' && (
                        <Tag color="red" style={{ marginLeft: 4, fontSize: 10 }}>未通过</Tag>
                      )}
                    </span>
                  ),
                  children: <L1Tab l1={tieredResults.l1} />,
                },
                {
                  key: 'l2',
                  label: 'L2 软指标',
                  children: <L2Tab l2={tieredResults.l2} report={report} />,
                },
                {
                  key: 'l3',
                  label: (
                    <span>
                      L3 终审
                      {tieredResults.l3 && tieredResults.l3.verdict !== 'PASS' && (
                        <Tag color={tieredResults.l3.verdict === 'REJECT' ? 'red' : 'orange'} style={{ marginLeft: 4, fontSize: 10 }}>
                          {tieredResults.l3.verdict === 'REJECT' ? '拒绝' : '需修改'}
                        </Tag>
                      )}
                    </span>
                  ),
                  children: <L3Tab l3={tieredResults.l3} />,
                },
              ]}
            />
          ) : (
            /* Fallback: single-page L2 view when no tiered data */
            <L2Tab l2={null} report={report} />
          )}
        </div>
      )}

      {/* No report yet */}
      {!reviewing && !loadingReport && !report && (
        <Alert
          type="info"
          message="尚未对本章节进行审查"
          description="点击上方「开始审查」按钮，AI 将执行三层评审：L1 硬指标（零LLM自动检查）→ L2 软指标（5维审查）→ L3 终审（AI综合裁决+反幻觉3定律检查）。"
          showIcon
          style={{ marginBottom: 20 }}
        />
      )}

      {/* Trend charts */}
      <Divider />
      <Title level={5} style={{ marginBottom: 10 }}>质量趋势</Title>
      {trend && trend.chapters.length > 0 ? (
        <Card size="small" style={{ marginBottom: 14 }}>
          <Text strong style={{ fontSize: 13 }}>综合评分趋势</Text>
          <TrendChart
            chapters={trend.chapters}
            seriesData={[{ name: '综合评分', data: trend.scores, color: '#5B9BD5' }]}
          />
        </Card>
      ) : (
        <Card size="small" style={{ marginBottom: 14 }}>
          <Empty description="完成至少一次审查后，这里将显示质量趋势图" />
        </Card>
      )}

      {dimensionTrend && dimensionTrend.chapters.length > 0 ? (
        <Card size="small">
          <Text strong style={{ fontSize: 13 }}>各维度评分趋势</Text>
          <TrendChart
            chapters={dimensionTrend.chapters}
            seriesData={Object.entries(dimensionTrend.dimensions).map(([dim, data]) => ({
              name: dim,
              data: data as (number | null)[],
              color: DIMENSION_COLORS[dim] || '#5B9BD5',
            }))}
          />
        </Card>
      ) : (
        <Card size="small">
          <Empty description="完成至少一次审查后，这里将显示各维度趋势图" />
        </Card>
      )}
    </AppLayout>
  );
}