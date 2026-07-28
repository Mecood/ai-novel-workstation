import { useEffect, useState, useMemo } from 'react';
import { Card, Row, Col, Statistic, Progress, List, Tag, Typography, Empty, Spin, Tooltip, Space } from 'antd';
import {
  FileTextOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  RiseOutlined,
  FallOutlined,
  TeamOutlined,
  NodeIndexOutlined,
  RadarChartOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  DollarOutlined,
  FileProtectOutlined,
} from '@ant-design/icons';
import type { Project } from '../../../services/api';
import { projectApi, chapterApi, characterApi, foreshadowingApi, reviewApi, debtApi, contractApi } from '../../../services/api';

const { Title, Text, Paragraph } = Typography;

interface ChartData {
  chapters: any[];
  characters: any[];
  foreshadowings: any[];
}

/** 迷你柱状图：用 div 堆叠模拟 */
function MiniBar({ label, current, max, color }: { label: string; current: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0;
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
        <span style={{ color: '#666' }}>{label}</span>
        <span style={{ fontWeight: 600 }}>{current}/{max}</span>
      </div>
      <div style={{ background: '#f0f0f0', borderRadius: 2, height: 6 }}>
        <div style={{ width: `${pct}%`, background: color, borderRadius: 2, height: 6, transition: 'width 0.5s' }} />
      </div>
    </div>
  );
}

