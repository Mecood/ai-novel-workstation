import { useParams } from 'react-router-dom';
import { useEffect, useState, useMemo, useCallback } from 'react';
import { Card, Spin, Typography, Empty, List, Tag, message, Button, Space, Modal, Input } from 'antd';
import { ReadOutlined, EditOutlined, SaveOutlined, CloseOutlined, ExperimentOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, aiApi } from '../../services/api';
import type { Chapter } from '../../services/api';
import dayjs from 'dayjs';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

/** 从 content 中提取纯文本（兼容 {text:...} JSON 和纯字符串） */
function extractText(content: unknown): string {
  if (!content) return '';
  if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content);
      if (parsed && typeof parsed === 'object' && typeof parsed.text === 'string') {
        return parsed.text;
      }
    } catch { /* 纯文本 */ }
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

  // 编辑模式
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [saving, setSaving] = useState(false);
  const [deAiLoading, setDeAiLoading] = useState(false);

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
      .catch(() => message.error('加载章节失败'))
      .finally(() => setLoading(false));
  }, [id]);

  // 提取纯文本
  const selectedText = useMemo(() => extractText(selected?.content), [selected]);

  // 进入编辑
  const startEdit = useCallback(() => {
    setEditText(selectedText);
    setEditing(true);
  }, [selectedText]);

  // 取消编辑
  const cancelEdit = useCallback(() => {
    setEditing(false);
    setEditText('');
  }, []);

  // 保存
  const saveEdit = useCallback(async () => {
    if (!id || !selected) return;
    setSaving(true);
    try {
      const content = { text: editText };
      await chapterApi.update(id, selected.id, {
        content,
        word_count: editText.length,
        title: selected.title,
      });
      // 更新本地状态
      setSelected({ ...selected, content, word_count: editText.length });
      setChapters(prev => prev.map(c =>
        c.id === selected.id ? { ...c, content, word_count: editText.length } : c
      ));
      message.success('已保存');
      setEditing(false);
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [id, selected, editText]);

  // de-AI 改写
  const handleDeAi = useCallback(async () => {
    if (!id || !selected) return;
    setDeAiLoading(true);
    let rewritten = '';
    try {
      await fetch(`/v1/projects/${id}/chapters/${selected.id}/de-ai`, { method: 'POST' })
        .then(async r => {
          const reader = r.body?.getReader();
          if (!reader) throw new Error('No reader');
          const dec = new TextDecoder();
          let buf = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              const raw = line.slice(6);
              if (raw === '[DONE]') continue;
              try {
                const parsed = JSON.parse(raw);
                if (parsed.type === 'chunk' && parsed.text) rewritten += parsed.text;
              } catch { rewritten += raw; }
            }
          }
        });
      if (rewritten) {
        const content = { text: rewritten };
        await chapterApi.update(id, selected.id, {
          content,
          word_count: rewritten.length,
          title: selected.title,
        });
        setSelected({ ...selected, content, word_count: rewritten.length });
        setChapters(prev => prev.map(c =>
          c.id === selected.id ? { ...c, content, word_count: rewritten.length } : c
        ));
        message.success('de-AI 改写完成');
      } else {
        message.warning('改写未返回内容');
      }
    } catch {
      message.error('de-AI 改写失败');
    } finally {
      setDeAiLoading(false);
    }
  }, [id, selected]);

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
        {/* 目录 */}
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
                if (ch.created_at) metaParts.push(dayjs(ch.created_at).format('YYYY-MM-DD HH:mm'));
                return (
                  <List.Item
                    onClick={() => { setSelected(ch); setEditing(false); }}
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
                            <span style={{ fontSize: 12, color: '#888' }}>{metaParts.join(' · ')}</span>
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

        {/* 内容区 */}
        <Card
          style={{ flex: 1 }}
          extra={
            selected && !editing ? (
              <Space>
                <Button icon={<EditOutlined />} size="small" onClick={startEdit}>编辑</Button>
                <Button
                  icon={<ExperimentOutlined />}
                  size="small"
                  loading={deAiLoading}
                  onClick={handleDeAi}
                >
                  de-AI
                </Button>
              </Space>
            ) : editing ? (
              <Space>
                <Button icon={<SaveOutlined />} size="small" type="primary" loading={saving} onClick={saveEdit}>保存</Button>
                <Button icon={<CloseOutlined />} size="small" onClick={cancelEdit}>取消</Button>
              </Space>
            ) : null
          }
        >
          {selected ? (
            editing ? (
              <div style={{ maxWidth: 800, margin: '0 auto' }}>
                <TextArea
                  value={editText}
                  onChange={e => setEditText(e.target.value)}
                  autoSize={{ minRows: 20, maxRows: 60 }}
                  style={{ fontFamily: 'serif', fontSize: 15, lineHeight: 2 }}
                  placeholder="编辑章节内容……"
                />
              </div>
            ) : (
              <div style={{ maxWidth: 720, margin: '0 auto', lineHeight: 2, fontSize: 16 }}>
                <Title level={4} style={{ textAlign: 'center', marginBottom: 24 }}>
                  {formatTitle(selected)}
                </Title>
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
            )
          ) : (
            <Empty description="没有任何章节" />
          )}
        </Card>
      </div>
    </AppLayout>
  );
}