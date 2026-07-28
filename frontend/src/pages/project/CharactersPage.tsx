import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, message, Button, Typography, Tag, Descriptions, Empty, Avatar, Alert, Space } from 'antd';
import { ThunderboltOutlined, UserOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { characterApi, aiApi } from '../../services/api';
import type { Character, StaleReport } from '../../services/api';

const { Title, Text } = Typography;

export default function CharactersPage() {
  const { id } = useParams<{ id: string }>();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [staleReport, setStaleReport] = useState<StaleReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchData = () => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      characterApi.list(id).then(r => r.data),
      characterApi.staleReport(id).then(r => r.data).catch(() => null),
    ])
      .then(([chars, report]) => {
        setCharacters(Array.isArray(chars) ? chars : []);
        setStaleReport(report);
      })
      .catch(() => {
        message.error('加载角色失败');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      await aiApi.generateCharacters(id);
      message.success('角色生成完成');
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
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={id!}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          角色
        </Title>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={generating}
          onClick={handleGenerate}
        >
          AI 生成角色
        </Button>
      </div>

      {characters.length === 0 ? (
        <Empty description="暂无角色，点击上方按钮生成" />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: 16,
            alignItems: 'start',
          }}
        >
          {(characters[0] as any)?._stale === 'true' && staleReport && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16, gridColumn: '1 / -1' }}
              message={
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Text strong style={{ fontSize: 14 }}>
                    上游数据已变更 — {staleReport.message}
                  </Text>
                  {staleReport.changed_names.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      变更来源：{staleReport.changed_names.join('、')}
                    </Text>
                  )}
                  {staleReport.affected_chapters.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      受影响章节：{staleReport.affected_chapters.map(c => `第${c.chapter_number}章`).join('、')}
                    </Text>
                  )}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    推荐操作：重新生成角色以同步最新设定
                  </Text>
                </Space>
              }
            />
          )}
          {characters.map((c) => (
            <Card
              key={c.id}
              hoverable
              style={{ maxHeight: 480, overflow: 'auto' }}
            >
              <Card.Meta
                avatar={
                  <Avatar size={48} icon={<UserOutlined />} style={{ background: '#5B9BD5' }} />
                }
                title={c.name}
                description={<Tag color="blue">{c.role_type}</Tag>}
              />
              <Descriptions column={1} size="small" style={{ marginTop: 16 }} layout="vertical">
                {c.personality && c.personality.length > 0 && (
                  <Descriptions.Item label="性格">
                    {c.personality.map((p, i) => (
                      <Tag key={i} style={{ marginBottom: 4 }}>{p}</Tag>
                    ))}
                  </Descriptions.Item>
                )}
                {c.appearance && (
                  <Descriptions.Item label="外貌">
                    <div style={{ maxHeight: 80, overflow: 'auto' }}>{c.appearance}</div>
                  </Descriptions.Item>
                )}
                {c.background && (
                  <Descriptions.Item label="背景">
                    <div style={{ maxHeight: 80, overflow: 'auto' }}>{c.background}</div>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          ))}
        </div>
      )}
    </AppLayout>
  );
}