/** 章节质量趋势迷你图 */
function QualityTrend({ scores, chapters }: { scores: number[]; chapters: number[] }) {
  if (scores.length === 0) return <Text type="secondary">暂无数据</Text>;
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 60, padding: '4px 0' }}>
      {scores.map((s, i) => {
        const h = ((s - min) / range) * 50 + 8;
        const color = s >= 70 ? '#52c41a' : s >= 50 ? '#faad14' : '#ff4d4f';
        return (
          <Tooltip key={i} title={`第${chapters[i]}章 · ${s}分`}>
            <div style={{ flex: 1, maxWidth: 24 }}>
              <div style={{ height: `${h}px`, background: color, borderRadius: '2px 2px 0 0', minHeight: 2 }} />
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}

export default function DashboardPage({ project }: { project: Project }) {
  const id = project.id;
  const [data, setData] = useState<ChartData>({ chapters: [], characters: [], foreshadowings: [] });
  const [reviewTrend, setReviewTrend] = useState<{ chapters: number[]; scores: number[] }>({ chapters: [], scores: [] });
  const [debtSummary, setDebtSummary] = useState(null);
  const [contractStats, setContractStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      chapterApi.list(id),
      characterApi.list(id),
      foreshadowingApi.list(id),
      reviewApi.getTrend(id).catch(() => ({ data: { chapters: [], scores: [] } })),
      debtApi.getSummary(id).catch(() => ({ data: null })),
      contractApi.getAll(id).catch(() => ({ data: { stats: {} } })),
    ])
      .then(([chs, chars, fsh, trend, debt, cont]) => {
        setData({
          chapters: Array.isArray(chs.data) ? chs.data : [],
          characters: Array.isArray(chars.data) ? chars.data : [],
          foreshadowings: Array.isArray(fsh.data) ? fsh.data : [],
        });
        setReviewTrend(trend.data || { chapters: [], scores: [] });
        setDebtSummary(debt.data || null);
        setContractStats(cont.data?.stats || null);
      })
      .finally(() => setLoading(false));
  }, [id]);

  // ── 统计数据 ──
  const stats = useMemo(() => {
    const chs = data.chapters;
    const fsh = data.foreshadowings;
    const generated = chs.filter(c => c.status === 'generated');
    const totalWords = generated.reduce((sum, c) => sum + (c.word_count || 0), 0);
    const unresolved = fsh.filter(f => f.status !== 'resolved' && f.status !== 'paid_off');
    const overdue = unresolved.filter(f => f.target_chapter && generated.length > 0 && f.target_chapter <= generated[generated.length - 1]?.chapter_number);
    const avgWords = generated.length > 0 ? Math.round(totalWords / generated.length) : 0;

    return {
      generatedCount: generated.length,
      totalChapters: chs.length,
      totalWords,
      avgWords,
      characterCount: data.characters.length,
      foreshadowingTotal: fsh.length,
      unresolvedForeshadowings: unresolved.length,
      overdueForeshadowings: overdue.length,
      reviewAvg: reviewTrend.scores.length > 0
        ? Math.round(reviewTrend.scores.reduce((a, b) => a + b, 0) / reviewTrend.scores.length)
        : null,
    };
  }, [data, reviewTrend]);

  // ── 角色关系分析 ──
  const relationships = useMemo(() => {
    const chars = data.characters;
    const pairs: { from: string; to: string; type: string }[] = [];
    const typeColors: Record<string, string> = {
      ally: '#52c41a', enemy: '#ff4d4f', neutral: '#d9d9d9',
      friend: '#1890ff', family: '#722ed1', lover: '#eb2f96',
      mentor: '#fa8c16', rival: '#faad14',
    };
    chars.forEach(c => {
      const rels = c.relationships || [];
      (Array.isArray(rels) ? rels : []).forEach((r: any) => {
        if (r && r.name) {
          pairs.push({ from: c.name, to: r.name, type: r.type || 'neutral' });
        }
      });
    });
    return { pairs, typeColors };
  }, [data]);

  // ── 伏笔风险 ──
  const foreshadowingRisk = useMemo(() => {
    const all = data.foreshadowings;
    const unresolved = all.filter(f => f.status !== 'resolved' && f.status !== 'paid_off');
    const total = all.length;
    const riskPct = total > 0 ? Math.round((unresolved.length / total) * 100) : 0;
    return { riskPct, unresolved, total };
  }, [data]);

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      {/* 第一行：关键指标 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="已生成章节" value={stats.generatedCount} suffix={`/ ${stats.totalChapters}`}
              prefix={<FileTextOutlined />} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="总字数" value={stats.totalWords.toLocaleString()}
              prefix={<RiseOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="平均每章" value={`${stats.avgWords}字`}
              valueStyle={{ fontSize: 20 }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="角色数" value={stats.characterCount}
              prefix={<TeamOutlined />} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="伏笔总数" value={stats.foreshadowingTotal}
              prefix={<LinkOutlined />} suffix={stats.unresolvedForeshadowings > 0 ? <Tag color="orange" style={{ marginLeft: 4 }}>{stats.unresolvedForeshadowings}待回收</Tag> : null} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic title="平均质量分" value={stats.reviewAvg ?? '-'}
              prefix={stats.reviewAvg != null && stats.reviewAvg >= 70 ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
              valueStyle={{ color: stats.reviewAvg != null ? (stats.reviewAvg >= 70 ? '#52c41a' : stats.reviewAvg >= 50 ? '#faad14' : '#ff4d4f') : '#999' }} />
          </Card>
        </Col>
      </Row>

      {/* 第二行：进度条 + 质量趋势 + 伏笔风险 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title={<><NodeIndexOutlined style={{ marginRight: 6 }} />创作进度</>} size="small">
            <MiniBar label="章节生成" current={stats.generatedCount} max={stats.totalChapters} color="#1890ff" />
            <MiniBar label="伏笔回收" current={stats.foreshadowingTotal - stats.unresolvedForeshadowings} max={stats.foreshadowingTotal} color="#52c41a" />
            <Progress
              percent={stats.totalChapters > 0 ? Math.round((stats.generatedCount / stats.totalChapters) * 100) : 0}
              strokeColor={{ from: '#108ee9', to: '#87d068' }}
              style={{ marginTop: 8 }}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={<><RadarChartOutlined style={{ marginRight: 6 }} />质量趋势</>} size="small">
            {reviewTrend.scores.length > 0 ? (
              <QualityTrend scores={reviewTrend.scores} chapters={reviewTrend.chapters} />
            ) : (
              <Text type="secondary">生成章节并评审后将显示质量趋势</Text>
            )}
            {reviewTrend.scores.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                最高 {Math.max(...reviewTrend.scores)} · 最低 {Math.min(...reviewTrend.scores)} · 趋势{' '}
                {reviewTrend.scores.length >= 2 && reviewTrend.scores[reviewTrend.scores.length - 1] > reviewTrend.scores[0] ? <Tag color="green">上升<ArrowUpOutlined /></Tag> : <Tag color="red">下降<ArrowDownOutlined /></Tag>}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 第三行：角色关系网络 + 伏笔风险列表 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title={<><TeamOutlined style={{ marginRight: 6 }} />角色关系网络</>} size="small">
            {relationships.pairs.length === 0 ? (
              <Text type="secondary">暂无角色关系数据</Text>
            ) : (
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                {relationships.pairs.map((p, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: 13 }}>
                    <Tag color="blue">{p.from}</Tag>
                    <span style={{ color: '#999' }}>→</span>
                    <Tag color={relationships.typeColors[p.type] || '#d9d9d9'}>{p.type}</Tag>
                    <span style={{ color: '#999' }}>→</span>
                    <Tag color="blue">{p.to}</Tag>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            title={<><LinkOutlined style={{ marginRight: 6 }} />伏笔管理</>}
            size="small"
            extra={foreshadowingRisk.riskPct > 30 ? <Tag color="red">高风险</Tag> : foreshadowingRisk.riskPct > 10 ? <Tag color="orange">注意</Tag> : <Tag color="green">健康</Tag>}
          >
            {foreshadowingRisk.unresolved.length === 0 ? (
              <Text type="secondary">所有伏笔已回收 ✓</Text>
            ) : (
              <List
                size="small"
                dataSource={foreshadowingRisk.unresolved.slice(0, 5)}
                renderItem={(f: any) => (
                  <List.Item>
                    <List.Item.Meta
                      title={<Text style={{ fontSize: 13 }}>{f.title || '未命名伏笔'}</Text>}
                      description={
                        <Space size={4}>
                          <Tag color={f.target_chapter && stats.generatedCount >= f.target_chapter ? 'red' : 'default'}>
                            {f.target_chapter ? `第${f.target_chapter}章` : '无目标'}
                          </Tag>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {f.description?.slice(0, 40)}{(f.description?.length || 0) > 40 ? '…' : ''}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 第四行：债务 + 合同履约率 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card
            title={<><DollarOutlined style={{ marginRight: 6 }} />伏笔债务</>}
            size="small"
            extra={debtSummary?.overdue_count > 0 ? <Tag color="red">{debtSummary.overdue_count} 逾期</Tag> : <Tag color="green">健康</Tag>}
          >
            {debtSummary ? (
              <Space direction="vertical" size={6}>
                <MiniBar label="活跃债务" current={debtSummary.active_count} max={debtSummary.total_count} color="#faad14" />
                <MiniBar label="逾期债务" current={debtSummary.overdue_count} max={debtSummary.total_count} color="#ff4d4f" />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  债务利息累计：{debtSummary.total_interest} · 最大债务：{debtSummary.top_debts?.[0]?.description || '无'}
                </Text>
              </Space>
            ) : <Text type="secondary">暂无债务数据</Text>}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            title={<><FileProtectOutlined style={{ marginRight: 6 }} />合同履约率</>}
            size="small"
            extra={contractStats && contractStats.accepted > 0 ? (
              <Tag color="green">通过 {contractStats.accepted}</Tag>
            ) : null}
          >
            {contractStats ? (
              <Space direction="vertical" size={6}>
                <MiniBar label="已签署" current={contractStats.signed} max={contractStats.signed + (contractStats?.total ?? 0) - contractStats.signed} color="#1890ff" />
                <MiniBar label="已通过" current={contractStats.accepted} max={contractStats.submitted} color="#52c41a" />
                {contractStats.rejected > 0 && (
                  <MiniBar label="已拒绝" current={contractStats.rejected} max={contractStats.submitted} color="#ff4d4f" />
                )}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  总提交：{contractStats.submitted} · 通过率：{contractStats.submitted > 0
                    ? `${Math.round(contractStats.accepted / contractStats.submitted * 100)}%` : '-'}
                </Text>
              </Space>
            ) : <Text type="secondary">暂无合同数据</Text>}
          </Card>
        </Col>
      </Row>
    </div>
  );
}