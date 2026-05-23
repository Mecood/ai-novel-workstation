import { useParams } from 'react-router-dom';
import { useEffect, useState, useCallback, useRef } from 'react';
import { Card, Typography, Button, List, Input, Empty, Spin, message, Space, Tag } from 'antd';
import { OrderedListOutlined, HolderOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi } from '../../services/api';
import type { Chapter } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface OutlineItem extends Chapter {
  draftSummary: string;
}

export default function OutlinePage() {
  const { id } = useParams<{ id: string }>();
  const [items, setItems] = useState<OutlineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const fetchData = useCallback(() => {
    if (!id) return;
    setLoading(true);
    chapterApi
      .list(id)
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : [];
        const sorted = [...list].sort((a, b) => a.chapter_number - b.chapter_number);
        setItems(sorted.map((ch) => ({ ...ch, draftSummary: ch.summary || '' })));
      })
      .catch(() => {
        message.error('加载章节失败');
      })
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDragStart = (index: number) => (e: React.DragEvent) => {
    dragIndexRef.current = index;
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (index: number) => (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragOverIndex !== index) setDragOverIndex(index);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (index: number) => (e: React.DragEvent) => {
    e.preventDefault();
    const from = dragIndexRef.current;
    dragIndexRef.current = null;
    setDragOverIndex(null);
    if (from === null || from === index) return;
    setItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(index, 0, moved);
      return next;
    });
  };

  const handleDragEnd = () => {
    dragIndexRef.current = null;
    setDragOverIndex(null);
  };

  const updateSummary = (chapterId: string, value: string) => {
    setItems((prev) =>
      prev.map((item) => (item.id === chapterId ? { ...item, draftSummary: value } : item)),
    );
  };

  const handleSaveAll = async () => {
    if (!id) return;
    message.loading({ content: '保存中...', key: 'outline_save' });
    try {
      await Promise.all(
        items.map((item) =>
          chapterApi.update(id, item.id, {
            title: item.title,
            summary: item.draftSummary,
            status: item.status,
          }),
        ),
      );
      message.success({ content: '大纲已保存', key: 'outline_save' });
    } catch {
      message.error({ content: '保存失败', key: 'outline_save' });
    }
  };

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
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <OrderedListOutlined style={{ marginRight: 8 }} />
            大纲规划
          </Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
            拖动章节调整顺序，并为每章撰写简要大纲
          </Paragraph>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} disabled={loading}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveAll}
            disabled={loading || items.length === 0}
          >
            保存大纲
          </Button>
        </Space>
      </div>

      <Card>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <Empty
            image={<OrderedListOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
            description="暂无章节，先到「写作工作区」创建或生成章节"
          />
        ) : (
          <List
            itemLayout="vertical"
            dataSource={items}
            renderItem={(item, index) => (
              <List.Item
                key={item.id}
                onDragOver={handleDragOver(index)}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop(index)}
                style={{
                  background: dragOverIndex === index ? '#e6f4ff' : undefined,
                  borderRadius: 8,
                  transition: 'background 0.15s',
                  padding: '12px 16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div
                    draggable
                    onDragStart={handleDragStart(index)}
                    onDragEnd={handleDragEnd}
                    style={{
                      cursor: 'grab',
                      padding: '4px 6px',
                      color: '#8c8c8c',
                      userSelect: 'none',
                      fontSize: 18,
                      lineHeight: 1,
                    }}
                    title="拖动以调整顺序"
                  >
                    <HolderOutlined />
                  </div>
                  <div style={{ flex: 1 }}>
                    <Space size={8} style={{ marginBottom: 8 }} wrap>
                      <Text strong>第 {index + 1} 章</Text>
                      <Text>{item.title || '未命名章节'}</Text>
                      <Tag color="blue">{item.status}</Tag>
                      <Text type="secondary">{item.word_count} 字</Text>
                    </Space>
                    <TextArea
                      value={item.draftSummary}
                      onChange={(e) => updateSummary(item.id, e.target.value)}
                      placeholder="为本章撰写简要大纲，例如：主角的关键抉择、本章核心冲突、悬念铺设……"
                      autoSize={{ minRows: 2, maxRows: 6 }}
                    />
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>
    </AppLayout>
  );
}
