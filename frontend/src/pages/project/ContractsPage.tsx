// @ts-nocheck
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Table, Statistic, Tag, Button, Modal, Typography,
  Row, Col, Spin, Empty, Space, Popconfirm,
} from 'antd';
import {
  CheckCircleOutlined, FileProtectOutlined, SendOutlined,
  EyeOutlined, LogoutOutlined, QuestionCircleOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import {
  contractApi,
  type ContractAllResponse,
  type ContractOverviewItem,
  type ChapterContract,
} from '../../services/api';

const { Title, Text } = Typography;

// ── 状态标签与颜色 ───────────────────────────────────────────────────────
const CONTRACT_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:   { label: '未签署', color: 'default' },
  signed:    { label: '已签署', color: '#5B9BD5' },
  fulfilled: { label: '已履行', color: '#52c41a' },
  rejected:  { label: '已拒绝', color: 'error' },
};

const SUBMIT_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:   { label: '待提交', color: 'default' },
  accepted:  { label: '已通过', color: '#52c41a' },
  rejected:  { label: '已拒绝', color: 'error' },
};

const contractStatusTag = (status: string) => {
  const c = CONTRACT_STATUS_CONFIG[status] || CONTRACT_STATUS_CONFIG.pending;
  return <Tag color={c.color}>{c.label}</Tag>;
};

const submitStatusTag = (status: string) => {
  const c = SUBMIT_STATUS_CONFIG[status] || SUBMIT_STATUS_CONFIG.pending;
  return <Tag color={c.color}>{c.label}</Tag>;
};

// ── 表格列 ───────────────────────────────────────────────────────────────
interface ContractsPageProps {}

