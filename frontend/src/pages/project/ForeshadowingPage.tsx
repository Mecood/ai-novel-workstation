import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, message, Button, Typography, Tag, Tabs, Modal, Form, Input, Space, Select, Divider, Tooltip, Alert, Empty } from 'antd';
import { PlusOutlined, ExclamationCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { foreshadowingApi } from '../../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

type StatusFilter = 'all' | 'active' | 'resolved';

const REMINDER_COLORS: Record<string, string> = {
  urgent: '#cf1322',
  high: '#ff4d4f',
  medium: '#fa8c16',
  low: '#8c8c8c',
};

const STATUS_LABELS: Record<string, string> = {
  planted: '已埋下',
  active: '激活中',
  collected: '已回收',
  resolved: '已回收',
  discarded: '已废弃',
  abandoned: '已放弃',
};

export default function ForeshadowingPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [form] = Form.useForm();

  const fetchData = () => {
    if (!id) return;
    setLoading(true);
    foreshadowingApi.list(id).then(({ data }) => {
      const list = Array.isArray(data) ? data : [];
      setData(list);
      // 自动计算提醒等级
      for (const item of list) {
        if (!item.reminder_level && item.status !== 'resolved' && item.status !== 'collected') {
          if (item.auto_match_confidence && Number(item.auto_match_confidence) > 0.7) {
            item.reminder_level = 'high';
          } else if (item.expected_redemption_chapter && item.expected_redemption_chapter <= (max_chapter || 50)) {
            item.reminder_level = 'medium';
          } else {
            item.reminder_level = 'low';
          }
        }
      }
    }).catch(() => message.error('加载失败')).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [id]);

  const max_chapter = data.length > 0
    ? Math.max(...data.map(d => Math.max(d.target_chapter || 0, d.expected_redemption_chapter || 0, 0)))
    : 50;

  // 过滤
  const filtered = filter === 'all' ? data
    : filter === 'active' ? data.filter(d => !['resolved', 'collected', 'discarded', 'abandoned'].includes(d.status || ''))
    : data.filter(d => ['resolved', 'collected'].includes(d.status || ''));

  // Tab 统计
  const activeCount = data.filter(d => !['resolved', 'collected', 'discarded', 'abandoned'].includes(d.status || '')).length;
  const resolvedCount = data.filter(d => ['resolved', 'collected'].includes(d.status || '')).length;

  const handleSave = async () => {
    if (!id) return;
    try {
      const values = await form.validateFields();
      if (editingItem) {
        await foreshadowingApi.update(id, editingItem.id, values);
        message.success('更新成功');
      } else {
        await foreshadowingApi.create(id, values);
        message.success('添加成功');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingItem(null);
      fetchData();
    } catch { /* noop */ }
  };

  const handleEdit = (item: any) => {
    setEditingItem(item);
    form.setFieldsValue({
      title: item.title,
      description: item.description,
      target_chapter: item.target_chapter,
      status: item.status,
      reminder_level: item.reminder_level || 'low',
      evidence_chapter: item.evidence_chapter || undefined,
      evidence_line: item.evidence_line || undefined,
      evidence_text: item.evidence_text || undefined,
    });
    setModalOpen(true);
  };

  const handleResolve = async (item: any) => {
    if (!id || !item) return;
    try {
      await foreshadowingApi.update(id, item.id, { status: 'resolved' });
      message.success('已回收');
      fetchData();
    } catch { message.error('操作失败'); }
  };

  const handleDiscard = async (item: any) => {
    if (!id || !item) return;
    try {
      await foreshadowingApi.update(id, item.id, { status: 'discarded' });
      message.success('已废弃');
      fetchData();
    } catch { message.error('操作失败'); }
  };

  const tabItems = [
    {
      key: 'all',
      label: `全部 (${data.length})`,
    },
    {
      key: 'active',
      label: (
        <span>
          待提醒 <ExclamationCircleOutlined style={{ color: '#fa8c16', marginLeft: 4, fontSize: 12 }} />
          ({activeCount})
        </span>
      ),
    },
    {
      key: 'resolved',
      label: (
        <span>
          已回收 <CheckCircleOutlined style={{ color: '#52c41a', marginLeft: 4, fontSize: 12 }} />
          ({resolvedCount})
        </span>
      ),
    },
  ];

  return (
    <AppLayout projectId={id!}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>伏笔追踪</Title>
          <Text type="secondary">管理伏笔埋设、提醒与回收。每条伏笔关联证据链，可追溯到正文。</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingItem(null); form.resetFields(); setModalOpen(true); }}>
          添加伏笔
        </Button>
      </div>

      <Tabs
        activeKey={filter}
        onChange={(k) => setFilter(k as StatusFilter)}
        items={tabItems}
        style={{ marginBottom: 16 }}
        tabBarExtraContent
      />

      {loading ? <Spin style={{ display: 'block', margin: '60px auto' }} /> : (
        filtered.length === 0 ? (
          <Empty description={filter === 'active' ? '当前没有未处理的伏笔，好记性。' : '暂无伏笔，点击「添加伏笔」开始埋设。'} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {filtered.map(item => (
              <Card
                key={item.id}
                size="small"
                hoverable
                onClick={() => handleEdit(item)}
                style={{
                  borderLeft: `4px solid ${REMINDER_COLORS[(item.reminder_level || 'low') as string] || '#8c8c8c'}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <Text strong style={{ fontSize: 14 }}>{item.title}</Text>
                      <Tag color={
                        item.status === 'resolved' || item.status === 'collected' ? 'green'
                        : item.status === 'discarded' ? 'default'
                        : item.reminder_level === 'urgent' ? 'red'
                        : item.reminder_level === 'high' ? 'orange'
                        : 'blue'
                      }>
                        {STATUS_LABELS[item.status] || item.status}
                      </Tag>
                      <Tag color={REMINDER_COLORS[item.reminder_level] || '#8c8c8c'}>
                        {item.reminder_level === 'urgent' ? '🚨 紧急'
                         : item.reminder_level === 'high' ? '⚠️ 高'
                         : item.reminder_level === 'medium' ? '◐ 中'
                         : '○ 低'}
                      </Tag>
                    </div>
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.description && item.description.length > 80
                          ? item.description.slice(0, 80) + '…'
                          : item.description}
                      </Text>
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 12, fontSize: 11, color: '#8c8c8c' }}>
                      {item.target_chapter && <span>🎯 目标：第{item.target_chapter}章</span>}
                      {item.expected_redemption_chapter && <span>📅 预计回收：第{item.expected_redemption_chapter}章</span>}
                      {item.evidence_text && (
                        <Tooltip title={item.evidence_text}>
                          <span style={{ color: '#1890ff', cursor: 'help' }}>
                            📌 证据：第{item.evidence_chapter}章 · L{item.evidence_line}
                          </span>
                        </Tooltip>
                      )}
                    </div>
                  </div>
                  <Space>
                    {item.status !== 'resolved' && item.status !== 'discarded' && (
                      <Button
                        size="small"
                        type="primary"
                        ghost
                        icon={<CheckCircleOutlined />}
                        onClick={(e) => { e.stopPropagation(); handleResolve(item); }}
                      >
                        回收
                      </Button>
                    )}
                    {item.status === 'planted' && (
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<CloseCircleOutlined />}
                        onClick={(e) => { e.stopPropagation(); handleDiscard(item); }}
                      >
                        废弃
                      </Button>
                    )}
                  </Space>
                </div>
              </Card>
            ))}
          </div>
        )
      )}

      <Modal
        title={editingItem ? '编辑伏笔' : '添加伏笔'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditingItem(null); form.resetFields(); }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="伏笔标题" rules={[{ required: true, message: '请填写标题' }]}>
            <Input placeholder="如：神秘的古剑" />
          </Form.Item>
          <Form.Item name="description" label="伏笔描述">
            <Input.TextArea rows={3} placeholder="描述这个伏笔的内容和预期效果" />
          </Form.Item>
          <Form.Item name="target_chapter" label="目标章节">
            <Input type="number" placeholder="预计回收的章节号" />
          </Form.Item>
          <Form.Item name="expected_redemption_chapter" label="预计回收章节">
            <Input type="number" placeholder="最晚在第几章回收" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select>
              <Option value="planted">已埋下</Option>
              <Option value="active">激活中</Option>
              <Option value="resolved">已回收</Option>
              <Option value="discarded">已废弃</Option>
            </Select>
          </Form.Item>
          <Form.Item name="reminder_level" label="提醒等级">
            <Select>
              <Option value="low">○ 低</Option>
              <Option value="medium">◐ 中</Option>
              <Option value="high">⚠️ 高</Option>
              <Option value="urgent">🚨 紧急</Option>
            </Select>
          </Form.Item>
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="📌 证据链">
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Form.Item name="evidence_chapter" label="证据所在章节">
                <Input type="number" placeholder="正文中第几章" />
              </Form.Item>
              <Form.Item name="evidence_line" label="证据行号">
                <Input placeholder="如：L12-L18" />
              </Form.Item>
              <Form.Item name="evidence_text" label="证据摘要">
                <Input.TextArea rows={2} placeholder="摘录正文中对应段落" />
              </Form.Item>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </AppLayout>
  );
}
