import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, message, Button, Typography, Tag, Timeline, Empty } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { worldviewApi, aiApi } from '../../services/api';
import type { Worldview } from '../../services/api';

const { Title, Paragraph } = Typography;

export default function WorldviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [worldviews, setWorldviews] = useState<Worldview[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchData = () => {
    if (!id) return;
    setLoading(true);
    worldviewApi.list(id).then(({ data }) => {
      setWorldviews(Array.isArray(data) ? data : []);
    }).catch(() => {
      message.error('加载世界观失败');
    }).finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [id]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      await aiApi.generateWorldview(id);
      message.success('世界观生成完成');
      fetchData();
    } catch {
      message.error('生成失败');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}><Spin size="large" /></div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={id!}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>世界观</Title>
        <Button type="primary" icon={<ThunderboltOutlined />} loading={generating} onClick={handleGenerate}>
          AI 生成世界观
        </Button>
      </div>

      {worldviews.length === 0 ? (
        <Empty description="暂无世界观设定，点击上方按钮生成" />
      ) : (
        worldviews.map((wv) => (
          <Card key={wv.id} title={wv.name} style={{ marginBottom: 16 }}>
            <Paragraph>{wv.description}</Paragraph>
            {wv.rules && wv.rules.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Title level={5}>规则</Title>
                {wv.rules.map((rule, i) => <Tag key={i} style={{ marginBottom: 4 }}>{rule}</Tag>)}
              </div>
            )}
            {wv.timeline && wv.timeline.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Title level={5}>时间线</Title>
                <Timeline items={wv.timeline.map((t: any) => ({ children: `${t.time || ''}: ${t.event || ''}` }))} />
              </div>
            )}
          </Card>
        ))
      )}
    </AppLayout>
  );
}