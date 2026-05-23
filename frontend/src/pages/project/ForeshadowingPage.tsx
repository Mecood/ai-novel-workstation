import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, message, Button, Typography, Tag, Table, Select, Empty, Modal, Form, Input, Space } from 'antd';
import { PlusOutlined, LinkOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { foreshadowingApi } from '../../services/api';
import type { Foreshadowing } from '../../services/api';

const { Title } = Typography;

export default function ForeshadowingPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Foreshadowing[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchData = () => {
    if (!id) return;
    setLoading(true);
    foreshadowingApi.list(id).then(({ data }) => {
      setData(Array.isArray(data) ? data : []);
    }).catch(() => {
      message.error('加载失败');
    }).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [id]);

  const handleCreate = async () => {
    if (!id) return;
    try {
      const values = await form.validateFields();
      await foreshadowingApi.create(id, values);
      message.success('伏笔添加成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch { }
  };

  const handleStatusChange = async (fid: string, status: string) => {
    if (!id) return;
    try {
      await foreshadowingApi.updateStatus(id, fid, status);
      message.success('状态已更新');
      fetchData();
    } catch { message.error('更新失败'); }
  };

  const columns = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '目标章节', dataIndex: 'target_chapter', key: 'target_chapter', render: (v: number) => `第${v}章` },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (status: string, record: Foreshadowing) => (
        <Select value={status} onChange={(v) => handleStatusChange(record.id, v)} size="small" style={{ width: 100 }}>
          <Select.Option value="planted">已埋下</Select.Option>
          <Select.Option value="active">激活中</Select.Option>
          <Select.Option value="collected">已回收</Select.Option>
          <Select.Option value="discarded">已废弃</Select.Option>
        </Select>
      ),
    },
  ];

  return (
    <AppLayout projectId={id!}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>伏笔追踪</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          添加伏笔
        </Button>
      </div>

      {loading ? <Spin style={{ display: 'block', margin: '120px auto' }} /> : (
        data.length === 0 ? <Empty description="暂无伏笔" /> : (
          <Table dataSource={data} columns={columns} rowKey="id" pagination={false} />
        )
      )}

      <Modal title="添加伏笔" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="伏笔标题" rules={[{ required: true }]}>
            <Input placeholder="如：神秘的古剑" />
          </Form.Item>
          <Form.Item name="description" label="伏笔描述">
            <Input.TextArea rows={3} placeholder="描述这个伏笔的内容和预期效果" />
          </Form.Item>
          <Form.Item name="target_chapter" label="目标章节" rules={[{ required: true }]}>
            <Input type="number" placeholder="预计回收的章节号" />
          </Form.Item>
        </Form>
      </Modal>
    </AppLayout>
  );
}