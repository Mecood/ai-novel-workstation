// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import {
  Card, Spin, Button, Typography, Tag, Space, Row, Col,
  Statistic, Table, Empty, Tabs, Modal, Form, Select, InputNumber,
  Input, message, Alert,
} from 'antd';
import {
  WarningOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  DollarOutlined, BarChartOutlined, FileAddOutlined, ReloadOutlined,
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { debtApi, DEBT_TYPE_LABELS, DEBT_STATUS_LABELS, CONTRACT_STATUS_LABELS,
         CONSTRAINT_TYPE_LABELS, RATIONALE_TYPE_LABELS, HOOK_TYPE_LABELS,
         HOOK_STRENGTH_LABELS } from '../../services/api';
import type { DebtSummary, OverrideContract, ReadingPowerTrend, ChaseDebt } from '../../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

// 追读力评分颜色
const SCORE_COLOR = (score: number) => {
  if (score >= 8) return '#52c41a';
  if (score >= 6) return '#1890ff';
  if (score >= 4) return '#faad14';
  return '#f5222d';
};

// 债务类型颜色
const DEBT_COLORS: Record<string, string> = {
  hook_strength: '#f5222d',
  micropayoff: '#fa8c16',
  coolpoint: '#eb2f96',
  reading_desire: '#722ed1',
};

export default function DebtDashboard() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState<DebtSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [contractModalOpen, setContractModalOpen] = useState(false);
  const [contractForm] = Form.useForm();

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await debtApi.getSummary(id);
      setSummary(res.data);
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // ECharts 追读力趋势图
  const trendOption = summary?.trend?.chapters?.length
    ? {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
        },
        legend: { data: ['追读力评分', '债务余额'], top: 0, right: 0 },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: {
          type: 'category',
          data: summary.trend.chapters.map(c => `第${c}章`),
          axisLabel: { rotate: 45 },
        },
        yAxis: [
          { type: 'value', name: '评分', min: 0, max: 10 },
          { type: 'value', name: '债务', min: 0 },
        ],
        series: [
          {
            name: '追读力评分',
            type: 'line',
            data: summary.trend.scores,
            smooth: true,
            lineStyle: { color: '#5B9BD5', width: 2 },
            itemStyle: {
              color: (params: any) => {
                const v = summary.trend.scores[params.dataIndex];
                return SCORE_COLOR(v);
              },
            },
            markLine: {
              silent: true,
              data: [
                { yAxis: 6, label: { formatter: '合格线(6分)', color: '#999' } },
                { yAxis: 8, label: { formatter: '偿还线(8分)', color: '#52c41a' } },
              ],
              lineStyle: { type: 'dashed', opacity: 0.4 },
            },
          },
          {
            name: '债务余额',
            type: 'bar',
            yAxisIndex: 1,
            data: summary.trend.debt_balances,
            itemStyle: {
              color: (params: any) => {
                const v = summary.trend.debt_balances[params.dataIndex];
                return v > 0 ? '#f5222d' : '#d9d9d9';
              },
              opacity: 0.6,
            },
          },
        ],
      }
    : {};

  // 债务表格列
  const debtColumns = [
    {
      title: '类型',
      dataIndex: 'debt_type',
      key: 'debt_type',
      width: 100,
      render: (t: string) => (
        <Tag color={DEBT_COLORS[t] || '#1890ff'}>{DEBT_TYPE_LABELS[t] || t}</Tag>
      ),
    },
    { title: '来源章节', dataIndex: 'source_chapter', key: 'source_chapter', width: 100 },
    {
      title: '初始金额', dataIndex: 'original_amount', key: 'original_amount', width: 100,
      render: (v: number) => <Text>{v.toFixed(1)}</Text>,
    },
    {
      title: '当前金额', dataIndex: 'current_amount', key: 'current_amount', width: 100,
      render: (v: number) => (
        <Text strong style={{ color: v > 0 ? '#f5222d' : '#52c41a' }}>{v.toFixed(1)}</Text>
      ),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => {
        const colorMap: Record<string, string> = {
          active: 'red', partial: 'orange', paid: 'green', overdue: '#722ed1', cancelled: 'default',
        };
        return <Tag color={colorMap[s] || 'default'}>{DEBT_STATUS_LABELS[s] || s}</Tag>;
      },
    },
    { title: '截止章节', dataIndex: 'due_chapter', key: 'due_chapter', width: 90 },
    {
      title: '描述', dataIndex: 'description', key: 'description',
      ellipsis: true,
    },
  ];

  // 创建 Override Contract
  const handleCreateContract = async (values: any) => {
    if (!id) return;
    try {
      await debtApi.createContract(id, values);
      message.success('Override Contract 创建成功');
      setContractModalOpen(false);
      contractForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e.message || '创建失败');
    }
  };

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <DollarOutlined style={{ color: '#fa8c16', marginRight: 8 }} />
            追读力债务系统
          </Title>
          <Text type="secondary">追读力评估 · 债务追踪 · 利息计算 · Override Contract</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
            <Button type="primary" icon={<FileAddOutlined />}
                    onClick={() => setContractModalOpen(true)}>
              创建 Override Contract
            </Button>
          </Space>
        </Col>
      </Row>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '80px auto' }} /> : (
        <>
          {/* 统计卡片 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="活跃债务"
                  value={summary?.active_count || 0}
                  suffix={`笔 (${summary?.active_total.toFixed(1) || 0})`}
                  valueStyle={{ color: '#f5222d' }}
                  prefix={<WarningOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="逾期债务"
                  value={summary?.overdue_count || 0}
                  suffix={`笔 (${summary?.overdue_total.toFixed(1) || 0})`}
                  valueStyle={{ color: '#722ed1' }}
                  prefix={<ExclamationCircleOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="已还清"
                  value={summary?.paid_count || 0}
                  suffix={`笔 (${summary?.paid_total.toFixed(1) || 0})`}
                  valueStyle={{ color: '#52c41a' }}
                  prefix={<CheckCircleOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="累计利息"
                  value={summary?.total_interest_accrued || 0}
                  suffix={` / 初始 ${summary?.total_original.toFixed(1) || 0}`}
                  precision={1}
                  valueStyle={{ color: '#fa8c16' }}
                  prefix={<BarChartOutlined />}
                />
              </Card>
            </Col>
          </Row>

          {/* 追读力趋势图 */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 13 }}>追读力评分 & 债务余额趋势</Text>
            {summary?.trend?.chapters?.length ? (
              <ReactEChartsCore option={trendOption} style={{ height: 300 }} notMerge />
            ) : (
              <Empty description="暂无数据，请先评估章节追读力" />
            )}
            <Alert
              style={{ marginTop: 8 }}
              type="info"
              showIcon
              message="虚线：合格线(6分) / 偿还线(8分)。评分低于6分时自动产生债务，高于8分时自动偿还。"
            />
          </Card>

          {/* 债务列表 */}
          <Card title="所有债务记录" size="small">
            {summary?.debts?.length ? (
              <Table
                dataSource={summary.debts}
                columns={debtColumns}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 10 }}
              />
            ) : (
              <Empty description="暂无债务" />
            )}
          </Card>
        </>
      )}

      {/* 创建 Override Contract 弹窗 */}
      <Modal
        title="创建 Override Contract"
        open={contractModalOpen}
        onCancel={() => { setContractModalOpen(false); contractForm.resetFields(); }}
        onOk={() => contractForm.submit()}
        width={640}
      >
        <Form form={contractForm} layout="vertical" onFinish={handleCreateContract}>
          <Form.Item name="chapter_number" label="产生章节" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder="当前章节号" />
          </Form.Item>
          <Form.Item name="constraint_type" label="违背的约束类型" rules={[{ required: true }]}>
            <Select placeholder="选择约束类型">
              {Object.entries(CONSTRAINT_TYPE_LABELS).map(([k, v]) => (
                <Option key={k} value={k}>{v}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="rationale_type" label="理由类型" rules={[{ required: true }]}>
            <Select placeholder="选择理由类型">
              {Object.entries(RATIONALE_TYPE_LABELS).map(([k, v]) => (
                <Option key={k} value={k}>{v}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="rationale_text" label="理由说明" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="为什么必须违背这个软建议？" />
          </Form.Item>
          <Form.Item name="payback_plan" label="偿还计划">
            <Input.TextArea rows={2} placeholder="计划在后续哪几章通过什么方式偿还？" />
          </Form.Item>
          <Form.Item name="due_chapter" label="截止章节" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder="必须在哪章前偿还？" />
          </Form.Item>
          <Form.Item name="auto_extend" label="自动延期" valuePropName="checked">
            <Select>
              <Option value={false as any}>不自动延期（到期未履行标记逾期）</Option>
              <Option value={true as any}>自动延期 5 章</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </AppLayout>
  );
}