export default function ContractsPage(_props: ContractsPageProps) {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ContractOverviewItem[]>([]);
  const [stats, setStats] = useState({
    signed: 0,
    submitted: 0,
    accepted: 0,
    rejected: 0,
  });
  const [loading, setLoading] = useState(true);
  // 详情弹窗
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailChapter, setDetailChapter] = useState<number | null>(null);
  const [contractDetail, setContractDetail] = useState<ChapterContract | null>(null);
  const [signLoadingMap, setSignLoadingMap] = useState<Record<number, boolean>>({});
  const [commitLoadingMap, setCommitLoadingMap] = useState<Record<number, boolean>>({});

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await contractApi.getAllContracts(id);
      const payload = res.data;
      setData(payload.contracts);
      setStats({
        signed: payload.signed,
        submitted: payload.submitted,
        accepted: payload.accepted,
        rejected: payload.rejected,
      });
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // ── 签署契约 ──────────────────────────────────────────────────────────
  const handleSign = async (chapterNumber: number) => {
    if (!id) return;
    setSignLoadingMap((m) => ({ ...m, [chapterNumber]: true }));
    try {
      await contractApi.signContract(id, chapterNumber);
      await load();
    } finally {
      setSignLoadingMap((m) => ({ ...m, [chapterNumber]: false }));
    }
  };

  // ── 提交章节 ──────────────────────────────────────────────────────────
  const handleCommit = async (chapterNumber: number) => {
    if (!id) return;
    setCommitLoadingMap((m) => ({ ...m, [chapterNumber]: true }));
    try {
      await contractApi.commitChapter(id, chapterNumber);
      await load();
    } finally {
      setCommitLoadingMap((m) => ({ ...m, [chapterNumber]: false }));
    }
  };

  // ── 查看契约详情 ──────────────────────────────────────────────────────
  const handleViewDetail = async (chapterNumber: number) => {
    if (!id) return;
    setDetailOpen(true);
    setDetailChapter(chapterNumber);
    setDetailLoading(true);
    setContractDetail(null);
    try {
      const res = await contractApi.getContract(id, chapterNumber);
      setContractDetail(res.data);
    } catch {
      setContractDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // ── 渲染节点列表（required / optional） ───────────────────────────────
  const renderNodes = (nodes: Array<{ id?: string; title?: string; description?: string; character?: string }> | undefined) => {
    if (!nodes || nodes.length === 0) return <Text type="secondary">无</Text>;
    return nodes.map((n) => (
      <div key={n.id ?? n.title} style={{ marginBottom: 8 }}>
        <Text strong>{n.title || n.id}</Text>
        {n.character && <Tag color="blue" style={{ marginLeft: 6 }}>角色: {n.character}</Tag>}
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {n.description || '—'}
          </Text>
        </div>
      </div>
    ));
  };

  // ── 渲染约束列表 ──────────────────────────────────────────────────────
  const renderConstraints = (
    constraints: Array<{ key?: string; label?: string; value?: string }> | undefined
  ) => {
    if (!constraints || constraints.length === 0) return <Text type="secondary">无</Text>;
    return constraints.map((c) => (
      <div key={c.key} style={{ marginBottom: 6 }}>
        <Text strong>{c.label || c.key}</Text>
        <Text type="secondary" style={{ marginLeft: 8 }}>
          {c.value || '—'}
        </Text>
      </div>
    ));
  };

  // ── 渲染禁区列表 ──────────────────────────────────────────────────────
  const renderForbiddenZones = (
    zones: Array<{ id?: string; description?: string; reason?: string }> | undefined
  ) => {
    if (!zones || zones.length === 0) return <Text type="secondary">无</Text>;
    return zones.map((z) => (
      <div key={z.id} style={{ marginBottom: 8 }}>
        <Text strong style={{ color: '#cf1322' }}>⚠ {z.description || z.id}</Text>
        {z.reason && (
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              原因：{z.reason}
            </Text>
          </div>
        )}
      </div>
    ));
  };

  // ── 表格列定义 ────────────────────────────────────────────────────────
  const columns = [
    {
      title: '章节号',
      dataIndex: 'chapter_number',
      key: 'chapter_number',
      width: 130,
      render: (v: number, row: ContractOverviewItem) => (
        <div>
          <Text strong>第 {v} 章</Text>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {row.chapter_title}
            </Text>
          </div>
        </div>
      ),
      sorter: (a: ContractOverviewItem, b: ContractOverviewItem) =>
        a.chapter_number - b.chapter_number,
    },
    {
      title: '契约状态',
      dataIndex: 'contract_status',
      key: 'contract_status',
      width: 140,
      render: (v: string) => contractStatusTag(v),
    },
    {
      title: '提交状态',
      dataIndex: 'submit_status',
      key: 'submit_status',
      width: 140,
      render: (v: string) => submitStatusTag(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 320,
      render: (_: unknown, row: ContractOverviewItem) => (
        <Space wrap size="small">
          {/* 签署契约：未签署时显示 */}
          {!row.has_contract && (
            <Popconfirm
              title="确认签署第 {row.chapter_number} 章契约？"
              description="将根据大纲细纲、世界观和角色设定生成并签署本章契约。"
              onConfirm={() => handleSign(row.chapter_number)}
              okText="签署"
              cancelText="取消"
            >
              <Button
                type="primary"
                icon={<SignOutlined />}
                size="small"
                loading={signLoadingMap[row.chapter_number]}
                disabled={row.submit_status !== 'pending'}
              >
                签署契约
              </Button>
            </Popconfirm>
          )}

          {/* 提交章节：已签署但未提交时显示 */}
          {row.has_contract && row.submit_status === 'pending' && (
            <Popconfirm
              title="确认提交第 {row.chapter_number} 章？"
              description="将汇总审查、履行、提取结果并判定通过/拒绝。"
              onConfirm={() => handleCommit(row.chapter_number)}
              okText="提交"
              cancelText="取消"
            >
              <Button
                icon={<SendOutlined />}
                size="small"
                loading={commitLoadingMap[row.chapter_number]}
                style={{ borderColor: '#5B9BD5', color: '#5B9BD5' }}
              >
                提交章节
              </Button>
            </Popconfirm>
          )}

          {/* 查看详情：已有契约时显示 */}
          {row.has_contract && (
            <Button
              icon={<EyeOutlined />}
              size="small"
              onClick={() => handleViewDetail(row.chapter_number)}
              style={{ borderColor: '#5B9BD5', color: '#5B9BD5' }}
            >
              查看详情
            </Button>
          )}

          {/* 未签署且未提交：仅提示 */}
          {!row.has_contract && row.submit_status === 'pending' && (
            <Button
              type="text"
              size="small"
              disabled
              icon={<QuestionCircleOutlined />}
            >
              未签署
            </Button>
          )}
        </Space>
      ),
    },
  ];

  // ── 渲染页面 ──────────────────────────────────────────────────────────
  return (
    <AppLayout projectId={id || ''}>
      {/* 标题 */}
      <Title level={3} style={{ margin: '0 0 16px' }}>
        <FileProtectOutlined style={{ color: '#5B9BD5', marginRight: 8 }} />
        合同管理
      </Title>

      {/* 顶部分类统计 */}
      <Card
        style={{ marginBottom: 16 }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <Row gutter={40} justify="space-around">
          <Col>
            <Statistic
              title={<span style={{ color: '#888' }}>已签署</span>}
              value={stats.signed}
              valueStyle={{ color: '#5B9BD5' }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
          <Col>
            <Statistic
              title={<span style={{ color: '#888' }}>已提交</span>}
              value={stats.submitted}
              valueStyle={{ color: '#1890ff' }}
              prefix={<SendOutlined />}
            />
          </Col>
          <Col>
            <Statistic
              title={<span style={{ color: '#888' }}>已通过</span>}
              value={stats.accepted}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
          <Col>
            <Statistic
              title={<span style={{ color: '#888' }}>已拒绝</span>}
              value={stats.rejected}
              valueStyle={{ color: '#f5222d' }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
        </Row>
      </Card>

      {/* 契约列表表格 */}
      <Card
        title="章节契约列表"
        extra={
          <Button type="link" onClick={load} icon={<QuestionCircleOutlined />}>
            刷新
          </Button>
        }
      >
        <Table
          rowKey="chapter_number"
          columns={columns}
          dataSource={data}
          loading={loading}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无章节数据" /> }}
        />
      </Card>

      {/* 契约详情弹窗 */}
      <Modal
        title={detailChapter !== null ? `第 ${detailChapter} 章 契约详情` : '契约详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={720}
        maskClosable={false}
      >
        <Spin spinning={detailLoading} size="large">
          {contractDetail ? (
            <div style={{ maxHeight: 600, overflow: 'auto', paddingRight: 8 }}>
              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">
                  状态：{contractStatusTag(contractDetail.status)} &nbsp;
                  签署时间：{contractDetail.signed_at
                    ? new Date(contractDetail.signed_at).toLocaleString('zh-CN')
                    : '—'}
                </Text>
              </div>

              <Title level={5}>必填节点（required_nodes）</Title>
              {renderNodes(contractDetail.required_nodes)}

              <Title level={5}>可选节点（optional_nodes）</Title>
              {renderNodes(contractDetail.optional_nodes)}

              <Title level={5}>写作约束（constraints）</Title>
              {renderConstraints(contractDetail.constraints)}

              <Title level={5}>内容禁区（forbidden_zones）</Title>
              {renderForbiddenZones(contractDetail.forbidden_zones)}

              {contractDetail.context_summary && (
                <>
                  <Title level={5}>生成上下文</Title>
                  <div
                    style={{
                      background: '#FAFAFA',
                      padding: 12,
                      borderRadius: 6,
                      fontSize: 12,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    <Text type="secondary">{contractDetail.context_summary}</Text>
                  </div>
                </>
              )}
            </div>
          ) : (
            !detailLoading && (
              <Empty description="该章节尚未签署契约，无法查看详情" />
            )
          )}
        </Spin>
      </Modal>
    </AppLayout>
  );
}
