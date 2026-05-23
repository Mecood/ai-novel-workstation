import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, Typography, Empty, List, Tag, message } from 'antd';
import { ReadOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi } from '../../services/api';
import type { Chapter } from '../../services/api';

const { Title, Paragraph } = Typography;

export default function ReaderPage() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Chapter | null>(null);

  useEffect(() => {
    if (!id) return;
    chapterApi
      .list(id)
      .then(({ data }) => {
        const list = (Array.isArray(data) ? data : []).slice().sort(
          (a, b) => a.chapter_number - b.chapter_number
        );
        setChapters(list);
        if (list.length > 0) setSelected(list[0]);
      })
      .catch(() => {
        message.error('加载章节失败');
      })
      .finally(() => setLoading(false));
  }, [id]);

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
        <ReadOutlined style={{ marginRight: 8 }} />
        阅读器
      </Title>
      <div style={{ display: 'flex', gap: 16 }}>
        <Card title="目录" style={{ width: 240, flexShrink: 0 }} bodyStyle={{ padding: 0 }}>
          {chapters.length === 0 ? (
            <div style={{ padding: 24 }}>
              <Empty description="暂无章节" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </div>
          ) : (
            <List
              size="small"
              dataSource={chapters}
              renderItem={(ch) => (
                <List.Item
                  onClick={() => setSelected(ch)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selected?.id === ch.id ? '#e6f4ff' : undefined,
                  }}
                >
                  <List.Item.Meta
                    title={`第${ch.chapter_number}章 ${ch.title}`}
                    description={<Tag>{ch.status}</Tag>}
                  />
                </List.Item>
              )}
            />
          )}
        </Card>

        <Card style={{ flex: 1 }}>
          {selected ? (
            <div style={{ maxWidth: 720, margin: '0 auto', lineHeight: 2, fontSize: 16 }}>
              <Title level={4} style={{ textAlign: 'center', marginBottom: 32 }}>
                第{selected.chapter_number}章 {selected.title}
              </Title>
              <Paragraph style={{ textIndent: '2em', whiteSpace: 'pre-wrap', lineHeight: 2 }}>
                {typeof selected.content === 'string'
                  ? selected.content
                  : JSON.stringify(selected.content || '')}
              </Paragraph>
            </div>
          ) : (
            <Empty description="没有任何章节" />
          )}
        </Card>
      </div>
    </AppLayout>
  );
}
