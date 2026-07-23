import { useParams } from 'react-router-dom';
import { useEffect, useState, useMemo } from 'react';
import { Card, Spin, Typography, Empty, List, Tag, message } from 'antd';
import { ReadOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi } from '../../services/api';
import type { Chapter } from '../../services/api';
import dayjs from 'dayjs';

const { Title, Paragraph } = Typography;

/** 从 content 中提取纯文本（兼容 {text:...} JSON 和纯字符串） */
function extractText(content: unknown): string {
  if (!content) return '';
  if (typeof content === 'string') {
    // 尝试解析 JSON
    try {
      const parsed = JSON.parse(content);
      if (parsed && typeof parsed === 'object' && typeof parsed.text === 'string') {
        return parsed.text;
      }
    } catch {
      // 不是 JSON，直接当纯文本
    }
    return content;
  }
  if (typeof content === 'object' && content !== null) {
    const obj = content as Record<string, unknown>;
    if (typeof obj.text === 'string') return obj.text;
    if (typeof obj.content === 'string') return obj.content;
    return JSON.stringify(content);
  }
  return String(content);
}

/** 格式化章节标题：剔除重复的"第N章"前缀 */
function formatTitle(ch: Chapter): string {
  const num = ch.chapter_number ?? '';
  let title = ch.title || '';
  // 如果 title 已经是 "第N章 xxx"，去掉前缀只留 xxx
  const prefix = `第${num}章`;
  if (title.startsWith(prefix)) {
    title = title.slice(prefix.length).trim();
  }
  return title ? `${prefix} ${title}` : prefix;
}

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

  // 提取纯文本用于渲染
  const selectedText = useMemo(() => extractText(selected?.content), [selected]);

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
        <Card title="目录" style={{ width: 260, flexShrink: 0 }} bodyStyle={{ padding: 0 }}>
          {chapters.length === 0 ? (
            <div style={{ padding: 24 }}>
              <Empty description="暂无章节" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </div>
          ) : (
            <List
              size="small"
              dataSource={chapters}
              renderItem={(ch) => {
                const metaParts: string[] = [];
                if (ch.word_count) metaParts.push(`${ch.word_count}字`);
                if (ch.created_at) {
                  metaParts.push(dayjs(ch.created_at).format('YYYY-MM-DD HH:mm'));
                }
                return (
                  <List.Item
                    onClick={() => setSelected(ch)}
                    style={{
                      cursor: 'pointer',
                      padding: '12px 16px',
                      background: selected?.id === ch.id ? '#e6f4ff' : undefined,
                    }}
                  >
                    <List.Item.Meta
                      title={formatTitle(ch)}
                      description={
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Tag color={ch.status === 'generated' ? 'blue' : 'default'}>
                            {ch.status === 'generated' ? '已生成' : ch.status}
                          </Tag>
                          {metaParts.length > 0 && (
                            <span style={{ fontSize: 12, color: '#888' }}>
                              {metaParts.join(' · ')}
                            </span>
                          )}
                        </div>
                      }
                    />
                  </List.Item>
                );
              }}
            />
          )}
        </Card>

        <Card style={{ flex: 1 }}>
          {selected ? (
            <div style={{ maxWidth: 720, margin: '0 auto', lineHeight: 2, fontSize: 16 }}>
              <Title level={4} style={{ textAlign: 'center', marginBottom: 24 }}>
                {formatTitle(selected)}
              </Title>
              {/* 元信息 */}
              <div style={{
                textAlign: 'center', marginBottom: 32, fontSize: 13, color: '#999',
                display: 'flex', justifyContent: 'center', gap: 16,
              }}>
                {selected.word_count != null && <span>{selected.word_count} 字</span>}
                {selected.created_at && <span>生成于 {dayjs(selected.created_at).format('YYYY-MM-DD HH:mm')}</span>}
              </div>
              <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 2 }}>
                {selectedText || '（暂无内容）'}
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